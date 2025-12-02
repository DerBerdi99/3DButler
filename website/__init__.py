from flask import Flask
from flask_session import Session
import os
def create_app():

    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'website', 'templates'))

    app.config['SECRET_KEY']='dsdsdfsdfsdfsdf'
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)
    from .views import views
    from .auth import auth
    from .admin_views import admin_bp

    app.register_blueprint(views,url_prefix='/')
    app.register_blueprint(auth,url_prefix='/') #localhost:5000/login
    app.register_blueprint(admin_bp)

    return app