
import os
import sqlite3
from sys import prefix
import uuid
from typing import Tuple, List, Dict, Any

class MaterialManager:
    """
    Verwaltet die gesamte Datenbank- und Business-Logik für die 
    Werkstatt-Zentrale (Materials, SpareParts, PrintProfiles und Maschinenpark).
    """

    def __init__(self):
        self.db_path = os.getenv('DB_PATH')
        if not self.db_path:
            raise RuntimeError("DB_PATH-Umgebungsvariable ist nicht gesetzt!")
        
        if not os.path.exists(self.db_path):
            print(f"WARNUNG: Datenbankdatei nicht gefunden unter: {self.db_path}")

    def _execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """
        Zentraler DB-Executor für maximale Sicherheit (SQL-Injection-Schutz)
        und einheitlichen Zugriff über Spaltennamen.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if query.strip().upper().startswith("SELECT"):
                return cursor.fetchall()
            else:
                conn.commit()
                return []
        except sqlite3.Error as e:
            print(f"Datenbankfehler im MaterialManager: {e}")
            raise RuntimeError(f"Datenbankfehler: {e}")
        finally:
            if conn:
                conn.close()

    def generate_unique_id(self,prefix):

        return f"{prefix}_{uuid.uuid4()}"
    # =========================================================================
    # MATERIALS LOGIC
    # =========================================================================
    def get_materials(self, category: str = "") -> List[sqlite3.Row]:
        if category:
            return self._execute_query("SELECT * FROM Materials WHERE Category = ?", (category,))
        return self._execute_query("SELECT * FROM Materials")

    def add_material(self, data: Dict[str, Any]) -> str:
        material_id = self.generate_unique_id("MATE")
        query = """
            INSERT INTO Materials (MaterialID, MaterialName, Category, Color, DensityCM3, Manufacturer, CostPerKG, InStockKG)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            material_id,
            data.get('MaterialName'),
            data.get('Category'),
            data.get('Color'),
            float(data.get('DensityCM3') or 0.0),
            data.get('Manufacturer'),
            float(data.get('CostPerKG') or 0.0),
            float(data.get('InStockKG') or 0.0)
        )
        self._execute_query(query, params)
        return material_id

    def increment_material(self, material_id: str, amount: float = 1.0) -> None:
        self._execute_query(
            "UPDATE Materials SET InStockKG = InStockKG + ? WHERE MaterialID = ?", 
            (amount, material_id)
        )

    def delete_material(self, material_id: str) -> None:
        self._execute_query("DELETE FROM Materials WHERE MaterialID = ?", (material_id,))


    # =========================================================================
    # SPARE PARTS LOGIC
    # =========================================================================
    def get_spare_parts(self, assigned_to: str = "") -> List[sqlite3.Row]:
        if assigned_to:
            return self._execute_query("SELECT * FROM SpareParts WHERE AssignedTo = ?", (assigned_to,))
        return self._execute_query("SELECT * FROM SpareParts")

    def get_unassigned_spare_parts(self) -> List[sqlite3.Row]:
        return self._execute_query("SELECT * FROM SpareParts WHERE AssignedTo = 'Unassigned' OR AssignedTo IS NULL")

    def add_spare_part(self, data: Dict[str, Any]) -> str:
        part_id = self.generate_unique_id("SPAR")
        query = """
            INSERT INTO SpareParts (PartID, PartName, Category, StockCount, Condition, AssignedTo)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            part_id,
            data.get('PartName'),
            data.get('Category'),
            int(data.get('StockCount') or 0),
            data.get('Condition', 'new'),
            data.get('AssignedTo') or 'Unassigned'
        )
        self._execute_query(query, params)
        return part_id

    def increment_spare_part(self, part_id: str) -> None:
        self._execute_query("UPDATE SpareParts SET StockCount = StockCount + 1 WHERE PartID = ?", (part_id,))

    def delete_spare_part(self, part_id: str) -> None:
        self._execute_query("DELETE FROM SpareParts WHERE PartID = ?", (part_id,))


    # =========================================================================
    # PRINT PROFILES LOGIC
    # =========================================================================
    def get_print_profiles(self) -> List[sqlite3.Row]:
        return self._execute_query("SELECT * FROM PrintProfiles")

    def add_print_profile(self, data: Dict[str, Any]) -> str:
        profile_id = self.generate_unique_id("PROF")
        query = """
            INSERT INTO PrintProfiles (ProfileID, ProfileName, SpeedMultiplier, MarkupMultiplier, InfillDensity, LayerHeightMM, CostMultiplier, CostPerMin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            profile_id,
            data.get('ProfileName'),
            float(data.get('SpeedMultiplier') or 1.0),
            float(data.get('MarkupMultiplier') or 1.0),
            int(data.get('InfillDensity') or 20),
            float(data.get('LayerHeightMM') or 0.2),
            float(data.get('CostMultiplier') or 1.0),
            float(data.get('CostPerMin') or 0.0)
        )
        self._execute_query(query, params)
        return profile_id

    def delete_print_profile(self, profile_id: str) -> None:
        self._execute_query("DELETE FROM PrintProfiles WHERE ProfileID = ?", (profile_id,))


    # =========================================================================
    # MACHINE PARK LOGIC (Printers, Lathes, Mills, Moulds, Stoves)
    # =========================================================================
    def get_machines(self, machine_type: str) -> List[sqlite3.Row]:
        """
        Liefert alle Maschinen eines Typs. Fängt nicht existierende Tabellen 
        sauber ab, falls diese in der DB noch nicht migriert wurden.
        """
        table_map = {'printer': 'Printers', 'lathe': 'Lathes', 'mill': 'Mills', 'mould': 'Moulds', 'stove': 'Stoves'}
        if machine_type not in table_map:
            return []
        try:
            return self._execute_query(f"SELECT * FROM {table_map[machine_type]}")
        except Exception:
            return []

    def add_printer(self, data: Dict[str, Any]) -> str:
        printer_id = self.generate_unique_id("PRIN")
        query = """
            INSERT INTO Printers (PrinterID, PrinterName, PrinterStatus, HotendID, PrintHeadID, BuildPlateID, DimX, DimY, DimZ, CostPerMin, RuntimeHours, PowerKW)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            printer_id, data.get('PrinterName'), data.get('PrinterStatus', 'online'),
            data.get('HotendID') or None, data.get('PrintHeadID') or None, data.get('BuildPlateID') or None,
            int(data.get('DimX') or 0), int(data.get('DimY') or 0), int(data.get('DimZ') or 0),
            float(data.get('CostPerMin') or 0.0), float(data.get('RuntimeHours') or 0.0), float(data.get('PowerKW') or 0.0)
        )
        self._execute_query(query, params)
        return printer_id

    def add_lathe(self, data: Dict[str, Any]) -> str:
        lathe_id = self.generate_unique_id("LATH")
        query = """
            INSERT INTO Lathes (LatheID, LatheName, LatheStatus, ChuckleID, ToolHolderID, MaxLengthMM, MaxSwingMM, PowerKW, CostPerMin, RuntimeHours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            lathe_id, data.get('LatheName'), data.get('LatheStatus', 'online'),
            data.get('ChuckleID') or None, data.get('ToolHolderID') or None,
            float(data.get('MaxLengthMM') or 0.0), float(data.get('MaxSwingMM') or 0.0),
            float(data.get('PowerKW') or 0.0), float(data.get('CostPerMin') or 0.0), float(data.get('RuntimeHours') or 0.0)
        )
        self._execute_query(query, params)
        return lathe_id

    def delete_machine(self, machine_type: str, machine_id: str) -> None:
        table_map = {'printer': 'Printers', 'lathe': 'Lathes', 'mill': 'Mills', 'mould': 'Moulds', 'stove': 'Stoves'}
        if machine_type in table_map:
            id_column = f"{table_map[machine_type][:-1]}ID" # Generiert z.B. 'PrinterID' aus 'Printers'
            self._execute_query(f"DELETE FROM {table_map[machine_type]} WHERE {id_column} = ?", (machine_id,))