import os
import uuid
import sqlite3
from datetime import datetime
# Importiere die Klasse, die die _execute_query-Methode implementiert (z.B. DatabaseManager)

class OrderManager:
    """Verwaltet alle Bestell- und Zahlungsvorgänge."""

    def __init__(self):
        self.db_path = os.getenv('DB_PATH')

    def _execute_query(self, query, params=(), fetch=False, get_lastrowid=False, fetch_one=False):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            # Hinzufügen der row_factory, um den Zugriff über Spaltennamen zu ermöglichen (wie in Ihrem Frontend verwendet)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)

            # NOTE: COMMIT VOR dem FETCH ist in den meisten Fällen NICHT empfohlen,
            # da es Abfragen von Status-Änderungen trennt. In SQLite ist es oft toleriert.
            if not fetch and not get_lastrowid:
                conn.commit()

            if fetch:
                if fetch_one:
                    # Holt EINE Zeile (für get_project_by_id)
                    result = cursor.fetchone()
                else:
                    # Holt ALLE Zeilen (für get_all_product_categories)
                    result = cursor.fetchall()

                return result

            if get_lastrowid:
                conn.commit() # Commit für INSERT/UPDATE/DELETE
                return cursor.lastrowid

            # Für alle anderen INSERT/UPDATE/DELETE Operationen, die keinen Rückgabewert benötigen
            conn.commit()
            return None

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            # Fehler wird weitergereicht
            raise
        finally:
            if conn:
                conn.close()
    # Hilfsfunktion (muss in der DB-Zugriffsklasse existieren)
    # Annahme: Holen der ersten gültigen Adresse und Zahlungsmethode des Kunden, da diese
    # auf der Checkout-Seite später ausgewählt werden.
    def _get_default_ids(self, user_id):
        # Ruft die Adress- und Zahlungsmethoden-IDs ab (Beispiel: die erste gefundene)

        # Abfrage der Adresse:
        address_query = "SELECT AddressID FROM Addresses WHERE UserID = ? LIMIT 1"
        address_result = self._execute_query(address_query, (user_id,), fetch=True, fetch_one=True)
        address_id = address_result['AddressID'] if address_result else None

        # Abfrage der Zahlungsmethode:
        payment_query = "SELECT PaymentID FROM Payments WHERE UserID = ? LIMIT 1"
        payment_result = self._execute_query(payment_query, (user_id,), fetch=True, fetch_one=True)
        payment_id = payment_result['PaymentID'] if payment_result else None
        payment_id = 'NOT_SELECTED' if payment_id is None else payment_id # Fallback-Wert also mal testweise bis zur Implementierung der Zahlungsmethoden
        # NOTE: Falls keine IDs gefunden werden, führt dies zu einem Fehler (da die Spalten NOT NULL sind).
        # In diesem Fall MÜSSEN Sie sicherstellen, dass Benutzer immer eine Adresse/Zahlungsmethode haben.
        if not address_id or not payment_id:
             raise ValueError("Benutzer hat keine gespeicherte Adresse oder Zahlungsmethode.")

        return address_id, payment_id



    def get_product_id_by_project_id(self, project_id: str):
        """
        Sucht die ProductID in der Products-Tabelle basierend auf der
        SourceProjectID, die beim Quoten gesetzt wurde.
        """
        # Annahme: Products hat die Spalte SourceProjectID
        query = "SELECT ProductID FROM Products WHERE SourceProjectID = ?"
        result = self._execute_query(query, (project_id,), fetch=True, fetch_one=True)

        if result:
            return result['ProductID']
        return None


    # --- 2. Bestellung und Position erstellen ---
    def create_shop_order(self, user_id: str, project_id: str, product_id: str, price: float) -> str:
        """
        Erstellt die Einträge in Orders und OrderPositions für einen Sofortkauf
        aus einem erfolgreich gequoteten Projekt.
        """
        # Generiere IDs und aktuelles Datum
        order_id = f"ORDE_{str(uuid.uuid4())}"
        position_id =f"POSI_{str(uuid.uuid4())}"
        order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        price_in_cents = int(price * 100) # Speicherung als Cent-Betrag (Integer)

        # Holen der Standard-IDs (für initiale Erstellung, wird auf Checkout-Seite ggf. überschrieben)
        address_id, payment_id = self._get_default_ids(user_id)

        # --- Transaktion starten (optional, aber empfohlen) ---

        try:
            # 1. Orders-Eintrag erstellen
            print("ORDER WIRD ERSTELLT")
            order_query = """
            INSERT INTO Orders
            (OrderID, UserID, AddressID, SourceProjectID, PaymentID, OrderStatus, OrderDate, OrderAmount, PaymentStatus, TransactionID, PaymentMethod)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            order_params = (
                order_id,
                user_id,
                address_id,         # Initialer Standardwert
                project_id,
                payment_id,         # Initialer Standardwert
                'ORDER_CREATED',    # Status: Bestellung erstellt, bereit für Checkout
                order_date,
                price_in_cents,     # Gesamtbetrag
                'PENDING_PAYMENT',  # Status: Zahlung ausstehend
                None,
                None
            )
            # Führt die Abfrage aus und speichert in Orders (kein fetch nötig)
            self._execute_query(order_query, order_params)
            print("ORDER ERSTELLT")
            # 2. OrderPositions-Eintrag erstellen
            # Dies ist ein Sofortkauf, daher ist die Menge 1
            position_query = """
            INSERT INTO OrderPositions
            (PositionID, OrderID, ProductID, ProductType, Quantity, PricePerUnit)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            position_params = (
                position_id,
                order_id,
                product_id,
                'QUOTED_PROJECT',    # Typ: Quote-Projekt
                1,                  # Menge ist immer 1 für Quote-Projekte
                price_in_cents      # Preis der Einzelposition
            )
            self._execute_query(position_query, position_params)

            # --- Transaktion abschließen (Commit ist in _execute_query enthalten) ---

            return order_id

        except Exception as e:
            # Wenn ein Fehler auftritt (z.B. DB-Verbindung), rollbackt die _execute_query-Methode
            print(f"Fehler bei create_order_from_quote: {e}")
            raise # Leitet den Fehler an den Flask-Endpoint weiter

    def get_order_by_id(self, order_id: str):
        """Ruft eine einzelne Bestellung anhand der ID ab."""
        query = "SELECT * FROM Orders WHERE OrderID = ?"
        # fetch_one=True, da es eine einzelne Bestellung ist
        return self._execute_query(query, (order_id,), fetch=True, fetch_one=True)

    def get_order_position_for_checkout(self, order_id: str):
        query= "SELECT Quantity FROM OrderPositions WHERE OrderID = ?"
        # auch fetch_one
        return self._execute_query(query, (order_id,), fetch=True, fetch_one=True)

    def get_order_positions(self, order_id: str):
        """Ruft alle Positionen für eine bestimmte Bestellung ab."""
        # HINWEIS: Für Multi-Bestellung
        query = """
        SELECT op.*, p.ProductName,
        op.PricePerUnit AS Price
        FROM OrderPositions op
        JOIN Products p ON op.ProductID = p.ProductID
        WHERE op.OrderID = ?
        """
        # fetch=True, da es eine Liste von Positionen ist
        return self._execute_query(query, (order_id,), fetch=True)

    def finalize_order_details(self, order_id: str, address_id: str, payment_id: str):

        order_status ='ORDER_FINALIZED'

        """Aktualisiert die Adresse und Zahlungsmethode einer Bestellung vor dem Checkout."""
        query = """
        UPDATE Orders
        SET AddressID = ?, PaymentID = ?, OrderStatus = ?
        WHERE OrderID = ?
        """
        params = (address_id, payment_id, order_status, order_id)

        # Ausführung der Abfrage (kein Fetch nötig, da es ein UPDATE ist)
        # Die _execute_query-Methode sollte hier automatisch commiten.
        try:
            self._execute_query(query, params)
            print(f"Details für Bestellung {order_id} aktualisiert: Adresse={address_id}, Zahlung={payment_id}")
            return True
        except Exception as e:
            print(f"Fehler bei finalize_order_details für Bestellung {order_id}: {e}")
            # Wir lassen die Exception zur Flask-View durch, damit sie den Fehler anzeigen kann.
            raise

    def get_orders_by_user(self, user_id: str):
        """Ruft alle Bestellungen eines bestimmten Benutzers ab."""
        query = "SELECT * FROM Orders WHERE UserID = ? ORDER BY OrderDate DESC"
        return self._execute_query(query, (user_id,), fetch=True)

    def get_orders_quantity(self, order_id: str):
        """Ruft Stückzahl aller Bestellungen einer bestimmten Order ab."""
        query = "SELECT Quantity FROM OrderPositions WHERE OrderID = ?"
        return self._execute_query(query, (order_id,), fetch=True)

    def get_address_by_id(self, address_id: str):
        """Ruft eine Adresse anhand der AddressID ab."""
        query = "SELECT * FROM Addresses WHERE AddressID = ?"
        return self._execute_query(query, (address_id,), fetch=True, fetch_one=True)
    def get_payment_by_id(self, payment_id: str):
        """Ruft eine Zahlungsmethode anhand der PaymentID ab."""
        query = "SELECT * FROM Payments WHERE PaymentID = ?"
        return self._execute_query(query, (payment_id,), fetch=True, fetch_one=True)

    def make_new_single_order(self,order_id, user_id, order_date, final_quote_price, project_id):

        order_query="""
            INSERT INTO Orders (OrderID, UserID, OrderDate, OrderAmount, OrderStatus, PaymentStatus, SourceProjectID)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """

        order_params= (
            order_id,
            user_id,
            order_date,
            final_quote_price,
            'DRAFT',
            'PENDING_PAYMENT',
            project_id
        )

        self._execute_query(order_query,order_params)

    def make_single_order_position(self, position_id, order_id, product_id, product_type, quantity, price_per_unit):

        order_query="""
            INSERT INTO OrderPositions (PositionID, OrderID, ProductID, ProductType, Quantity, PricePerUnit)
            VALUES (?, ?, ?, ?, ?, ?)
            """
        order_params=(
            position_id,
            order_id,
            product_id,
            product_type,
            quantity,
            price_per_unit
        )
        self._execute_query(order_query,order_params)


    def get_open_order_for_project(self, project_id: str, user_id: str):
        """
        Gibt die OrderID einer offenen Bestellung für ein gegebenes Projekt und Benutzer zurück.
        Falls keine offene Bestellung existiert, wird None zurückgegeben.
        """
        query = """
        SELECT OrderID
        FROM Orders
        WHERE SourceProjectID = ? AND UserID = ?
        LIMIT 1
        """
        result = self._execute_query(query, (project_id, user_id), fetch=True, fetch_one=True)
        return result['OrderID'] if result else None