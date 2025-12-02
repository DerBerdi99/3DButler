from flask import Blueprint,render_template, flash, session, url_for, redirect, request, abort
import os
import sqlite3
import uuid
from datetime import datetime
from .project_manager import ProjectManager
from .order_manager import OrderManager
from .user_manager import UserManager   

DB_PATH  = os.getenv('DB_PATH')
TEMP_UPLOAD_FOLDER = os.environ.get('UPLOAD_DIR') or os.path.join(os.getcwd(), 'temp_uploads')
views = Blueprint('views', __name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))  # Relative to blueprint file
project_manager = ProjectManager() 
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
        return render_template('home.html', logged_in=True, username=username)  # Pass logged_in and username to the template
    else:
        return render_template('home.html', logged_in=False) # Important: Pass logged_in as False if user is not logged in

@views.route('/cart')  # Your cart route
def cart():
    if 'user_id' not in session:
        flash('You must be logged in to view the cart.', 'info')
        return redirect(url_for('auth.login'))

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        user_id = session['user_id']
        cursor.execute("""
            SELECT sc.CartItemID, p.ProductID, p.ProductName, p.ProductDescription, pp.Price, sc.Quantity, p.ProductImage 
            FROM ShoppingCart sc
            JOIN Products p ON sc.ProductID = p.ProductID
            JOIN ProductPrice pp ON p.ProductID = pp.ProductID
            WHERE sc.UserID = ?
        """, (user_id,))
        cart_items = cursor.fetchall()
        
    except Exception as e:
        print(f"Error fetching cart items: {e}")
        flash('An error occurred. Please try again.', 'danger')
        cart_items = []
    finally:
        conn.close()
    
    print(f"Cart items: {cart_items}")  # just console output
    return render_template('cart.html', cart_items=cart_items)
     
    
@views.route('/products/<product_id>')
def product_detail(product_id):
    print(f"product_id (Received): {product_id} (Type: {type(product_id)})")  # Print the received ID

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        query = """
            SELECT p.ProductName, p.ProductDescription, p.StockQuantity, pp.Price, p.ProductImage
            FROM Products p
            INNER JOIN ProductPrice pp ON p.ProductID = pp.ProductID COLLATE NOCASE
            WHERE p.ProductID = ? COLLATE NOCASE
        """
        cursor.execute(query, (product_id,))  # Use the product_id directly
        

        product_data = cursor.fetchone()
        conn.close()

        if product_data:
            product_name, product_description, stock_quantity, price, product_image = product_data
            print(f"Product details: {product_name}, {product_description}, {stock_quantity}, {price}, {product_image}")
            return render_template('product_detail.html', product_name=product_name, product_description=product_description, stock_quantity=stock_quantity, price=price, product_image=product_image,product_id=product_id)
        else:
            print("Product data is None. No matching product found.")
            flash('Product not found.', 'warning')
            return redirect(url_for('views.home'))

    except Exception as e:
        print(f"Error fetching product details: {e}")
        flash('An error occurred. Please try again.', 'danger')
        return redirect(url_for('views.home'))


@views.route('/add_to_cart/<product_id>', methods=['POST'])  # Add to cart route
def add_to_cart(product_id):
    if 'user_id' not in session:  # Check if logged in
        flash('You must be logged in to add to cart.', 'info')
        return redirect(url_for('auth.login'))

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if the product exists and get price and stock
        cursor.execute("""
            SELECT pp.Price, p.StockQuantity 
            FROM Products p
            JOIN ProductPrice pp ON p.ProductID = pp.ProductID
            WHERE p.ProductID = ?
        """, (product_id,))
        product_info = cursor.fetchone()

        if product_info:
            price, stock = product_info
            quantity = int(request.form.get('quantity', 1))  # Get quantity from form, default is 1
            if quantity <= 0:
                flash('Invalid quantity.', 'warning')
                return redirect(url_for('views.product_detail', product_id=product_id))

            if quantity > stock:
                flash(f'Only {stock} units of this product are in stock.', 'warning')
                return redirect(url_for('views.product_detail', product_id=product_id))

            user_id = session['user_id']

            # Add to cart (you'll need a cart mechanism - session, database, etc.)
            cart = session.get('cart', {})  # Get cart from session or create empty dict
            if product_id in cart:
                cart[product_id]['quantity'] += quantity
            else:
                cart[product_id] = {'quantity': quantity, 'price': price}

            session['cart'] = cart  # Update the session with the cart

            # Add entry to the ShoppingCart table
            cursor.execute("""
                INSERT INTO ShoppingCarts (UserID, ProductID, Quantity)
                VALUES (?, ?, ?)
            """, (user_id, product_id, quantity))
            conn.commit()

            flash('Product added to cart!', 'success')
            return redirect(url_for('views.product_detail', product_id=product_id))

        else:
            flash('Product not found.', 'warning')
            return redirect(url_for('views.shop'))

    except Exception as e:
        print(f"Error adding to cart: {e}")
        flash('An error occurred. Please try again.', 'danger')
        return redirect(url_for('views.shop'))

    finally:
        conn.close()

@views.route('/cart/delete/<item_id>', methods=['POST'])
def delete_cart_product(item_id):
    if 'user_id' not in session:  # Check if logged in
        flash('You must be logged in to remove cart items.', 'info')
        return redirect(url_for('auth.login'))
    user_id = session['user_id']

    try:
        conn = sqlite3.connect(DB_PATH)  # Replace with your database file
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Delete the item from the WishList table based on UserID and ItemID
        cursor.execute("DELETE FROM ShoppingCarts WHERE UserID = ? AND CartItemID = ?", (user_id, item_id))
        conn.commit()
        flash('Item removed from cart.', 'success')

    except sqlite3.Error as e:
        flash(f'An error occurred: {e}', 'error')

    finally:
        if conn:
            conn.close()

    return redirect(url_for('views.cart'))   

@views.route('/add_to_wishlist/<product_id>', methods=['POST'])
def add_to_wishlist(product_id):
    if 'user_id' not in session:
        flash('You must be logged in to add to cart.', 'info')
        return redirect(url_for('auth.login'))
    else:
        userid = session['user_id']
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""SELECT Products.ProductDescription,ProductPrice.Price,Products.ProductImage,Products.ProductID FROM Products JOIN ProductPrice ON Products.ProductID = ProductPrice.ProductID WHERE Products.ProductID = ?""", (product_id,))
            product = cursor.fetchone()
            if product:
                articlename, price, image, product_id = product
                cursor.execute("INSERT INTO WishLists (ArtikelName, Price, UserID, ProductImage, ProductID) VALUES (?, ?, ?, ?, ?)", (articlename, price, userid, image, product_id))
                conn.commit()
                flash("Item added to wishlist", "success")
            else:
                flash("Product not found.", "danger")
            cursor.execute("SELECT * FROM WishLists WHERE UserID = ?", (userid,)) #correct tuple.
            wishlist_items = cursor.fetchall()
            wishlist_items = [(item[0], item[1], item[2], item[3] ,item[4]) for item in wishlist_items]
            return render_template('wishlist.html', items=wishlist_items)
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            flash('An error occurred while fetching products.', 'danger')
            return render_template('error.html'), 500
        finally:
            if conn:
                conn.close()
    


@views.route('/wishlist')
def wishlist():
    if 'user_id' not in session:  # Check if logged in
        flash('You must be logged in to go to wishlist.', 'info')
        return redirect(url_for('auth.login'))
    else:
        userid = session['user_id']
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # Fetch all Wishlist items from the database
            cursor.execute("SELECT * FROM WishLists WHERE UserID = ?",(userid,))
            wishlist_items = cursor.fetchall()
            wishlist_items = [(item[0],item[1],item[2],item[3],item[4]) for item in wishlist_items]
            return render_template('wishlist.html', items=wishlist_items) 
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            flash('An error occurred while fetching products.', 'danger') 
            return render_template('error.html'), 500  

        finally:
            if conn:
                conn.close()

@views.route('/wishlist/delete/<product_id>', methods=['POST'])
def delete_wishlist_product(product_id):
    if 'user_id' not in session:  # Check if logged in
        flash('You must be logged in to remove wishlist items.', 'info')
        return redirect(url_for('auth.login'))
    user_id = session['user_id']

    try:
        conn = sqlite3.connect(DB_PATH)  # Replace with your database file
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Delete the item from the WishList table based on UserID and ProductID
        cursor.execute("DELETE FROM WishList WHERE UserID = ? AND ProductID = ?", (user_id, product_id))
        conn.commit()
        flash('Item removed from wishlist.', 'success')

    except sqlite3.Error as e:
        flash(f'An error occurred: {e}', 'error')

    finally:
        if conn:
            conn.close()

    return redirect(url_for('views.wishlist'))   

@views.route('/check_payment', methods=['GET', 'POST'])
def check_payment():
    if 'user_id' not in session:  # Check if logged in
        flash('You must be logged in to  check payment.', 'info')
        return redirect(url_for('auth.login'))
    
    
    user_id = session['user_id']
    conn = None 
    
    try:
        print("ESTABLISH CONN TO PAYMENT")
        conn = sqlite3.connect(DB_PATH)  
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        print("ESTABLISHED...")
        if request.method == 'GET':
            print("METHOD IS GET...SELECT STARTING..")
            # Prüfen, ob Zahlungsinfo existiert
            cursor.execute("SELECT * FROM Payments WHERE UserID = ?", (user_id,))
            payment_info = cursor.fetchone()
            print("CURSOR FETCHED DATA")
            if payment_info:
                print("PAYMENT INFO FULL")
                # Leitet den Nutzer zur zentralen Checkout-Einstiegsseite weiter
                return redirect(url_for('views.checkout_entry')) 
            else:
                return render_template('payment_form.html')
        
        elif request.method == 'POST':
            print("METHOD IS POST")

            # 1. Die tatsächlich gewählte Methode aus dem Frontend lesen
            payment_method = request.form.get('payment_method')

            # Initialisierung der Variablen
            card_number = request.form.get('card_number')
            expiry = request.form.get('expiry')
            method_name = payment_method.capitalize()
            last_digits = ''

            # 2. Bedingte Validierung: Nur wenn Kreditkarte gewählt
            if payment_method == 'card':
                if not card_number or not expiry:
                    flash('Bitte füllen Sie alle Kartenfelder aus.', 'error')
                    return render_template('payment_form.html') # Passen Sie den Template-Namen an

                last_digits = card_number[-4:] # Letzten 4 Ziffern speichern

            # Wenn PayPal, Wallets oder Rechnung gewählt wurde
            elif payment_method in ['paypal', 'wallets', 'rechnung']:
                # Setze Platzhalter für die DB, da keine Kartendaten gesendet wurden
                expiry = 'N/A'
                last_digits = ''

            else:
                flash('Ungültige Zahlungsmethode ausgewählt.', 'error')
                return render_template('payment_form.html') # Passen Sie den Template-Namen an

            # 3. Speichern in die 'Payments' Tabelle mit der korrekten Methode
            new_payment_id = 'PAYM_' + str(uuid.uuid4())

            cursor.execute("INSERT INTO Payments (PaymentID, UserID, Method, LastIDDigits, Expiry, IsDefaultMethod) VALUES (?, ?, ?, ?, ?, ?)",
                           (new_payment_id, user_id, method_name, last_digits, expiry, 1))
            conn.commit()

            flash('Zahlungsmethode erfolgreich gespeichert.', 'success')
            return redirect(url_for('views.checkout_entry'))

    except sqlite3.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('views.home'))
            
    finally:
        if conn:
            conn.close()

# -----------------------------------------------------------
# ROUTE: checkout_entry (UNIFIZIERTER EINSTIEGspunkt)
# -----------------------------------------------------------
@views.route('/checkout', methods=["GET"])
@views.route('/checkout/<order_id>', methods=["GET"])
def checkout_entry(order_id=None):
    if 'user_id' not in session:  # Check if logged in
        flash('You must be logged in to  check payment.', 'info')
        return redirect(url_for('auth.login'))
    print("checkout_entry Z322")
    """
    Zentraler Einstiegspunkt für den Checkout.
    1. Wenn OrderID vorhanden (Projekt/Quote): Prüft die Order.
    2. Wenn OrderID NICHT vorhanden (Shop Cart): Erstellt eine neue Draft Order.
    """
    user_id = session['user_id']
    conn = None
    
    try:

        conn = sqlite3.connect(DB_PATH)  
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        print("DB VERBIDUNG AUFGEBAUT")
        # Fall 1: OrderID ist NICHT vorhanden (-> Shop Warenkorb)
        if not order_id:
    
            cursor.execute('''
                           SELECT 
                           cp.ProductID,
                           cp.Quantity 
                           FROM CartPositions cp 
                           JOIN ShoppingCarts sc on cp.CartID = sc.CartID
                           WHERE UserID = ?''', (user_id,))
            cart_items = cursor.fetchall()
            
            if not cart_items:
                flash("Ihr Warenkorb ist leer.", "warning")
                return redirect(url_for("views.home"))

            # Berechne den Gesamtbetrag und sammle Order-Positionsdaten
            total_amount = 0
            order_positions = []
            
            for item in cart_items:
                cursor.execute("SELECT ProductPrice FROM ProductPrices WHERE ProductID = ?", (item['ProductID'],))
                price_result = cursor.fetchone()
                
                if price_result and price_result['ProductPrice'] is not None:
                    price = int(price_result['ProductPrice']) 
                    sub_total = price * item['Quantity']
                    total_amount += sub_total
                    
                    # Speichere die Details für die OrderDetails Tabelle
                    order_positions.append({
                        'ProductID': item['ProductID'],
                        'Quantity': item['Quantity'],
                        'Price': price, # Einzelpreis in Cent
                        'SubTotal': sub_total # Gesamtpreis der Position in Cent
                    })
                else:
                    flash(f"Preis für Produkt {item['ProductID']} nicht gefunden.", "error")
                    return redirect(url_for("views.home"))
            
            # --- ERSTELLE DIE NEUE DRAFT-ORDER ---
            order_id = 'ORDE_' + str(uuid.uuid4())
            order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # SourceProjectID = NULL, um Shop-Bestellungen zu kennzeichnen
            cursor.execute("""
                INSERT INTO Orders (OrderID, UserID, OrderDate, OrderAmount, OrderStatus, PaymentStatus, SourceProjectID) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (order_id, user_id, order_date, total_amount, 'DRAFT', 'PENDING_PAYMENT', None))
            
                 
            product_type = 'CART_PRODUCT'  # Typ für Shop-Warenkorb-Produkte
            price_per_unit = 0  # Placeholder, da Preis in OrderPositions gespeichert wird
            # Fülle die OrderPositions Tabelle
            for pos in order_positions:
                position_id = 'POSI_' + str(uuid.uuid4())
                # Annahme: PositionID wird in OrderPositions automatisch erhöht oder wir generieren sie hier.
                # Da sie nicht in der DB-Struktur angegeben war, nutzen wir nur OrderID, ProductID, Quantity.
                price_per_unit = pos['Price']  # Einzelpreis in Cent
                cursor.execute("""
                    INSERT INTO OrderPositions (PositionID, OrderID, ProductID, ProductType, Quantity, PricePerUnit) 
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (position_id, order_id, pos['ProductID'],product_type, pos['Quantity'], price_per_unit))
            
            conn.commit()
            
            # Setze die Positionsdaten direkt in die Order-Variable
            order_positions_for_template = order_positions
            order_amount = total_amount
            source_project_id = None

        # Fall 2: OrderID ist vorhanden (-> Projekt/Quote oder bestehender Draft)
        else:
            print("checkout_entry Z401")
            # Lade bestehende Order-Details
            cursor.execute("SELECT * FROM Orders WHERE OrderID = ? AND UserID = ?", (order_id, user_id))
            order_data = cursor.fetchone()
            
            if not order_data:
                flash("Bestellung nicht gefunden oder Zugriff verweigert.", "error")
                return redirect(url_for("views.home"))
                
            order_amount = order_data['OrderAmount']
            source_project_id = order_data['SourceProjectID']

            # Lade Order-Positionen (OrderDetails) und Preise für das Template
            cursor.execute("""
                SELECT op.ProductID, op.Quantity, pp.ProductPrice, p.ProductName
                FROM OrderPositions op
                JOIN ProductPrices pp ON op.ProductID = pp.ProductID
                JOIN Products p ON op.ProductID = p.ProductID
                WHERE op.OrderID = ?
                """, (order_id,))
            
            order_positions_for_template = []
            for item in cursor.fetchall():
                 order_positions_for_template.append({
                    'ProductName': item['ProductName'],
                    'Quantity': item['Quantity'],
                    'ProductPrice': item['ProductPrice'], # Einzelpreis in Cent
                    'SubTotal': item['ProductPrice'] * item['Quantity']
                })
            print("ORDER POS: ", order_positions_for_template)
        # --- UNIFIZIERTE DATEN FÜR CHECKOUT_DETAILS.HTML LADEN ---
        
        # 1. Adressen laden
        cursor.execute("SELECT * FROM Addresses WHERE UserID = ? ORDER BY IsDefaultShipping DESC", (user_id,))
        addresses = cursor.fetchall()

        # 2. Zahlungsweisen laden
        cursor.execute("SELECT * FROM Payments WHERE UserID = ? ORDER BY IsDefaultMethod DESC", (user_id,))
        payment_methods = cursor.fetchall()
        
        if not addresses:
             flash("Bitte legen Sie zuerst eine Lieferadresse an.", "info")
             # Hier müsste zur Add-Address-Seite geleitet werden
        
        if not payment_methods:
             flash("Bitte hinterlegen Sie zuerst eine Zahlungsart.", "info")
             return redirect(url_for("views.check_payment"))

        order_data = dict(order_data)
        # Order-Daten für das Template zusammenstellen (einheitliches Format)
        order_for_template = {
            'OrderID': order_id,
            'AddressID': order_data.get('AddressID') if order_id else None,
            'PaymentID': order_data.get('PaymentID') if order_id else None,
            'SourceProjectID': source_project_id
        }
        print("checkout_entry Z457")
        return render_template(
            'checkout_details.html',
            order=order_for_template,
            positions=order_positions_for_template,
            total_amount=order_amount, # Betrag in EUR
            addresses=addresses,
            payment_methods=payment_methods,
            # user=current_user, # Kann entfernt werden, wenn login_required genutzt wird
            title="Checkout Abschließen"
        )

    except sqlite3.Error as e:
        flash(f"Database error during checkout preparation: {e}", "error")
        return redirect(url_for("views.home"))
        
    finally:
        if conn:
            conn.close()

@views.route('/shop')  # New route for Steinplatten (Stone Plates)
def shop():
    logged_in = 'user_id' in session
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Fetch all Steinplatten products from the database  # naja steinplatten ist natürliich nur ein beispiel und jetzt obsolet, späterersetzen durch categorie
        cursor.execute("SELECT * FROM Products WHERE IsShopReady = 1")  # Assuming you have a 'Category' column
        all_products = cursor.fetchall()
        all_products = [(product[11], product[4], product[5],product[9],product[0]) for product in all_products]
        return render_template('shop.html', products=all_products, logged_in=logged_in)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        flash('An error occurred while fetching products.', 'danger') # Flash the message
        return render_template('error.html'), 500  # Or redirect to an error page

    finally:
        if conn:
            conn.close()

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
    """
    Verarbeitet das POST-Formular zum Senden einer neuen Nachricht vom Kunden.
    
    :param project_id: Die ID des Projekts, zu dem die Nachricht gehört.
    """
    
    # 1. SICHERHEIT: Login-Check
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an, um Ihre Projekte einzusehen.", 'warning')
        return redirect(url_for('auth.login'))
        
    # 1. Extrahieren der Nachricht aus dem Formular
    # Der Name 'messageText' kommt vom 'name'-Attribut des HTML-Input-Feldes.
    message_text = request.form.get('messageText', '').strip()
    
    # Optional: Prüfen Sie, ob die Nachricht nicht leer ist.
    if not message_text:
        # Fügen Sie eine Fehlermeldung hinzu (optional)
        flash('Nachricht kann nicht leer sein.', 'danger')
        return redirect(url_for('views.project_detail', project_id=project_id))
    
    # 2. Ermitteln des Senders (in diesem Fall der Kunde/Benutzer)
    # HINWEIS: Ersetzen Sie 'User' durch die tatsächliche Logik zur Ermittlung des eingeloggten Benutzers.
    # Hier verwenden wir den festen Wert 'User', da der Kunde sendet.
    sender = 'User' 
    
    try:
        # Erstellen einer neuen Nachricht User > Admin

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        comm_id = 'COMM_' + str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO ProjectMessages (CommID, ProjectID, SenderType, MessageText, Timestamp, IsUnreadAdmin, RequiresFileUpload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (comm_id, project_id, sender, message_text, timestamp, 1, 0))

        conn.commit()
        conn.close()

        flash('Nachricht erfolgreich gesendet.', 'success')
        
    except Exception as e:
        # Fehlerbehandlung: Bei einem Datenbankfehler den Benutzer informieren
        print(f"Fehler beim Speichern der Nachricht: {e}")
        flash('Fehler beim Senden der Nachricht. Bitte versuchen Sie es später erneut.', 'danger')
        
    # 4. Weiterleitung zurück zur Detailseite, um die Nachricht sofort anzuzeigen
    # ('project_detail' ist hier der Name Ihrer View-Funktion für die Detailseite)
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
            
'''  

@views.route('/test_checkout_design')   #TestView für das Checkout-Design mit Mock-Daten
def test_checkout_design():
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an.", 'warning')
        return redirect(url_for('auth.login'))
    current_user = session['user_id']
    """
    Rendert das checkout_details.html Template mit Mock-Daten für Design-Tests.
    Umgeht Datenbank und Bestelllogik.
    """
    
    # --- MOCK-DATEN GENERIEREN ---
    
    # 1. Bestell-Objekt (order)
    # Simuliert eine bereits erstellte Bestellung.
    mock_order_id = 'ORDER_DESIGN_TEST_12345'
    order = {
        'OrderID': mock_order_id,
        'UserID': 'MOCK_USER_123',
        # Gesamtbetrag in Cent für 129,99 €
        'OrderAmount': 12999, 
        'AddressID': 'ADDR_DEFAULT_MOCK', # Die vorausgewählte Adresse
        'PaymentID': 'INVOICE_METHOD_ID', # Die vorausgewählte Zahlungsmethode
        'OrderStatus': 'ORDER_CREATED',
        'PaymentStatus': 'PENDING_PAYMENT',
        'SourceProjectID': 'PROJ_MOCK_123'
    }
    
    # 2. Bestellpositionen (positions)
    positions = [
        {
            'PositionID': 'POS_' + str(uuid.uuid4()),
            'ProductName': 'Propeller-Teil 3000 (Custom)',
            'Quantity': 1,
            'Price': 8999, # Preis in Cent (89.99 €)
            'SubTotal': 8999
        },
        {
            'PositionID': 'POS_' + str(uuid.uuid4()),
            'ProductName': 'Zukaufteil: Montageschraube V2',
            'Quantity': 8,
            'Price': 500, # Preis in Cent (5.00 €)
            'SubTotal': 4000
        }
    ]
    
    # 3. Lieferadressen (addresses)
    addresses = [
        # Die Standard-Adresse
        {'AddressID': 'ADDR_DEFAULT_MOCK', 'Street': 'Mockstraße 1', 'City': 'Musterstadt', 'ZIPCode': '12345', 'Country': 'Deutschland', 'IsDefaultShipping': 1},
        {'AddressID': 'ADDR_OTHER_MOCK', 'Street': 'Testing-Allee 42', 'City': 'Probedorf', 'ZIPCode': '54321', 'Country': 'Österreich', 'IsDefaultShipping': 0},
    ]

    # 4. Zahlungsmethoden (payment_methods)
    payment_methods = [
        # Die hinterlegte Methode
        {'PaymentID': 'CARD_VISA_MOCK', 'Method': 'Visa', 'LastIDDigits': '4242', 'Expiry': '12/26', 'IsDefaultMethod': 1},
        {'PaymentID': 'PAYPAL_MOCK', 'Method': 'PayPal', 'LastIDDigits': 'user@mock.com', 'Expiry': 'N/A', 'IsDefaultMethod': 0},
    ]

    # Gesamtbetrag in EUR konvertieren
    total_amount_eur = order['OrderAmount'] / 100.0
    
    return render_template(
        'checkout_details.html',
        order=order,
        positions=positions,
        total_amount=total_amount_eur,
        addresses=addresses,
        payment_methods=payment_methods,
        user=current_user, # Optional, falls Ihre base.html user benötigt
        title="Checkout Design Test"
    )

'''

@views.route('/checkout/update/<string:order_id>', methods=['POST'])
def update_checkout_details(order_id):
    if 'user_id' not in session:
        flash("Bitte melden Sie sich an.", 'warning')
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    selected_address_id = request.form.get('address_id') #holt die (evtl) neue addresse
    selected_payment_id = request.form.get('payment_id') #holt die (evtl) neue payment
    
    order = order_manager.get_order_by_id(order_id)
    
    if not order or order['UserID'] != user_id or order['OrderStatus'] != 'DRAFT':
        flash("Bestellung ist nicht mehr im Bearbeitungsstatus.", 'danger')
        return redirect(url_for('views.my_reviews'))
        
    # Validierung der Auswahl
    if not selected_address_id or not selected_payment_id:
        flash("Bitte wählen Sie eine Lieferadresse und eine Zahlungsmethode.", 'warning')
        return redirect(url_for('views.start_order_from_quote', project_id=order['SourceProjectID']))
        
    conn = None 
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # ====================================================================
        # --- LOGIK 1: ADRESS-HANDLING (unverändert) ---
        # ...
        # ====================================================================
        final_address_id_to_use = selected_address_id
        if selected_address_id == 'NEW_ADDRESS':
            new_address_id = f"ADDR_{str(uuid.uuid4())}"
            final_address_id_to_use = new_address_id
            
            # Validierung der neuen Adresse
            street = request.form.get('new_street', '').strip()
            city = request.form.get('new_city', '').strip()
            zip_code = request.form.get('new_zip_code', '').strip()
            country = request.form.get('new_country', '').strip()
            
            if not all([street, city, zip_code, country]):
                flash('Bitte füllen Sie alle Adressfelder für die neue Adresse aus.', category='error')
                return redirect(url_for('views.checkout_entry', order_id=order_id))
                
            cursor.execute("""
                INSERT INTO Addresses (AddressID, UserID, Street, City, Zipcode, Country, IsDefaultShipping) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (new_address_id, str(user_id), street, city, zip_code, country, 0))
        
        # ====================================================================
        # --- LOGIK 2: ZAHLUNGSMETHODEN-HANDLING (FIXED KEY) ---
        # ====================================================================
        final_payment_id_to_use = selected_payment_id
        if selected_payment_id == 'NEW_PAYMENT':
            new_payment_id = f"PAYM_{str(uuid.uuid4())}"
            final_payment_id_to_use = new_payment_id
            
            # NEU: Liest den Wert aus dem korrekten Feld 'payment_method' des Frontends
            method_type_raw = request.form.get('new_payment_type_radio', '').strip() 
            
            if not method_type_raw:
                flash('Bitte wählen Sie die Art der neuen Zahlungsmethode (z.B. Kreditkarte oder PayPal).', category='error')
                return redirect(url_for('views.checkout_entry', order_id=order_id))
                
            token = ''
            last_digits = ''
            expiry = ''
            method_type_db = '' # Der Name, der in die DB gespeichert wird

            if method_type_raw == 'Card': # Wert: 'card' (aus <option value="card">)
                method_type_db = 'Credit Card'
                
                # Holen der Kreditkartenfelder
                token = request.form.get('card_number', '').strip() 
                last_digits = token[-4:] if token and len(token) >= 4 else '****'
                expiry = request.form.get('expiry', '').strip()
                
                # Spezifische Validierung für Kreditkarten
                if not all([token, expiry]):
                    flash('Bitte geben Sie alle Kreditkartendetails ein (Kartennummer und Ablaufdatum).', category='error')
                    return redirect(url_for('views.checkout_entry', order_id=order_id))

            elif method_type_raw == 'PayPal': # Wert: 'paypal'
                method_type_db = 'PayPal'
                # KEINE ZUSÄTZLICHEN FELDER ERFORDERLICH, da dies nur die Option speichert
                token = 'PAYPAL_SAVED' 
                last_digits = 'PayPal'
                expiry = 'N/A'
                
            elif method_type_raw == 'Rechnung' or method_type_raw == 'Invoice':
                # Rechnung / Invoice: optional separate Rechnungsadresse angeben
                method_type_db = 'Invoice'

                # Lese die Invoice-Mask Felder aus dem Formular
                inv_street = request.form.get('new_invoiceStreet', '').strip()
                inv_zip = request.form.get('new_invoiceZipcode', '').strip()
                inv_city = request.form.get('new_invoiceCity', '').strip()
                inv_country = request.form.get('new_invoiceCountry', '').strip()

                # Wenn alle Invoice-Felder ausgefüllt sind, lege eine neue Rechnungsadresse an
                if all([inv_street, inv_zip, inv_city, inv_country]):
                    billing_address_id = f"ADDR_{str(uuid.uuid4())}"
                    cursor.execute("""
                        INSERT INTO Addresses (AddressID, UserID, Street, City, Zipcode, Country, IsDefaultShipping) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (billing_address_id, str(user_id), inv_street, inv_city, inv_zip, inv_country, 0))
                    # Speichere die Billing AddressID im Token-Feld der Payment-Zeile, damit sie wiedergefunden werden kann
                    token = billing_address_id
                else:
                    # Keine separate Rechnungsadresse angegeben -> markiere Rechnung ohne separate Adresse
                    token = 'INVOICE_SAVED'

                last_digits = 'Rechnung'
                expiry = 'N/A'

            elif method_type_raw == 'Wallet': # Wert: 'wallets'
                method_type_db = 'Mobile Wallet'
                # KEINE ZUSÄTZLICHEN FELDER ERFORDERLICH
                token = 'WALLET_SAVED' 
                last_digits = 'Wallet'
                expiry = 'N/A'
                
            else:
                 # Unbekannte Methode
                flash(f'Unbekannte Zahlungsmethode: {method_type_raw}.', category='error')
                return redirect(url_for('views.checkout_entry', order_id=order_id))
                
            # Neue Zahlungsmethode dauerhaft in die PAYMENTS-Tabelle einfügen
            cursor.execute("""
                INSERT INTO Payments (PaymentID, UserID, Method, Token, LastIDDigits, Expiry, IsDefaultMethod) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (new_payment_id, str(user_id), method_type_db, token, last_digits, expiry, 0))

        
        # ====================================================================
        # --- LOGIK 3: FINALES UPDATE DER ORDER (unverändert) ---
        # ====================================================================
        cursor.execute("""
            UPDATE Orders 
            SET AddressID = ?, PaymentID = ?
            WHERE OrderID = ? AND UserID = ?
            """, (final_address_id_to_use, final_payment_id_to_use, str(order_id), str(user_id)))

        # Commit und Finalisierung
        conn.commit()
        
        order_manager.finalize_order_details(
            order_id, 
            final_address_id_to_use, 
            final_payment_id_to_use
        )

        project_manager.finalize_project_details(order['SourceProjectID'])
        flash("Details gespeichert. Weiter zur Bezahlung.", 'success')
        
        # Weiterleitung zur eigentlichen Zahlungsabwicklung
        return redirect(url_for('views.order_success', order_id=order_id))
        
    except Exception as e:
        flash(f"Fehler beim Speichern der Checkout-Details: {e}", 'danger')
        # ... (Fehlerbehandlung)
        return redirect(url_for('views.checkout_entry', order_id=order_id))
    
    finally:
        # Datenbankverbindung im Fehlerfall und Erfolgsfall schließen
        if conn:
            conn.close()

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

