from functools import wraps
from flask import session, redirect, url_for, flash
from flask import current_app



def login_required(f):
    """
    Sichert Routen ab: Überprüft, ob der Benutzer angemeldet ist.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Bitte melden Sie sich an.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def check_active(f):
    """
    Sichert Routen ab: Validiert den IsActive-Status direkt gegen die Datenbank.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')

        # 1. Login-Check (Session)
        if not user_id:
            flash("Bitte melden Sie sich an.", "warning")
            return redirect(url_for('auth.login'))

        # 2. Echtzeit-Check gegen die Datenbank
        # Wir nutzen den user_manager, um den aktuellen Status zu ziehen
        user_data = current_app.user_manager.find_user_by_id(user_id) 
        
        if not user_data:
            session.clear()
            return redirect(url_for('auth.login'))

        # Prüfung des IsActive Flags (Spalte aus deiner Tabelle)
        if user_data['IsActive'] != 1:
            flash("Ihr Konto ist noch nicht verifiziert.", "warning")
            return redirect(url_for('auth.verify_account'))

        # 3. Zugriff gewährt
        return f(*args, **kwargs)

    return decorated_function

def check_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        user = current_app.user_manager.find_user_by_id(user_id)
        
        if not user or not (user.get('IsAdmin') == 1 and user.get('IsActive') == 1):
            flash("Admin-Rechte erforderlich!", "danger")
            return redirect(url_for('views.home'))
        return f(*args, **kwargs)
    return decorated_function
# Da die UserManager-Instanz und der Import der Klasse hier nicht mehr benötigt werden,
# können sie aus dieser Datei entfernt werden, um die Architektur sauber zu halten.