from functools import wraps
from flask import session, redirect, url_for, flash, Blueprint
# Entfernt: from .user_manager import UserManager und user_manager = UserManager()
# Die Instanz des Managers ist hier nicht mehr nötig, da wir die Session prüfen.

# Behalte den Blueprint-Platzhalter, falls dieses Modul ihn definiert.
# HINWEIS: Es ist besser, den Blueprint (admin) in der admin_views.py zu definieren.
# admin = Blueprint('admin', __name__)


def check_admin(f):
    """
    Sichert Routen ab: Prüft, ob der eingeloggte Benutzer Admin (IsAdmin=1) ist,
    indem der in der Session gespeicherte Wert 'is_admin' geprüft wird.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')

        # 1. Login-Check
        if not user_id:
            flash("Bitte melden Sie sich an, um diesen Bereich zu sehen.", "warning")
            return redirect(url_for('auth.login'))

        # 2. Admin-Rollen-Check (OPTIMIERT: Prüft nur die Session)
        is_admin_flag = session.get('is_admin')

        # Wir prüfen explizit auf den Wert 1 (oder True), wie er aus der DB kam.
        if is_admin_flag != 1:
            # Zugriff verweigert: Der Benutzer ist eingeloggt, aber kein Admin.
            flash("Zugriff verweigert. Sie benötigen Administratorrechte.", "danger")
            return redirect(url_for('views.home'))

        # 3. Zugriff gewährt
        return f(*args, **kwargs)

    return decorated_function

# Da die UserManager-Instanz und der Import der Klasse hier nicht mehr benötigt werden,
# können sie aus dieser Datei entfernt werden, um die Architektur sauber zu halten.