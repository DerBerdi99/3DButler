import os
import uuid
import hashlib
import sqlite3
import bcrypt
from datetime import datetime, timedelta

class UserManager:
    def __init__(self):
        self.db_path = os.getenv('DB_PATH')
        self.TOKEN_TYPE = 'PASSWORD_RESET'

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

    def verify_login(self, username: str, password: str):
        """
        Verifies login credentials and returns user info if valid.

        Returns:
            Tuple (success: bool, user_id: int|None, username: str|None, is_admin: bool|None)
        """
        # ── 1. Grundlegende Eingabevalidierung ──────────────────────────────
        if not username or not isinstance(username, str):
            return False, None, None, None

        if not password or not isinstance(password, str):
            return False, None, None, None

        # Sehr einfache Längenprüfung (kann später erweitert werden)
        if len(username.strip()) < 3 or len(username.strip()) > 80:
            return False, None, None, None

        if len(password) < 8:  # Mindestlänge, in Produktion höher einstellen
            return False, None, None, None

        # Benutzername normalisieren (Leerzeichen entfernen, Kleinbuchstaben – optional)
        username = username.strip()

        # ── 2. Prepared Statement – schützt bereits vor SQL-Injection ───────
        query = """
            SELECT u.UserID, p.Password, u.IsAdmin
            FROM Users u
            INNER JOIN Passwords p ON u.UserID = p.UserID
            WHERE u.Username = ?
        """
        user_data = self._execute_query(query, (username,), fetch=True, fetch_one=True)

        # ── 3. Kein User gefunden → frühzeitig abbrechen ─────────────────────
        if not user_data:
            # Optional: konstante Zeitverzögerung gegen Timing-Attacken
            # bcrypt.checkpw(b"dummy", bcrypt.gensalt())  # sehr teuer → nur wenn du paranoid bist
            return False, None, None, None

        # ── 4. Daten auspacken ──────────────────────────────────────────────
        user_id, stored_password_hash, is_admin = user_data

        # Typ-Sicherheit (für den Fall, dass row_factory fehlt)
        if not isinstance(stored_password_hash, bytes):
            # Sollte eigentlich nie passieren, wenn DB korrekt ist
            return False, None, None, None

        # ── 5. Passwortvergleich mit bcrypt ─────────────────────────────────
        try:
            password_correct = bcrypt.checkpw(
                password.encode('utf-8'),
                stored_password_hash
            )
        except Exception:  # z. B. ungültiges Hash-Format
            return False, None, None, None

        if password_correct:
            return True, user_id, username, bool(is_admin)
        else:
            return False, None, None, None
        

    def logout_user(self,session):
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('is_admin', None)
# TODO: alle  INSERTs in eine Transaktion packen (multi_queries=True), aktuell noch  separate _execute_query → Race-Condition möglich
    def register_user(self, data):
        #Fügt User, Passwort und Adresse in einer Transaktion hinzu.

        user_id = f"USER_{str(uuid.uuid4())}"
        
        address_id = f"ADDR_{str(uuid.uuid4())}"

        password_bytes = data['password'].encode('utf-8')
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

        # Token-Generierung

        verification_token_plain = str(uuid.uuid4()).replace('-', '')

        # Hashen des Tokens für die Speicherung mit SHA256 (wie üblich für Verifikationstokens)
        token_hash = hashlib.sha256(verification_token_plain.encode('utf-8')).hexdigest()

        # Ablaufdatum: 24 Stunden ab jetzt
        expiration_date = datetime.now() + timedelta(hours=24)

        user_query = """
            INSERT INTO Users (UserID, FirstName, LastName, Email, Phone, Gender, Username, IsAdmin, IsActive)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        user_params = (
            user_id, data['firstname'], data['lastname'], data['email'],
            data['phone'], data['gender'], data['username'], 0, 0)
        # 1. INSERT INTO Users


        self._execute_query(user_query, user_params)

        # 2. INSERT INTO Passwords
        pass_query = "INSERT INTO Passwords (UserID, Password) VALUES (?, ?)"
        pass_params = (user_id, hashed_password)
        self._execute_query(pass_query, pass_params)

        # 3. INSERT INTO Addresses
        address_query = """
            INSERT INTO Addresses (AddressID, UserID, Street, City, Zipcode, Country, IsDefaultShipping)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        address_params = (
            address_id, user_id, data['street_name'] + ' ' + data['street_number'], # Zusammenführung von Name und Nummer
            data['city'], data['zipcode'], data['country'],1
        )

        self._execute_query(address_query, address_params)

        # 4. INSERT INTO VerificationTokens
        token_query = """
            INSERT INTO VerificationTokens (UserID, TokenHash, Expiry)
            VALUES (?, ?, ?)
        """
        expiration_date = datetime.now() + timedelta(hours=3) 

        # 2. Dann für die Datenbank formatieren (String-Ebene)
        expiration_str = expiration_date.strftime('%Y-%m-%d %H:%M:%S')

        token_params = (
            user_id,
            token_hash,
            expiration_str
        )
        self._execute_query(token_query, token_params)

        # Der Klartext-Token wird zurückgegeben, um ihn in der auth.py per E-Mail zu versenden
        return verification_token_plain

    def activate_user_with_token(self, email, submitted_token):
        # 1. UserID anhand der E-Mail finden und prüfen
        user = self._execute_query("SELECT UserID, IsActive FROM Users WHERE Email = ?", (email,), fetch=True)
        if not user:
            return False # E-Mail existiert nicht

        user_id = user[0][0]
        is_active = user[0][1]
        print(f"DEBUG: USER_ID: {user_id}, IS_ACTIVE: {is_active}")
        print(f"DEBUG: SUBMITTED TOKEN: {submitted_token}")
      
        # Frühzeitiger Exit: Wenn der Benutzer bereits aktiv ist
        if is_active == 1:
            return False

        # 2. Submitted Token hashen, um mit dem gespeicherten Hash zu vergleichen
        submitted_token_hash = hashlib.sha256(submitted_token.encode('utf-8')).hexdigest()
        
        print(f"DEBUG: SUB_HASH: {submitted_token_hash}")
        # 3. Datenbankabfrage nach dem Token und ExpirationDate
        # Wichtig: Wir prüfen nur auf den Hash und sortieren nach 'Created' absteigend, um den neuesten Token zu prüfen
        token_data = self._execute_query("""
            SELECT TokenHash, Expiry
            FROM VerificationTokens
            WHERE UserID = ? AND TokenHash = ?
            ORDER BY Created DESC
            LIMIT 1
        """, (user_id, submitted_token_hash), fetch=True)

        db_hash = token_data[0][0] if token_data else None
        print(f"DEBUG: DB_HASH: {db_hash}")

        if not token_data:
            return False # Kein passender Token gefunden

        token_hash, expiry_str = token_data[0]

        # 4. Gültigkeitsprüfung (Expiry)
        expiry_time = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
        if datetime.now() > expiry_time:
            # Token abgelaufen
            self._execute_query("DELETE FROM VerificationTokens WHERE TokenHash = ?", (token_hash,))
            return False

        # 5. Token gültig: User aktivieren und Token löschen

        # User aktivieren: IsActive = 1
        self._execute_query("UPDATE Users SET IsActive = 1 WHERE UserID = ?", (user_id,))

        # Token aus der Tabelle löschen, da er verbraucht ist
        self._execute_query("DELETE FROM VerificationTokens WHERE TokenHash = ?", (token_hash,))

        return True


    def get_all_addresses(self, user_id: str):
        """Ruft alle gespeicherten Adressen eines Benutzers ab."""
        query = "SELECT * FROM Addresses WHERE UserID = ? ORDER BY IsDefaultShipping DESC"
        return self._execute_query(query, (user_id,), fetch=True)

    def get_all_payment_methods(self, user_id: str):
        """Ruft alle gespeicherten Zahlungs-Tokens/Methoden eines Benutzers ab."""
        query = "SELECT * FROM Payments WHERE UserID = ? ORDER BY IsDefaultMethod DESC"
        return self._execute_query(query, (user_id,), fetch=True)


    def find_user_by_id(self, user_id):
        query = "SELECT IsActive, IsAdmin FROM Users WHERE UserID = ?"
        result = self._execute_query(query, (user_id,), fetch=True)
        if result:
            return {'IsActive': result[0][0], 'IsAdmin': result[0][1]}
        return None
    
    def find_user_by_email(self, email: str):
        """Find a user by email. Returns a dict with user fields or None if not found."""
        query = """
            SELECT UserID
            FROM Users
            WHERE Email = ?
        """
        data = self._execute_query(query, (email,), fetch=True)
        if not data:
            return None

        columns = ['UserID']

        # Das erste (und einzige) Ergebnis-Tupel
        user_tuple = data[0]

        # Konvertierung zu Dictionary
        user_dict = dict(zip(columns, user_tuple))

        return user_dict

    # Passwort zurücksetzen 1: TOKEN SPEICHERN
    # =================================================================

    def save_reset_token(self, user_id, token):
        """Speichert den Reset-Token und setzt das Ablaufdatum (1 Stunde). Verwendet SHA256-Hashing."""
        TOKEN_VALIDITY_HOURS = 1

        expiry_time = datetime.now() + timedelta(hours=TOKEN_VALIDITY_HOURS)
        expiry_str = expiry_time.isoformat()

        token_hash_str = hashlib.sha256(token.encode('utf-8')).hexdigest()

        # Zwei Operationen in einer Transaktion
        operations = [
            # 1. Alte PASSWORD_RESET-Tokens für diesen User löschen
            (
                'DELETE FROM VerificationTokens WHERE UserID = ? AND TokenType = ?',
                (user_id, self.TOKEN_TYPE)
            ),
            # 2. Neuen Token einfügen
            (
                'INSERT INTO VerificationTokens (UserID, TokenHash, Expiry, TokenType) VALUES (?, ?, ?, ?)',
                (user_id, token_hash_str, expiry_str, self.TOKEN_TYPE)
            )
        ]

        try:
            self._execute_query(operations, multi_queries=True)
            return True
        except sqlite3.Error as e:
            # Optional: Logging statt print
            # logging.error(f"Fehler beim Speichern des Reset-Tokens für {user_id}: {e}")
            return False

    # Passwort zurücksetzen 2: TOKEN SUCHEN UND GÜLTIGKEIT PRÜFEN
    # =================================================================

    def find_user_by_reset_token(self, token_hash):
        """
        Sucht einen Benutzer über den SHA256-Hash des Reset-Tokens in der VerificationTokens-Tabelle
        und prüft das Ablaufdatum.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        print("CONN ESTABLISHED")
        # SQLite kann ISO-Strings vergleichen.
        current_time_str = datetime.now().isoformat()
        print("current_time_str und token hash")
        print(current_time_str)
        print(token_hash)

        # Sucht den User, wo der TokenHash passt UND der Token nicht abgelaufen ist.
        query = cursor.execute(
            """
            SELECT u.* FROM Users u
            JOIN VerificationTokens vt ON u.UserID = vt.UserID
            WHERE vt.TokenHash = ?
              AND vt.TokenType = ?
              AND vt.Expiry > ?
            """,
            (token_hash, self.TOKEN_TYPE, current_time_str)
        )
        user = query.fetchone()
        print(user)
        cursor.close()
        conn.close()

        return user

    # Passwort zurücksetzen 3: PASSWORT AKTUALISIEREN UND TOKEN LÖSCHEN
    # =================================================================

    def update_password(self, user_id, new_password):
        """Aktualisiert das Passwort und löscht das verwendete Token."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Hashing mit bcrypt für das neue Passwort
            password_bytes = new_password.encode('utf-8')
            hashed_password_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
            password = hashed_password_bytes

            # 1. Passwort aktualisieren
            cursor.execute(
                'UPDATE Passwords SET Password = ? WHERE UserID = ?',
                (password, user_id)
            )

            # 2. Token aus der separaten Tabelle löschen (Konsumierung)
            cursor.execute(
                'DELETE FROM VerificationTokens WHERE UserID = ? AND TokenType = ?',
                (user_id, self.TOKEN_TYPE)
            )

            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"FEHLER: Fehler beim Aktualisieren des Passworts für {user_id}: {e}")
            return False
        finally:
            conn.close()

    def reset_password_with_token(self, token, new_password):
        """Setzt das Passwort zurück mit einem gültigen Reset-Token."""
        # KORREKTUR: Hashe den erhaltenen Klartext-Token mit SHA256, um ihn mit der DB abzugleichen.
        token_hash_str = hashlib.sha256(token.encode('utf-8')).hexdigest()

        print(f"Token Hash für Suche: {token_hash_str}")
        print(f"Neues Passwort: {new_password}")

        # 1. Benutzer anhand des Token-Hash finden und Gültigkeit prüfen
        user = self.find_user_by_reset_token(token_hash_str)

        if not user:
            print("Konnte User nicht finden (Token ungültig/abgelaufen)")
            return False

        print("User gefunden")

        # ANMERKUNG: Abhängig von der User-Tabelle-Struktur, kann die UserID an einer anderen Stelle sein.
        # Da SELECT u.* verwendet wurde, ist es wahrscheinlich das erste Feld.
        user_id = user[0]

        # 2. Passwort aktualisieren und Token löschen
        # update_password kümmert sich um das bcrypt-Hashing des neuen Passworts.
        return self.update_password(user_id, new_password)
    

    def get_user_email(self, user_id: str):
        """Retrieves the email address of a user by their user ID."""
        query = "SELECT Email FROM Users WHERE UserID = ?"
        result = self._execute_query(query, (user_id,), fetch=True)
        if result:
            return result[0][0]
        return None

    def get_all_users(self):
        """Ruft alle Benutzer aus der Datenbank ab."""
        query = "SELECT UserID, FirstName, LastName, Email, Phone, Gender, Username, IsAdmin, IsActive FROM Users"
        return self._execute_query(query, fetch=True)

    def toggle_active_status(self, user_id):
        """Invertiert den aktuellen IsActive-Status des Benutzers."""
        # Hole aktuellen Status
        user_status = self.find_user_by_id(user_id)
        if not user_status:
            raise ValueError("Benutzer nicht gefunden.")

        new_status = 0 if user_status['IsActive'] == 1 else 1
        query = "UPDATE Users SET IsActive = ? WHERE UserID = ?"
        self._execute_query(query, (new_status, user_id)) # Falls _execute_query ein Commit kapselt, sonst commit() hinzufügen

    def delete_user(self, user_id):
        """
        Löscht einen Benutzer kaskadensicher. 
        Umsortierung von NOT-NULL-Fremdschlüsseln auf einen Dummy-User.
        """
        dummy_id = "DELETED_USER"

        # Sicherstellen, dass der Dummy-User in der DB existiert
        check_dummy = "SELECT 1 FROM Users WHERE UserID = ?"
        if not self._execute_query(check_dummy, (dummy_id,), fetch=True):
            create_dummy = """
                INSERT INTO Users (UserID, FirstName, LastName, Email, Username, IsAdmin, IsActive)
                VALUES (?, 'Gelöschter', 'Nutzer', 'deleted@3dbutler.local', 'deleted_user', 0, 0)
            """
            self._execute_query(create_dummy, (dummy_id,))

        # 1. Fremdschlüssel-Umschreibung (NOT NULL Spalten)
        self._execute_query("UPDATE Products SET UserID = ? WHERE UserID = ?", (dummy_id, user_id))
        self._execute_query("UPDATE Projects SET UserID = ? WHERE UserID = ?", (dummy_id, user_id))
        self._execute_query("UPDATE Orders SET UserID = ? WHERE UserID = ?", (dummy_id, user_id))

        # 2. Löschen aus Tabellen ohne ON DELETE CASCADE (Optionale Bereinigung)
        self._execute_query("DELETE FROM ShoppingCarts WHERE UserID = ?", (user_id,))
        self._execute_query("DELETE FROM WishLists WHERE UserID = ?", (user_id,))
        self._execute_query("DELETE FROM VerificationTokens WHERE UserID = ?", (user_id,))

        # 3. Credentials & Hauptdatensatz löschen (Addresses/Payments fallen über DB CASCADE, falls definiert)
        self._execute_query("DELETE FROM Passwords WHERE UserID = ?", (user_id,))
        self._execute_query("DELETE FROM Users WHERE UserID = ?", (user_id,))