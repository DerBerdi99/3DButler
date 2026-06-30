import os
import secrets
import datetime
import logging
from flask import Flask, session
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_apscheduler import APScheduler
from .user_manager import UserManager

# Globales Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# Logger-Instanz für diese Datei definieren (Das hat gefehlt!)
logger = logging.getLogger(__name__)

# Globale Erweiterungen
limiter = Limiter(key_func=get_remote_address, default_limits=[os.getenv('STANDARD_ACCESS_LIMIT', '1000 per day')])
scheduler = APScheduler()

# Pfad zur SQLite-Datenbank definieren
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '3dbutler.db')

def create_app():
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'website', 'templates'))

    # Konfigurationen
    app.config['SECRET_KEY'] = 'dsdsdfsdfsdfsdf'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['DATABASE'] = DB_PATH
    app.config['SCHEDULER_API_ENABLED'] = True
    
    # HINWEIS: os.getenv Standard auf 30.0 Minuten geändert, statt 0.5 (30 Sekunden)
    app.config['BANK_UPDATE_INTERVAL'] = float(os.getenv('BANK_UPDATE_INTERVAL', 30.0))

    # Instanzen initialisieren
    app.user_manager = UserManager()
    Session(app)
    limiter.init_app(app)
    scheduler.init_app(app) # Nur initialisieren

    # Blueprints importieren & registrieren
    from .views import views
    from .auth import auth
    from .admin_views import admin_bp

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(admin_bp)
    
    # Context Processor für CSRF
    @app.context_processor
    def inject_csrf_token():
        def get_csrf_token():
            if 'csrf_token' not in session:
                session['csrf_token'] = secrets.token_hex(16)
            return session['csrf_token']
        return dict(csrf_token=get_csrf_token)

# ==================== ZEITGESTEUERTER BANK SYNC ====================
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        from .bank_service import sync_bank_balance
        
        def scheduled_bank_sync():
            with app.app_context():
                sync_bank_balance(app)

        # Job sauber registrieren – doppelte IDs überschreiben sich im Live-Betrieb
        scheduler.add_job(
            id='sync_bank_task',
            func=scheduled_bank_sync,
            trigger='interval',
            minutes=app.config['BANK_UPDATE_INTERVAL'],
            misfire_grace_time=900,
            max_instances=1,
            replace_existing=True
        )

        scheduler.start()
        logger.info("🚀 APScheduler im Hauptprozess gestartet.")
    # ===================================================================

    return app