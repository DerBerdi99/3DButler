import os
import sqlite3
from datetime import datetime
from typing import Tuple, Dict, Any

class CalculationManager:
    """
    Verantwortlich für die gesamte Preisberechnungslogik,
    basierend auf Slicing-Daten und DB-Konstanten.
    """

    # Standard-Mehrwertsteuersatz (VAT)
    VAT_RATE = 0.19

    # Fallback-Werte, falls DB-Abfragen fehlschlagen oder Daten fehlen
    DEFAULT_COST_PER_MIN = 0.50
    DEFAULT_COST_PER_KG = 20.00
    DEFAULT_MARKUP = 1.6
    DEFAULT_MULTIPLIER = 1.05 # Z.B. für Rüstzeiten/Ausfall

    def __init__(self):

        self.db_path = os.getenv('DB_PATH')

        # Sicherstellen, dass die Datenbank existiert
        if not os.path.exists(self.db_path):
            print(f"WARNUNG: Datenbankdatei nicht gefunden unter: {self.db_path}")

    def _execute_query(self, query: str, params: Tuple = ()) -> list:
        """
        Führt eine SQL-Abfrage aus und gibt die Ergebnisse als sqlite3.Row-Objekte zurück.
        Stellt die Typsicherheit und den Schutz vor SQL Injection sicher.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Zugriff auf Spaltennamen
            cursor = conn.cursor()
            cursor.execute(query, params)
            if query.strip().upper().startswith("SELECT"):
                return cursor.fetchall()
            else:
                conn.commit()
                return []
        except sqlite3.Error as e:
            print(f"Datenbankfehler im CalculationManager: {e}")
            raise RuntimeError(f"Datenbankfehler: {e}")
        finally:
            if conn:
                conn.close()

    def get_constants(self, profile_id: int, material_name: str) -> Dict[str, float]:
        """
        Ruft die notwendigen Preis-Konstanten aus den DB-Tabellen ab.
        """
        constants = {
            'cost_per_min': self.DEFAULT_COST_PER_MIN,
            'cost_per_kg': self.DEFAULT_COST_PER_KG,
            'markup': self.DEFAULT_MARKUP,
            'profile_multiplier': self.DEFAULT_MULTIPLIER
        }

        # 1. Konstanten aus PrintProfiles abrufen
        profile_query = """
        SELECT CostMultiplier, MarkupMultiplier, CostPerMin
        FROM PrintProfiles
        WHERE PrintProfiles.ProfileID = ?
        """
        profile_data = self._execute_query(profile_query, (profile_id,))
        if profile_data:
            data = profile_data[0]
            constants['profile_multiplier'] = data['CostMultiplier']
            constants['markup'] = data['MarkupMultiplier']
            # Falls CostPerMin direkt im Drucker steht
            if data['CostPerMin']:
                 constants['cost_per_min'] = data['CostPerMin']

        # 2. Konstanten aus Materials abrufen
        material_query = """
        SELECT CostPerKG
        FROM Materials
        WHERE MaterialName = ?
        """
        material_data = self._execute_query(material_query, (material_name,))
        if material_data and material_data[0]['CostPerKG']:
            constants['cost_per_kg'] = material_data[0]['CostPerKG']

        return constants

    def calculate_pricing(
        self,
        project_id: int, # Kann für spezifische Projektdaten (Stückzahl, etc.) genutzt werden
        volume_cm3: float,
        print_time_min: float,
        material_g: float,
        profile_id: int,
        material_name: str,
        initial_quantity: int = 1, # Annahme: Wenn keine Stückzahl angegeben, ist es 1
        manual_surcharge: float = 0.0 # Annahme: Manueller Zuschlag vom Admin (optional)
    ) -> Tuple[float, float]:
        """
        Berechnet den Basispreis und den Markup-Faktor für eine Ad-hoc-Schätzung.

        :returns: (base_cost, markup_factor)
        """

        # Sicherstellen, dass alle Eingaben Floats/Ints sind
        try:
            material_g = float(material_g)
            print_time_min = float(print_time_min)
            initial_quantity = int(initial_quantity)
        except ValueError:
            # Falls die Eingabe fehlschlägt, geben wir einen Fehler aus
            raise ValueError("Ungültige Eingabe für Slicing-Parameter.")

        # 1. Konstanten aus der Datenbank abrufen
        const = self.get_constants(profile_id, material_name)

        cost_per_kg = const['cost_per_kg']
        cost_per_min = const['cost_per_min']
        markup_factor = const['markup']
        profile_multiplier = const['profile_multiplier']

        # 2. Berechnung der Rohkosten pro Stück (Schritt 2A)

        # Materialkosten pro Stück (in €)
        # MaterialG / 1000 * CostPerKG
        material_cost = (material_g / 1000.0) * cost_per_kg

        # Druckzeitkosten pro Stück (in €)
        # PrintTimeMin * CostPerMin
        runtime_cost = print_time_min * cost_per_min

        # 3. Anwendung des Profil-Multiplikators (Rüstzeit, Ausfall etc.)
        raw_cost_per_unit = (material_cost + runtime_cost) * profile_multiplier

        # 4. Gesamte Rohkosten (Schritt 2C)
        # Hinzufügen des optionalen manuellen Zuschlags (falls vorhanden) und Multiplikation mit der Stückzahl
        total_base_cost = (raw_cost_per_unit * initial_quantity) + manual_surcharge

        # HINWEIS: Mengenrabatt (Volume Discount) und Mehrwertsteuer (VAT)
        # werden in einem späteren Schritt im Admin-Endpunkt angewendet,
        # da calculate_pricing_ad_hoc nur die Basis für den FinalQuotePrice liefern soll.

        return total_base_cost, markup_factor