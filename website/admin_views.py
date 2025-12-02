from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
# Importiere den ProjectManager, um Projekt-Daten abzurufen, den CalculationManager für Berechnungen
import os
from .project_manager import ProjectManager
from .calculation_manager import CalculationManager
# Importiere den Decorator aus der admin.py
from .admin import check_admin
from datetime import datetime

DB_PATH = os.getenv('DB_PATH')
# Blueprint Definition
admin_bp = Blueprint('admin_views', __name__, url_prefix='/admin')
project_manager = ProjectManager()
calculation_manager = CalculationManager()

# --- 1. ENDPOINT FÜR DASHBOARD (Übersicht) ---
@admin_bp.route('/', methods=['GET'])
@check_admin
def dashboard():
    # KORREKTUR: Aufruf über die Instanz project_manager
    projects = project_manager.get_all_projects_for_admin()
    # KORREKTUR: Template-Pfad zur Konsistenz dashboard.html'
    return render_template('admin/dashboard.html', projects=projects)


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
    return render_template('admin/user_manager.html')

# --- 2. ENDPOINT ZUR BEGUTACHTUNG (GET-Anfrage zum Anzeigen der Details) ---


@admin_bp.route('/review_projects', methods=['GET'])
@check_admin
def review_projects():
    # 1. Parameter aus der URL lesen (z.B. ?status=NEW)
    filter_status = request.args.get('status')

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
        default_review_statuses = ['NEW', 'P1_NEU_EINGEREICHT', 'P2_ZUGWIESEN', 'UNDER_REVIEW', 'WAITING_FOR_QUOTE']
        projects = [p for p in all_projects if p['Status'] in default_review_statuses]
        title = "Review-Queue (Standardansicht)"


    # 4. Status-Optionen für die Button-Leiste abrufen
    # Diese Liste enthält alle eindeutigen Status aus der DB
    all_available_statuses = project_manager.get_all_unique_statuses()

    if not projects and filter_status:
        flash(f"Es wurden keine Projekte mit dem Status '{filter_status.replace('_', ' ')}' gefunden.", 'info')

    return render_template(
        'admin/review_projects.html',
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
    calculation_data = {
        'volume_cm3': 100.0,
        'material_g': 50.0,
        'print_time_min': 300.0,
        'profile_id': print_profiles[0]['ProfileID'] if print_profiles else 1,
        'material_name': materials[0]['MaterialName'] if materials else 'PLA'
    }
    suggested_price = 10.00 # Fallback-Preis

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'calculation':
            # --- 1. PREIS BERECHNEN (durch das kleine Formular) ---
            try:
                # 1.1 Daten aus dem POST-Request abrufen und Zustand aktualisieren
                calculation_data['volume_cm3'] = float(request.form.get('volume_cm3'))
                calculation_data['material_g'] = float(request.form.get('material_g'))
                calculation_data['print_time_min'] = float(request.form.get('print_time_min'))
                calculation_data['profile_id'] = str(request.form.get('profile_id'))
                calculation_data['material_name'] = request.form.get('material_name_calc')

                # 1.2 Berechnung aufrufen
                base_cost, markup_factor = calculation_manager.calculate_pricing(
                    project_id=project_id,
                    **calculation_data # Übergabe der aktualisierten Daten
                )
                suggested_price = round(base_cost * markup_factor, 2)
                flash(f"Preis erfolgreich berechnet: {suggested_price:.2f} €", 'info')

            except (ValueError, RuntimeError) as e:
                flash(f"Fehler bei der Ad-hoc-Berechnung: {e}", 'danger')
                # suggested_price bleibt beim Fallback

            # Wichtig: Die Seite wird mit den neuen Werten (suggested_price und calculation_data) neu gerendert
            pass

        elif form_type =='save':

            # Daten aus dem Formular abrufen
            # Basisfelder:
            quote_price = request.form.get('quote_price')
            product_name = request.form.get('product_name')
            category_name = request.form.get('category_name')
            image_url = request.form.get('image_url')
            is_shop_ready_raw = request.form.get('IsShopReady')
            is_shop_ready = 1 if is_shop_ready_raw == 'on' else 0
            # NEU: Zusätzliche Felder aus der rechten Spalte des Formulars (admin/review_final_quote.html)
            volume_cm3 = float(request.form.get('volume_cm3'))

            print_time = float(request.form.get('print_time'))

            weight = float(request.form.get('weight'))
            description = request.form.get('description')

            # Alle Formulardaten in einem Dictionary bündeln (vereinfacht die Übergabe)
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

            # NOTE: Fügen Sie hier alle notwendigen Validierungen hinzu!

            try:
                print("UPDATE_PROJECT_STATUS")
                float_price = float(quote_price)

                # 1. Status setzen und Quote speichern (nutzt die in der letzten Runde erstellte update_project_status)
                project_manager.update_project_status(
                    project_id=project_id,
                    new_status='QUOTED_AWAITING_CUSTOMER', # Korrekter Status laut früherem Plan
                    volume_cm3 = volume_cm3,
                    print_time = print_time,
                    weight = weight,
                    final_quote_price=float_price
                    # quote_date ist nun in update_project_status intern definiert
                )
                print("DONE... PM_SEND_SIMPLE_MESSAGE")
                # 2. Protokoll-Nachricht senden
                message_content = f"Admin hat ein finales Angebot von {float_price:.2f} € erstellt."
                project_manager.send_simple_admin_message(
                    project_id=project_id,
                    message_content=message_content
                )
                print("DONE... PM_CREATE_PRODUCT")
                # 3. NEU: Produkt in die DB verschieben
                new_product_id = project_manager.create_product_from_project(
                    project_data=project,
                    form_data=form_data,
                    volume_cm3=volume_cm3,
                    print_time_min=print_time,
                    weight_g=weight,
                    final_quote_price=float_price,
                    is_shop_ready=is_shop_ready
                )

                flash(f"Angebot erstellt und Produkt-ID {new_product_id} gespeichert.", 'success')
                return redirect(url_for('admin_views.review_projects'))

            except ValueError:

                flash("Ungültiger Preis. Bitte eine Zahl eingeben.", 'danger')
                return redirect(url_for('admin_views.review_final_quote', project_id=project_id))

            except Exception as e:

                flash(f"Fehler bei der Angebotserstellung: {e}", 'danger')
                return redirect(url_for('admin_views.review_final_quote', project_id=project_id))

        else:
            flash("Unbekannter Formular-Typ übermittelt.", 'danger')

    if request.method == 'GET' and suggested_price == 10.00:
        try:
             # Initialer Aufruf mit Default-Werten
            base_cost, markup_factor = calculation_manager.calculate_pricing(
                project_id=project_id,
                **calculation_data # Übergabe der initialisierten Daten
            )
            suggested_price = round(base_cost * markup_factor, 2)
        except Exception:
            suggested_price = 10.00 # Fallback


            suggested_price = 10.00 # Fallback

    # HINWEIS: Hier müssen Sie die calculation_data in die suggested_price logik übergeben,
    # damit das quote_price Feld den NEUEN, berechneten Preis erhält.

    return render_template(
        'admin/review_final_quote.html',
        project=project,
        suggested_price=suggested_price, # Der Preis, der ins Angebotsfeld kommt
        categories=categories,
        print_profiles=print_profiles, # NEU für Dropdown
        materials=materials, # NEU für Dropdown
        calculation_data=calculation_data, # NEU für die Persistenz der Kalkulationsfelder
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