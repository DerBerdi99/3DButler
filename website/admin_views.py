import os # Für Dateipfade
import json # Für BOM-Handling
from flask import send_from_directory, abort # Für sicheren Datei-Download
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify # Flask-Module für Routing, Templates, Formulardaten, Flash-Messages und JSON-Antworten
### Importiere den ProjectManager, um Projekt-Daten abzurufen, den CalculationManager für Berechnungen ###
from .project_manager import ProjectManager
from .calculation_manager import CalculationManager
from .product_manager import ProductManager
from .order_manager import OrderManager
from .material_manager import MaterialManager
from .user_manager import UserManager
from .transaction_manager import TransactionManager
### Importiere den Decorator aus der user.py ###
from .user import check_admin
from dotenv import load_dotenv
load_dotenv() # Lädt die Umgebungsvariablen aus der .env-Datei, damit wir TEMP_UPLOAD_FOLDER korrekt setzen können
### Konfiguration ###
TEMP_UPLOAD_FOLDER = os.environ.get('UPLOAD_DIR_PATH') or os.path.join(os.getcwd(), 'temp_uploads') # Sicherstellen, dass der Upload-Ordner existiert
### Blueprint für Admin-Views erstellen ###
admin_bp = Blueprint('admin_views', __name__, url_prefix='/admin')
### Instanzen der Manager-Klassen erstellen (die DB-Verbindung wird im Konstruktor aufgebaut) ###
project_manager = ProjectManager()
calculation_manager = CalculationManager()
product_manager = ProductManager()
order_manager = OrderManager()
material_manager = MaterialManager()
user_manager = UserManager()
transaction_manager = TransactionManager()

# --- 1. ENDPOINT FÜR DASHBOARD (Übersicht) ---
# Konstante Liste aller verfügbaren Sektionen in ihrer Basisreihenfolge
BASE_SECTIONS = ['finances', 'orders', 'analysis']
@admin_bp.route('/admin/dashboard', methods=['GET'])
@check_admin
def dashboard():
    # 1. Rotations-Schritt über den ProjectManager (PM) holen
    rotation_step = project_manager._get_config_value('DashboardRotationStep') or 0
    
    # 2. Reihenfolge berechnen (Circular Right Shift)
    n = len(BASE_SECTIONS)
    shift = rotation_step % n
    current_order = BASE_SECTIONS[-shift:] + BASE_SECTIONS[:-shift] if shift > 0 else BASE_SECTIONS
    
    # 3. Finanz- und Bestelldaten über den neuen TransactionManager (TM) holen
    account_data = transaction_manager.get_primary_bank_account()
    orders_data = transaction_manager.get_recent_orders(limit=5)
    
    # 4. Plots generieren (über existierende Plot-Routinen/Manager)
    order_plot_url = transaction_manager.generate_order_plot() # Oder entsprechende Plot-Logik
    bank_plot_url = transaction_manager.generate_bank_plot()
    
    return render_template(
        'admin/admin_dashboard.html', # Dein Template-Pfad bleibt gleich
        section_order=current_order,
        account=account_data,
        orders=orders_data,
        order_plot_url=order_plot_url,
        bank_plot_url=bank_plot_url
    )

@admin_bp.route('/admin/dashboard/rotate', methods=['POST'])
@check_admin
def rotate_dashboard():
    # 1. Aktuellen Schritt holen
    current_step = project_manager._get_config_value('DashboardRotationStep') or 0
    
    # 2. Begrenzen über Modulo der Sektions-Anzahl
    # (new_step wird dadurch NIEMALS größer als 2, sprich: 0, 1, 2, 0, 1, 2...)
    n = len(BASE_SECTIONS)
    new_step = (current_step + 1) % n
    
    # 3. Persistent speichern
    project_manager.set_config_value('DashboardRotationStep', new_step)
    
    return redirect(url_for('admin_views.dashboard'))

# --- 2. ENDPOINT FÜR PROJEKT-DETAILS (Review-Ansicht) ---
@admin_bp.route('/project/<string:project_id>', methods=['GET'])
@check_admin
def project_details(project_id):
    project = project_manager.get_project_details(project_id)
    messages = project_manager.get_project_messages(project_id)

    if not project:
        flash("Projekt nicht gefunden.", 'danger')
        return redirect(url_for('admin_views.dashboard'))

    # DATEIEN ERMITTELN
    project_files = []
    # Falls in FileIDs mehrere IDs durch Komma getrennt sind, splitten wir sie auf
    file_ids = [fid.strip() for fid in project.get('FileIDs', '').split(',') if fid.strip()]
    
    for fid in file_ids:
        # Hier nutzen wir deinen file_manager oder fragen die DB direkt nach der FileID ab
        # Beispiel über deinen project_manager oder file_manager (musst du ggf. anpassen):
        file_info = project_manager.get_file_by_id(fid) 
        if file_info:
            project_files.append(file_info)

    return render_template(
        'admin/admin_project_detail.html', 
        project=project, 
        messages=messages, 
        project_files=project_files
    )

# --- NEUER ENDPOINT: SICHERER DATEI-DOWNLOAD FÜR ADMINS ---
@admin_bp.route('/project/file/<string:file_id>', methods=['GET'])
@check_admin
def admin_download_file(file_id):
    # Die Projekt-ID aus dem Query-Parameter holen (für den Rückweg)
    project_id = request.args.get('project_id')
    
    file_info = project_manager.get_file_by_id(file_id)
    if not file_info:
        if project_id:
            flash("Datei nicht in Datenbank gefunden.", "danger")
            return redirect(url_for('admin_views.project_details', project_id=project_id))
        abort(404, description="Datei nicht in Datenbank gefunden.")

    file_name = file_info['FileName']
    # Absoluten Pfad zur Prüfung bauen
    target_path = os.path.join(TEMP_UPLOAD_FOLDER, file_name)

    if not os.path.exists(target_path):
        # Fallback: Aus dem DB-Pfad extrahieren
        file_name = os.path.basename(file_info['FilePath'])
        target_path = os.path.join(TEMP_UPLOAD_FOLDER, file_name)
        
        if not os.path.exists(target_path):
            if project_id:
                flash(f"Die Datei '{file_name}' existiert physisch nicht auf dem Server.", "danger")
                return redirect(url_for('admin_views.project_details', project_id=project_id))
            abort(404, description="Datei physisch auf Datenträger nicht gefunden.")

    return send_from_directory(TEMP_UPLOAD_FOLDER, file_name, as_attachment=True)

@admin_bp.route('/project/<string:project_id>/files', methods=['GET'])
@check_admin
def admin_get_project_files_api(project_id):
    """
    Liefert alle Dateimetadaten für ein bestimmtes Projekt als JSON.
    Wird vom BOM-Builder im Frontend per Fetch-API aufgerufen.
    """
    try:
        # Da get_files_by_id bereits 'return jsonify(file_list), 200' macht,
        # geben wir dieses fertige Response-Objekt einfach DIREKT zurück.
        return project_manager.get_files_by_id(project_id)
        
    except Exception as e:
        print(f"Fehler in admin_get_project_files_api-Wrapper: {e}")
        return jsonify({"error": "Fehler beim Weiterleiten der Dateien"}), 500

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


# --- 2. ENDPOINT ZUR BEGUTACHTUNG (GET-Anfrage zum Anzeigen der Details) ---


@admin_bp.route('/review_projects', methods=['GET'])
@check_admin
def review_projects():
    # 1. Parameter aus der URL lesen (z.B. ?status=NEW)
    filter_status = request.args.get('status')
    print(filter_status)
    # 2. Alle Projekte abrufen (sqlite3.Row-Objekte)
    customer_projects = project_manager.get_all_projects_for_admin()
    system_projects = [p for p in project_manager.get_all_system_projects()] 
    # 3. Filterung basierend auf dem URL-Parameter
    if filter_status:
        # Filtert nur nach dem spezifischen Status
        projects = [p for p in customer_projects if p['Status'] == filter_status]
        titles = [f"Projekte: {filter_status.replace('_', ' ')}", "Eigene Projekte"]
    else:
        # Standard: Zeigt alle an, die in der Review-Queue relevant sind
        default_review_statuses = ['UNDER_REVIEW', 'WAITING_FOR_QUOTE']
        projects = [p for p in customer_projects if p['Status'] in default_review_statuses]
        titles = ["Review-Queue (Standardansicht)", "Eigene Projekte"]
    # 4. Status-Optionen für die Button-Leiste abrufen
    # Diese Liste enthält alle eindeutigen Status aus der DB
    all_available_statuses = project_manager.get_all_unique_statuses()
    if not projects and filter_status:
        flash(f"Es wurden keine Projekte mit dem Status '{filter_status.replace('_', ' ')}' gefunden.", 'info')
    return render_template(
        'admin/admin_review_projects.html',
        projects=projects,
        system_projects=system_projects,
        titles=titles,
        current_filter=filter_status,
        available_statuses=all_available_statuses # WICHTIG: Übergibt die Liste an das Template
    )


# Angebot erstellen
@admin_bp.route('/review_final_quote/<project_id>', methods=['GET', 'POST'])
@check_admin
def review_final_quote(project_id):
    try:
        project = project_manager.get_project_by_id(project_id)
        if not project:
            flash("Projekt existiert nicht.", "warning")
            return redirect(url_for('admin_views.review_projects'))
        categories, print_profiles, materials = project_manager.get_calculation_context()

    except Exception as e:
        print(f"Kritischer Fehler beim Laden der View-Daten: {e}")
        flash("Fehler beim Laden der Projektdaten. Bitte versuchen Sie es später erneut.", "danger")
        return redirect(url_for('admin_views.review_projects'))
    
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


@admin_bp.route('/manage_products', methods=['GET', 'POST']) #TODO: Fehler bei Produkt Live Schalten fixen. Bei klick auf "zum shop hinzufügen" Fehler: Kritische Finalisierungsdaten fehlen.
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
        elif action == 'view_product' or 'selected_product_id' in request.form:
            selected_id = request.form.get('selected_product_id')
            print(f"DEBUG: Lade Produkt ID {selected_id}") # Check in der Konsole
            try:
                selected_product_data = product_manager.get_system_product_by_id(selected_id)
                if not selected_product_data:
                     flash("Produkt-Datensatz leer.", "warning")
            except Exception as e:
                flash(f'Fehler beim Laden der Details: {e}', 'danger')
                
        elif 'selected_product_id' in request.form and action != 'toggle_status':
            selected_id = request.form.get('selected_product_id')
            try:
                selected_product_data = product_manager.get_system_product_by_id(selected_id)
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
        all_categories = project_manager.get_all_categories()
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

    # GET: Abruf der Daten für die Anzeige 
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

# DER NEUE API-ENDPOINT FÜR DAS INFINITE SCROLLING
@admin_bp.route('/bank_transactions', methods=['GET'])
@check_admin  # Gleicher Schutz wie beim Order-Manager
def get_bank_transactions():
    try:
        # Werte aus dem AJAX-Request abfangen
        limit = request.args.get('limit', default=20, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        # Hole die häppchenweisen Daten aus deinem ProjectManager
        transactions = project_manager.get_paginated_transactions(limit, offset)
        
        return jsonify({
            "success": True,
            "transactions": transactions,
            "has_more": len(transactions) == limit
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
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
@check_admin 
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
@check_admin 
def admin_get_bom(project_id):
    bom_filename = f"BOM_{project_id}.json"
    full_path = os.path.join(TEMP_UPLOAD_FOLDER, bom_filename)
    
    # Wenn die Datei existiert, laden und senden
    if os.path.exists(full_path):
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify({"success": True, "data": data}), 200
        except Exception as e:
            print(f"Fehler beim Lesen der BOM-Datei: {e}")
            return jsonify({"success": False, "message": "BOM beschädigt"}), 500
            
    # FALLBACK: Datei existiert nicht -> Kein 404, sondern leere Struktur senden!
    else:
        empty_bom = {
            "assemblies": [],
            "loose_parts": []
        }
        return jsonify({"success": True, "data": empty_bom}), 200

@admin_bp.route('/get_printers', methods=['GET'])
@check_admin 
def get_printers():
    try:
        # Business-Logik und DB-Abfragen komplett ausgelagert
        printer_list = project_manager.get_all_printers_with_queue()
        return jsonify(printer_list), 200
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Interner Fehler: {str(e)}"}), 500

@admin_bp.route('/initialize_printer', methods=['POST'])
@check_admin 
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
@check_admin 
def generate_jobs(project_id):
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
@check_admin 
def get_jobs_data():
    # Status aus den Query-Parametern extrahieren (?status=QUEUED)
    status = request.args.get('status', 'QUEUED')
    
    # Delegation an den Manager
    jobs = project_manager.get_production_jobs_by_status(status)
    
    # Rückgabe als JSON-Liste
    return jsonify(jobs)


@admin_bp.route('/workshop', methods=['GET', 'POST'])
@check_admin 
def workshop():
    manager = material_manager

    # --------------------------------------------------------
    # POST-LOGIK: Reines Payload-Routing an den Manager
    # --------------------------------------------------------
    if request.method == 'POST':
        action = request.form.get('action')
        
        try:
            # Materials
            if action == 'add_new_material':
                manager.add_material(request.form)
            elif action == 'increment_material':
                manager.increment_material(request.form.get('MaterialID'), float(request.form.get('amount', 1.0)))
            elif action == 'delete_material':
                manager.delete_material(request.form.get('MaterialID'))

            # Spare Parts
            elif action == 'add_new_spare_part':
                manager.add_spare_part(request.form)
            elif action == 'increment_spare_part':
                manager.increment_spare_part(request.form.get('PartID'))
            elif action == 'delete_spare_part':
                manager.delete_spare_part(request.form.get('PartID'))

            # Print Profiles
            elif action == 'add_print_profile':
                manager.add_print_profile(request.form)
            elif action == 'delete_print_profile':
                manager.delete_print_profile(request.form.get('ProfileID'))

            # Maschinen
            elif action == 'add_printer':
                manager.add_printer(request.form)
            elif action == 'add_lathe':
                manager.add_lathe(request.form)
            elif action.startswith('delete_machine_'):
                machine_type = action.replace('delete_machine_', '')
                manager.delete_machine(machine_type, request.form.get('MachineID'))

            flash("Aktion erfolgreich ausgeführt.", "success")
        except Exception as e:
            flash(f"Fehler bei der Verarbeitung: {str(e)}", "danger")
            
        return redirect(url_for('admin_views.workshop'))

    # --------------------------------------------------------
    # GET-LOGIK: Daten über Manager für das Template sammeln
    # --------------------------------------------------------
    mat_category = request.args.get('mat_category', '')
    part_assignment = request.args.get('part_assignment', '')

    # Daten über saubere Schnittstellen laden
    materials = manager.get_materials(mat_category)
    spare_parts = manager.get_spare_parts(part_assignment)
    unassigned_parts = manager.get_unassigned_spare_parts()
    print_profiles = manager.get_print_profiles()
    
    # Maschinenpark laden
    printers = manager.get_machines('printer')
    lathes = manager.get_machines('lathe')
    mills = manager.get_machines('mill')
    moulds = manager.get_machines('mould')
    stoves = manager.get_machines('stove')

    # Aggregieren aller vergebenen IDs für das Zuweisungs-Dropdown
    all_machines = [p['PrinterID'] for p in printers] + [l['LatheID'] for l in lathes]
    # Falls Mills, Moulds, Stoves IDs besitzen, werden sie hier angehängt:
    all_machines += [m['MillID'] for m in mills if 'MillID' in m.keys()]
    all_machines += [m['MouldID'] for m in moulds if 'MouldID' in m.keys()]
    all_machines += [s['StoveID'] for s in stoves if 'StoveID' in s.keys()]

    return render_template(
        'admin/admin_workshop.html',
        materials=materials,
        spare_parts=spare_parts,
        unassigned_parts=unassigned_parts,
        print_profiles=print_profiles,
        printers=printers,
        lathes=lathes,
        mills=mills,
        moulds=moulds,
        stoves=stoves,
        all_machines=all_machines,
        selected_mat_category=mat_category,
        selected_part_assignment=part_assignment
    )


@admin_bp.route('/assign_job_to_printer', methods=['POST'])
@check_admin 
def assign_job_to_printer():
    data = request.get_json() or {}
    job_id = data.get('job_id')
    printer_id = data.get('printer_id')

    if not job_id or not printer_id:
        return jsonify({"success": False, "message": "Fehlende JobID oder PrinterID."}), 400

    try:
        # DB-Logik und Positions-Verschiebung komplett ausgelagert
        success, message = project_manager.assign_job_to_printer_queue(job_id, printer_id)
        
        if not success:
            return jsonify({"success": False, "message": message}), 400
            
        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"Interner Fehler: {str(e)}"}), 500


@admin_bp.route('/remove_job_from_printer', methods=['POST'])
@check_admin 
def remove_job_from_printer():
    data = request.get_json() or {}
    queue_id = data.get('queue_id')      # Erwartet jetzt die eindeutige Instanz-ID
    printer_id = data.get('printer_id')

    if not queue_id or not printer_id:
        return jsonify({"success": False, "message": "Fehlende QueueID oder PrinterID."}), 400

    try:
        # Übergabe der queue_id an den umgebauten ProjectManager
        success, message = project_manager.remove_job_from_printer_queue(queue_id, printer_id)
        
        if not success:
            return jsonify({"success": False, "message": message}), 442
            
        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"Interner Fehler: {str(e)}"}), 500

@admin_bp.route('/manage_users', methods=['GET', 'POST'])
@check_admin  # Dein Decorator sichert die Route bereits komplett ab
def manage_users():
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')

        try:
            if action == 'toggle_active':
                user_manager.toggle_active_status(user_id)
                flash(f'Status für Benutzer {user_id} erfolgreich geändert.', 'success')

            elif action == 'delete_user':
                user_manager.delete_user(user_id)
                flash(f'Benutzer {user_id} wurde kaskadensicher entfernt (Daten migriert).', 'success')

        except Exception as e:
            flash(f'Fehler bei der Benutzerverwaltung: {e}', 'danger')

        return redirect(url_for('admin_views.manage_users'))

    # GET-Logik: Alle Benutzer abrufen
    users = user_manager.get_all_users()
    return render_template('admin/admin_user_manager.html', users=users)


@admin_bp.route('/project_autofill/<string:project_id>', methods=['GET'])
@check_admin 
def project_autofill(project_id):
    values = project_manager.get_project_autofill_values(project_id)

    if not values:
        return jsonify({
            "success": False,
            "message": "Projekt nicht gefunden."
        }), 404

    return jsonify({
        "success": True,
        "material_id": values["MaterialID"],
        "profile_id": values["ProfileID"],
        "weight": values["EstimatedMaterialG"],
        "print_time": values["PrintTimeMin"]
    }), 200

@admin_bp.route('/start_project', methods=['GET','POST'])
@check_admin 
def start_project():
    #TODO: hier die db-abfrage hin die die configuratios ausliest, damit die upload_limit_mb dynamisch im Template verfügbar ist
    upload_limit_mb = 25 # Beispielhafter Wert, in der Realität aus DB oder Config laden
    current_user_id = session['user_id']

    # NEU: Dropdown-Quellen für Profil/Material, analog zu manufacturing_control
    print_profiles_list = project_manager.get_all_print_profiles()
    materials_list = project_manager.get_all_materials()

    if request.method == 'POST':
        uploaded_files = request.files.getlist('file_upload') # Holt alle Dateien mit dem Namen 'file_upload' (muss im HTML-Formular so benannt sein)

        # Wir erwarten jetzt, dass project_id im Fehlerfall den Fehler-Typ enthält
        success, message, result = project_manager.process_project_submission(
            user_id=current_user_id,
            form_data=request.form,
            uploaded_files=uploaded_files,
            temp_upload_folder=TEMP_UPLOAD_FOLDER,
            admin=True
        ) # result enthält entweder die neue project_id oder einen Fehlercode/Fehlertyp (z.B. "INVALID_FORMAT", "LIMIT_REACHED", etc.)

        if success:
            flash(message, 'success')

            return redirect(url_for('views.project_detail', project_id=result))

        else:
            # Hier greift deine gewünschte Änderung: Nur die Flash-Meldung!
            flash(message, 'danger')  # Nutzt 'danger' (bzw. 'error' je nach deinem Bootstrap CSS)

            # Kein **request.form mehr, um den csrf_token-Callable-Konflikt komplett zu eliminieren.
            # Wir rendern das Template einfach frisch und leer.
            return render_template(
                'admin/admin_start_project.html',
                upload_limit_mb=upload_limit_mb,
                print_profiles_list=print_profiles_list,
                materials_list=materials_list
            )

    return render_template(
        'admin/admin_start_project.html',
        upload_limit_mb=upload_limit_mb,
        print_profiles_list=print_profiles_list,
        materials_list=materials_list
    )

@admin_bp.route('/convert_to_product/<string:project_id>', methods=['GET','POST'])
@check_admin 
def convert_to_product(project_id):
    if request.method == "POST":
        try:
            success, message = project_manager.convert_project_to_product(project_id)
            if success:
                flash(f"Projekt {project_id} erfolgreich in ein Produkt umgewandelt.", "success")
            else:
                flash(f"Fehler bei der Umwandlung: {message}", "danger")
        except Exception as e:
            flash(f"Interner Fehler: {str(e)}", "danger")

        return redirect(url_for('admin_views.review_projects'))
    else:
        return redirect(url_for('admin_views.review_projects'))
        
@admin_bp.route('/show_quote_pricing/<string:project_id>', methods=['GET','POST'])
@check_admin 
def show_quote_pricing(project_id):
    try:
        project = project_manager.get_project_by_id(project_id)
        if not project:
            flash("Projekt existiert nicht.", "warning")
            return redirect(url_for('admin_views.review_projects'))
        categories, print_profiles, materials = project_manager.get_calculation_context()

    except Exception as e:
        print(f"Kritischer Fehler beim Laden der View-Daten: {e}")
        flash("Fehler beim Laden der Projektdaten. Bitte versuchen Sie es später erneut.", "danger")
        return redirect(url_for('admin_views.review_projects'))
    
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
                    message_content=f"Stammdaten gespeichert: {quote_price:.2f} €"
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

                flash("Stammdaten erfolgreich gespeichert.", 'success')
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
        'admin/admin_show_quote_price.html',
        project=project,
        suggested_price=suggested_price,
        categories=categories,
        print_profiles=print_profiles,
        materials=materials,
        calculation_data=calculation_data,
        title=f"Angebot für {project['ProjectName']}"
    )