from functools import wraps
from flask import session, redirect, url_for, flash, request



def require_csrf(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            expected = session.get('csrf_token')
            submitted = request.form.get('csrf_token')
            if not expected or submitted != expected:
                flash('Ungültige Anfrage (CSRF-Fehler).', 'danger')
                session.pop('csrf_token', None)
                return redirect(url_for('views.home'))
            session.pop('csrf_token', None)  # Token verbrauchen
        return f(*args, **kwargs)
    return decorated_function





