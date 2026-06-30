import os
import json
import uuid
import sqlite3
import re
import struct
from flask import jsonify
from werkzeug.utils import secure_filename
from datetime import datetime

from .calculation_manager import CalculationManager

calculation_manager = CalculationManager()

# Definieren Sie hier Ihre Konfigurationskonstanten (z.B. Dateipfade, Limits)
# HINWEIS: Die Klasse wird den UPLOAD_FOLDER nun dynamisch übergeben bekommen,
# aber wir behalten die Konstante für Fallbacks oder initiale Struktur bei.
TEMP_UPLOAD_FOLDER = os.getenv('UPLOAD_DIR_PATH')
ALLOWED_EXTENSIONS = {'stl', 'step', 'obj', '3mf', 'pdf', 'png', 'jpg', 'jpeg', 'zip'}
ALLOWED_CANCELLATION_STATUSES = ['UNDER_REVIEW','WAITING_FOR_QUOTE','QUOTED_AWAITING_CUSTOMER']

class ProjectManager:
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

    def _detect_extension_by_content(self, file_storage):
        # Lese den Anfang für ASCII/Blender/GCode
        header = file_storage.read(2048)
        file_storage.seek(0, 2) # Springe ans Ende
        file_size = file_storage.tell() # Hole Dateigröße
        file_storage.seek(0) # Zurück zum Anfang

        # 1. Bekannte Header
        if header.startswith(b'BLENDER'): return 'blend'
        if header.lower().startswith(b'solid'): return 'stl' # ASCII STL
        # G-Code Erkennung (Header wurde bereits gelesen)
        # 1. Check auf Kommentare (viele Slicer starten so)
        if header.startswith(b';') or header.startswith(b'('):
            return 'gcode'

        # 2. Check auf typische G-Befehle (G0-G4, G20, G21, G28, G90, G91, G92)
        # Wir suchen in den ersten 500 Bytes nach dem Muster "G" gefolgt von Zahlen
        if re.search(b'(?m)^(G|M)[0-9]{1,3}', header[:500]):
            return 'gcode'

        # 2. Binäre STL Validierung
        # Eine binäre STL ist (80 Bytes Header) + (4 Bytes Count) + (Count * 50 Bytes)
        if file_size >= 84:
            # Die 4 Bytes nach dem 80-Byte Header enthalten die Anzahl der Dreiecke (uint32)
            tri_count_data = header[80:84]
            if len(tri_count_data) == 4:
                tri_count = struct.unpack('<I', tri_count_data)[0]
                expected_size = 80 + 4 + (tri_count * 50)
                if file_size == expected_size:
                    return 'stl'

        return None
    
    def _process_file_validation(self, file_storage):
        filename = file_storage.filename
        detected_ext = self._detect_extension_by_content(file_storage)

        # 1. Fall: Keine Endung -> Reparatur-Versuch
        if '.' not in filename:
            return f"{filename}.{detected_ext}" if detected_ext else None

        current_ext = filename.rsplit('.', 1)[1].lower()
        is_valid_whitelisted = current_ext in ALLOWED_EXTENSIONS

        # 2. Fall: Inhalt wurde erkannt (Blender, Gcode, STL-ASCII)
        if detected_ext:
            if current_ext == detected_ext:
                return filename
            # Wenn Endung Müll ist (.9mm), hängen wir die richtige an
            if current_ext not in ALLOWED_EXTENSIONS:
                return f"{filename}.{detected_ext}"
            # Wenn Endung valide ist (.stl) aber Inhalt Blender -> REJECT
            return None

        # 3. Fall: Inhalt NICHT eindeutig erkannt (MIME-Spoofing Verdacht oder STEP)
        if is_valid_whitelisted:
            # HARTE REGEL: Wenn es behauptet, STL/GCODE/BLEND zu sein, 
            # aber der Header-Check oben (detected_ext) fehlgeschlagen ist: REJECT
            STRICT_CHECK_EXTENSIONS = {'stl', 'gcode', 'blend'}

            if current_ext in STRICT_CHECK_EXTENSIONS:
                return None

            # Für STEP/STP vertrauen wir weiterhin der Endung (da schwer zu erkennen)
            return filename

        return None
    
    def _allowed_file(self, file_storage):
        filename = file_storage.filename
        
        # 1. Klassische Prüfung über die Dateiendung
        if '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
            return True
    
        # 2. Inhaltsprüfung (MIME/Magic Bytes), falls Endung fehlt oder falsch ist
        # Wir lesen die ersten Bytes direkt aus dem file_storage Stream
        header = file_storage.read(32)
        file_storage.seek(0) # Stream sofort zurücksetzen!
    
        # Check auf Blender (Datei beginnt mit 'BLENDER')
        if header.startswith(b'BLENDER'):
            # Optional: Hier könnte man dem file_storage ein Suffix verpassen, 
            # falls dein nachfolgender Code auf die Endung angewiesen ist
            if '.' not in filename:
                file_storage.filename += '.blend'
            return True
    
        # Check auf Gcode (Beginnt meist mit G0, G1 oder Semikolon für Kommentare)
        if header.startswith(b'G') or header.startswith(b'M') or header.startswith(b';'):
            if '.' not in filename:
                file_storage.filename += '.gcode'
            return True
            
        # Check auf STL (Binary fängt oft mit 80 Bytes Header an, schwer zu greifen, 
        # ASCII fängt mit 'solid' an)
        if header.startswith(b'solid'):
            if '.' not in filename:
                file_storage.filename += '.stl'
            return True
    
        return False

    def _get_config_value(self, key):
        # UNVERÄNDERT: Konfigurationsabfrage
        query = "SELECT Value FROM Configurations WHERE Key = ?"
        try:
            result = self._execute_query(query, (key,), fetch=True)
            return result[0][0] if result and result[0] else None
        except Exception:
            return None

    def _check_project_limits(self, user_id):
        # UNVERÄNDERT: Limit-Check
        max_total_projects = self._get_config_value('MaxProjects')
        max_under_review = self._get_config_value('UnderReview')

        if max_total_projects is None or max_under_review is None:
            return False, "Fehler in der Systemkonfiguration: Projekt-Limits nicht definiert."

        # 1. Gesamtprojekt-Limit prüfen
        query_total = "SELECT COUNT(ProjectID) FROM Projects WHERE UserID = ?"
        result_total = self._execute_query(query_total, (user_id,), fetch=True)
        total_count = result_total[0][0] if result_total and result_total[0] else 0

        if total_count >= int(max_total_projects):
            return False, f"Sie haben das Gesamtlimit von {max_total_projects} Projekten in allen Status erreicht."

        # 2. Aktives Review-Limit prüfen
        query_review = "SELECT COUNT(ProjectID) FROM Projects WHERE UserID = ? AND Status = 'UNDER_REVIEW'"
        result_review = self._execute_query(query_review, (user_id,), fetch=True)
        review_count = result_review[0][0] if result_review and result_review[0] else 0

        if review_count >= int(max_under_review):
            return False, f"Sie haben bereits {max_under_review} Projekte in der aktiven Überprüfung. Bitte warten Sie auf eine Rückmeldung."

        return True, "Limits OK."


    def set_config_value(self, key, value):
        """
        Persistiert einen Konfigurationswert. 
        Löst Insert und Update über ein einziges SQL-Statement (SQLite-spezifisch).
        """
        query = "INSERT OR REPLACE INTO Configurations (Key, Value) VALUES (?, ?)"
        try:
            self._execute_query(query, (key, value))
            return True
        except Exception as e:
            print (f"Fehler beim Setzen von {key}: {e}")
            return False
    # **********************************************
    # NEUE INTERNE HILFSFUNKTION FÜR DATEI-SPEICHERUNG
    # **********************************************
    def _save_files_and_metadata(self, user_id, uploaded_files, temp_upload_folder):
        all_file_ids = []
        os.makedirs(temp_upload_folder, exist_ok=True)

        for uploaded_file in uploaded_files:
            # 1. Validierung & Reparatur über deine Helper-Funktion
            # Diese Funktion muss intern den Content prüfen und den Namen fixen
            fixed_name = self._process_file_validation(uploaded_file)

            if not fixed_name:
                # Wenn None zurückkommt, war es weder eine erlaubte Endung 
                # noch ein erkennbarer Inhalt.
                raise ValueError(f"Ungültiges Dateiformat für '{uploaded_file.filename}'.")

            # 2. Den Namen absichern (für das Dateisystem)
            safe_name = secure_filename(fixed_name)

            # 3. Einzigartige IDs für Datei und Pfad erstellen
            file_id = f"FILE_{str(uuid.uuid4())}"

            # Sicherer Split: Da fixed_name validiert wurde, ist ein Punkt vorhanden
            file_extension = safe_name.rsplit('.', 1)[1].lower()
            new_filename = f"{file_id}.{file_extension}"
            file_path = os.path.join(temp_upload_folder, new_filename)

            # 4. Datei speichern
            # WICHTIG: Deine Helper-Funktion MUSS am Ende ein .seek(0) gemacht haben!
            uploaded_file.save(file_path)

            # 5. Metadaten ermitteln
            filesize_kb = int(round(os.path.getsize(file_path) / 1024))

            # 6. Datenbank-Eintrag
            file_insert_query = "INSERT INTO Files (FileID, FilePath, FileName, FileSizeKB, UserID) VALUES (?, ?, ?, ?, ?)"
            # Wir speichern 'safe_name', damit der ursprüngliche Name (mit Endung) erhalten bleibt
            self._execute_query(file_insert_query, (file_id, new_filename, safe_name, filesize_kb, user_id))

            all_file_ids.append(file_id)

        if not all_file_ids:
            return [], "Keine gültigen Dateien zum Speichern gefunden.", False

        return all_file_ids, f"{len(all_file_ids)} Datei(en) erfolgreich gespeichert.", True


    # **********************************************
    # 1. Projekterstellung (Aktualisiert)
    # **********************************************
    def process_project_submission(self, user_id, form_data, uploaded_files, temp_upload_folder, admin):
        """
        Verarbeitet die Formular-Daten und Dateien beim Start eines Projekts.
        NEU: Akzeptiert den temp_upload_folder als Argument.
        NEU: Admin-Formular liefert zusätzlich Engineering-/Kalkulationsdaten
        (VolumeCM3, EstimatedMaterialG, PrintTimeMin, ProfileID, MaterialID, FinalQuotePrice).
        """
        project_name = form_data.get('project_name')
        description = form_data.get('description')
        quantity = form_data.get('requestet_quantity')

        # NEU: optionale Engineering-/Kalkulationsfelder (nur im Admin-Formular vorhanden)
        volume = form_data.get('volume') or None
        weight = form_data.get('weight') or None
        print_time = form_data.get('print_time') or None
        profile_id = form_data.get('profile_id') or None
        material_id = form_data.get('material_id') or None
        final_quote_price = form_data.get('final_quote_price') or None

        # ----------------------------------------
        # 1. Validierung & Limits
        # ----------------------------------------
        if not project_name or not description:
            return False, "Bitte füllen Sie den Projektnamen und die Beschreibung aus.", None

        if not uploaded_files or (uploaded_files and uploaded_files[0].filename == ''):
            return False, "Bitte wählen Sie mindestens eine Datei aus.", None

        can_submit, limit_message = self._check_project_limits(user_id)
        if not can_submit:
            return False, limit_message, "LIMIT_REACHED"

        all_file_ids = []

        try:
            # ----------------------------------------
            # 2. Dateien speichern und Metadaten erstellen (Refaktorierte Logik)
            # ----------------------------------------
            all_file_ids, file_save_message, success = self._save_files_and_metadata(
                user_id=user_id,
                uploaded_files=uploaded_files,
                temp_upload_folder=temp_upload_folder
            )

            if not success:
                return False, file_save_message, None

            # ----------------------------------------
            # 3. OrderType bestimmen
            # ----------------------------------------
            check_metal = 'check_metal' in form_data
            check_zukaufteile = 'check_zukaufteile' in form_data

            order_type = 'PURE_FDM'
            if check_metal or check_zukaufteile:
                order_type = 'COMPLEX_ASSEMBLY'

            # ----------------------------------------
            # 4. Projects-Tabelle füllen
            # ----------------------------------------
            project_id = f"PROJ_{str(uuid.uuid4())}"
            status = 'SYSTEM_REVIEW' if admin else 'UNDER_REVIEW'
            date_submitted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # NEU: QuoteDate nur setzen, wenn auch tatsächlich ein Endpreis hinterlegt wurde
            quote_date = date_submitted if final_quote_price else None

            file_ids_string = ",".join(all_file_ids)

            project_insert_query = """
                INSERT INTO Projects (
                    ProjectID, FileIDs, UserID, MaterialType, ProjectDescription,
                    ProjectName, ProjectQuantity, Status, DateAdded,
                    VolumeCM3, EstimatedMaterialG, PrintTimeMin,
                    ProfileID, MaterialID, FinalQuotePrice, QuoteDate
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            print(f"Speichere Projekt {project_id} mit Dateien {file_ids_string} für Benutzer {user_id}")
            self._execute_query(project_insert_query, (
                project_id, file_ids_string, user_id, order_type, description,
                project_name, quantity, status, date_submitted,
                volume, weight, print_time,
                profile_id, material_id, final_quote_price, quote_date
            ))

            return True, f"Projekt erfolgreich mit {len(all_file_ids)} Datei(en) eingereicht.", project_id

        except ValueError:
             # Fängt ungültiges Dateiformat aus _save_files_and_metadata
            return False, f"Fehler beim Speichern der Datei.", "INVALID_FORMAT"
        except sqlite3.Error:
            # Rollback-Logik für Dateilöschung fehlt hier, ist aber idealerweise nötig.
            return False, f"Fehler bei der Datenbankoperation.", None
        except Exception:
            return False, f"Ein unerwarteter Fehler ist aufgetreten.", None

    # **********************************************
    # 2. Chat-Upload (NEU)
    # **********************************************
    def handle_chat_upload(self, user_id, project_id, uploaded_files, temp_upload_folder):
        # TODO: alle  INSERTs in eine Transaktion packen (multi_queries=True), aktuell noch  separate _execute_query → Race-Condition möglich
        """
        Verarbeitet den Upload von Dateien in einem bestehenden Projekt-Chat.
        Speichert die Dateien und erstellt eine entsprechende Chat-Nachricht.
        """

        if not uploaded_files or uploaded_files[0].filename == '':
            return False, "Keine Datei zum Hochladen gefunden."

        # 1. Dateien speichern und Metadaten erstellen
        try:
            all_file_ids, file_save_message, success = self._save_files_and_metadata(
                user_id=user_id,
                uploaded_files=uploaded_files,
                temp_upload_folder=temp_upload_folder
            )
        except ValueError:
            return False, f"Fehler beim Speichern der Datei."
        except Exception:
            return False, f"Ein Fehler ist beim Speichern der Dateien aufgetreten."


        if not success:
            return False, "Keine gültigen Dateien zum Hochladen gefunden."

        # 2. Chat-Nachricht erstellen
        # Der Nachrichteninhalt soll die Namen der hochgeladenen Dateien auflisten

        # Dateinamen aus der Files-Tabelle anhand der all_file_ids abrufen (optional, oder nur FileIDs verwenden)
        # Für Einfachheit verwenden wir hier nur die IDs im Nachrichten-Text:
        uploaded_count = len(all_file_ids)

        chat_insert_query = """
            INSERT INTO ProjectMessages (CommID, ProjectID, SenderType, MessageText, Timestamp, IsUnreadAdmin, RequiresFileUpload, RequiredFilesProvided)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        comm_id=f"COMM_{str(uuid.uuid4())}"
        sender_type='User'
        date_sent = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Der Benutzer (Kunde) ist nicht intern, daher IsInternal=0
        try:
            self._execute_query(chat_insert_query, (comm_id, project_id, sender_type, file_save_message, date_sent, 1, 0, 1))
        except sqlite3.Error:
            return False, f"Datenbankfehler beim Speichern der Chat-Nachricht"

        return True, f"{uploaded_count} Datei(en) erfolgreich hochgeladen und als Chat-Nachricht gespeichert."

    def delete_project(self, project_id):
        
     
        try:
            operations = []

            select_query = """
                SELECT 
                    p.Status,
                    p.FileIDs,
                    COALESCE(GROUP_CONCAT(f.FilePath), '') AS FilePaths
                FROM Projects p
                LEFT JOIN Files f ON ',' || p.FileIDs || ',' LIKE '%,' || f.FileID || ',%'
                WHERE p.ProjectID = ?
                GROUP BY p.ProjectID
            """
            operations.append((select_query, (project_id,)))

            operations.append(
                ("DELETE FROM Projects WHERE ProjectID = ?", (project_id,))
            )

            delete_files_query = """
                DELETE FROM Files 
                WHERE FileID IN (
                    SELECT TRIM(value) 
                    FROM (
                        WITH RECURSIVE split(value, str) AS (
                            SELECT '', ? || ','
                            UNION ALL
                            SELECT TRIM(SUBSTR(str, 1, INSTR(str, ',') - 1)), 
                                   SUBSTR(str, INSTR(str, ',') + 1)
                            FROM split
                            WHERE str != ''
                        )
                        SELECT value FROM split WHERE value != ''
                    )
                )
            """
            operations.append((delete_files_query, (project_id,)))  # FileIDs-String wird als Parameter übergeben

            # EINZIGER Aufruf – alles in einer Transaktion
            result = self._execute_query(operations, multi_queries=True, fetch=True, fetch_one=True)

            if not result:
                return True, "Projekt existiert nicht oder wurde bereits gelöscht."

            current_status = result['Status']
            file_paths_string = result['FilePaths'] or ''

            if current_status not in ALLOWED_CANCELLATION_STATUSES:
                return False, f"Löschen nicht möglich. Status war '{current_status}'."

            file_paths_list = [p.strip() for p in file_paths_string.split(',') if p.strip()]

            # Physische Löschung
            successful_deletes = 0
            for rel_path in file_paths_list:
                full_path = os.path.join(TEMP_UPLOAD_FOLDER, rel_path)
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        successful_deletes += 1
                    except Exception:
                        pass

            msg = "Projekt und DB-Einträge gelöscht."
            if file_paths_list and successful_deletes < len(file_paths_list):
                msg += f" (Nur {successful_deletes}/{len(file_paths_list)} Dateien physisch entfernt.)"

            return True, msg

        except sqlite3.Error as e:
            return False, f"Datenbankfehler beim Löschen: {e}"
        except Exception as e:
            return False, f"Unerwarteter Fehler: {e}"

    def send_review_message(self, project_id: str, message_text: str, skip_review_1: bool, request_file_upload: bool) -> tuple[bool, str]:
        """
        Speichert die Review-Nachricht und steuert ggf. den Status.
        Alles in einer Transaktion, wenn Status-Update nötig.
        """
        comm_id = f"COMM_{uuid.uuid4()}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sender_type = 'Admin'
        is_unread_admin = 0
        requires_file_upload = 1 if request_file_upload else 0

        operations = []

        # 1. Status-Update nur wenn skip_review_1=True
        if skip_review_1:
            new_status = 'WAITING_FOR_QUOTE'
            operations.append(
                ("UPDATE Projects SET Status = ? WHERE ProjectID = ?", (new_status, project_id))
            )
            log_message = "Review 1 übersprungen. Status auf 'WAITING_FOR_QUOTE' gesetzt."
        else:
            log_message = "Review-Nachricht gespeichert."

        # 2. Nachricht immer einfügen
        operations.append(
            (
                """
                INSERT INTO ProjectMessages 
                (CommID, ProjectID, SenderType, MessageText, Timestamp, IsUnreadAdmin, RequiresFileUpload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (comm_id, project_id, sender_type, message_text, timestamp, is_unread_admin, requires_file_upload)
            )
        )

        try:
            self._execute_query(operations, multi_queries=True)
            return True, log_message
        except sqlite3.Error as e:
            return False, f"Datenbankfehler: {e}"


    def add_project_message(self, project_id, message_text, sender_type='User'):
        """
        Speichert eine neue Nachricht (vereinfacht, einzelne Operation).
        """
        comm_id = f"COMM_{uuid.uuid4()}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        query = """
            INSERT INTO ProjectMessages 
            (CommID, ProjectID, SenderType, MessageText, Timestamp, IsUnreadAdmin)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (comm_id, project_id, sender_type, message_text, timestamp, 1)

        try:
            self._execute_query(query, params)
            return True
        except sqlite3.Error as e:
            return False


    def create_product_from_project(self, project_data: dict, form_data: dict, volume_cm3: float, print_time_min: int, weight_g: float, final_quote_price: float, is_shop_ready: int) -> str:
        """
        Erstellt Produkt + Preis + optionaler Projekt-Status-Update in einer Transaktion.
        """
        product_id = f"PROD_{uuid.uuid4()}"
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        product_description = form_data.get('description', f"Produkt aus Projekt {project_data['ProjectID']}")

        operations = []

        # 1. Optional: Projekt-Update (Volume, Time, Weight, Status)
        operations.append(
            (
                """
                UPDATE Projects 
                SET VolumeCM3 = ?, PrintTimeMin = ?, EstimatedMaterialG = ?, 
                    FinalQuotePrice = ?, Status = 'QUOTED_AWAITING_CUSTOMER'
                WHERE ProjectID = ?
                """,
                (volume_cm3, print_time_min, weight_g, final_quote_price, project_data['ProjectID'])
            )
        )

        # 2. Neues Produkt einfügen
        operations.append(
            (
                """
                INSERT INTO Products (
                    ProductID, UserID, ProductCategory, MaterialType, ProductName,
                    ProductDescription, WeightG, PrintTimeMin, CreatedAt, StockQuantity,
                    IsActive, ImagePath, IsShopReady, Color, SourceProjectID
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    project_data['UserID'],
                    form_data['category_name'],
                    project_data['MaterialType'],
                    form_data['product_name'],
                    product_description,
                    weight_g,
                    print_time_min,
                    current_time,
                    project_data['ProjectQuantity'],
                    1,
                    form_data.get('image_url'),
                    is_shop_ready,
                    'Default',
                    project_data['ProjectID']
                )
            )
        )

        # 3. Preis-Historie einfügen
        price_id = f"PRIC_{uuid.uuid4()}"
        operations.append(
            (
                "INSERT INTO ProductPrices (PriceID, ProductID, ProductPrice, DateAdded) VALUES (?, ?, ?, ?)",
                (price_id, product_id, final_quote_price, current_time)
            )
        )

        try:
            self._execute_query(operations, multi_queries=True)
            return product_id
        except sqlite3.Error as e:
            raise Exception(f"Fehler beim Erstellen des Produkts: {e}")

    def get_files_by_id(self, project_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Hol zuerst den String mit den kommagetrennten IDs aus der Projects-Tabelle
        cursor.execute("SELECT FileIDs FROM Projects WHERE ProjectID = ?", (project_id,))
        project_row = cursor.fetchone()

        # Falls kein Projekt gefunden wurde oder das Feld leer ist
        if not project_row or not project_row['FileIDs']:
            cursor.close()
            conn.close()
            return jsonify([]), 200

        # 2. Den String splitten und eine saubere Python-Liste aus IDs bauen
        # Ergebnis: ['FILE_63997d06...', 'FILE_96bcbc1c...', ...]
        file_ids = [fid.strip() for fid in project_row['FileIDs'].split(',') if fid.strip()]

        if not file_ids:
            cursor.close()
            conn.close()
            return jsonify([]), 200

        # 3. Dynamische Platzhalter (?, ?, ?) für das "IN"-Statement generieren
        placeholders = ",".join("?" for _ in file_ids)

        # 4. Alle Dateien abfragen, deren ID in unserer Liste vorkommt
        query = f"""
        SELECT FileID, FileName, FileSizeKB, FilePath
        FROM Files
        WHERE FileID IN ({placeholders})
        """

        cursor.execute(query, file_ids)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # Umwandeln in eine Liste von Standard-Python-Dicts
        file_list = [dict(row) for row in rows]

        return jsonify(file_list), 200

    def get_file_by_id(self, file_id: str):
        """
        Holt die Metadaten einer Datei anhand ihrer FileID aus der Datenbank.
        Gibt ein Dictionary mit den Spaltennamen als Keys zurück oder None.
        """
        # Hinweis: Falls dein ProjectManager eine andere Verbindungsart nutzt (z. B. self.db),
        # passe das Handling für den Cursor und die Connection entsprechend an.
        import sqlite3

        query = "SELECT FileID, UserID, FilePath, FileName, FileSizeKB FROM Files WHERE FileID = ?"

        try:
            # Hier nutzen wir den Pfad zu deiner zentralen Commerce.db
            # Wenn dein Manager bereits eine Methode für Connections hat, nutze die.
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Erlaubt Zugriff via Spaltenname als Key
            cursor = conn.cursor()

            cursor.execute(query, (file_id,))
            row = cursor.fetchone()

            cursor.close()
            conn.close()

            if row:
                return dict(row)
            return None

        except sqlite3.Error as e:
            print(f"Datenbankfehler in get_file_by_id: {e}")
            return None

    def is_project_owner(self, user_id, project_id):
        query = "SELECT COUNT(1) FROM Projects WHERE ProjectID = ? AND UserID = ?"
        result = self._execute_query(query, (project_id, user_id), fetch=True)
        count = result[0][0] if result and result[0] else 0
        return count > 0


    def get_project_list(self):
        query = "SELECT * FROM Projects"
        # 1. Daten abrufen (Liste von Tupeln)
        result_rows = self._execute_query(query, fetch=True)

        # Frühes Beenden, wenn keine Daten gefunden wurden
        if not result_rows:
            return []

        projects = []
        conn = None # Wird für die Spaltenabfrage benötigt

        try:
            # 2. Spaltennamen dynamisch abrufen
            conn = sqlite3.connect(self.db_path)
            # Verwenden von PRAGMA table_info, um die Spaltennamen zu erhalten
            cursor = conn.execute("PRAGMA table_info(Projects)")
            # Der Spaltenname ist das 2. Element (Index 1) im Tupel
            columns = [col[1] for col in cursor.fetchall()]

            # 3. Daten zu Dictionaries zusammenfügen
            for row_tupel in result_rows:
                # dict(zip(Schlüssel, Werte)) erstellt das korrekte Dictionary
                project_dict = dict(zip(columns, row_tupel))
                projects.append(project_dict)

            return projects

        except sqlite3.Error as e:
            # Fehlerbehandlung, falls PRAGMA fehlschlägt
            print(f"Fehler beim Abrufen der Spaltennamen: {e}")
            return []

        finally:
            if conn:
                conn.close()

    def get_project_details(self, project_id):
        # Explizites SELECT der Spalten, um die Reihenfolge zu garantieren
        query = "SELECT ProjectID, FileIDs, UserID, MaterialType, ProjectDescription, ProjectName, ProjectQuantity, Status, VolumeCM3, PrintTimeMin, EstimatedMaterialG, DateAdded, Priority, FinalQuotePrice FROM Projects WHERE ProjectID = ?"

        result = self._execute_query(query, (project_id,), fetch=True)

        if result and result[0]:
            # Die Spaltennamen müssen EXAKT mit der SELECT-Anweisung übereinstimmen
            # Wir definieren die Spalten EXPLIZIT, damit das Mapping sicher ist
            columns = [
                "ProjectID", "FileIDs", "UserID", "MaterialType", "ProjectDescription",
                "ProjectName", "ProjectQuantity","Status", "VolumeCM3", "PrintTimeMin",
                "EstimatedMaterialG", "DateAdded", "Priority", "FinalQuotePrice"
            ]
            project_details = dict(zip(columns, result[0]))
            return project_details

        return None
    
    def get_project_autofill_values(self, project_id):
        """Schlankes SELECT für BOM-Autofill: nur Material, Profil, Gewicht, Druckzeit."""
        # Explizites SELECT der Spalten, um die Reihenfolge zu garantieren
        query = "SELECT MaterialID, ProfileID, EstimatedMaterialG, PrintTimeMin FROM Projects WHERE ProjectID = ?"

        result = self._execute_query(query, (project_id,), fetch=True)

        if result and result[0]:
            # Spaltennamen müssen EXAKT mit der SELECT-Anweisung übereinstimmen
            columns = ["MaterialID", "ProfileID", "EstimatedMaterialG", "PrintTimeMin"]
            return dict(zip(columns, result[0]))

        return None
    
    def get_project_messages(self, project_id):
        """
        Ruft alle Nachrichten eines Projekts ab und mappt sie auf Dictionaries.
        Nutzt nur eine Verbindung für PRAGMA und SELECT.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
    
            # 1. Spaltennamen holen (PRAGMA table_info)
            cursor.execute("PRAGMA table_info(ProjectMessages)")
            columns = [col[1] for col in cursor.fetchall()]  # Name ist Index 1
    
            # 2. Daten abrufen (gleiche Connection!)
            query = "SELECT * FROM ProjectMessages WHERE ProjectID = ? ORDER BY Timestamp ASC"
            cursor.execute(query, (project_id,))
            result_rows = cursor.fetchall()
    
            if not result_rows:
                return []
    
            # 3. Mapping
            messages = [dict(zip(columns, row)) for row in result_rows]
    
            return messages
    
        except sqlite3.Error as e:
            print(f"Fehler beim Abrufen der Nachrichten: {e}")
            return []
    
        finally:
            if conn:
                conn.close()

    def update_project_status(self, project_id: str, new_status: str, volume_cm3: float, 
                              print_time: float, weight: float, 
                              final_quote_price: float = None):
        """
        Aktualisiert den Projektstatus. Wirft bei Fehlern eine Exception,
        um den Prozess im Controller kontrolliert abzubrechen.
        """
        query = '''UPDATE Projects SET Status = ?, 
                    VolumeCM3 = ?, 
                    PrintTimeMin = ?, 
                    EstimatedMaterialG = ?'''
        params = [new_status, volume_cm3, print_time, weight]

        if final_quote_price is not None:
            quote_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            query += ", FinalQuotePrice = ?, QuoteDate = ?"
            params.extend([final_quote_price, quote_date])     #QuoteDate auf DATETIME-Format umstellen ASAP! 

        query += " WHERE ProjectID = ?"
        params.append(project_id)

        try:
            # Zentrale Ausführung. Wir verlassen uns darauf, dass _execute_query 
            # bei Fehlern sqlite3.Error wirft.
            self._execute_query(query, tuple(params))

        except sqlite3.Error as e:
            # Protokollierung und Weitergabe an den Controller
            print(f"Datenbankfehler bei Statusaktualisierung: {e}")
            raise Exception(f"Status-Update fehlgeschlagen (Datenbank): {e}")

        except Exception as e:
            print(f"Unerwarteter Fehler bei Statusaktualisierung: {e}")
            raise Exception(f"Status-Update fehlgeschlagen (System): {e}")

    def get_projects_by_user(self, user_id):
        # Die Query gibt die Reihenfolge vor
        query = "SELECT ProjectID, ProjectName, Status, DateAdded, ProjectDescription FROM Projects WHERE UserID = ? ORDER BY DateAdded DESC"
        results = self._execute_query(query, (user_id,), fetch=True)

        # Wenn dein Database-Cursor bereits Dictionary-ähnliche Objekte liefert (z.B. sqlite3.Row):
        # return list(results) if results else []

        # Falls es reine Tupel sind, reicht ein minimales Mapping:
        columns = ["ProjectID", "ProjectName", "Status", "DateAdded", "ProjectDescription"]
        return [dict(zip(columns, row)) for row in results] if results else []

    def get_all_projects_for_admin(self) -> list[sqlite3.Row]:
            """
            Ruft alle Projekte mit Kundennamen ab und zählt ungelesene Nachrichten,
            basierend auf dem aktuellen Schema. Verwendet self._execute_query.
            """
            query = """
                SELECT
                    p.ProjectID,
                    p.ProjectName,
                    p.Status,
                    p.Priority,
                    p.DateAdded,
                    p.MaterialType,
                    u.Username AS CustomerName,
                    (
                        SELECT COUNT(CommID)
                        FROM ProjectMessages pm
                        WHERE pm.ProjectID = p.ProjectID
                        AND pm.IsUnreadAdmin = 1
                        AND pm.SenderType = 'User'
                    ) AS UnreadCustomerMessages,
                    (
                        SELECT COUNT(CommID)
                        FROM ProjectMessages pm_admin
                        WHERE pm_admin.ProjectID = p.ProjectID
                        AND pm_admin.SenderType = 'Admin'
                    ) AS AdminMessagesSent
                FROM
                    Projects p
                JOIN
                    Users u ON p.UserID = u.UserID
                ORDER BY
                    p.Priority DESC,
                    p.DateAdded ASC
            """

            # Führt die Abfrage über die zentrale Methode aus.
            # fetch=True stellt sicher, dass alle Zeilen zurückgegeben werden.
            # Die Fehlerbehandlung und das Schließen der Verbindung erfolgen in _execute_query.
            try:
                projects = self._execute_query(query, fetch=True)
                print(projects)
                return projects
                
            except sqlite3.Error as e:
                # Fehler werden von _execute_query (durch re-raising) hierhin weitergegeben.
                print(f"Datenbankfehler beim Abrufen aller Projekte für Admin: {e}")
                return []

    def get_all_system_projects(self) -> list[sqlite3.Row]:
        """fragt alle Projects ab und joint auf Users um den isadmin flag abzufragen. wenn isadmin=1 es ist ein sytemprojekt"""
        query = """
                SELECT
                    p.ProjectID,
                    p.ProjectName,
                    p.Status,
                    p.Priority,
                    p.DateAdded,
                    p.VolumeCM3,
                    p.PrintTimeMin,
                    p.EstimatedMaterialG,
                    p.ProfileID,
                    p.MaterialID,
                    p.MaterialType,
                    u.Username AS AdminName
                FROM
                    Projects p
                JOIN
                    Users u ON p.UserID = u.UserID
                WHERE
                    u.IsAdmin = 1
                ORDER BY
                    p.Priority DESC,
                    p.DateAdded ASC
            """
        try:
            projects = self._execute_query(query, fetch=True)
            print(projects)
            return projects
            
        except sqlite3.Error as e:
            # Fehler werden von _execute_query (durch re-raising) hierhin weitergegeben.
            print(f"Datenbankfehler beim Abrufen aller Projekte für Admin: {e}")
            return []

    def convert_project_to_product(self, project_id):
        """
        Liest einen Projekt-Datensatz und kopiert die Werte stumpf 1:1
        in einen neuen Products-Datensatz. Keine NULL-Validierung hier
        (wird vorgelagert im Frontend über den grauen Button abgefangen).
        Ermittelt zusätzlich über den CalculationManager einen Preis und
        legt dafür einen Datensatz in ProductPrices an.
        """
        # 1. Quell-Projekt vollständig laden (inkl. UserID, die übernommen wird)
        query_select = """
            SELECT ProjectID, UserID, MaterialType, ProjectName, ProjectDescription,
                   VolumeCM3, EstimatedMaterialG, PrintTimeMin, ProfileID, MaterialID, ProjectQuantity
            FROM Projects
            WHERE ProjectID = ?
        """
        result = self._execute_query(query_select, (project_id,), fetch=True)

        if not result or not result[0]:
            return False, "Projekt nicht gefunden."

        row = result[0]
        columns = ["ProjectID", "UserID", "MaterialType", "ProjectName", "ProjectDescription",
                   "VolumeCM3", "EstimatedMaterialG", "PrintTimeMin", "ProfileID", "MaterialID", "ProjectQuantity"]
        project = dict(zip(columns, row))

        # 2. MaterialName auflösen (calculate_pricing braucht den Namen, nicht die ID)
        material_query = "SELECT MaterialName FROM Materials WHERE MaterialID = ?"
        material_result = self._execute_query(material_query, (project["MaterialID"],), fetch=True)

        if not material_result or not material_result[0]:
            return False, "Material nicht gefunden."

        material_name = material_result[0]["MaterialName"]

        # 3. Neue ProductID generieren
        product_id = f"PROD_{uuid.uuid4()}"

        # 4. Insert in Products (stumpfe 1:1-Übernahme der Projekt-Werte)
        query_insert = """
            INSERT INTO Products (
                ProductID,
                UserID,
                ProductCategory,
                MaterialType,
                ProductName,
                ProductDescription,
                WeightG,
                PrintTimeMin,
                CreatedAt,
                StockQuantity,
                IsActive,
                ImagePath,
                IsShopReady,
                IsShopVisible,
                Color,
                SourceProjectID
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            product_id,
            project["UserID"],
            "Default",                                      # ProductCategory: fester Default
            project["MaterialType"],
            project["ProjectName"],
            project["ProjectDescription"],
            project["EstimatedMaterialG"],
            project["PrintTimeMin"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            1,              # StockQuantity: fester Default
            1,              # IsActive
            f"product_images/{project['ProjectName']}.png",           # ImagePath: zusammengesetzt aus ProjectName
            1,              # IsShopReady
            0,              # IsShopVisible
            "Default",      # Color: fester Default
            project["ProjectID"]   # SourceProjectID
        )

        self._execute_query(query_insert, params)

        # 5. Preis über den CalculationManager ermitteln
        
        total_base_cost, markup_factor = calculation_manager.calculate_pricing(
            project_id=project["ProjectID"],
            volume_cm3=project["VolumeCM3"],
            print_time_min=project["PrintTimeMin"],
            material_g=project["EstimatedMaterialG"],
            profile_id=project["ProfileID"],
            material_name=material_name,
            initial_quantity=project["ProjectQuantity"],
            manual_surcharge=0.0
        )

        final_price = round(total_base_cost * markup_factor, 2)

        # 6. Insert in ProductPrices
        price_id = f"PRIC_{uuid.uuid4()}"
        price_insert_query = """
            INSERT INTO ProductPrices (PriceID, ProductID, ProductPrice, DateAdded)
            VALUES (?, ?, ?, ?)
        """
        self._execute_query(price_insert_query, (
            price_id,
            product_id,
            final_price,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        return True, product_id

    def get_all_unique_statuses(self) -> list[str]:      #für das Status-Filter-Dropdown in admin_views.py
        """Ruft eine Liste aller eindeutigen Status aus der Projects-Tabelle ab."""
        query = "SELECT DISTINCT Status FROM Projects ORDER BY Status"
        # Verwenden Sie _execute_query, das Tupel zurückgibt
        results = self._execute_query(query, fetch=True)

        # Ergebnisse von Tupeln (('STATUS',), ('STATUS2',)) in eine flache Liste umwandeln
        return [row[0] for row in results] if results else []

    def send_simple_admin_message(self, project_id: str, message_content: str):
        """
        Fügt eine reine Protokoll-Nachricht des Admins hinzu.
        Wirft eine Exception bei Datenbankfehlern, um die Kette im Controller zu stoppen.
        """
        comm_id = f"COMM_{str(uuid.uuid4())}"
        sender_type = 'Admin'
        date_sent = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
            INSERT INTO ProjectMessages (CommID, ProjectID, SenderType, MessageText, Timestamp, IsUnreadAdmin)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        
        try:
            # Ausführung über die zentrale Methode
            self._execute_query(query, (comm_id, project_id, sender_type, message_content, date_sent, 0))
        
        except sqlite3.Error as e:
            # Protokollierung des Fehlers
            print(f"Fehler beim Speichern der Admin-Nachricht: {e}")
            # Weitergabe an den Controller
            raise Exception(f"Protokollierung fehlgeschlagen: {e}")

    def get_all_categories(self):
        """Ruft alle Kategorienamen für das Formular ab."""
        query = "SELECT CategoryName FROM ProductCategories ORDER BY CategoryName"
        # Gibt eine Liste von Row-Objekten oder Strings zurück, je nach Implementierung
        return [row['CategoryName'] for row in self._execute_query(query, fetch=True)]

    def get_all_print_profiles(self):

        """Ruft alle Druckprofile als Liste von Dictionaries ab."""
        query = "SELECT * FROM PrintProfiles ORDER BY ProfileName"
        result_rows = self._execute_query(query, fetch=True)

        if not result_rows:
            return []

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("PRAGMA table_info(PrintProfiles)")
            columns = [col[1] for col in cursor.fetchall()]

            profiles = [dict(zip(columns, row)) for row in result_rows]
            return profiles

        except sqlite3.Error as e:
            print(f"Fehler beim Abrufen der PrintProfiles-Spaltennamen: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_all_materials(self):
        """Ruft alle Materialien als Liste von Dictionaries ab."""
        query = "SELECT * FROM Materials ORDER BY MaterialName"
        result_rows = self._execute_query(query, fetch=True)

        if not result_rows:
            return []

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("PRAGMA table_info(Materials)")
            columns = [col[1] for col in cursor.fetchall()]

            materials = [dict(zip(columns, row)) for row in result_rows]
            return materials

        except sqlite3.Error as e:
            print(f"Fehler beim Abrufen der Materials-Spaltennamen: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_calculation_context(self):
        try:
            categories = self.get_all_categories()
            print_profiles = self.get_all_print_profiles()
            materials = self.get_all_materials()
            return categories, print_profiles, materials
        except Exception as e:
            return False, e
        
    def get_project_by_id(self, project_id: str):
        # Aktualisierte Methode, um auch die neuen Felder abzurufen
        query = """
            SELECT
                p.*, u.Username AS CustomerName
            FROM Projects p
            JOIN Users u ON p.UserID = u.UserID
            WHERE p.ProjectID = ?
        """
        return self._execute_query(query, (project_id,), fetch=True,fetch_one=True)

    def get_project_status_details(self, project_id):

        query_data= "SELECT UserID, Status, VolumeCM3, PrintTimeMin, EstimatedMaterialG, FinalQuotePrice FROM Projects WHERE ProjectID = ?"
        # 1. Projekt- und Statusprüfung (Simuliert die Logik der Manager)
        project=self._execute_query(query_data, (project_id,), fetch=True)

        return project


    def create_product_from_project(self, project_data: dict, form_data: dict, volume_cm3: float, print_time_min: int, weight_g: float, final_quote_price: float, is_shop_ready: int) -> str:
        """
        Erstellt einen neuen Eintrag in Products und ProductPrices basierend auf den
        Projektdaten und den Admin-Formulardaten.

        Gibt die ProductID bei Erfolg zurück.
        """
        product_id = f"PROD_{str(uuid.uuid4())}"
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Sicherstellen, dass alle Werte vorhanden sind (hier nur Beispiele aus dem Formular/Projekt)
        product_description = form_data.get('description', f"Produkt basierend auf Projekt {project_data['ProjectID']}")

        # Die tatsächlichen Werte MÜSSEN aus dem Formular ausgelesen werden,
        # da sie im Endpoint nicht vollständig vorhanden sind (siehe Punkt 2)
        project_update_query = """
            UPDATE Projects
            SET
                VolumeCM3 = ?,
                PrintTimeMin = ?,
                EstimatedMaterialG = ?,
                FinalQuotePrice = ?,
                status = ?
            WHERE
                ProjectID = ?
        """
        project_update_params = (
            volume_cm3,
            print_time_min,
            weight_g,
            final_quote_price,
            'QUOTED_AWAITING_CUSTOMER',
            project_data['ProjectID']

        )
        # 1. Eintrag in die PRODUCTS Tabelle
        product_query = """
            INSERT INTO Products (
                ProductID, UserID, ProductCategory, MaterialType, ProductName,
                ProductDescription, WeightG, PrintTimeMin, CreatedAt, StockQuantity,
                IsActive, ImagePath, IsShopReady, Color, SourceProjectID
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        product_params = (
            product_id,
            project_data['UserID'],                 # Vom Original-Projekt
            form_data['category_name'],            # Vom Admin-Formular
            project_data['MaterialType'],          # Vom Original-Projekt
            form_data['product_name'],             # Vom Admin-Formular
            product_description,                   # Vom Admin-Formular (oder Standard)
            weight_g,                            # Vom Admin-Formular
            print_time_min,                         # Vom Admin-Formular
            current_time,
            project_data['ProjectQuantity'],        # Standard-Lagerbestand ist 1
            1,                                     # Standardmäßig aktiv, ANPASSEN AN ECHTE STOCK_QUANTITY!
            form_data.get('image_url'),            # Vom Admin-Formular
            is_shop_ready,
            'Default'  ,                            # Standardwert (muss anpassbar sein)
            project_data['ProjectID']              # Verknüpfung zum Original-Projekt
        )

        # 2. Eintrag in die PRODUCTPRICES Tabelle
        price_id = f"PRIC_{str(uuid.uuid4())}"
        price_query = """
            INSERT INTO ProductPrices (PriceID, ProductID, ProductPrice, DateAdded)
            VALUES (?, ?, ?, ?)
        """
        price_params = (
            price_id,
            product_id,
            final_quote_price,
            current_time
        )

        # Ausführung beider Queries in einer Transaktion
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(project_update_query, project_update_params)
            cursor.execute(product_query, product_params)
            cursor.execute(price_query, price_params)
            conn.commit()
            return product_id
        except sqlite3.Error as e:
            conn.rollback()
            raise Exception(f"Fehler beim Erstellen des Produkts: {e}")
        finally:
            conn.close()

    def get_project_material_details(self, project_id):

        query_data="SELECT ProductID, MaterialType, StockQuantity FROM Products WHERE SourceProjectID = ?"

        product = self._execute_query(query_data, (project_id,), fetch=True, fetch_one=True)

        return product



    def finalize_project_details(self, project_id):
        """
        Markiert das Projekt mit dem gegebenen project_id als abgeschlossen
        (Status = 'PROJECT_COMPLETED').
        Gibt (True, message) bei Erfolg, sonst (False, message).
        """
        try:
            updated = self.update_project_status(project_id, 'PROJECT_COMPLETED')
            if updated:
                return True, "Projekt erfolgreich als abgeschlossen markiert."
            else:
                return False, "Projekt nicht gefunden oder konnte nicht aktualisiert werden."
        except Exception as e:
            return False, f"Fehler beim Abschließen des Projekts: {e}"

    def load_project_to_mes(self, project_id: str) -> tuple[bool, str]:
        """
        Lädt ein Projekt in die MES-Umgebung durch Erstellen eines Blueprint-Datensatzes.
        """
        # 1. Projektinformationen abrufen (um Existenz zu prüfen)
        project = self.get_project_details(project_id)
        if not project:
            return False, "Projekt nicht gefunden."

        try:
            # 2. Prüfen, ob bereits ein Blueprint existiert
            # Wir nutzen fetch=True und fetch_one=True für eine saubere Abfrage
            check_query = "SELECT Status FROM Blueprints WHERE ProjectID = ?"
            existing = self._execute_query(check_query, (project_id,), fetch=True, fetch_one=True)

            if existing:
                # Da row_factory = sqlite3.Row aktiv ist, Zugriff über Key oder Index
                return True, f"Projekt bereits im MES vorhanden (Status: {existing['Status']})."

            # 3. Blueprint-Datensatz anlegen
            blueprint_id = f"BLUE_{str(uuid.uuid4())}"
            insert_query = """
                INSERT INTO Blueprints (BlueprintID, ProjectID, Status, CreatedAt, UpdatedAt)
                VALUES (?, ?, 'INITIALIZED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """

            print(f"Initialisiere technischen Blueprint für {project_id}...")
            self._execute_query(insert_query, (blueprint_id, project_id))

            return True, f"Projekt {project_id} erfolgreich in die Fertigungssteuerung geladen."

        except Exception as e:
            # Das Exception-Handling und Rollback passiert bereits in deiner _execute_query
            return False, f"Fehler beim Laden in die Fertigungssteuerung: {str(e)}"
        
    def get_active_blueprints(self):
        """
        Hält alle Projekte bereit, die in die Fertigungssteuerung geladen wurden.
        Koppelt Blueprint-Daten mit Projekt-Stammdaten.
        """
        query = """
            SELECT 
                b.BlueprintID, 
                b.Status as BlueprintStatus, 
                b.CreatedAt as LoadedAt,
                u.UserName as CustomerName,
                p.* 
            FROM Blueprints b
            JOIN Projects p ON b.ProjectID = p.ProjectID
            JOIN Users u ON p.UserID = u.UserID
            ORDER BY b.CreatedAt DESC
        """
        try:
            # fetch=True um alle aktiven Blueprints zu erhalten
            return self._execute_query(query, fetch=True)
        except Exception as e:
            print(f"Fehler beim Abrufen der Blueprints: {e}")
            return []

    def delete_blueprint(self, blueprint_id: str) -> tuple[bool, str]:
        """
        Löscht einen Blueprint-Datensatz aus der Fertigungssteuerung.
        """
        try:
            delete_query = "DELETE FROM Blueprints WHERE BlueprintID = ?"
            self._execute_query(delete_query, (blueprint_id,))
            return True, f"Blueprint {blueprint_id} erfolgreich gelöscht."
        except Exception as e:
            return False, f"Fehler beim Löschen des Blueprints: {str(e)}"
        
    def update_project_technical_data(self, project_id, volume_cm3, weight_g, print_time_min, profile_id, material_id):
        """
        Speichert die finalen technischen Parameter aus dem Manufacturing 
        direkt im Projekt für die kaufmännische Kalkulation.
        """
        query = """
            UPDATE Projects 
            SET VolumeCM3 = ?, 
                EstimatedMaterialG = ?, 
                PrintTimeMin = ?, 
                ProfileID = ?, 
                MaterialID = ?
            WHERE ProjectID = ?
        """
        # Ausführung der Query in deiner DB-Klasse
        self._execute_query(query, (volume_cm3, weight_g, print_time_min, profile_id, material_id, project_id))

    def update_blueprint_status(self, blueprint_id, new_status):
        """Aktualisiert rein den Status in der Blueprints-Tabelle."""
        query = "UPDATE Blueprints SET Status = ? WHERE BlueprintID = ?"
        return self._execute_query(query, (new_status, blueprint_id))

    
    def finalize_blueprint(self, project_id, full_path):
        """Aktualisiert nur den Status des Blueprints und den Pfad zur JSON-Datei."""
        query = """
            UPDATE Blueprints 
            SET BOMPath = ?, 
                Status = 'BOM_FINISHED',
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE ProjectID = ?
        """
        return self._execute_query(query, (full_path, project_id))
    

    def finalize_blueprint(self, project_id, bom_path):
        try:
            # Wir versuchen nur das Nötigste zu updaten
            query = """
                UPDATE Blueprints 
                SET BOMPath = ?, 
                    Status = 'COMPLETED'
                WHERE ProjectID = ?
            """
            self._execute_query(query, (bom_path, project_id))
            return True
        except Exception as e:
            # Das gibt uns jetzt die ECHTE Fehlermeldung der DB aus
            print(f"DATABASE ERROR: {str(e)}") 
            return False
        
    def check_bom_exists(self, project_id):
        bom_filename = f"BOM_{project_id}.json"
        return os.path.exists(os.path.join(TEMP_UPLOAD_FOLDER, bom_filename))

    def process_bom_to_production(self, project_id):
        """Zentrale Koordination: BOM finden, Preprocessing, Job-Erzeugung."""

        # 1. Datenbeschaffung (Kapselung der DB-Zustände)
        # Erst in Temp schauen, dann in Permanent
        bom_raw = self._get_bom_source(project_id)
        if not bom_raw:
            return False, "BOM-Quelle nicht identifizierbar."

        # 2. Preprocessing (Flachklopfen der Struktur)
        printable_parts = self._extract_printable_parts(bom_raw)

        # 3. Job-Erzeugung
        count = self._persist_production_jobs(project_id, printable_parts)

        return True, count

    def _get_bom_source(self, project_id):
        """Interne Logik: Sucht die BOM in temp_uploads oder Projects."""
        # Suche in Temp
        bom_filename = f"BOM_{project_id}.json"
        full_path = os.path.join(TEMP_UPLOAD_FOLDER, bom_filename)

        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        else:
            return None


    def _extract_printable_parts(self, bom_data):
        """Filtert das JSON auf das Wesentliche."""
        parts = []
        # Alles aus Assemblies
        for assy in bom_data.get('assemblies', []):
            parts.extend([p for p in assy.get('parts', []) 
                          if not p.get('is_bought') 
                          and p.get('process') == 'FDM_PRINT'
                          # Skip: kein file_id zugewiesen -> kein Job ohne Datei erzeugen
                          and p.get('file_id')])
        # Alles aus Loose Parts
        parts.extend([p for p in bom_data.get('loose_parts', []) 
                      if not p.get('is_bought') 
                      and p.get('process') == 'FDM_PRINT'
                      # Skip: kein file_id zugewiesen -> kein Job ohne Datei erzeugen
                      and p.get('file_id')])
        return parts

    def _persist_production_jobs(self, project_id, parts_list):
        """Schreibt die finalen Zeilen in ProductionJobs basierend auf dem neuen Schema."""
        count = 0
        for part in parts_list:
            # Extraktion der technischen Daten aus der BOM
            qty = int(part.get('quantity', 1))
            part_name = part.get('part_name', 'Unbenanntes Teil')
            file_id = part.get('file_id')
            file_name = part.get('file_name')
            material = part.get('material_id')
            profile = part.get('profile_id')
            color = part.get('color')
            print_time = part.get('print_time', 0)
            nozzle = part.get('nozzle', 0.4)
            # Dimensionen
            dx = part.get('dim_x', 0)
            dy = part.get('dim_y', 0)
            dz = part.get('dim_z', 0)

            for i in range(qty):
                # Eindeutige JobID (kurz & knackig)
                job_id = f"JOB_{uuid.uuid4()}"

                query = """
                    INSERT INTO ProductionJobs (
                        JobID, 
                        SourceProjectID, 
                        JobStatus, 
                        Priority, 
                        PartName,
                        FileID,
                        FileName,
                        MaterialID, 
                        ProfileID,
                        Color, 
                        NozzleDiam, 
                        PrintTimeMin,
                        DimX, 
                        DimY, 
                        DimZ
                    ) VALUES (?, ?, 'QUEUED', 3, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                params = (
                    job_id,
                    project_id,
                    part_name,
                    file_id,
                    file_name,
                    material,
                    profile,
                    color,
                    nozzle,
                    print_time,
                    dx,
                    dy,
                    dz
                )

                self._execute_query(query, params)
                count += 1

        return count

    def get_all_printers_with_queue(self) -> list:
        """
        Holt alle Drucker aus der Datenbank und ordnet ihnen ihre aktuell
        eingereihten Jobs aus der PrinterQueues-Tabelle zu (sortiert nach Position).
        """
        # 1. Alle Drucker abfragen
        printers_query = "SELECT * FROM Printers"
        printer_rows = self._execute_query(printers_query, fetch=True)
        
        # 2. Alle Queue-Jobs mit den zugehörigen Job-Details abfragen
        queue_query = """
            SELECT q.QueueID, q.PrinterID, q.Position, j.JobID, j.PartName, j.PrintTimeMin
            FROM PrinterQueues q
            JOIN ProductionJobs j ON q.JobID = j.JobID
            ORDER BY q.PrinterID, q.Position ASC
        """
        queue_rows = self._execute_query(queue_query, fetch=True)
        
        # 3. Datenstruktur für das Frontend aufbereiten
        structured_printers = []
        
        for p_row in printer_rows:
            printer_dict = dict(p_row)  # Konvertierung von sqlite3.Row zu dict
            
            # Alle Jobs filtern, die zu diesem spezifischen Drucker gehören
            printer_dict['jobs'] = [
                dict(q_row) for q_row in queue_rows 
                if q_row['PrinterID'] == printer_dict['PrinterID']
            ]
            
            structured_printers.append(printer_dict)
            
        return structured_printers

    def initialize_printer(self, printer_name, dim_x, dim_y, dim_z, cost_per_min):
        """Initialisiert einen neuen Drucker in der Datenbank."""
        query = """
            INSERT INTO Printers (
                PrinterID,
                PrinterName,
                PrinterStatus,
                DimX,
                DimY,
                DimZ,
                CostPerMin,
                RuntimeHours,
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self._execute_query(query, (
            f"PRNT_{str(uuid.uuid4())}",
            printer_name,
            'NEWBORN',
            dim_x,
            dim_y,
            dim_z,
            cost_per_min,
            0
        ))

    def get_production_jobs_by_status(self, status):
        """Holt alle Jobs eines bestimmten Status aus der DB."""
        query = """
            SELECT 
                JobID, SourceProjectID, JobStatus, Priority, PartName, FileID, FileName,
                MaterialID, ProfileID, Color, NozzleDiam, PrintTimeMin, 
                DimX, DimY, DimZ
            FROM ProductionJobs 
            WHERE JobStatus = ?
            ORDER BY Priority ASC, JobID DESC
        """
        # Nutze deinen DB-Wrapper, der Dicts zurückgibt
        rows = self._execute_query(query, (status,), fetch=True)
        # Falls keine Treffer, leere Liste zurückgeben statt None
        if not rows:
            return []
        # Umwandlung: Jedes Row-Objekt wird zu einem Dict
        return [dict(row) for row in rows]
    
    def assign_job_to_printer_queue(self, job_id: str, printer_id: str) -> tuple[bool, str]:
        """
        Reiht einen Job nach dem LIFO-Prinzip auf Position 1 eines Druckers ein.
        Nutzt die Multi-Query-Transaktionslogik des ProjectManagers.
        """
        queue_id = f"QUEUE_{uuid.uuid4()}"
        
        # Beide SQLs als atomare Transaktion vorbereiten
        queries = [
            (
                "UPDATE PrinterQueues SET Position = Position + 1 WHERE PrinterID = ?", 
                (printer_id,)
            ),
            (
                "INSERT INTO PrinterQueues (QueueID, PrinterID, JobID, Position) VALUES (?, ?, ?, 1)", 
                (queue_id, printer_id, job_id)
            )
        ]

        try:
            self._execute_query(queries, multi_queries=True)
            return True, "Job erfolgreich an Position 1 eingereiht."
            
        except sqlite3.Error as e:
            error_msg = str(e)
            if "UNIQUE" in error_msg:
                return False, "Dieser Job existiert bereits in der Warteschlange dieses Druckers."
            return False, f"Datenbankfehler bei Zuweisung: {error_msg}"
        
    def remove_job_from_printer_queue(self, queue_id: str, printer_id: str) -> tuple[bool, str]:
        try:
            # 1. Position über die QueueID ermitteln
            pos_query = "SELECT Position FROM PrinterQueues WHERE QueueID = ?"
            row = self._execute_query(pos_query, (queue_id,), fetch=True, fetch_one=True)
            
            if not row:
                return False, "Job wurde in der Queue nicht gefunden."
    
            removed_pos = row['Position']
    
            # 2. Präzise nur diesen einen Eintrag löschen
            queries = [
                (
                    "DELETE FROM PrinterQueues WHERE QueueID = ?", 
                    (queue_id,)
                ),
                (
                    "UPDATE PrinterQueues SET Position = Position - 1 WHERE PrinterID = ? AND Position > ?", 
                    (printer_id, removed_pos)
                )
            ]
            
            self._execute_query(queries, multi_queries=True)
            return True, "Job erfolgreich entfernt."
    
        except sqlite3.Error as e:
            return False, f"Datenbankfehler: {str(e)}"

    def get_paginated_transactions(self, limit: int, offset: int) -> list:
        """
        Holt Banktransaktionen sortiert nach Buchungsdatum, limitiert auf 'limit' 
        und überspringt die ersten 'offset' Einträge.
        """
        query = """
            SELECT TransactionID, PartnerName, Amount, BookingDate, Purpose 
            FROM BankTransactions 
            ORDER BY BookingDate DESC 
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(query, (limit, offset), fetch=True)
        return [dict(row) for row in rows]