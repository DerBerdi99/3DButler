import sqlite3
from flask import request, redirect, url_for, flash, render_template, Blueprint, session
from flask import current_app
import secrets
import os
import smtplib
import ssl
from email.message import EmailMessage
from .utils import require_csrf
from . import limiter # aus init.py importierter request-limiter

auth = Blueprint('auth', __name__)

def send_system_email(recipient_email, subject, body_html, body_plain):
    """
    Zentrale Funktion für den E-Mail-Versand via SMTP.
    Nutzt Umgebungsvariablen für die Konfiguration.
    """
    smtp_host = os.environ.get('SMTP_HOST', 'localhost')
    smtp_port = int(os.environ.get('SMTP_PORT', '465'))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')
    sender = os.environ.get('SMTP_SENDER', 'noreply@yourdomain.com')

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient_email
    msg.set_content(body_plain)
    msg.add_alternative(body_html, subtype='html')

    try:
        if smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls(context=ssl.create_default_context())
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True
    except Exception as e:
        print(f"Kritischer Mail-Fehler an {recipient_email}: {e}")
        return False

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute, 20 per hour") # Erlaubt maximal 5 Versuche pro Minute pro IP
@require_csrf
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            # DELEGATION: Die gesamte Logik wird an den UserManager übergeben
            success, user_id, user_name, is_admin = current_app.user_manager.verify_login(username, password)

            if success:
                # Login erfolgreich: Session setzen und umleiten
                session['user_id'] = user_id
                session['username'] = user_name
                session['is_admin'] = is_admin

                if is_admin:
                    return redirect(url_for('admin_views.dashboard'))
                else:
                    return redirect(url_for('views.home'))
            else:
                # Login fehlgeschlagen (Passwort oder Benutzername falsch)
                flash('Incorrect username or password.', 'danger')
                return render_template('index.html', login_success=False)

        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred during login. Please try again.', 'danger')
            return render_template('index.html', login_success=False)

    return render_template('index.html')

@auth.route('/logout')
def logout():
    current_app.user_manager.logout_user(session)
    return redirect(url_for('auth.login'))

@auth.route('/registrationform')
def registrationform():
    if 'user_id' in session:
        flash('Sie sind bereits eingeloggt.','info')
        return redirect(url_for('views.home'))
    else:
        return render_template('register.html')

@auth.route('/send', methods=['GET', 'POST'])
@require_csrf
def register():
    if 'user_id' in session:              
        flash('Sie sind bereits eingeloggt. Eine weitere Registrierung ist nicht möglich.', 'info')
        return redirect(url_for('views.home'))   
    if request.method == 'POST':
        username = request.form.get('username')
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        email = request.form.get('email')
        phone = request.form.get('phone')
        zipcode = request.form.get('zipcode')
        gender = request.form.get('gender')
        password = request.form.get('password')
        passwordvalidation = request.form.get('passwordvalidation')
        street_name = request.form.get('street-name')
        street_number = request.form.get('street-number')
        city = request.form.get('city')
        country = request.form.get('country')

        # Manual Validation
        errors = {}  # Dictionary to store error messages

        if not firstname:
            errors['firstname'] = "First name is required."
        if not lastname:
            errors['lastname'] = "Last name is required."
        if not email:
            errors['email'] = "Email is required."
        if not zipcode:
            errors['zipcode'] = "Zipcode is required."
        if not city:
            errors['city'] = "City is required."
        if not country:
            errors['country'] = "Country is required."

        # Add other required field checks, is zipcode, city (address stuff) necessary from the beginning?

        if password != passwordvalidation:
            errors['password'] = "Passwords do not match."
        if len(password) < 8:
            errors['password'] = "Password must be at least 8 characters long."

        if errors:  # If there are any validation errors
            for field, error in errors.items():
                flash(f"Error in {field.capitalize()}: {error}", 'danger') # capitalize the field name
            return render_template('home.html', errors=errors) # Pass errors and form data back to the template

        if len(errors) == 0:  # Oder einfach der Code, der nach dem Fehler-Block kommt
            # Erstelle ein Dictionary 'data' mit allen benötigten Werten
            data = {
                'username': username,
                'firstname':firstname,
                'lastname':lastname,
                'email':email,
                'phone':phone,
                'zipcode':zipcode,
                'gender':gender,
                'password':password,
                'passwordvalidation':passwordvalidation,
                'street_name':street_name,
                'street_number':street_number,
                'city':city,
                'country':country
            }

            try:
                # NEU: Vorab-Check auf Duplikate
                existing_user = current_app.user_manager.find_user_by_email(email)
                if existing_user:
                    flash('Diese E-Mail-Adresse ist bereits registriert. Bitte nutzen Sie den Login.', 'warning')
                    return render_template('register.html') # Zurück zum Formular
                # 1. User in DB anlegen und Token generieren
                verification_token_plain = current_app.user_manager.register_user(data)

                # --- PHASE 1: E-Mail-Versand (Zentrale Engine nutzen) ---
                subject = "Aktiviere dein Konto"
                plain = f"Willkommen! Dein Verifizierungs-Code lautet: {verification_token_plain}"
                html = f"""
                    <h3>Willkommen bei {os.environ.get('APP_NAME', 'unserem Service')}!</h3>
                    <p>Dein Verifizierungs-Code lautet: <b>{verification_token_plain}</b></p>
                    <p>Bitte gib diesen Code auf der Verifizierungsseite ein.</p>
                """

                # Aufruf der zentralen Engine
                send_system_email(data['email'], subject, html, plain)

                # Erfolgsmeldung und Weiterleitung
                flash('Registration successful! Please check your email to verify your account.', 'success')
                return redirect(url_for('auth.verify_account'))

            except sqlite3.IntegrityError as e:
                # ... (Ihre bestehende Fehlerbehandlung)
                if 'email' in str(e).lower():
                    flash('Email already exists.', 'danger')
                elif 'username' in str(e).lower():
                     flash('Username already exists.', 'danger')
                else:
                     flash('A database conflict occurred.', 'danger')
                return render_template('register.html', data=data)

            except Exception as e:
                # Allgemeiner Datenbankfehler
                # ... (Ihre bestehende Fehlerbehandlung)
                flash('An unexpected error occurred during registration.', 'danger')
                print(f"Registration Error: {e}")
                return render_template('register.html', data=data)

    # ... (GET-Request-Logik, falls vorhanden)
    return render_template('register.html') # Annahme: /send ist die Seite mit dem Registrierungsformular

#Email Versand Funktion für Verifizierungs-Emails
def send_verification_email(recipient_email, token):
    html = f"<h3>Willkommen!</h3><p>Dein Code lautet: <b>{token}</b></p>"
    plain = f"Willkommen! Dein Verifizierungs-Code lautet: {token}"
    return send_system_email(recipient_email, "Aktiviere dein Konto", html, plain)
# Speichert den Klartext-Token temporär in der Session, falls keine URL-Weiterleitung genutzt wird
# Dies ist eine einfache Methode, um den Token an die /verify_account-Seite zu übergeben,
# ohne ihn als URL-Parameter zu senden (was sicherer ist).
def store_token_for_verification(user_id, token):
    session['pending_verification'] = {'user_id': user_id, 'token': token}



@auth.route('/verify_account', methods=['GET', 'POST'])
@require_csrf
def verify_account():
    if request.method == 'GET':
        return render_template('verify_account.html')

    if request.method == 'POST':
        submitted_token = request.form.get('verification_code')
        user_email = request.form.get('email')
        print(f"DEBUG: Versuche Aktivierung für {user_email} mit Code {submitted_token}") # Konsole prüfen!

        if not submitted_token or not user_email:
            flash('Bitte E-Mail und Code eingeben.', 'warning')
            return render_template('verify_account.html')

        try:
            if current_app.user_manager.activate_user_with_token(user_email, submitted_token):
                # WICHTIG: Session live aktualisieren
                session['is_active'] = 1 
                
                flash('Konto verifiziert! Du kannst jetzt Projekte starten.', 'success')
                # Optional: Wenn ein Ziel in der Session war (next_url), dahin schicken
                return redirect(url_for('views.start_project'))
            else:
                flash('Code ungültig oder abgelaufen.', 'danger')
                return render_template('verify_account.html')

        except Exception as e:
            flash('Ein Fehler ist aufgetreten.', 'danger')
            return render_template('verify_account.html')

@auth.route('/resend_verification', methods=['GET', 'POST'])
def resend_verification():
    # Placeholder: Wir implementieren die Logik später.
    # Wichtig: Der Endpunkt 'auth.resend_verification' existiert nun für url_for()
    return "Die Seite zum erneuten Senden des Codes kommt noch..."

@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = current_app.user_manager.find_user_by_email(email)

        if user:
            try:
                # 1. Token generieren & speichern
                token = secrets.token_urlsafe(32)
                current_app.user_manager.save_reset_token(user['UserID'], token)

                # 2. Link erstellen
                reset_url = url_for('auth.reset_password', token=token, _external=True)

                # 3. Zentrale Mail-Engine nutzen
                subject = "Passwort zurücksetzen"
                plain = f"Klicken Sie auf den Link, um Ihr Passwort zurückzusetzen: {reset_url}"
                html = f"<p>Klicken Sie <a href='{reset_url}'>hier</a>, um Ihr Passwort zurückzusetzen.</p>"
                
                send_system_email(email, subject, html, plain)

            except Exception as e:
                print(f"Reset Error: {e}")
                # Wir flashen trotzdem Erfolg (Sicherheit!), loggen aber den Fehler intern.
        
        flash('Wenn die Adresse existiert, wurde ein Link gesendet.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')

@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        return render_template('reset_password.html', token=token)

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        password_confirm = request.form.get('password_confirm')

        if not new_password or not password_confirm:
            flash('Please enter your new password.', 'warning')
            return render_template('reset_password.html', token=token)

        if new_password != password_confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('reset_password.html', token=token)

        try:
            if current_app.user_manager.reset_password_with_token(token, new_password):
                flash('Your password has been successfully reset. You can now log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Invalid or expired reset token.', 'danger')
                return render_template('reset_password.html', token=token)

        except Exception as e:
            flash('An error occurred while resetting your password.', 'danger')
            print(f"Password Reset Error: {e}")
            return render_template('reset_password.html', token=token)