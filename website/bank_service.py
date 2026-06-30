import os
import logging
import datetime
import sqlite3
import uuid
from fints.client import FinTS3PinTanClient

logger = logging.getLogger(__name__)

def generate_unique_id(prefix):
    return f"{prefix}_{uuid.uuid4()}"

def sync_bank_balance(app):
    """
    Verbindet sich mit der ING, zieht Kontostand + Umsätze 
    und schreibt die Daten direkt in die SQLite-Datenbank.
    """
    blz = os.getenv('BANK_BLZ', '50010517')
    user = os.getenv('BANK_USER')
    pin = os.getenv('BANK_PIN')
    url = os.getenv('BANK_URL', 'https://fints.ing.de/fints/')
    product_id = "6151256F3D4F9975B877BD4A2"

    if not user or not pin:
        logger.error("❌ FinTS-Sync abgebrochen: BANK_USER oder BANK_PIN fehlen in der .env!")
        return False

    logger.info("🚀 Starte automatischen FinTS-Sync und DB-Import mit UUID-Präfixen...")
    
    client = FinTS3PinTanClient(
        bank_identifier=blz,
        user_id=user,
        customer_id=user,
        pin=pin,
        server=url,
        product_id=product_id
    )

    conn = None
    try:
        db_connect = os.getenv('DB_PATH')
        if not db_connect:
            logger.error("❌ DB-Fehler: DB_PATH ist nicht in der .env definiert!")
            return False
            
        conn = sqlite3.connect(db_connect)
        cursor = conn.cursor()

        with client:
            accounts = client.get_sepa_accounts()
            
            if client.init_tan_response:
                logger.warning("🔒 [SCA erforderlich] Bitte Freigabe in der ING-App erteilen!")
            
            target_index = 1  
            if len(accounts) <= target_index:
                logger.error(f"❌ Fehler: Konto-Index {target_index} existiert nicht.")
                return False

            main_account = accounts[target_index]
            
            # --- 1. KONTOSTAND (SALDO) AUSLESEN ---
            balance_data = client.get_balance(main_account)
            amount = float(balance_data.amount.amount)
            iban = main_account.iban
            today_str = datetime.date.today().isoformat()
            local_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('SELECT AccountID FROM BankAccounts WHERE IBAN = ?', (iban,))
            row = cursor.fetchone()
            
            if row:
                account_id = row[0]
                cursor.execute('''
                    UPDATE BankAccounts 
                    SET CurrentBalance = ?, LastSync = ? 
                    WHERE AccountID = ?
                ''', (amount, local_now, account_id))
            else:
                account_id = generate_unique_id("ACCO")
                cursor.execute('''
                    INSERT INTO BankAccounts (AccountID, IBAN, AccountName, BankName, CurrentBalance, LastSync)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (account_id, iban, "Girokonto", "ING", amount, local_now))

            cursor.execute('''
                SELECT HistoryID, Balance FROM BankBalanceHistories 
                WHERE AccountID = ? AND Date = ?
            ''', (account_id, today_str))
            history_row = cursor.fetchone()
            
            if history_row:
                existing_hist_id, existing_balance = history_row
                if float(existing_balance) != amount:
                    cursor.execute('''
                        UPDATE BankBalanceHistories 
                        SET Balance = ? 
                        WHERE HistoryID = ?
                    ''', (amount, existing_hist_id))
                    logger.info(f"🔄 Kontostand-Historie für heute aktualisiert (neuer Saldo: {amount})")
            else:
                history_id = generate_unique_id("HIST")
                cursor.execute('''
                    INSERT INTO BankBalanceHistories (HistoryID, AccountID, Date, Balance)
                    VALUES (?, ?, ?, ?)
                ''', (history_id, account_id, today_str, amount))
                logger.info(f"📁 Neuer Historie-Eintrag für heute angelegt ({history_id})")
            
            # --- 2. UMSÄTZE AUSLESEN ---
            start_date = datetime.date.today() - datetime.timedelta(days=30)
            
            try:
                statements = client.get_transactions(main_account, start_date)
                inserted_tx_count = 0
                
                if not statements:
                    logger.info("📊 Keine Umsätze im angegebenen Zeitraum gefunden.")
                    conn.commit()
                    return True

                # CRITICAL GOBD-FIX: Sortiere den API-Stream chronologisch nach Datum vor!
                # Das stellt sicher, dass die Sequenz-Nummern (NMSC-xxxxxx) immer in der korrekten 
                # zeitlichen Reihenfolge vergeben werden.
                statements.sort(key=lambda x: x.data.get('date') if x.data.get('date') else datetime.date.min)

                # Cache zur Ermittlung der höchsten Primanota im aktuellen Lauf (Vermeidet DB-Abfrage-Kollision)
                cursor.execute('''
                    SELECT Primanota FROM BankTransactions 
                    WHERE AccountID = ? AND Primanota LIKE 'NMSC-%'
                    ORDER BY CAST(SUBSTR(Primanota, 6) AS INTEGER) DESC LIMIT 1
                ''', (account_id,))
                last_primanota_row = cursor.fetchone()
                current_max_num = int(last_primanota_row[0].split('-')[1]) if last_primanota_row else 0

                for tx in statements:
                    tx_date = tx.data.get('date')
                    tx_date = tx_date.isoformat() if isinstance(tx_date, datetime.date) else (str(tx_date) if tx_date else today_str)
                    
                    amt_obj = tx.data.get('amount')
                    tx_amount_val = float(amt_obj.amount) if amt_obj and hasattr(amt_obj, 'amount') else 0.0
                    
                    tx_applicant = tx.data.get('applicant_name', 'Unbekannter Partner')
                    tx_purpose = tx.data.get('purpose')
                    tx_purpose = str(tx_purpose) if tx_purpose else 'Kein Verwendungszweck'
                    tx_curr = getattr(amt_obj, 'currency', 'EUR')
                    
                    raw_primanota = tx.data.get('primanota') or tx.data.get('id')
                    if not raw_primanota:
                        continue 

                    # 1. ZÄHLEN: Wie viele identische Buchungen existieren bereits in der DB?
                    cursor.execute('''
                        SELECT COUNT(*) FROM BankTransactions 
                        WHERE AccountID = ? AND BookingDate = ? AND Amount = ? AND Purpose = ?
                    ''', (account_id, tx_date, tx_amount_val, tx_purpose))
                    existing_count = cursor.fetchone()[0]

                    # 2. ZÄHLEN: Wie oft kommt dieser Umsatz in der aktuellen API-Lieferung vor?
                    current_delivery_count = sum(
                        1 for match in statements
                        if (match.data.get('date').isoformat() if isinstance(match.data.get('date'), datetime.date) else str(match.data.get('date'))) == tx_date
                        and float(match.data.get('amount').amount) == tx_amount_val
                        and (str(match.data.get('purpose')) if match.data.get('purpose') else 'Kein Verwendungszweck') == tx_purpose
                    )

                    # 3. VERGLEICHEN: Nur einfügen, wenn physisch neu
                    if existing_count < current_delivery_count:
                        
                        # --- GOBD PRIMANOTA ENGINE (FIXED) ---
                        if raw_primanota in ['NMSC', '0000', '0']:
                            current_max_num += 1
                            primanota = f"NMSC-{current_max_num:06d}"
                        else:
                            primanota = raw_primanota

                        tx_id = generate_unique_id("TRAN")
                        
                        cursor.execute('''
                            INSERT OR IGNORE INTO BankTransactions (
                                TransactionID, AccountID, Primanota, BookingDate, PartnerName, Amount, Currency, Purpose
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (tx_id, account_id, primanota, tx_date, tx_applicant, tx_amount_val, tx_curr, tx_purpose))
                        
                        if cursor.rowcount > 0:
                            inserted_tx_count += 1
                    else:
                        # Reines Scheduler-Duplikat
                        if tx_applicant != 'Unbekannter Partner':
                            cursor.execute('''
                                UPDATE BankTransactions
                                SET PartnerName = ?
                                WHERE AccountID = ? AND BookingDate = ? AND Amount = ? AND Purpose = ? AND PartnerName = 'Unbekannter Partner'
                            ''', (tx_applicant, account_id, tx_date, tx_amount_val, tx_purpose))

                # PERFORMANCE-FIX: Nur ein einziges Commit für alle Änderungen am Ende des gesamten Syncs!
                conn.commit()
                logger.info(f"📊 Umsatz-Sync beendet. {inserted_tx_count} neue Transaktionen in DB gespeichert.")
                return True
                
            except Exception as tx_err:
                if conn: conn.rollback()
                logger.error(f"⚠️ Umsätze konnten nicht ausgelesen/gespeichert werden: {str(tx_err)}")
                return False

    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"🔴 FinTS-Sync fehlgeschlagen: {str(e)}")
        return False
        
    finally:
        if conn:
            conn.close()