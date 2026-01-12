import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
# Importiere den ProjectManager, um Projekt-Daten abzurufen, den CalculationManager für Berechnungen
from .project_manager import ProjectManager
from .calculation_manager import CalculationManager
from .product_manager import ProductManager
from .order_manager import OrderManager
# Importiere den Decorator aus der admin.py
from .admin import check_admin
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
# Konfiguration
TEMP_UPLOAD_FOLDER = os.environ.get('UPLOAD_DIR') or os.path.join(os.getcwd(), 'temp_uploads')
# Blueprint Definition
admin_bp = Blueprint('admin_views', __name__, url_prefix='/admin')
project_manager = ProjectManager()
calculation_manager = CalculationManager()
product_manager = ProductManager()
order_manager = OrderManager()

# --- 1. ENDPOINT FÜR DASHBOARD (Übersicht) ---
@admin_bp.route('/', methods=['GET'])
@check_admin
def dashboard():
    # KORREKTUR: Aufruf über die Instanz project_manager
    projects = project_manager.get_all_projects_for_admin()
    # KORREKTUR: Template-Pfad zur Konsistenz admin_dashboard.html'
    return render_template('admin/admin_dashboard.html', projects=projects)


# --- 2. ENDPOINT FÜR PROJEKT-DETAILS (Review-Ansicht) ---
@admin_bp.route('/project/<string:project_id>', methods=['GET'])
@check_admin
def project_details(project_id):
    # KORREKTUR: Aufruf über die Instanz
    project = project_manager.get_project_details(project_id)
    messages = project_manager.get_project_messages(project_id)

    if not project:
        flash("Projekt nicht gefunden.", 'danger')
        # KORREKTUR: url_for nutzt den Blueprint-Namen 'admin_views'
        return redirect(url_for('admin_views.dashboard'))

    return render_template('admin/admin_project_detail.html', project=project, messages=messages)


# --- 3. ENDPOINT FÜR REVIEW 1 SENDEN ---
@admin_bp.route('/send_review/<string:project_id>', methods=['POST'])
@check_admin
def admin_send_review(project_id):
    message_text = request.form.get('message_text')
    skip_review_1 = 'skip_review_1' in request.form
    request_documents_required = 'request_documents' in request.form
    if not message_text:
        flash("Nachrichtentext darf nicht leer sein.", 'warning')
        # KORREKTUR: url_for nutzt den Blueprint-Namen 'admin_views'
        return redirect(url_for('admin_views.project_details', project_id=project_id))

    # KORREKTUR: Aufruf über die Instanz project_manager (nicht die Klasse ProjectManager,
    # da die Klasse keine DB-Verbindung hält, die Instanz schon)
    success, message = project_manager.send_review_message(
        project_id,
        message_text,
        skip_review_1,
        request_file_upload=request_documents_required
    )

    if success:
        flash(f'Review erfolgreich gesendet. {message}', 'success')
    else:
        flash(f'Fehler beim Senden des Reviews: {message}', 'danger')

    # KORREKTUR: url_for nutzt den Blueprint-Namen 'admin_views'
    return redirect(url_for('admin_views.project_details', project_id=project_id))


# --- 4. ENDPOINT FÜR FINALE ENTSCHEIDUNG --- DEN ES NOCH NICHT GIBT!
@admin_bp.route('/process_review/<string:project_id>', methods=['POST'])
@check_admin
def process_review(project_id):
    status_action = request.form.get('status_action')

    if status_action in ['ACCEPT', 'REJECT']:
        try:
            # KORREKTUR: Aufruf über die Instanz project_manager
            success = project_manager.update_project_status(project_id, status_action)

            if success:
                flash(f"Projekt {project_id} wurde erfolgreich auf {status_action} gesetzt.", 'success')
            else:
                flash(f"Fehler beim Aktualisieren des Status von Projekt {project_id}.", 'danger')

        except Exception as e:
            flash("Ein Fehler ist bei der Statusaktualisierung aufgetreten.", 'danger')
            print(f"Fehler bei process_review: {e}")

    else:
        flash("Ungültige Statusaktion.", 'warning')

    # KORREKTUR: url_for nutzt den Blueprint-Namen 'admin_views'
    # und leitet zur Detailansicht zurück
    return redirect(url_for('admin_views.project_details', project_id=project_id))


# --- 5. ENDPOINT FÜR USER-MANAGEMENT ---
@admin_bp.route('/user_management', methods=['GET'])
@check_admin
def user_management():
    return render_template('admin/admin_user_manager.html')

# --- 2. ENDPOINT ZUR BEGUTACHTUNG (GET-Anfrage zum Anzeigen der Details) ---


@admin_bp.route('/review_projects', methods=['GET'])
@check_admin
def review_projects():
    # 1. Parameter aus der URL lesen (z.B. ?status=NEW)
    filter_status = request.args.get('status')
    print(filter_status)
    # 2. Alle Projekte abrufen (sqlite3.Row-Objekte)
    all_projects = project_manager.get_all_projects_for_admin()

    # 3. Filterung basierend auf dem URL-Parameter
    if filter_status:
        # Filtert nur nach dem spezifischen Status
        projects = [p for p in all_projects if p['Status'] == filter_status]
        title = f"Projekte: {filter_status.replace('_', ' ')}"
    else:
        # Standard: Zeigt alle an, die in der Review-Queue relevant sind
        # Wenn Sie wirklich ALLE anzeigen wollen: projects = all_projects

        # Annahme: Standardmäßig sollen NUR die folgenden Status in der Übersicht sein
        default_review_statuses = ['UNDER_REVIEW', 'WAITING_FOR_QUOTE']
        projects = [p for p in all_projects if p['Status'] in default_review_statuses]
        title = "Review-Queue (Standardansicht)"


    # 4. Status-Optionen für die Button-Leiste abrufen
    # Diese Liste enthält alle eindeutigen Status aus der DB
    all_available_statuses = project_manager.get_all_unique_statuses()

    if not projects and filter_status:
        flash(f"Es wurden keine Projekte mit dem Status '{filter_status.replace('_', ' ')}' gefunden.", 'info')

    return render_template(
        'admin/admin_review_projects.html',
        projects=projects,
        title=title,
        current_filter=filter_status,
        available_statuses=all_available_statuses # WICHTIG: Übergibt die Liste an das Template
    )


# NEUER ENDPOINT: Angebot erstellen
@admin_bp.route('/review_final_quote/<project_id>', methods=['GET', 'POST'])
@check_admin
def review_final_quote(project_id):
    project = project_manager.get_project_by_id(project_id)
    categories = project_manager.get_all_product_categories()
    print_profiles = project_manager.get_all_print_profiles()
    materials = project_manager.get_all_materials()

    # --- 1. DATEN-INITIALISIERUNG ---
    # Wir prüfen, ob bereits Daten aus dem Manufacturing (Slicer) in Projects stehen
    has_blueprint_data = project['VolumeCM3'] is not None

    calculation_data = {
        'volume_cm3': project['VolumeCM3'] if has_blueprint_data else 100.0,
        'material_g': project['EstimatedMaterialG'] if has_blueprint_data else 50.0,
        'print_time_min': project['PrintTimeMin'] if has_blueprint_data else 300.0,
        'profile_id': print_profiles[0]['ProfileID'] if print_profiles else 1,
        'material_name': materials[0]['MaterialName'] if materials else 'PLA'
        # ... rest
    }
    
    suggested_price = 0.00

    # --- 2. POST LOGIK ---
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'calculation':
            try:
                calculation_data['volume_cm3'] = float(request.form.get('volume_cm3'))
                calculation_data['material_g'] = float(request.form.get('material_g'))
                calculation_data['print_time_min'] = float(request.form.get('print_time_min'))
                calculation_data['profile_id'] = str(request.form.get('profile_id'))
                calculation_data['material_name'] = request.form.get('material_name_calc')

                base_cost, markup_factor = calculation_manager.calculate_pricing(
                    project_id=project_id,
                    **calculation_data
                )
                suggested_price = round(base_cost * markup_factor, 2)
                flash(f"Preis erfolgreich neu berechnet: {suggested_price:.2f} €", 'info')

            except (ValueError, RuntimeError) as e:
                flash(f"Fehler bei der Ad-hoc-Berechnung: {e}", 'danger')

        elif form_type == 'save':
            try:
                # Extraktion der finalen Werte (entweder aus Slicer-Übernahme oder manuellem Form-Override)
                quote_price = float(request.form.get('quote_price'))
                product_name = request.form.get('product_name')
                category_name = request.form.get('category_name')
                image_url = request.form.get('image_url')
                is_shop_ready = 1 if request.form.get('IsShopReady') == 'on' else 0
                
                # Wir nehmen die Werte, die im "Internen Details" Bereich stehen (Slicer-Werte)
                volume_cm3 = float(request.form.get('volume_cm3'))
                print_time = float(request.form.get('print_time'))
                weight = float(request.form.get('weight'))
                description = request.form.get('description')

                form_data = {
                    'quote_price': quote_price,
                    'product_name': product_name,
                    'category_name': category_name,
                    'image_url': image_url,
                    'volume_cm3': volume_cm3,
                    'print_time': print_time,
                    'weight': weight,
                    'description': description
                }

                # 1. Datenbank-Update des Projekts
                project_manager.update_project_status(
                    project_id=project_id,
                    new_status='QUOTED_AWAITING_CUSTOMER',
                    volume_cm3=volume_cm3,
                    print_time=print_time,
                    weight=weight,
                    final_quote_price=quote_price
                )

                # 2. Protokollierung
                project_manager.send_simple_admin_message(
                    project_id=project_id,
                    message_content=f"Finales Angebot erstellt: {quote_price:.2f} €"
                )

                # 3. Shop-Produkt erstellen
                project_manager.create_product_from_project(
                    project_data=project,
                    form_data=form_data,
                    volume_cm3=volume_cm3,
                    print_time_min=print_time,
                    weight_g=weight,
                    final_quote_price=quote_price,
                    is_shop_ready=is_shop_ready
                )

                flash("Angebot erfolgreich an Kunden übermittelt.", 'success')
                return redirect(url_for('admin_views.review_projects'))

            except Exception as e:
                flash(f"Fehler bei der Speicherung: {e}", 'danger')

    # --- 3. INITIALE PREIS-BERECHNUNG (GET) ---
    # Falls wir noch keinen suggested_price durch einen POST haben, berechnen wir ihn jetzt
    if suggested_price == 0.00:
        try:
            # Nutzt entweder Default oder bereits vorhandene Slicer-Daten
            base_cost, markup_factor = calculation_manager.calculate_pricing(
                project_id=project_id,
                **calculation_data
            )
            suggested_price = round(base_cost * markup_factor, 2)
        except Exception:
            suggested_price = 10.00  # Letzter Fallback

    return render_template(
        'admin/admin_review_final_quote.html',
        project=project,
        suggested_price=suggested_price,
        categories=categories,
        print_profiles=print_profiles,
        materials=materials,
        calculation_data=calculation_data,
        title=f"Angebot für {project['ProjectName']}"
    )

@admin_bp.route('/delete_project/<string:project_id>', methods=['POST'])
@check_admin
def delete_project_route(project_id):
    # Logik aus dem ProjectManager aufrufen
    success, message = project_manager.delete_project(project_id)

    if success:
        # success=True bedeutet entweder: Gelöscht ODER existierte nicht (siehe Logik in delete_project)
        flash(f"Projekt {project_id} erfolgreich gelöscht. {message}", 'success')
    else:
        # success=False bedeutet: Löschen aufgrund des Status blockiert
        flash(f"Löschen blockiert: {message}", 'danger')

    # Nach der Löschung zur Übersichtsseite zurückleiten
    return redirect(url_for('admin_views.review_projects'))


@admin_bp.route('/manage_products', methods=['GET', 'POST'])
@check_admin
def manage_products():
    selected_product_data = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # A) Finalisierungs-Aktion
        if action == 'finalize_product':
            try:
                product_id = request.form.get('product_id')
                final_price = float(request.form.get('final_price'))
                final_category = request.form.get('final_category')
                
                if not product_id or final_price is None or not final_category:
                    flash('Fehler: Kritische Finalisierungsdaten fehlen.', 'danger')
                else:
                    product_manager.finalize_product(
                        product_id=product_id,
                        final_price=final_price,
                        final_category=final_category,
                        is_shop_visible=1
                    )
                    flash(f'Produkt **{product_id}** erfolgreich finalisiert.', 'success')
                    return redirect(url_for('admin_views.manage_products'))
            except Exception as e:
                flash(f'Fehler bei Finalisierung: {e}', 'danger')

        # B) Produkt-Auswahl-Aktion
        elif 'selected_product_id' in request.form and action != 'toggle_status':
            selected_id = request.form.get('selected_product_id')
            try:
                selected_product_data = product_manager.get_product_by_id(selected_id)
            except Exception as e:
                flash(f'Fehler beim Laden der Details: {e}', 'danger')

        # C) NEU: Status-Aktion (Aktivieren/Deaktivieren)
        elif action == 'toggle_status':
            product_id = request.form.get('product_id')
            new_status = int(request.form.get('new_status'))
            try:
                product_manager.toggle_product_visibility(product_id, new_status)
                msg = "reaktiviert" if new_status == 1 else "deaktiviert"
                flash(f'Produkt wurde erfolgreich {msg}.', 'success')
                return redirect(url_for('admin_views.manage_products'))
            except Exception as e:
                flash(f'Status-Fehler: {e}', 'danger')

    # --- 2. GET-Handling ---
    try:
        products_to_finalize = product_manager.get_products_for_finalization(include_inactive=True)
        all_categories = product_manager.get_all_product_categories()
    except Exception as e:
        flash(f'Fehler beim Laden: {e}', 'danger')
        products_to_finalize, all_categories = [], []
        
    return render_template(
        'admin/admin_product_main.html',
        products_for_review=products_to_finalize,
        selected_product=selected_product_data,
        all_categories=all_categories
    )

@admin_bp.route('/delete_product', methods=['POST'])
@check_admin
def delete_product():
    product_id = request.form.get('product_id')

    if not product_id:
        flash("Produkt-ID fehlt.", "danger")
        return redirect(url_for('admin_views.manage_products'))

    try:
        product_manager.delete_product(product_id)
    except Exception as e:
       
        flash(f'Fehler beim Löschen des Produktes: {e}', 'danger')
    finally:

        return redirect(url_for('admin_views.manage_products'))
    
@admin_bp.route('/manage_orders', methods=['GET', 'POST'])
@check_admin
def manage_orders():
    # POST: Status-Update verarbeiten
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        new_status = request.form.get('new_status')
        
        if order_id and new_status:
            success = order_manager.update_order_status(order_id, new_status)
            if success:
                flash(f"Status für Order {order_id[-8:]} erfolgreich auf {new_status} gesetzt.", "success")
            else:
                flash("Fehler beim Aktualisieren des Status in der Datenbank.", "danger")
        
        # Nach dem POST immer redirecten (Post-Redirect-Get Pattern)
        # Wir behalten den aktuellen Filter bei, falls vorhanden
        return redirect(url_for('admin_views.manage_orders', status=request.args.get('status')))

    # GET: Abruf der Daten für die Anzeige (wie bisher)
    filter_status = request.args.get('status')
    all_orders = order_manager.get_all_orders_for_admin()

    if filter_status:
        orders = [o for o in all_orders if o['Status'] == filter_status]
        title = f"Bestellungen: {filter_status.replace('_', ' ')}"
    else:
        # Standard: Nur relevante Zahlungs-Status anzeigen
        default_statuses = ['ORDER_FINALIZED','DRAFT','PAID']
        orders = [o for o in all_orders if o['Status'] in default_statuses]
        title = "Zahlungs-Queue (Standard)"

    all_available_statuses = order_manager.get_all_unique_statuses()

    return render_template(
        'admin/admin_order_manager.html',
        orders=orders,
        title=title,
        current_filter=filter_status,
        available_statuses=all_available_statuses
    )

@admin_bp.route('/archive_order/<string:order_id>', methods=['POST'])
@check_admin
def archive_order_route(order_id):
    success = order_manager.archive_order(order_id)
    if success:
        # Wir geben JSON zurück, damit das Frontend weiß, dass es die Card entfernen kann
        return jsonify({"success": True, "message": "Bestellung archiviert"}), 200
    else:
        return jsonify({"success": False, "message": "Fehler beim Archivieren"}), 500
    
@admin_bp.route('/order_details/<string:order_id>')
@check_admin
def order_details(order_id):
    # 1. Basis-Informationen der Bestellung holen
    order = order_manager.get_order_by_id(order_id)
    if not order:
        flash("Bestellung nicht gefunden.", "danger")
        return redirect(url_for('admin_views.manage_orders'))

    # 2. Adresse und Positionen abrufen
    # Hinweis: In deinem OrderManager hast du bereits get_order_positions und get_address_by_id
    positions = order_manager.get_order_positions(order_id)
    address = order_manager.get_address_by_id(order['AddressID'])
    
    return render_template(
        'admin/admin_order_details.html',
        order=order,
        positions=positions,
        address=address
    )

@admin_bp.route('/manufacturing_control', methods=['GET'])
@check_admin
def manufacturing_control():
    # druckprofile und materialien laden
    print_profiles = project_manager.get_all_print_profiles()
    materials = project_manager.get_all_materials()
    # 1. Blueprints laden (sind noch sqlite3.Row Objekte)
    raw_blueprints = project_manager.get_active_blueprints()
    #hier jobs laden, jetzt erstmaln Dummy:
    jobs_dummy = [
        {
            "JobID": "JOB-2024-001",
            "ProjectName": "Futterspender Gehäuse",
            "PrinterName": "Bambu Lab X1C #1",
            "Progress": 65,
            "StartTime": "10:30",
            "RemainingTime": "45"
        },
        {
            "JobID": "JOB-2024-002",
            "ProjectName": "Halterung V2",
            "PrinterName": "Prusa MK4 #2",
            "Progress": 12,
            "StartTime": "11:15",
            "RemainingTime": "120"
        }
    ]

    # 2. In echte Dictionaries umwandeln und BOM-Check durchführen
    blueprints = []
    for row in raw_blueprints:
        # Umwandlung in dict, damit wir Felder hinzufügen können
        bp = dict(row) 
    
        bom_filename = f"BOM_{bp['ProjectID']}.json"
        full_path = os.path.join(TEMP_UPLOAD_FOLDER, bom_filename)
    
        # Jetzt klappt die Zuweisung ohne TypeError
        bp['bom_exists'] = os.path.exists(full_path)
    
        blueprints.append(bp)

    # 3. Die neue Liste 'blueprints' ans Template schicken
    return render_template(
        'admin/admin_manufacturing_main.html', 
        blueprints_list=blueprints,
        jobs_list=jobs_dummy,
        print_profiles_list=print_profiles,
        materials_list=materials
    )

@admin_bp.route('/load_project_to_mes/<string:project_id>', methods=['POST'])
@check_admin
def load_project_to_mes(project_id):
    try:
        # success ist hier das (bool, str) Tupel aus deinem Manager
        success, message = project_manager.load_project_to_mes(project_id)
        
        if success:
            flash(message, "success")
        else:
            flash(message, "danger")
            
    except Exception as e:
        # Im Fehlerfall: Nachricht flashen und zurück zur Liste
        flash(f"Systemfehler: {str(e)}", "danger")
    
    # Der Redirect muss IMMER am Ende stehen, damit der Admin 
    # wieder auf der Übersicht landet, egal ob Erfolg oder Error.
    return redirect(url_for('admin_views.review_projects'))

@admin_bp.route('/delete_blueprint/<string:blueprint_id>', methods=['POST'])
@check_admin
def delete_blueprint(blueprint_id):
    try:
        project_manager.delete_blueprint(blueprint_id)
        flash(f"Blueprint {blueprint_id} erfolgreich gelöscht.", "success")
    except Exception as e:
        flash(f"Fehler beim Löschen des Blueprints: {str(e)}", "danger")
    
    return redirect(url_for('admin_views.manufacturing_control'))

@admin_bp.route('/save_blueprint_data/<string:bp_id>', methods=['POST'])
@check_admin
def save_blueprint_data(bp_id):
    try:
        # Technische Daten aus dem Manufacturing-Formular
        project_id = request.form.get('project_id')
        weight = float(request.form.get('weight'))
        print_time = int(request.form.get('print_time'))
        volume = float(request.form.get('volume'))
        
        # NEU: Profil und Materialart (für die Vorauswahl im Quote)
        profile_id = request.form.get('profile_id')
        material_id = request.form.get('material_id')
        
        # 1. Update der Projekttabelle (Technische Wahrheit für Kalkulation)
        # Wir fügen hier die Felder ProfileID und MaterialID hinzu
        project_manager.update_project_technical_data(
            project_id=project_id,
            volume_cm3=volume,
            weight_g=weight,
            print_time_min=print_time,
            profile_id=profile_id,
            material_id=material_id
        )
        
        # 2. Update des Blueprints (Status auf COMPLETED oder IN_PROGRESS)
        project_manager.update_blueprint_status(bp_id, 'COMPLETED')
        
        flash(f"Technische Daten für Projekt {project_id} gespeichert. BOM ist bereit.", "success")
        
    except Exception as e:
        flash(f"Fehler beim Speichern der technischen Daten: {str(e)}", "danger")
    
    return redirect(url_for('admin_views.manufacturing_control'))

@admin_bp.route('/save_bom/<string:project_id>', methods=['POST'])
def save_bom(project_id):
    data = request.get_json()
    bom_filename = f"BOM_{project_id}.json"
    full_path = os.path.join(TEMP_UPLOAD_FOLDER, bom_filename)

    try:
        # 1. Datei physisch schreiben
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # 2. DB-Update delegieren
        # Wir fangen den spezifischen Fehler des Managers ab
        success = project_manager.finalize_blueprint(project_id, full_path)
        
        if not success:
            # Wenn der Manager False liefert, aber keine Exception wirft
            return jsonify({
                "success": False, 
                "error_type": "DB_FINALIZE_FAILED",
                "message": f"Manager konnte Projekt {project_id} nicht finalisieren. Check die DB-Constraints."
            }), 422 

        return jsonify({"success": True, "message": "BOM gespeichert und Blueprint finalisiert."})

    except Exception as e:
        # Hier loggen wir den echten Traceback in die Konsole
        import traceback
        print(f"ERROR in save_bom: {str(e)}")
        traceback.print_exc()
        
        return jsonify({
            "success": False, 
            "error_type": "PYTHON_EXCEPTION",
            "message": str(e) # Das landet in deinem Alert im Frontend
        }), 500

@admin_bp.route('/get_bom/<string:project_id>', methods=['GET'])
def get_bom(project_id):
    bom_filename = f"BOM_{project_id}.json"
    full_path = os.path.join(TEMP_UPLOAD_FOLDER, bom_filename)
    
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"success": True, "data": data})
    
    return jsonify({"success": False, "message": "Keine BOM gefunden."}), 404

@admin_bp.route('/get_printers', methods=['GET'])
def get_printers():
    try:
        # get_all_printers liefert bereits [{}, {}]
        printers = project_manager.get_all_printers()
        return jsonify(printers) # Direkt das Array senden
    except Exception as e:
        print(f"Fehler: {e}")
        return jsonify([]), 500

@admin_bp.route('/initialize_printer', methods=['POST'])
def initialize_printer():
    try:
        data = request.get_json()
        printer_name = data.get('printer_name')
        hotend_id = data.get('hotend_id')
        printhead_id = data.get('printhead_id')
        buildplate_id = data.get('buildplate_id')
        dim_x = int(data.get('dim_x'))
        dim_y = int(data.get('dim_y'))
        dim_z = int(data.get('dim_z'))
        cost_per_min = float(data.get('cost_per_min'))
        
        if not all([printer_name, hotend_id, printhead_id, buildplate_id, dim_x, dim_y, dim_z, cost_per_min]):
            return jsonify({"success": False, "message": "Alle Felder müssen ausgefüllt sein."}), 400

        project_manager.initialize_printer(
            printer_name=printer_name,
            hotend_id=hotend_id,
            printhead_id=printhead_id,
            buildplate_id=buildplate_id,
            dim_x=dim_x,
            dim_y=dim_y,
            dim_z=dim_z,
            cost_per_min=cost_per_min
        )
        
        return jsonify({"success": True, "message": "Drucker erfolgreich initialisiert."})
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@admin_bp.route('/generate_jobs/<string:project_id>', methods=['POST'])
def generate_jobs_endpoint(project_id):
    success, result = project_manager.process_bom_to_production(project_id)
    
    if not success:
        return jsonify({
            "success": False, 
            "message": result
        }), 400
        
    return jsonify({
        "success": True, 
        "message": f"Jobs erfolgreich hinzugefügt: {result}",
        "jobs_created": result
    }), 200

@admin_bp.route('/jobs/data', methods=['GET'])
def get_jobs_data():
    # Status aus den Query-Parametern extrahieren (?status=QUEUED)
    status = request.args.get('status', 'QUEUED')
    
    # Delegation an den Manager
    jobs = project_manager.get_production_jobs_by_status(status)
    
    # Rückgabe als JSON-Liste
    return jsonify(jobs)