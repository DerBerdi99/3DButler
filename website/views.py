from flask import Blueprint,render_template, flash, session, url_for, redirect, request, abort
import os
import uuid
from datetime import datetime
from .cart_manager import CartManager
from .project_manager import ProjectManager
from .product_manager import ProductManager
from .order_manager import OrderManager
from .user_manager import UserManager   

TEMP_UPLOAD_FOLDER = os.environ.get('UPLOAD_DIR') or os.path.join(os.getcwd(), 'temp_uploads')
views = Blueprint('views', __name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))  # Relative to blueprint file
cart_manager = CartManager()
project_manager = ProjectManager() 
product_manager = ProductManager()
order_manager = OrderManager()
user_manager = UserManager()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'zip'}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@views.route('/home')
def home():
    if 'user_id' in session:  # Check if the user is logged in
        username = session['username']
        
        try:
            # 5 zufällige Produkte für die Slideshow holen
            slideshow_products = product_manager.get_random_shop_products(count=5)
        except Exception as e:
        # Fehlerbehandlung, falls die DB leer ist oder nicht erreicht werden kann
            slideshow_products = []
        return render_template('home.html', logged_in=True, username=username, slideshow_products=slideshow_products)  # Pass logged_in and username to the template
    else:
        try:
            # 5 zufällige Produkte für die Slideshow holen, nicht eingeloggt -> ohne cta
            slideshow_products = product_manager.get_random_shop_products(count=5)
        except Exception:
        # Fehlerbehandlung, falls die DB leer ist oder nicht erreicht werden kann
            slideshow_products = []
        return render_template('home.html', logged_in=False, slideshow_products=slideshow_products) # Important: Pass logged_in as False if user is not logged in

@views.route('/cart')  # Deine Warenkorb-Route
def cart():
    """
    Zeigt den Inhalt des Warenkorbs des angemeldeten Benutzers an.
    Delegiert die Datenabfrage an den CartManager.
    """
    if 'user_id' not in session:
        flash('Sie müssen angemeldet sein, um den Warenkorb anzuzeigen.', 'info')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cart_items = []

    try:
        # Delegation der Datenbankabfrage an den Manager
        cart_items = cart_manager.get_cart_items_for_user(user_id)
        
    except Exception as e:
        # Fehlerbehandlung für den Manager-Aufruf
        print(f"Fehler beim Abrufen der Warenkorbartikel: {e}")
        flash('Ein Fehler beim Laden des Warenkorbs ist aufgetreten. Bitte versuchen Sie es erneut.', 'danger')
        
    print(f"Warenkorbartikel: {cart_items}")  # Konsolenausgabe
    
    # Übergabe der Daten und Rendern des Templates
    # cart_items enthält nun die Ergebnisse des Managers
    return render_template('cart.html', cart_items=cart_items)
     
    
@views.route('/products/<product_id>')
def product_detail(product_id):
    is_logged_in = 'user_id' in session
    
    try:
        # Name bleibt gleich, liefert jetzt aber alle nötigen Daten
        product = product_manager.get_product_by_id(product_id)

        if product:
            return render_template(
                'product_detail.html', 
                product_name=product['ProductName'], 
                product_description=product['ProductDescription'], 
                stock_quantity=product['StockQuantity'], 
                price=product['ProductPrice'], 
                product_image=product['ImagePath'],
                product_id=product_id,
                creator_name=product['CreatorName'],
                logged_in=is_logged_in
            )
        else:
            flash('Product not found.', 'warning')
            return redirect(url_for('views.home'))

    except Exception as e:
        print(f"Error fetching product details: {e}")
        flash('An error occurred. Please try again.', 'danger')
        return redirect(url_for('views.home'))


@views.route('/add_to_cart/<product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash('You must be logged in to add to cart.', 'info')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']

    try:
        # 1. Daten validieren
        product_info = cart_manager.get_product_stock_info(product_id)
        if not product_info:
            flash('Product not found.', 'warning')
            return redirect(url_for('views.shop'))

        quantity = int(request.form.get('quantity', 1))
        stock = product_info['StockQuantity']

        if quantity <= 0:
            flash('Invalid quantity.', 'warning')
            return redirect(url_for('views.product_detail', product_id=product_id))

        if quantity > stock:
            flash(f'Only {stock} units in stock.', 'warning')
            return redirect(url_for('views.product_detail', product_id=product_id))

        # 2. Operation ausführen
        cart_manager.add_product_to_cart(user_id, product_id, quantity)
        
        flash('Product added to cart!', 'success')
        return redirect(url_for('views.product_detail', product_id=product_id))

    except Exception as e:
        print(f"Error in add_to_cart view: {e}")
        flash('An error occurred.', 'danger')
        return redirect(url_for('views.shop'))

@views.route('/cart/delete/<product_id>', methods=['POST'])
def delete_cart_product(product_id):
    if 'user_id' not in session:
        flash('You must be logged in to remove cart items.', 'info')
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']

    try:
        success = cart_manager.remove_product_from_cart(user_id, product_id)
        
        if success:
            flash('Item removed from cart.', 'success')
        else:
            flash('No cart found for the user.', 'warning')

    except Exception as e:
        print(f"Error in delete_cart_product view: {e}")
        flash('An error occurred while removing the item.', 'danger')

    return redirect(url_for('views.cart'))

@views.route('/wishlist')
def wishlist():
    if 'user_id' not in session:
        flash('You must be logged in to view your wishlist.', 'info')
        return redirect(url_for('auth.login'))
    
    try:
        items = cart_manager.get_wishlist_for_user(session['user_id'])
        return render_template('wishlist.html', items=items)
    except Exception as e:
        print(f"Error fetching wishlist: {e}")
        flash('An error occurred.', 'danger')
        return redirect(url_for('views.home'))

@views.route('/add_to_wishlist/<product_id>', methods=['POST'])
def add_to_wishlist(product_id):
    if 'user_id' not in session:
        flash('Please login to use the wishlist.', 'info')
        return redirect(url_for('auth.login'))
    
    
    try:
        if cart_manager.add_to_wishlist(session['user_id'], product_id):
            flash("Item added to wishlist", "success")
        else:
            flash("Product not found.", "danger")
        
        return redirect(url_for('views.wishlist'))
    except Exception as e:
        print(f"Error adding to wishlist: {e}")
        flash('Database error occurred.', 'danger')
        return redirect(url_for('views.shop'))

@views.route('/wishlist/delete/<product_id>', methods=['POST'])
def delete_wishlist_product(product_id):
    if 'user_id' not in session:
        flash('You must be logged in to remove wishlist items.', 'info')
        return redirect(url_for('auth.login'))
    
    try:
        cart_manager.remove_from_wishlist(session['user_id'], product_id)
        flash('Item removed from wishlist.', 'success')
    except Exception as e:
        print(f"Error deleting from wishlist: {e}")
        flash('An error occurred.', 'danger')

    return redirect(url_for('views.wishlist')) 

@views.route('/check_payment', methods=['GET', 'POST'])
def check_payment():
    if 'user_id' not in session:
        flash('You must be logged in.', 'info')
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # GET: Vorhandene Info prüfen
    if request.method == 'GET':
        if order_manager.get_payment_info(user_id):
            return redirect(url_for('views.checkout_entry'))
        return render_template('payment_form.html')
    
    # POST: Neue Info speichern
    payment_method = request.form.get('payment_method')
    card_number = request.form.get('card_number')
    expiry = request.form.get('expiry', 'N/A')
    last_digits = ''

    # Validierungs-Logik
    if payment_method == 'card':
        if not card_number or not expiry:
            flash('Bitte füllen Sie alle Kartenfelder aus.', 'error')
            return render_template('payment_form.html')
        last_digits = card_number[-4:]
    elif payment_method not in ['paypal', 'wallets', 'rechnung']:
        flash('Ungültige Zahlungsmethode.', 'error')
        return render_template('payment_form.html')

    try:
        order_manager.save_payment_info(
            user_id, 
            payment_method.capitalize(), 
            last_digits, 
            expiry
        )
        flash('Zahlungsmethode erfolgreich gespeichert.', 'success')
        return redirect(url_for('views.checkout_entry'))
    except Exception as e:
        flash(f'Fehler beim Speichern: {e}', 'error')
        return redirect(url_for('views.home'))

# -----------------------------------------------------------
# ROUTE: checkout_entry (UNIFIZIERTER EINSTIEGspunkt)
# -----------------------------------------------------------
@views.route('/checkout', methods=["GET"])
@views.route('/checkout/<order_id>', methods=["GET"])
def checkout_entry(order_id=None):
    if 'user_id' not in session:
        flash('You must be logged in to check payment.', 'info')
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    try:
        # Fall 1: Warenkorb -> Order erstellen
        if not order_id:
            data = order_manager.create_order_from_cart(user_id)
            if not data:
                flash("Ihr Warenkorb ist leer.", "warning")
                return redirect(url_for("views.home"))
        # Fall 2: Bestehende Order laden
        else:
            data = order_manager.get_order_with_positions(order_id, user_id)
            if not data:
                flash("Bestellung nicht gefunden.", "error")
                return redirect(url_for("views.home"))

        # Ressourcen für das Template laden (Adressen/Zahlung)
        addresses, payment_methods = order_manager.get_checkout_resources(user_id)

        if not addresses:
            flash("Bitte legen Sie zuerst eine Lieferadresse an.", "info")
            return redirect(url_for("views.home"))
        if not payment_methods:
            flash("Bitte hinterlegen Sie zuerst eine Zahlungsart.", "info")
            return redirect(url_for("views.home"))

        # Template-Daten aufbereiten
        order_info = data['order']
        positions = [{
            'ProductName': p['ProductName'],
            'Quantity': p['Quantity'],
            'ProductPrice': p['PricePerUnit'],
            'SubTotal': p['PricePerUnit'] * p['Quantity']
        } for p in data['positions']]

        return render_template(
            'checkout_details.html',
            order=order_info,
            positions=positions,
            total_amount=order_info['OrderAmount'],
            addresses=addresses,
            payment_methods=payment_methods,
            title="Checkout Abschließen"
        )

    except Exception as e:
        print(f"Checkout Error: {e}")
        flash(f"Fehler bei der Checkout-Vorbereitung.", "error")
        return redirect(url_for("views.home"))

@views.route('/shop', methods=['GET', 'POST'])
def shop():
    logged_in = 'user_id' in session
    # 1. Parameter aus dem Request holen
    search_query = request.args.get('search') or request.form.get('search')
    selected_categories = request.args.getlist('category[]')
    selected_materials = request.args.getlist('material[]')

    # 2. Dynamische Filter-Optionen für die Sidebar laden
    filter_options = product_manager.get_filter_options()
    
    # 3. Gefilterte Produkte abrufen
    raw_products = product_manager.get_filtered_products(
        search_query=search_query,
        selected_categories=selected_categories,
        selected_materials=selected_materials
    )

    # 4. Mapping (wie in deinem Code, am besten in eine Helper-Funktion im Manager auslagern)
    products_list = []
    for p in raw_products:
        # Hier dein Dictionary-Mapping anwenden...
        products_list.append(product_manager.map_row_to_dict(p))

    return render_template(
        'shop.html', 
        products=products_list,
        categories=filter_options['categories'],
        materials=filter_options['materials'],
        selected_categories=selected_categories,
        selected_materials=selected_materials,
        total_results_count=len(products_list),
        current_results_count=len(products_list), # Später für Pagination relevant
        logged_in=logged_in
    )


@views.route('/start_project', methods=['GET','POST'])
def start_project():
    # ----------------------------------------
    # 1. SICHERHEIT: Login-Check
    # ----------------------------------------
    if 'user_id' not in session:
        # Falls NICHT eingeloggt: Hinweis geben und Ziel speichern
        flash("Please log in or register to start a new project.", 'warning')
        session['next_url'] = url_for('views.start_project') 
        return redirect(url_for('auth.login')) 
        
    current_user_id = session['user_id']
    
    if request.method == 'POST':
        # **********************************************
        # Hier wird der Code, der process_project_submission aufruft, ausgeführt
        # **********************************************
        
        uploaded_files = request.files.getlist('file_upload')
        
        success, message, project_id = project_manager.process_project_submission(
            user_id=current_user_id, 
            form_data=request.form, 
            uploaded_files=uploaded_files,
            temp_upload_folder=TEMP_UPLOAD_FOLDER
        )
        
        if success:
            flash(message, 'success')
            return redirect(url_for('views.project_detail',project_id=project_id))  # Weiterleitung zur Projekt-Detailseite
        else:
            flash(message, 'error')
            # Rendert die Seite neu und gibt die Formulardaten zurück
            return render_template('start_project.html', **request.form)    
    # ----------------------------------------
    # 2. FORMULAR LADEN
    # ----------------------------------------
    # Wenn eingeloggt und Limit nicht erreicht, zeige die Seite an
    return render_template('start_project.html')

# Route, auf die das Formular in start_project.html POSTet
# Diese Route verarbeitet den Datei-Upload oder was auch immer nötig ist 

@views.route('/delete_project/<project_id>', methods=['POST'])
def delete_project_route(project_id):
    # 1. Login-Check
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an, um diesen Vorgang durchzuführen.", 'warning')
        return redirect(url_for('auth.login'))

    current_user_id = session['user_id']
    
    # 2. Ownership-Check (WICHTIG! Verhindert, dass User X Projekte von User Y löscht)
    
    if not project_manager.is_project_owner(project_id, current_user_id):
        flash("Zugriff verweigert.", 'danger')
        return redirect(url_for('views.my_reviews'))
        
    # 3. Lösch-Funktion aufrufen
    success, message = project_manager.delete_project(project_id)
    
    if success:
        flash(message, 'success')
        # Weiterleitung zur Projektübersicht (my_reviews), die nun ohne das gelöschte Projekt neu lädt
        return redirect(url_for('views.my_reviews')) 
    else:
        # Fehlermeldung anzeigen (z.B. "Löschen nicht möglich. Status ist QUOTE_READY")
        flash(f"Löschen fehlgeschlagen: {message}", 'error')
        # Zurück zur Detailseite, um die Fehlermeldung anzuzeigen
        return redirect(url_for('views.project_detail', project_id=project_id))


@views.route('/project/<project_id>', methods=['GET'])
def project_detail(project_id):
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an, um Ihre Projekte einzusehen.", 'warning')
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    print("UserID:", user_id)
    logged_in = True

    try:
        # 2. Projekt-Details abrufen (zentral über ProjectManager)
        # Angenommen, diese Methode holt das Projekt als Dictionary:
        project_data = project_manager.get_project_details(project_id)

        if not project_data:
            flash("Projekt nicht gefunden.", 'danger')
            return redirect(url_for('views.my_reviews')) # Oder zur Projektübersicht

        # 3. Sicherheitsprüfung: Ist der eingeloggte User der Besitzer?
        # NEU: Wenn die UserID nicht übereinstimmt, verbieten wir den Zugriff.
        if project_data.get('UserID') != user_id:
            abort(403) # Zugriff verweigert

        # 4. Nachrichten/Reviews für dieses Projekt abrufen
        # Angenommen, ProjectManager hat eine Methode dafür:
        messages = project_manager.get_project_messages(project_id)
    
        print(f"messages: {messages}")

        # 1. Finde die letzte Admin-Nachricht, die den Upload explizit angefordert hat (Flag=1)
        last_admin_message_requiring_upload = next(
            (m for m in reversed(messages) 
             if m.get('SenderType') == 'Admin' and m.get('RequiresFileUpload') == 1), 
            None
        )
        last_customer_message_with_upload = next(
            (m for m in reversed(messages) 
            if m.get('SenderType') == 'User' and m.get('RequiredFilesProvided') == 1), 
            None
        )

        show_file_upload_cta = False
        show_success_checkmark = False
        # 2. Wenn sie gefunden wurde, setze das Flag auf True
        if last_admin_message_requiring_upload:
            if last_customer_message_with_upload:
                if last_customer_message_with_upload['Timestamp'] > last_admin_message_requiring_upload['Timestamp']:
                    show_success_checkmark = True
                else:
                    show_file_upload_cta = True
            else:
                show_file_upload_cta = True

        print(f"show_file_upload_cta: {show_file_upload_cta}")
        # 5. Admin-Nachrichten als gelesen markieren (optional, aber empfohlen)
        # messages_manager.mark_as_read_customer_view(project_id) 
        print(f"ProjectMessages: {messages}")
        # 6. Template rendern
        return render_template('my_project.html', 
                               project=project_data, 
                               messages=messages,
                               logged_in=logged_in,
                               show_file_upload_cta=show_file_upload_cta,
                               show_success_checkmark=show_success_checkmark)

    except Exception as e:
        print(f"Fehler bei project_detail: {e}")
        flash('Ein unerwarteter Fehler ist aufgetreten.', 'danger')
        return redirect(url_for('views.my_reviews'))

@views.route('/my_reviews', methods=['GET']) 
def my_reviews():
    # 1. SICHERHEIT: Login-Check
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an, um Ihre Projekte einzusehen.", 'warning')
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    logged_in = True # Für das base.html-Template
    
    try:
        # 2. PROJEKTE ABRUFEN
       
        my_projects = project_manager.get_projects_by_user(user_id) 
      

        # 3. TEMPLATE RENDERN
        return render_template('my_reviews.html', 
                               projects=my_projects,
                               logged_in=logged_in)

    except Exception as e:
        print(f"Fehler beim Abruf der Kundenprojekte in my_reviews: {e}")
        flash('Ein unerwarteter Fehler ist beim Laden Ihrer Projekte aufgetreten.', 'danger')
        # Sicherer Fallback (Status 500 nur bei unbekanntem Fehler)
        return render_template('my_reviews.html', projects=[]), 500

@views.route('/send_message/<project_id>', methods=['POST'])
def send_message(project_id):
    # 1. SICHERHEIT: Login-Check
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an, um Ihre Projekte einzusehen.", 'warning')
        return redirect(url_for('auth.login'))
        
    # 2. Daten extrahieren und validieren
    message_text = request.form.get('messageText', '').strip()
    
    if not message_text:
        flash('Nachricht kann nicht leer sein.', 'danger')
        return redirect(url_for('views.project_detail', project_id=project_id))
    
    # 3. Logik über ProjectManager ausführen
    try:
        # project_manager ist global/zentral instanziiert
        success = project_manager.add_project_message(project_id, message_text, sender_type='User')
        
        if success:
            flash('Nachricht erfolgreich gesendet.', 'success')
        else:
            raise Exception("Manager returned False")
            
    except Exception as e:
        print(f"Fehler beim Senden der Nachricht: {e}")
        flash('Fehler beim Senden der Nachricht. Bitte versuchen Sie es später erneut.', 'danger')
        
    return redirect(url_for('views.project_detail', project_id=project_id))

@views.route('/upload_files/<project_id>', methods=['POST'])
def upload_files(project_id):
    """
    Verarbeitet Datei-Uploads vom Frontend. 
    Delegiert die Speicherung und die Erstellung der Chat-Nachricht an den ProjectManager.
    Verwendet flash-Nachrichten zur Benutzerinformation.
    """ 
    # HINWEIS: Die Konfiguration des Upload-Ordners muss aus Ihrer Flask-App stammen (z.B. app.config)
    # Da wir uns in einer isolierten Funktion befinden, simulieren wir den Zugriff:
    
    user_id = session.get('user_id')

    # 1. Authentifizierung und User-ID
    if not user_id:
        flash("Sitzung abgelaufen. Bitte melden Sie sich an, um Dateien hochzuladen.", 'warning')
        return redirect(url_for('auth.login'))
    
    # 2. Prüfen, ob Dateien im Request enthalten sind
    if 'files' not in request.files:
        flash("Fehler: Es wurden keine Dateien gefunden.", 'error')
        # Weiterleitung zur Projekt-Detailseite, wo der Upload stattfand
        return redirect(url_for('views.project_detail', project_id=project_id))

    # Holt alle hochgeladenen Dateien
    uploaded_files = request.files.getlist('files')

    # 3. Dateiverarbeitung mit dem ProjectManager
    # Die gesamte Logik (Speichern, Validieren, DB-Eintrag für Files, DB-Eintrag für Chat)
    # wird hier zentral ausgeführt.
    success, message = project_manager.handle_chat_upload(
        user_id=user_id, 
        project_id=project_id, 
        uploaded_files=uploaded_files,
        temp_upload_folder=TEMP_UPLOAD_FOLDER
    )
    
    # 4. Feedback und Weiterleitung
    if success:
        # Erfolgreiche Nachricht flashen
        flash(message, 'success')
    else:
        # Fehlermeldung flashen
        flash(f"Upload fehlgeschlagen: {message}", 'error')

    # Zurück zur Detailseite des Projekts
    return redirect(url_for('views.project_detail', project_id=project_id))

@views.route('/start_order_from_quote/<project_id>', methods=['POST'])
def start_order_from_quote(project_id):
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an, um eine Bestellung zu starten.", 'warning')
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    """
    Erstellt die DRAFT-Order aus einem abgeschlossenen Projekt/Quote und leitet 
    zur zentralen Checkout-Seite weiter.
    """
    try:
        # 1. Idempotenz-Prüfung: Bereits eine Order für diese Quote gestartet?
        existing_order_id = order_manager.get_open_order_for_project(project_id, user_id)
    
        if existing_order_id:
            flash("Sie setzen den begonnenen Bestellvorgang fort.", 'info')
            return redirect(url_for('views.checkout_entry', order_id=existing_order_id))
        
        # 2. Projektstatus und Berechtigungen prüfen
        project_result = project_manager.get_project_status_details(project_id)
        
        project = None
        if isinstance(project_result, list) and len(project_result) > 0:
            print("extrahieren erstes objekt")
            project = project_result[0] # Extrahieren des ersten Objekts

        # Wenn project ein SQLite Row Objekt ist, hier in ein Dict umwandeln.
        if project is not None and not isinstance(project, dict):
            print("project is not none")
            try:
                project = dict(project) 
            except TypeError:
                project = None 
        
        if not project or project['UserID'] != user_id or project['Status'] != 'QUOTED_AWAITING_CUSTOMER':
            flash("Fehler: Das Angebot ist nicht verfügbar, gehört Ihnen nicht oder wurde bereits bestellt.", 'danger')
            return redirect(url_for('views.home')) 

        final_quote_price = project.get('FinalQuotePrice')
        
        if not final_quote_price:
            flash("Fehler: Kein Preis gefunden. Wenden Sie sich an den Admin.", 'danger')
            return redirect(url_for('views.home'))

        volume_cm3 = project.get('VolumeCM3')
        print_time_min = project.get('PrintTimeMin')
        weight_g = project.get('EstimatedMaterialG')
        if volume_cm3 is None or print_time_min is None or weight_g is None:
            flash("Fehler: Kritische Projektdaten (Volumen/Zeit/Gewicht) fehlen. Admin kontaktieren.", 'danger')
            return redirect(url_for('views.home'))
        # 3. Produktdetails abrufen
        product_result = project_manager.get_project_material_details(project_id)
        
        # product_result ist hier KEINE Liste, sondern ein einzelnes Dict oder None
        if not product_result:
            flash("Fehler: Das zum Angebot gehörige Produkt (ProductID) wurde nicht gefunden.", 'danger')
            return redirect(url_for('views.home'))
        
        product_id = product_result['ProductID']
        product_type = product_result['MaterialType']
        quantity = product_result['StockQuantity']
        price_per_unit = final_quote_price 
        
        # 4. Bestellung und Bestellpositionen erstellen
        order_id = 'ORDE_' + str(uuid.uuid4())
        position_id = 'POSI_' + str(uuid.uuid4())
        order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        order_manager.make_new_single_order(order_id, user_id, order_date, final_quote_price, project_id)
        
        order_manager.make_single_order_position(position_id, order_id, product_id, product_type, quantity, price_per_unit)
        
        new_status='ORDER_STARTED'
        
        # 5. *** PROJEKTSTATUS AKTUALISIEREN ***
        project_manager.update_project_status(
            project_id=project_id,
            new_status=new_status, 
            volume_cm3=volume_cm3,
            print_time=print_time_min,
            weight=weight_g
            )

        flash("Bestellung erfolgreich erstellt. Bitte wählen Sie nun Liefer- und Zahlungsdetails.", 'success')
        
        # 6. Weiterleitung zur UNIFIZIERTEN Checkout-Seite
        return redirect(url_for('views.checkout_entry', order_id=order_id))

    except Exception as e:
        flash(f"Ein sehr unerwarteter Fehler ist aufgetreten: {e}", 'danger')
        return redirect(url_for('views.home'))
            

@views.route('/checkout/update/<string:order_id>', methods=['POST'])
def update_checkout_details(order_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    order = order_manager.get_order_by_id(order_id)
    
    if not order or order['UserID'] != user_id or order['OrderStatus'] != 'DRAFT':
        flash("Ungültiger Status.", 'danger')
        return redirect(url_for('views.my_reviews'))

    try:
        success, addr_id, pay_id = order_manager.process_checkout_update(user_id, order_id, request.form)
        
        if success:
            order_manager.finalize_order_details(order_id, addr_id, pay_id)
            project_manager.finalize_project_details(order['SourceProjectID'])
            flash("Details gespeichert. Weiter zur Bezahlung.", 'success')
            return redirect(url_for('views.order_success', order_id=order_id))
            
    except Exception as e:
        flash(f"Fehler beim Speichern: {e}", 'danger')
        
    return redirect(url_for('views.checkout_entry', order_id=order_id))

@views.route('/order/success/<string:order_id>') # NEUE ROUTE
def order_success(order_id): # NEUE FUNKTIONSNAME
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an.", 'warning')
        return redirect(url_for('auth.login'))
    """
    Zeigt die finale Bestätigungsseite nach erfolgreicher Bestellung an.
    """
    user_id = session['user_id']
    order = order_manager.get_order_by_id(order_id)
    
    if not order or order['UserID'] != user_id or order['OrderStatus'].strip().upper() not in ('ORDER_FINALIZED', 'PAID'):
        flash("Bestellung nicht gefunden oder ist nicht finalisiert.", 'danger')
        return redirect(url_for('views.my_orders')) # Gehen Sie zur Bestellübersicht
        
    # Rendert die Bestätigungsseite
    return render_template("order_placed.html", order=order)

@views.route('/my_orders', methods=['GET'])
def my_orders():
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an, um Ihre Bestellungen einzusehen.", 'warning')
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    logged_in = True # Für das base.html-Template
    
    try:
        # 2. BESTELLUNGEN ABRUFEN (OrderManager muss sqlite3.Row zurückgeben)
        my_orders_raw = order_manager.get_orders_by_user(user_id) 

        processed_orders = []

        for order in my_orders_raw:
            # 1. Hauptbestellung konvertieren (um Felder wie OrderID, OrderAmount zu bekommen)
            order_dict = dict(order)
            order_id = order_dict.get('OrderID')
            # Standardwert setzen, falls die Menge nicht gefunden wird
            single_quantity = 0 

            if order_id:
                try:
                    # Ruft die Liste der Mengen-Rows ab (z.B. [<sqlite3.Row object 1>, ...])
                    quantities_raw = order_manager.get_orders_quantity(order_id)
                    # WICHTIG: Prüfen, ob überhaupt Ergebnisse da sind und nur das ERSTE Element verwenden
                    if quantities_raw and len(quantities_raw) > 0:
                        # Das erste sqlite3.Row-Objekt in ein Dictionary umwandeln
                        first_quantity_row_dict = dict(quantities_raw[0]) 
                        # Den 'Quantity'-Wert als einzelne Zahl extrahieren
                        # Wir gehen davon aus, dass in dieser Row der Schlüssel 'Quantity' vorhanden ist.
                        single_quantity = first_quantity_row_dict.get('Quantity', 0)
                        print(f"SINGLE{single_quantity}")
                except Exception as e:
                    # print(f"Fehler beim Abruf der Mengen für OrderID {order_id}: {e}")
                    flash("Keine Mengen für Order gefunden",'warning')
                    return redirect(url_for('views.home')) 
                
            # 2. Füge die einzelne Menge (z.B. 4) der aktuellen Bestellung hinzu
            order_dict['Quantity'] = single_quantity 

            # 3. Verarbeite den Betrag (Cent zu Euro)
            amount = order_dict.get('OrderAmount', 'KEY_NOT_FOUND')
            if isinstance(amount, int):
                order_dict['OrderAmountEuro'] = amount / 100.0
            else:
                order_dict['OrderAmountEuro'] = 0.00

            processed_orders.append(order_dict)

            # 4. TEMPLATE RENDERN
        return render_template('my_orders.html', 
                    orders=processed_orders, # Übergibt die Dict-Listen
                    logged_in=logged_in)

    except Exception as e:
        flash('Ein unerwarteter Fehler ist beim Laden Ihrer Bestellungen aufgetreten.', 'danger')
        # Sicherer Fallback (Status 500 nur bei unbekanntem Fehler)
        return render_template('my_orders.html', orders=[]), 500

@views.route('/orders/order_detail/<string:order_id>', methods=['GET'])
def order_detail(order_id):
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an, um Ihre Bestellungen einzusehen.", 'warning')
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    logged_in = True # Für das base.html-Template
    
    try:
        # 2. BESTELLUNG ABRUFEN
        order = order_manager.get_order_by_id(order_id)
        orderpositions = order_manager.get_order_position_for_checkout(order_id)
        address = order_manager.get_address_by_id(order['AddressID']) if order else None
        payment = order_manager.get_payment_by_id(order['PaymentID']) if order else None

         
        if not order or order['UserID'] != user_id:
            flash("Bestellung nicht gefunden oder Zugriff verweigert.", 'danger')
            return redirect(url_for('views.my_orders'))

        # 3. TEMPLATE RENDERN
        return render_template('order_detail.html', 
                               order=order,
                               orderpositions=orderpositions,
                                 address=address,
                                    payment=payment,
                               logged_in=logged_in)

    except Exception as e:
        print(f"Fehler beim Abruf der Bestellung in order_detail: {e}")
        flash('Ein unerwarteter Fehler ist beim Laden Ihrer Bestellung aufgetreten.', 'danger')
        # Sicherer Fallback (Status 500 nur bei unbekanntem Fehler)
        return render_template('order_detail.html', order={}), 500

@views.route('/account/add_address', methods=['GET', 'POST'])
def add_address():
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an.", 'warning')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        # 1. Adresse aus Formular lesen
        # 2. user_manager.add_new_address(...) aufrufen
        # 3. flash('Adresse gespeichert', 'success')
        # 4. return redirect(url_for('views.account_settings')) oder zurück zum Checkout
        pass # Implementierung fehlt noch
        
    # GET-Anfrage: Zeigt das Formular zum Hinzufügen einer Adresse
    return render_template('account/add_address.html', title="Adresse hinzufügen")

@views.route('/what_we_make', methods=['GET'])
def what_we_make():

    return render_template('what_we_make_FAQ.html'), 500

@views.route('/handle_project_start', methods=['GET'])
def handle_project_start():

    return render_template('handle_project_start_FAQ.html'), 500

@views.route('/send_filaments', methods=['GET'])
def send_filaments():

    return render_template('send_filaments_FAQ.html'), 500

