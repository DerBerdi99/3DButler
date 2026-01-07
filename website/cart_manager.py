import os
import uuid
import sqlite3

# Annahme: DB_PATH ist global verfügbar oder hier definiert


class CartManager:
    """Verwaltet Datenbankoperationen für den Warenkorb (Shopping Cart)."""
    
    def __init__(self):
        self.db_path = os.getenv('DB_PATH')
        

    def _execute_query(self, query, params=(), fetch=False, get_lastrowid=False, fetch_one=False):
        # UNVERÄNDERT: Datenbank-Ausführungslogik
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)

            if not fetch and not get_lastrowid:
                conn.commit()

            if fetch:
                result = cursor.fetchone() if fetch_one else cursor.fetchall()
                return result

            if get_lastrowid:
                conn.commit()
                return cursor.lastrowid

            conn.commit()
            return None

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def get_cart_items_for_user(self, user_id):
        """
        Ruft alle Warenkorbartikel für einen bestimmten Benutzer ab,
        einschließlich Produktdetails, Preis und Menge.
        """
        query = """
            SELECT sc.CartID, p.ProductID, p.ProductName, p.ProductDescription, pp.ProductPrice, cp.Quantity, p.ImagePath 
            FROM ShoppingCarts sc
            JOIN CartPositions cp ON sc.CartID = cp.CartID
            JOIN Products p ON cp.ProductID = p.ProductID
            JOIN ProductPrices pp ON p.ProductID = pp.ProductID
            WHERE sc.UserID = ?
            AND pp.DateAdded = (
                SELECT MAX(DateAdded) 
                FROM ProductPrices 
                WHERE ProductID = pp.ProductID
            )
        """
        # Die ursprüngliche, nicht standardisierte Abfrage wurde direkt übernommen.
        return self._execute_query(query, (user_id,), fetch=True)
    
    def get_product_stock_info(self, product_id: str):
        """Holt Preis und Lagerbestand für die Validierung."""
        query = """
            SELECT pp.ProductPrice, p.StockQuantity 
            FROM Products p
            JOIN ProductPrices pp ON p.ProductID = pp.ProductID
            WHERE p.ProductID = ?
            ORDER BY pp.DateAdded DESC LIMIT 1
        """
        return self._execute_query(query, (product_id,), fetch=True, fetch_one=True)

    def add_product_to_cart(self, user_id: str, product_id: str, quantity: int):
        """Kapselt die gesamte 'In den Warenkorb'-Logik."""
        # 1. Cart suchen oder neu anlegen
        cart = self._execute_query("SELECT CartID FROM ShoppingCarts WHERE UserID = ?", (user_id,), fetch=True, fetch_one=True)
        
        if not cart:
            cart_id = f"CART_{str(uuid.uuid4())}"
            self._execute_query(
                "INSERT INTO ShoppingCarts (CartID, UserID, DateCreated) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (cart_id, user_id)
            )
        else:
            cart_id = cart['CartID']

        # 2. Prüfen, ob Produkt bereits im Cart ist
        existing_pos = self._execute_query(
            "SELECT Quantity FROM CartPositions WHERE CartID = ? AND ProductID = ?",
            (cart_id, product_id), fetch=True, fetch_one=True
        )

        if existing_pos:
            new_qty = existing_pos['Quantity'] + quantity
            self._execute_query(
                "UPDATE CartPositions SET Quantity = ?, DateAdded = CURRENT_TIMESTAMP WHERE CartID = ? AND ProductID = ?",
                (new_qty, cart_id, product_id)
            )
        else:
            pos_id = f"POSI_{str(uuid.uuid4())}"
            self._execute_query(
                "INSERT INTO CartPositions (PositionID, CartID, ProductID, Quantity, DateAdded) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (pos_id, cart_id, product_id, quantity)
            )
        return True
    
    def remove_product_from_cart(self, user_id: str, product_id: str) -> bool:
        """
        Löscht ein Produkt aus dem Warenkorb. 
        Löscht den Warenkorb-Header automatisch, wenn er leer ist.
        """
        # 1. CartID des Benutzers holen
        cart = self._execute_query(
            "SELECT CartID FROM ShoppingCarts WHERE UserID = ?", 
            (user_id,), fetch=True, fetch_one=True
        )

        if not cart:
            return False

        cart_id = cart['CartID']

        # 2. Position löschen
        self._execute_query(
            "DELETE FROM CartPositions WHERE CartID = ? AND ProductID = ?",
            (cart_id, product_id)
        )

        # 3. Prüfen, ob noch Items übrig sind
        remaining = self._execute_query(
            "SELECT COUNT(*) as count FROM CartPositions WHERE CartID = ?",
            (cart_id,), fetch=True, fetch_one=True
        )

        if remaining and remaining['count'] == 0:
            self._execute_query("DELETE FROM ShoppingCarts WHERE CartID = ?", (cart_id,))
        
        return True
    
    def get_wishlist_for_user(self, user_id: str):
        """Holt alle Wunschlisten-Einträge eines Nutzers."""
        query = "SELECT * FROM WishLists WHERE UserID = ?"
        return self._execute_query(query, (user_id,), fetch=True)

    def add_to_wishlist(self, user_id: str, product_id: str):
        """Holt Produktdaten und fügt sie der Wunschliste hinzu."""
        # Produktdaten mit aktuellstem Preis holen
        query_prod = """
            SELECT p.ProductName, p.ImagePath, pp.ProductPrice
            FROM Products p
            JOIN ProductPrices pp ON p.ProductID = pp.ProductID
            WHERE p.ProductID = ?
            ORDER BY pp.DateAdded DESC LIMIT 1
        """
        product = self._execute_query(query_prod, (product_id,), fetch=True, fetch_one=True)
        
        if product:
            insert_query = """
                INSERT INTO WishLists (ArtikelName, Price, UserID, ProductImage, ProductID)
                VALUES (?, ?, ?, ?, ?)
            """
            self._execute_query(insert_query, (
                product['ProductName'], 
                product['ProductPrice'], 
                user_id, 
                product['ImagePath'], 
                product_id
            ))
            return True
        return False
    
    def remove_from_wishlist(self, user_id: str, product_id: str) -> bool:
        """Entfernt ein spezifisches Produkt von der Wunschliste eines Nutzers."""
        query = "DELETE FROM WishLists WHERE UserID = ? AND ProductID = ?"
        self._execute_query(query, (user_id, product_id))
        return True