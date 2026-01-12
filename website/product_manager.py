import os
import sqlite3
import uuid
from datetime import datetime
import random
from typing import List, Dict, Any

class ProductManager:
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


    def get_all_product_categories(self) -> List[sqlite3.Row]:
        """Ruft alle verfügbaren Kategorien aus der ProductCategories-Tabelle ab."""
        query = "SELECT CategoryName FROM ProductCategories ORDER BY CategoryName ASC"
        return self._execute_query(query, fetch=True)
    

# --- 1. Admin-Workflow (Review-Queue) ---

    def get_products_for_finalization(self, include_inactive: bool = True):
        """
        ERSETZT die bisherige Fetch-Funktion für das Backlog.
        Liefert alle Produkte inkl. ihrem Aktivierungsstatus.
        """
        query = "SELECT * FROM Products"
        if not include_inactive:
            query += " WHERE IsActive = 1"

        query += " ORDER BY IsActive DESC, CreatedAt DESC" # Aktive zuerst
        return self._execute_query(query, fetch=True)
    
    def get_product_by_id(self, product_id: str) -> sqlite3.Row:
        """
        Ruft ein einzelnes Produkt ab (P.*, CreatorName) und fügt den 
        aktuell gültigen Preis über die Subquery-Logik hinzu.
        """
        query = """
            SELECT 
                p.*, 
                u.Username AS CreatorName,
                pp.ProductPrice
            FROM Products p
            INNER JOIN Users u ON p.UserID = u.UserID
            INNER JOIN ProductPrices pp ON p.ProductID = pp.ProductID COLLATE NOCASE
            WHERE p.ProductID = ? COLLATE NOCASE
            AND pp.DateAdded = (
                SELECT MAX(DateAdded)
                FROM ProductPrices 
                WHERE ProductID = pp.ProductID
            )
        """
        return self._execute_query(query, (product_id,), fetch=True, fetch_one=True)
    
    def finalize_product(self, product_id: str, final_price: float, final_category: str, is_shop_visible: int = 1) -> None:
        """
        Finalisiert ein Produkt: Aktualisiert den Status in Products und fügt den 
        neuen Listenpreis mit Zeitstempel in ProductPrices ein.
        """
        
        current_datetime = datetime.now().isoformat()
        
        # 1. Schreiboperation: Aktualisierung der Products-Tabelle (Status und Kategorie)
        # Die Spalte FinalPrice wird hier entfernt, da sie in ProductPrices liegt.
        update_product_query = """
        UPDATE Products 
        SET ProductCategory = ?, IsShopVisible = ?
        WHERE ProductID = ?
        """
        update_params = (final_category, is_shop_visible, product_id)
        
        self._execute_query(update_product_query, update_params)
        
        # 2. Schreiboperation: Einfügen des neuen Preises in ProductPrices (Historie)
        insert_price_query = """
        INSERT INTO ProductPrices (PriceID, ProductID, ProductPrice, DateAdded)
        VALUES (?, ?, ?, ?)
        """
        # Annahme: Wir generieren eine einfache eindeutige PriceID
        price_id = f"PRIC_{str(uuid.uuid4())}"
        insert_params = (price_id, product_id, final_price, current_datetime)
        
        self._execute_query(insert_price_query, insert_params)
        
        # Da _execute_query intern commit() aufruft, sind beide Operationen 
        # (wenn sie erfolgreich waren) persistent.


    def toggle_product_visibility(self, product_id: str, status: int):
        """
        NEUE FUNKTION: Ersetzt das harte Löschen im normalen Workflow.
        status: 0 für Deaktivieren (Soft Delete), 1 für Wiederherstellen.
        """
        self._execute_query(
            "UPDATE Products SET IsActive = ? WHERE ProductID = ?",
            (status, product_id)
        )
        return True

    def delete_product(self, product_id: str):
        """
        Löscht ein Produkt inkl. Preise, Cart-Referenzen und Bilddatei.
        """
        
        try:
            # 1. Produkt-Daten (für ImagePath)
            product = self._execute_query(
                "SELECT ImagePath FROM Products WHERE ProductID = ?",
                (product_id,),
                fetch=True,
                fetch_one=True
            )

            # Wenn Produkt gar nicht existiert → fertig
            if not product:
                return False

            # 2. Produktbild löschen (wenn vorhanden)
            image_path = product["ImagePath"]
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass  # Bild löschen ist optional, keine Unterbrechung

            # 3. Verknüpfte Daten löschen
            self._execute_query(
                "DELETE FROM ProductPrices WHERE ProductID = ?",
                (product_id,)
            )

            self._execute_query(
                "DELETE FROM CartPositions WHERE ProductID = ?",
                (product_id,)
            )

            # 4. Produkt selbst löschen
            self._execute_query(
                "DELETE FROM Products WHERE ProductID = ?",
                (product_id,)
            )

            return True

        except sqlite3.Error:
            raise
        
    # --- 2. Kunden-Shop-Logik (Slider/Shop-Ansicht) ---
    
    def get_random_shop_products(self, count: int = 5) -> List[sqlite3.Row]:
        """Ruft eine zufällige Auswahl an freigegebenen Shopartikeln ab."""
        
        # Nutzen der ORDER BY RANDOM() Funktion von SQLite für zufällige Auswahl
        query = """
        SELECT 
            ProductID, 
            ProductName, 
            ProductDescription, 
            ImagePath
        FROM Products 
        WHERE IsShopVisible = 1 
        ORDER BY RANDOM()
        LIMIT ?
        """
        # Wir übergeben nur die Felder, die für die Slideshow relevant sind
        return self._execute_query(query, (count,), fetch=True)
    
    
    def get_filter_options(self):
        """Erhebt alle in der DB vorkommenden Kategorien und Materialien."""
        categories = self._execute_query("SELECT DISTINCT ProductCategory FROM Products WHERE IsShopVisible = 1 AND IsActive = 1", fetch=True)
        materials = self._execute_query("SELECT DISTINCT MaterialType FROM Products WHERE IsShopVisible = 1 AND IsActive = 1", fetch=True)
        
        return {
            'categories': [c[0] for c in categories if c[0]],
            'materials': [m[0] for m in materials if m[0]]
        }

    def get_filtered_products(self, search_query=None, selected_categories=None, selected_materials=None):
        """Führt die gefilterte Suche inklusive Preisen aus."""
        
        params = []
        # Basis-Query (deine CTE Logik)
        sql = """
            WITH LatestPrices AS (
                SELECT ProductID, ProductPrice, DateAdded as PriceDateAdded,
                ROW_NUMBER() OVER(PARTITION BY ProductID ORDER BY DateAdded DESC) as rn
                FROM ProductPrices
            )
            SELECT p.*, lp.ProductPrice AS FinalPrice, lp.PriceDateAdded
            FROM Products p
            LEFT JOIN LatestPrices lp ON p.ProductID = lp.ProductID AND lp.rn = 1
            WHERE p.IsShopVisible = 1 AND p.IsActive = 1
        """
        
        # Dynamische WHERE-Erweiterung
        if search_query:
            sql += " AND (p.ProductName LIKE ? OR p.ProductDescription LIKE ?)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        
        if selected_categories:
            placeholders = ','.join(['?'] * len(selected_categories))
            sql += f" AND p.ProductCategory IN ({placeholders})"
            params.extend(selected_categories)

        if selected_materials:
            placeholders = ','.join(['?'] * len(selected_materials))
            sql += f" AND p.MaterialType IN ({placeholders})"
            params.extend(selected_materials)

        return self._execute_query(sql, params, fetch=True)

    def map_row_to_dict(self, row):
        if not row:
            return None

        # Da row ein sqlite3.Row Objekt ist, können wir Namen statt Indizes nutzen!
        return {
            'ProductID': row['ProductID'],
            'ProductName': row['ProductName'],
            'ProductDescription': row['ProductDescription'],
            'ProductCategory': row['ProductCategory'],
            'MaterialType': row['MaterialType'],
            'StockQuantity': row['StockQuantity'],
            'ImagePath': row['ImagePath'],
            # Hier greifen wir auf den Alias aus deinem SQL zu:
            'ProductPrice': row['FinalPrice']
        }