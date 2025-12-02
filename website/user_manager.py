import os
import sqlite3
import uuid
import bcrypt
from datetime import datetime, timedelta
import hashlib
import os
import sqlite3
import uuid
import bcrypt
from datetime import datetime, timedelta
import hashlib

class UserManager:
    def __init__(self):
        self.db_path = os.getenv('DB_PATH')
        self.TOKEN_TYPE= 'PASSWORD_RESET'

    def _execute_query(self, query, params=(), fetch=False, get_lastrowid=False):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()

            # 1. Daten abrufen (für SELECT)
            if fetch:
                # Gibt die Ergebnisse als Liste von Tupeln zurück
                return cursor.fetchall()

            # 2. Letzte eingefügte ID zurückgeben (für INSERT)
            if get_lastrowid:
                # Gibt die ID der Zeile zurück, die durch den letzten INSERT erstellt wurde
                return cursor.lastrowid

            # 3. Standard-Rückgabe (für UPDATE, DELETE, oder INSERT ohne lastrowid-Bedarf)
            return None

        except sqlite3.Error as e:
            # Rollback und Fehler weiterwerfen
            if conn:
                conn.rollback()
            raise

        finally:
            if conn:
                conn.close()

    def verify_login(self,username,password):
        # ANMERKUNG: Der hardgecodete Pfad sollte idealerweise durch self.db_path ersetzt werden.
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Join Users and Passwords tables to retrieve password
        cursor.execute("""
            SELECT u.UserID, p.Password, u.IsAdmin
            FROM Users u
            INNER JOIN Passwords p ON u.UserID = p.UserID
            WHERE u.Username = ?
        """, (username,))
        user_data = cursor.fetchone()
        conn.close()
        if user_data:
            user_id, stored_password, is_admin = user_data

            # 3. Passwort prüfen (bcrypt.checkpw)
            if bcrypt.checkpw(password.encode('utf-8'), stored_password):
                # Erfolg: Gibt die notwendigen Daten zurück
                return True, user_id, username, is_admin
            else:
                # Falsches Passwort
                return False, None, None, None
        else:
            # Benutzer nicht gefunden
            return False, None, None, None

    def logout_user(self,session):
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('is_admin', None)

    def register_user(self, data):
        #Fügt User, Passwort und Adresse in einer Transaktion hinzu.

        user_id = f"USER_{str(uuid.uuid4())}"
        address_id = f"ADDR_{str(uuid.uuid4())}"
        payment_id = f"PAYM_{str(uuid.uuid4())}"


        password_bytes = data['password'].encode('utf-8')
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

        # Token-Generierung

        verification_token_plain = str(uuid.uuid4()).replace('-', '')

        # Hashen des Tokens für die Speicherung mit SHA256 (wie üblich für Verifikationstokens)
        token_hash = hashlib.sha256(verification_token_plain.encode('utf-8')).hexdigest()

        # Ablaufdatum: 24 Stunden ab jetzt
        expiration_date = datetime.now() + timedelta(hours=24)

        user_query = """
            INSERT INTO Users (UserID, FirstName, LastName, Email, Phone, Gender, Username, IsAdmin, IsActive, AddressID, PaymentID)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        user_params = (
            user_id, data['firstname'], data['lastname'], data['email'],
            data['phone'], data['gender'], data['username'], 0, 0, address_id, payment_id )
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
        token_params = (
            user_id,
            token_hash,
            expiration_date.strftime('%Y-%m-%d %H:%M:%S') # Formatierung für SQLite DATETIME
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

        # Frühzeitiger Exit: Wenn der Benutzer bereits aktiv ist
        if is_active == 1:
            return False

        # 2. Submitted Token hashen, um mit dem gespeicherten Hash zu vergleichen
        submitted_token_hash = hashlib.sha256(submitted_token.encode('utf-8')).hexdigest()

        # 3. Datenbankabfrage nach dem Token und ExpirationDate
        # Wichtig: Wir prüfen nur auf den Hash und sortieren nach 'Created' absteigend, um den neuesten Token zu prüfen
        token_data = self._execute_query("""
            SELECT TokenHash, Expiry
            FROM VerificationTokens
            WHERE UserID = ? AND TokenHash = ?
            ORDER BY Created DESC
            LIMIT 1
        """, (user_id, submitted_token_hash), fetch=True)

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        TOKEN_VALIDITY_HOURS = 1
        try:
            # Ablaufdatum berechnen und als ISO-String speichern
            expiry_time = datetime.now() + timedelta(hours=TOKEN_VALIDITY_HOURS)
            expiry_str = expiry_time.isoformat()

            # NEU: HASHEN des Klartext-Tokens mit SHA256 vor der Speicherung
            token_hash_str = hashlib.sha256(token.encode('utf-8')).hexdigest()

            # 1. WICHTIG: Existierende PASSWORD_RESET-Tokens für diesen User löschen.
            cursor.execute('DELETE FROM VerificationTokens WHERE UserID = ? AND TokenType = ?',
                           (user_id, self.TOKEN_TYPE))
            print("OLD TOKEN DELETED")
            # 2. NEU: Token in die VerificationTokens-Tabelle einfügen
            cursor.execute(
                'INSERT INTO VerificationTokens (UserID, TokenHash, Expiry, TokenType) VALUES (?, ?, ?, ?)',
                (user_id, token_hash_str, expiry_str, self.TOKEN_TYPE)
            )
            print("NEW TOKEN INSERTED")
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"FEHLER: Fehler beim Speichern des Reset-Tokens für {user_id}: {e}")
            return False
        finally:
            conn.close()

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