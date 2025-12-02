import sqlite3
from flask import request, redirect, url_for, flash, render_template, Blueprint, session
import secrets
import os
import smtplib
import ssl
from email.message import EmailMessage
from .user_manager import UserManager #so importiert man halt klassen (mit nem punkt)
auth = Blueprint('auth', __name__)
user_manager = UserManager()



@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            # DELEGATION: Die gesamte Logik wird an den UserManager übergeben
            success, user_id, user_name, is_admin = user_manager.verify_login(username, password)

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
    user_manager.logout_user(session)
    return redirect(url_for('auth.login'))

@auth.route('/registrationform')
def registrationform():
    if 'user_id' in session:
        flash('Sie sind bereits eingeloggt.','info')
        return redirect(url_for('views.home'))
    else:
        return render_template('register.html')

@auth.route('/send', methods=['GET', 'POST'])
def register():
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
                # user_manager.register_user gibt jetzt den Klartext-Token zurück
                verification_token_plain = user_manager.register_user(data)

                # --- PHASE 1: E-Mail-Versand ---
                send_verification_email(data['email'], verification_token_plain)

                # Erfolgsmeldung und Weiterleitung
                flash('Registration successful! Please check your email to verify your account.', 'success')

                # --- PHASE 2: Weiterleitung zur Verifizierungsseite ---
                # Statt zum Login, leiten wir zur Verifizierungsseite weiter
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
# Simuliert den E-Mail-Versand. Muss später durch einen echten E-Mail-Dienst ersetzt werden.
def send_verification_email(recipient_email, verification_token):
    """
    Simuliert den Versand einer E-Mail mit dem Verifizierungs-Token.
    """
    # Im echten Code würden Sie hier eine Verbindung zu SendGrid/Mailgun/etc. herstellen
    print(f"--- E-Mail an {recipient_email} gesendet ---")
    print(f"Ihr Verifizierungs-Code: {verification_token}")
    print(f"Verifizierungs-Link: {url_for('auth.verify_account', token=verification_token, _external=True)}")
    print("---------------------------------------------")
    # In einer echten App: mailer.send(message)
    pass

# Speichert den Klartext-Token temporär in der Session, falls keine URL-Weiterleitung genutzt wird
# Dies ist eine einfache Methode, um den Token an die /verify_account-Seite zu übergeben,
# ohne ihn als URL-Parameter zu senden (was sicherer ist).
def store_token_for_verification(user_id, token):
    session['pending_verification'] = {'user_id': user_id, 'token': token}

@auth.route('/verify_account', methods=['GET', 'POST'])
def verify_account():
    # Phase 2: GET - Seite anzeigen
    if request.method == 'GET':
        return render_template('verify_account.html') # Sie benötigen dieses Template

    # Phase 3: POST - Verifizierung & Aktivierung
    if request.method == 'POST':
        # Holen des eingegebenen Codes vom Formular
        submitted_token = request.form.get('verification_code')
        user_email = request.form.get('email') # Es ist oft nützlich, die E-Mail abzufragen

        if not submitted_token or not user_email:
            flash('Please enter your email and the verification code.', 'warning')
            return render_template('verify_account.html')

        try:
            # Wir rufen eine neue Funktion im user_manager auf, um die Validierung durchzuführen
            if user_manager.activate_user_with_token(user_email, submitted_token):
                # Validierung erfolgreich: User ist aktiv (IsActive=1)
                flash('Your account has been successfully verified! You can now log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                # Validierung fehlgeschlagen (Code falsch oder abgelaufen)
                flash('Verification failed: The code is invalid or has expired.', 'danger')
                return render_template('verify_account.html')

        except Exception as e:
            flash('An unexpected error occurred during verification.', 'danger')
            print(f"Verification Error: {e}")
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

        # 1. Benutzer anhand der E-Mail suchen
        user = user_manager.find_user_by_email(email)

        if user:
            try:
                # 2. Token generieren (sicher und zeitlich limitiert)
                # Da wir secrets nutzen: Ein simples, langes Token (Ohne itsdangerous-Zeitlimit)
                # Ein echtes System würde hier ein Timed-Token nutzen!
                token = secrets.token_urlsafe(32)

                # 3. Token in der Datenbank beim Benutzer speichern
                # Diese Funktion müssen Sie im user_manager implementieren
                user_manager.save_reset_token(user['UserID'], token)

                # 4. Reset-Link erstellen und E-Mail senden (Diese Funktion fehlt noch!)

                reset_url = url_for('auth.reset_password', token=token, _external=True)


                def send_reset_email(recipient_email, reset_url):
                    """
                    Sends a password reset email using Python's standard library.
                   SMTP environment variables: (in .env, located in same dir as main.py!!!)
                      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SENDER
                    """
                    smtp_host = os.environ.get('SMTP_HOST', 'localhost')
                    smtp_port = int(os.environ.get('SMTP_PORT', '465'))

                    smtp_user = os.environ.get('SMTP_USER')
                    smtp_pass = os.environ.get('SMTP_PASS')
                    sender = os.environ.get('SMTP_SENDER', 'hanniberdi@gmail.com')  #nur fallback

                    msg = EmailMessage()
                    msg['Subject'] = 'Password Reset Request'
                    msg['From'] = sender
                    msg['To'] = recipient_email

                    plain = f"""Hello,

                You (or someone) requested a password reset for your account.
                Click the link below to reset your password:

                {reset_url}

                If you did not request this, please ignore this email.

                Regards,
                Support Team
                """
                    html = f"""<html>
                  <body>
                    <p>Hello,</p>
                    <p>You (or someone) requested a password reset for your account.</p>
                    <p><a href="{reset_url}">Click here to reset your password</a></p>
                    <p>If you did not request this, please ignore this email.</p>
                    <p>Regards,<br/>Support Team</p>
                  </body>
                </html>"""

                    msg.set_content(plain)
                    msg.add_alternative(html, subtype='html')

                    try:
                        if smtp_port == 465:
                            context = ssl.create_default_context()
                            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                                if smtp_user and smtp_pass:
                                    server.login(smtp_user, smtp_pass)
                                server.send_message(msg)
                        else:
                            with smtplib.SMTP(smtp_host, smtp_port) as server: # <- 1. Unverschlüsselte Verbindung herstellen
                                server.ehlo()

                                # Wichtig: Hier sollte starttls() ausgeführt werden, wie ich es korrigiert hatte,
                                # um die Verbindung auf TLS umzustellen.
                                # Dies stellt sicher, dass die Verbindung verschlüsselt wird.
                                server.starttls(context=ssl.create_default_context())

                                if smtp_user and smtp_pass:
                                    # Jetzt, da die Verbindung verschlüsselt ist,
                                    # erfolgt die Anmeldung mit den geheimen Daten.
                                    server.login(smtp_user, smtp_pass)

                                server.send_message(msg)

                    except Exception as e:
                        # Log and re-raise so the outer handler can show an error if needed
                        print(f"Error sending reset email to {recipient_email}: {e}")
                        raise

                # send the reset email (uses variables from the surrounding scope)
                send_reset_email(email, reset_url)
                # 5. Erfolgsmeldung anzeigen, ohne zu verraten, ob die E-Mail existiert (Sicherheitsstandard)
                flash('Wenn die E-Mail-Adresse in unserem System existiert, haben wir Ihnen einen Link zum Zurücksetzen Ihres Passworts gesendet.', 'info')

                return redirect(url_for('auth.login'))

            except Exception as e:
                # Fehler bei der Token-Speicherung oder beim E-Mail-Versand
                print(f"Fehler beim Passwort-Reset für {email}: {e}")
                flash('Ein interner Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.', 'danger')
        else:
            # Sicherheitsstandard: Sende die gleiche Meldung, um keine Kontoinformationen preiszugeben
            flash('Wenn die E-Mail-Adresse in unserem System existiert, haben wir Ihnen einen Link zum Zurücksetzen Ihres Passworts gesendet.', 'info')

            # Wichtig: Bleibe auf der Seite und zeige die Flash-Nachricht an
            return redirect(url_for('auth.forgot_password'))


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
            if user_manager.reset_password_with_token(token, new_password):
                flash('Your password has been successfully reset. You can now log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Invalid or expired reset token.', 'danger')
                return render_template('reset_password.html', token=token)

        except Exception as e:
            flash('An error occurred while resetting your password.', 'danger')
            print(f"Password Reset Error: {e}")
            return render_template('reset_password.html', token=token)