import os
import sqlite3
import io
import base64
from datetime import datetime

# WICHTIG: Matplotlib auf Non-GUI (Agg) umstellen, bevor es importiert wird!
# Verhindert Abstürze im Flask-Thread-Kontext.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TEMP_UPLOAD_FOLDER = os.getenv('UPLOAD_DIR_PATH')


class TransactionManager:
    def __init__(self):
        self.db_path = os.getenv('DB_PATH')
        # Erstellt den Standardordner, falls er nicht existiert (wichtig für Entwickler-Setup)
        os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

    def _execute_query(
        self,
        query,
        params=(),
        fetch=False,
        get_lastrowid=False,
        fetch_one=False,
        multi_queries=False
    ):
        """
        Erweiterte DB-Execution mit Unterstützung für mehrere Queries in einer Transaktion.

        Args:
            query: 
                - str → einzelner SQL-String
                - list of (query_str, params_tuple) → mehrere Queries (nur bei multi_queries=True)
            params: Parameter für einzelne Query (tuple)
            fetch: Soll ein Resultset zurückgegeben werden? (SELECT)
            get_lastrowid: Soll cursor.lastrowid zurückgegeben werden? (INSERT)
            fetch_one: fetchone() statt fetchall()
            multi_queries: True → query ist Liste von (query, params)-Tuplen

        Returns:
            - Bei fetch: sqlite3.Row oder Liste von sqlite3.Row
            - Bei get_lastrowid: int (lastrowid)
            - Sonst: None
            - Bei Fehler: wirft sqlite3.Error
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            # ── Wichtig: row_factory für dict-ähnlichen Zugriff ──
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if multi_queries and isinstance(query, list):
                # Mehrere Queries → Transaktion
                cursor.execute("BEGIN TRANSACTION")
                for q, p in query:
                    cursor.execute(q, p)
                conn.commit()
            else:
                # Einzelne Query
                cursor.execute(query, params)
                conn.commit()

            # Ergebnis abholen (nur bei SELECT relevant)
            if fetch:
                if fetch_one:
                    return cursor.fetchone()           # → sqlite3.Row oder None
                return cursor.fetchall()               # → Liste von sqlite3.Row

            # Letzte eingefügte ID (für INSERT)
            if get_lastrowid:
                return cursor.lastrowid

            # Standard-Rückgabe (UPDATE, DELETE, INSERT ohne ID-Interesse)
            return None

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise  # Fehler weiterwerfen – aufrufende Methode kann loggen/flashen

        finally:
            if conn:
                conn.close()

    def get_primary_bank_account(self):
        """Lädt das primäre Bankkonto aus BankAccounts für den CurrentBalance-Eintrag"""
        query = "SELECT AccountID, IBAN, AccountName, BankName, CurrentBalance, LastSync FROM BankAccounts LIMIT 1"
        try:
            result = self._execute_query(query, fetch=True)
            return result[0] if result else None
        except Exception:
            return None

    def get_recent_orders(self, limit=5):
        """Holt die letzten unarchivierten Bestellungen für das Dashboard-Table-Widget"""
        query = """
            SELECT OrderID, UserID, OrderStatus, OrderDate, OrderAmount, PaymentStatus 
            FROM Orders 
            WHERE IsArchived = 0 
            ORDER BY OrderDate DESC 
            LIMIT ?
        """
        try:
            return self._execute_query(query, (limit,), fetch=True)
        except Exception:
            return []
        
# =========================================================================
    # MATPLOTLIB PLOT GENERIERUNG (Liefert Base64-Strings fürs Template)
    # =========================================================================

    def generate_order_plot(self):
        """Generiert den Plot für Bestellumsätze aggregiert nach Datum"""
        query = """
            SELECT OrderDate, OrderAmount 
            FROM Orders 
            WHERE IsArchived = 0 
            ORDER BY OrderDate ASC
        """
        try:
            rows = self._execute_query(query, fetch=True)
            if not rows:
                return None

            # Daten nach Tag (YYYY-MM-DD) aggregieren
            daily_data = {}
            for row in rows:
                # Splittet "2026-02-11 17:42:01" auf "2026-02-11"
                date_str = row['OrderDate'].split(' ')[0]
                # OrderAmount von Cents in Euro umrechnen
                amount_eur = row['OrderAmount'] / 100.0
                daily_data[date_str] = daily_data.get(date_str, 0.0) + amount_eur

            # Sortieren nach Datum für korrekte X-Achsen-Abfolge
            sorted_dates = sorted(daily_data.keys())
            amounts = [daily_data[d] for d in sorted_dates]

            # Plot erstellen
            plt.figure(figsize=(6, 3.5))
            plt.plot(sorted_dates, amounts, marker='o', color='#1A237E', linewidth=2)
            plt.title('Umsatz nach Bestelldatum (in €)', fontsize=12, fontweight='bold', color='#343a40')
            plt.grid(True, linestyle='--', alpha=0.5)
            plt.xticks(rotation=30, ha='right', fontsize=8)
            plt.tight_layout()

            return self._convert_plot_to_base64()
        except Exception:
            return None

    def generate_bank_plot(self):
        """Generiert den Plot für den Bank-Cashflow (Einnahmen/Ausgaben)"""
        query = """
            SELECT BookingDate, Amount 
            FROM BankTransactions 
            ORDER BY BookingDate ASC
        """
        try:
            rows = self._execute_query(query, fetch=True)
            if not rows:
                return None

            # Da Bankdaten bereits tagesgenau sind (YYYY-MM-DD), direkt aggregieren
            daily_data = {}
            for row in rows:
                date_str = row['BookingDate']
                daily_data[date_str] = daily_data.get(date_str, 0.0) + row['Amount']

            sorted_dates = sorted(daily_data.keys())
            cashflow = [daily_data[d] for d in sorted_dates]

            # Plot erstellen
            plt.figure(figsize=(6, 3.5))
            # Balkendiagramm für Cashflow (Grün für positiv, Rot für negativ)
            colors = ['#28a745' if val >= 0 else '#dc3545' for val in cashflow]
            plt.bar(sorted_dates, cashflow, color=colors, alpha=0.85)
            plt.title('Bank-Cashflow nach Buchungstag (in €)', fontsize=12, fontweight='bold', color='#343a40')
            plt.grid(True, linestyle='--', alpha=0.5)
            plt.axhline(0, color='black', linewidth=0.8, linestyle='-') # Nulllinie
            plt.xticks(rotation=30, ha='right', fontsize=8)
            plt.tight_layout()

            return self._convert_plot_to_base64()
        except Exception:
            return None

    def _convert_plot_to_base64(self):
        """Hilfsmethode: Wandelt die aktuelle Fig in einen sauberen Base64-String um"""
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150)
        img_buffer.seek(0)
        base64_string = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        plt.close() # Speicher freigeben!
        return base64_string