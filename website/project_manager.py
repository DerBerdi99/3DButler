import os
import json
import uuid
import sqlite3
import re
import struct
from werkzeug.utils import secure_filename
from datetime import datetime

# Definieren Sie hier Ihre Konfigurationskonstanten (z.B. Dateipfade, Limits)
# HINWEIS: Die Klasse wird den UPLOAD_FOLDER nun dynamisch übergeben bekommen,
# aber wir behalten die Konstante für Fallbacks oder initiale Struktur bei.
TEMP_UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'stl', 'step', 'obj', '3mf', 'pdf', 'png', 'jpg', 'jpeg', 'zip'}
ALLOWED_CANCELLATION_STATUSES = ['UNDER_REVIEW','WAITING_FOR_QUOTE','QUOTED_AWAITING_CUSTOMER']

class ProjectManager:
    def __init__(self):
        self.db_path = os.getenv('DB_PATH')
        # Erstellt den Standardordner, falls er nicht existiert (wichtig für Entwickler-Setup)
        os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

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
            print(f"Fehler in _execute_query: {e}")
            if conn:
                print("Rollback der Transaktion aufgrund eines Fehlers.")
                conn.rollback()
            raise
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

    def get_config_value(self, key):
        # UNVERÄNDERT: Konfigurationsabfrage
        query = "SELECT Value FROM Configurations WHERE Key = ?"
        try:
            result = self._execute_query(query, (key,), fetch=True)
            return result[0][0] if result and result[0] else None
        except Exception:
            return None

    def check_project_limits(self, user_id):
        # UNVERÄNDERT: Limit-Check
        max_total_projects = self.get_config_value('MaxProjects')
        max_under_review = self.get_config_value('UnderReview')

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
    def process_project_submission(self, user_id, form_data, uploaded_files, temp_upload_folder):
        """
        Verarbeitet die Formular-Daten und Dateien beim Start eines Projekts.
        NEU: Akzeptiert den temp_upload_folder als Argument.
        """
        project_name = form_data.get('project_name')
        description = form_data.get('description')
        quantity = form_data.get('requestet_quantity')

        # ----------------------------------------
        # 1. Validierung & Limits
        # ----------------------------------------
        if not project_name or not description:
            return False, "Bitte füllen Sie den Projektnamen und die Beschreibung aus.", None

        if not uploaded_files or (uploaded_files and uploaded_files[0].filename == ''):
            return False, "Bitte wählen Sie mindestens eine Datei aus.", None

        can_submit, limit_message = self.check_project_limits(user_id)
        if not can_submit:
            return False, limit_message, None

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
            status = 'UNDER_REVIEW'
            date_submitted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            file_ids_string = ",".join(all_file_ids)

            project_insert_query = """
                INSERT INTO Projects (ProjectID, FileIDs, UserID, MaterialType, ProjectDescription, ProjectName, ProjectQuantity, Status, DateAdded)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            print(f"Speichere Projekt {project_id} mit Dateien {file_ids_string} für Benutzer {user_id}")
            self._execute_query(project_insert_query, (project_id, file_ids_string, user_id, order_type, description, project_name, quantity, status, date_submitted))

            return True, f"Projekt erfolgreich mit {len(all_file_ids)} Datei(en) eingereicht.", project_id

        except ValueError:
             # Fängt ungültiges Dateiformat aus _save_files_and_metadata
            return False, f"Fehler beim Speichern der Datei.", None
        except sqlite3.Error:
            # Rollback-Logik für Dateilöschung fehlt hier, ist aber idealerweise nötig.
            return False, f"Fehler bei der Datenbankoperation.", None
        except Exception:
            return False, f"Ein unerwarteter Fehler ist aufgetreten.", None


    # **********************************************
    # 2. Chat-Upload (NEU)
    # **********************************************
    def handle_chat_upload(self, user_id, project_id, uploaded_files, temp_upload_folder):
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
        except ValueError as e:
            return False, f"Fehler beim Speichern der Datei: {e}"
        except Exception as e:
            return False, f"Ein Fehler ist beim Speichern der Dateien aufgetreten: {e}"


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

    def delete_project(self, project_id):  #kann bis jetzt NUR DIE INITIALPROJEKT-FILE DATEN LÖSCHEN, NICHT DIE SEKUNDÄR ANGEFRAGTEN. 
        conn = None
        files_to_delete = []
 
        try:
            # 1. Daten abfragen (Status und FileIDs) - NUTZT _execute_query
            # Da _execute_query conn.close() aufruft, muss der SELECT-Teil außerhalb der Haupttransaktion bleiben.

            # Abfrage 1: Projektdaten abrufen
            query_data = "SELECT Status, FileIDs FROM Projects WHERE ProjectID = ?"
            result_list = self._execute_query(query_data, (project_id,), fetch=True)

            if not result_list:
                return True, "Projekt existiert nicht oder wurde bereits gelöscht."

            # Ergebnis verarbeiten (erwartet ein einzelnes Tupel)
            current_status, file_ids_string = result_list[0]

            # 2. Status-Prüfung (Gatekeeping)
            if current_status not in ALLOWED_CANCELLATION_STATUSES:
                return False, f"Löschen nicht möglich. Projektstatus ist '{current_status}' (Angebot wurde bereits erstellt oder Prozess begonnen)."

            # --- Vorbereitung der Multi-File-Löschung ---
            file_ids_list = [f.strip() for f in file_ids_string.split(',') if f.strip()]

            # 3. Physische Pfade der Dateien abrufen - NUTZT _execute_query
            if file_ids_list:
                placeholders = ','.join('?' for _ in file_ids_list)
                query_paths = f"SELECT FilePath FROM Files WHERE FileID IN ({placeholders})"

                # Abfrage 2: Pfade abrufen
                # Die resultierenden Tupel (Pfad,) in eine flache Liste umwandeln:
                files_to_delete = [row[0] for row in self._execute_query(query_paths, file_ids_list, fetch=True)]

            # 4. Datenbank-Transaktion: Löschen (Muss manuell bleiben)
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()

            # A) Projects-Eintrag löschen
            delete_project_query = "DELETE FROM Projects WHERE ProjectID = ?"
            cursor.execute(delete_project_query, (project_id,))
            print("Projekt ERFOLGREICH gelöscht")
            # B) Zugehörige Files-Einträge löschen
            if file_ids_list:
                print(f"FileIDListe: {file_ids_list}")
                delete_files_query = f"DELETE FROM Files WHERE FileID IN ({placeholders})"
                cursor.execute(delete_files_query, file_ids_list)

            conn.commit()

            # 5. Physische Dateien auf der Festplatte löschen (nach erfolgreichem Commit)
            successful_file_deletes = 0
            total_files = len(files_to_delete)

            for file_path_relative in files_to_delete:
                full_file_path = os.path.join(TEMP_UPLOAD_FOLDER, file_path_relative)
                if os.path.exists(full_file_path):
                    # os.remove(full_file_path) kann hier eine Ausnahme werfen
                    os.remove(full_file_path)
                    successful_file_deletes += 1

            # Rückmeldung
            if total_files > 0 and successful_file_deletes < total_files:
                return True, f"Projekt und DB-Einträge gelöscht. ACHTUNG: Nur {successful_file_deletes}/{total_files} Dateien physisch entfernt."

            return True, "Projekt und alle zugehörigen Dateien erfolgreich gelöscht."

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            return False, f"Datenbankfehler beim Löschen: {e}"

        except Exception as e:
            # Fängt Fehler beim Dateilöschen ab (DB-Löschung war erfolgreich)
            return True, f"Projekt-Einträge gelöscht, aber Fehler beim Löschen der Datei(en): {e}"

        finally:
            if conn:
                conn.close()

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

    def get_project_messages(self, project_id):        #auch von views.project_detail aufgerufen (die Review nachrichten)
        query = "SELECT * FROM ProjectMessages WHERE ProjectID = ?"
        result_rows = self._execute_query(query, (project_id,), fetch=True)

        if not result_rows:
            return []

        messages = []
        conn = None

        try:
            # Spaltennamen abrufen
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("PRAGMA table_info(ProjectMessages)")
            columns = [col[1] for col in cursor.fetchall()]

            for row_tupel in result_rows:
                message_dict = dict(zip(columns, row_tupel))
                messages.append(message_dict)

            return messages

        except sqlite3.Error as e:
            print(f"Fehler beim Abrufen der Nachrichten-Spaltennamen: {e}")
            return []

        finally:
            if conn:
                conn.close()

    def update_project_status(self, project_id: str, new_status: str, volume_cm3: float, print_time: float, weight: float, final_quote_price: float = None) -> bool:
            # Aktualisiert den Projektstatus, optional mit finalem Angebotspreis
            # 1. Basis-Query und Parameter vorbereiten
            query = '''UPDATE Projects SET Status = ?,
                        VolumeCM3 = ?,
                        PrintTimeMin = ?,
                        EstimatedMaterialG = ?'''
            params = [new_status,volume_cm3,print_time,weight]
            # 2. Optionalen Preis hinzufügen
            if final_quote_price is not None:
                quote_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # Erweitert die Query um die Preis- und Datumsfelder
                query += ", FinalQuotePrice = ?, QuoteDate = ?"
                params.append(final_quote_price)
                params.append(quote_date)
            # 3. WHERE-Klausel
            query += " WHERE ProjectID = ?"
            params.append(project_id)
            # 4. _execute_query für den UPDATE-Befehl verwenden
            try:
                # Führt die aktualisierte Query aus. Der Commit und die Fehlerbehandlung
                # erfolgen zentral in _execute_query. Der Rückgabewert ist hier None.
                self._execute_query(query, tuple(params))
                # Da _execute_query keine rowcount zurückgibt, gehen wir bei fehlender Exception
                # von einem Erfolg aus.
                return True

            except sqlite3.Error as e:
                print(f"Datenbankfehler bei Statusaktualisierung: {e}")
                # Die _execute_query hat bereits ein Rollback durchgeführt
                return False
            except Exception as e:
                print(f"Unerwarteter Fehler bei Statusaktualisierung: {e}")
                return False

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
                        AND pm.SenderType = 'Customer'
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
                return projects

            except sqlite3.Error as e:
                # Fehler werden von _execute_query (durch re-raising) hierhin weitergegeben.
                print(f"Datenbankfehler beim Abrufen aller Projekte für Admin: {e}")
                return []

    def send_review_message(self, project_id: str, message_text: str, skip_review_1: bool, request_file_upload: bool) -> tuple[bool, str]:
        """
        Speichert die Review-Nachricht des Admins und steuert den Projektstatus.

        Logik basierend auf 'Review 1 Options' Anforderung:
        1. skip_review_1=True -> Status auf WAITING_FOR_QUOTE setzen (Angebotsphase).
        2. skip_review_1=False & request_file_upload=False -> Nur Nachricht senden, Status bleibt UNDER_REVIEW.
        3. skip_review_1=False & request_file_upload=True -> Nachricht senden UND RequiresFileUpload=1 setzen.
           Status bleibt UNDER_REVIEW (keine Stopp-Logik).
        """
        comm_id = f"COMM_{str(uuid.uuid4())}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sender_type = 'Admin'
        isunreadadmin = 0

        # Setzt RequiresFileUpload auf 1, WENN Review 1 NICHT übersprungen wird UND der Admin den Haken gesetzt hat.
        requires_file_upload = 1 if not skip_review_1 and request_file_upload else 0

        try:
            # 1. Logik für Statusänderung in der Projects-Tabelle
            if skip_review_1:
                # OPTION 1: Review 1 überspringen -> Gehe zur Angebotserstellung
                new_status = 'WAITING_FOR_QUOTE'
                log_message = "Review 1 übersprungen. Status auf 'Finale Prüfung' gesetzt."

                update_query = "UPDATE Projects SET Status = ? WHERE ProjectID = ?"
                self._execute_query(update_query, (new_status, project_id))
            else:
                # OPTION 2 & 3: Nachricht senden und/oder Dateien anfordern -> Status bleibt UNDER_REVIEW

                # Nur Nachricht:
                action_desc = "Nachricht gesendet."

                # Nachricht UND Dateien anfordern:
                if requires_file_upload == 1:
                    action_desc = "Dateiupload vom Kunden angefordert."

                log_message = f"Review-Nachricht gespeichert ({action_desc}). Projektstatus unverändert."

                # HINWEIS: Es wird kein DB-UPDATE für Projects durchgeführt. Status bleibt stabil.


            # 2. Nachricht in die ProjectMessages-Tabelle speichern
            # Das RequiresFileUpload-Flag wird hier gespeichert.
            insert_query = """
                INSERT INTO ProjectMessages (CommID, ProjectID, SenderType, MessageText, Timestamp, IsUnreadAdmin, RequiresFileUpload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            self._execute_query(
                insert_query,
                (comm_id, project_id, sender_type, message_text, timestamp, isunreadadmin, requires_file_upload)
            )

            return True, log_message

        except sqlite3.Error as e:
            return False, f"Datenbankfehler beim Senden des Reviews: {e}"
        except Exception as e:
            return False, f"Ein unerwarteter Fehler ist aufgetreten: {e}"

    def add_project_message(self, project_id, message_text, sender_type='User'):
        """
        Speichert eine neue Nachricht zu einem Projekt in der Datenbank.
        """
        comm_id = 'COMM_' + str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        query = """
            INSERT INTO ProjectMessages (
                CommID, ProjectID, SenderType, MessageText, Timestamp, IsUnreadAdmin, RequiresFileUpload
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        # Nutzt die interne execute-Methode deines Managers
        return self._execute_query(query, (comm_id, project_id, sender_type, message_text, timestamp, 1, 0))

    def get_all_unique_statuses(self) -> list[str]:      #für das Status-Filter-Dropdown in admin_views.py
        """Ruft eine Liste aller eindeutigen Status aus der Projects-Tabelle ab."""
        query = "SELECT DISTINCT Status FROM Projects ORDER BY Status"
        # Verwenden Sie _execute_query, das Tupel zurückgibt
        results = self._execute_query(query, fetch=True)

        # Ergebnisse von Tupeln (('STATUS',), ('STATUS2',)) in eine flache Liste umwandeln
        return [row[0] for row in results] if results else []

    def send_simple_admin_message(self, project_id: str, message_content: str):
        """Fügt eine reine Protokoll-Nachricht des Admins hinzu."""
        comm_id = f"COMM_{str(uuid.uuid4())}"
        sender_type = 'Admin'
        date_sent = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = """
            INSERT INTO ProjectMessages (CommID, ProjectID, SenderType, MessageText, Timestamp, IsUnreadAdmin)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self._execute_query(query, (comm_id, project_id, sender_type, message_content, date_sent, 0))

    def get_all_product_categories(self):
        """Ruft alle Kategorienamen für das Formular ab."""
        query = "SELECT CategoryName FROM ProductCategories ORDER BY CategoryName"
        # Gibt eine Liste von Row-Objekten oder Strings zurück, je nach Implementierung
        return [row['CategoryName'] for row in self._execute_query(query, fetch=True)]

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
                          if not p.get('is_bought') and p.get('process') == 'FDM_PRINT'])
        # Alles aus Loose Parts
        parts.extend([p for p in bom_data.get('loose_parts', []) 
                      if not p.get('is_bought') and p.get('process') == 'FDM_PRINT'])
        return parts

    def _persist_production_jobs(self, project_id, parts_list):
        """Schreibt die finalen Zeilen in ProductionJobs basierend auf dem neuen Schema."""
        count = 0
        for part in parts_list:
            # Extraktion der technischen Daten aus der BOM
            qty = int(part.get('quantity', 1))
            part_name = part.get('part_name', 'Unbenanntes Teil')
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
                        MaterialID, 
                        ProfileID,
                        Color, 
                        NozzleDiam, 
                        PrintTimeMin,
                        DimX, 
                        DimY, 
                        DimZ
                    ) VALUES (?, ?, 'QUEUED', 3, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                params = (
                    job_id,
                    project_id,
                    part_name,
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

    def get_all_printers(self):
        """Ruft alle Drucker ab und mappt sie ohne Umwege auf Spaltennamen."""
        query = "SELECT * FROM Printers ORDER BY PrinterName"
        
        # Wir holen die Daten über deine bestehende Methode
        # Falls _execute_query direkt sqlite3.Row Objekte liefert, reicht ein [dict(row) for row in rows]
        result_rows = self._execute_query(query, fetch=True)
    
        if not result_rows:
            return []
    
        # Falls result_rows einfache Tupel sind, mappen wir sie hier manuell.
        # Wenn deine DB-Klasse sqlite3.Row nutzt, kannst du direkt:
        # return [dict(row) for row in result_rows] nutzen.
        
        # Sicherster Weg ohne PRAGMA, falls es Tupel sind:
        return [dict(row) for row in result_rows] if result_rows else []

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
                JobID, SourceProjectID, JobStatus, Priority, PartName, 
                MaterialID, ProfileID, Color, NozzleDiam, PrintTimeMin, 
                DimX, DimY, DimZ, PrinterID 
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