from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import Config
from models import db, Admin, User

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    from flask import session
    if session.get('user_type') == 'user':
        return User.query.get(int(user_id))
    return Admin.query.get(int(user_id))

# Register blueprints
from blueprints.auth import auth_bp
from blueprints.staff import staff_bp
from blueprints.boss import boss_bp
from blueprints.user_portal import user_bp

app.register_blueprint(auth_bp)
app.register_blueprint(staff_bp, url_prefix='/staff')
app.register_blueprint(boss_bp, url_prefix='/boss')
app.register_blueprint(user_bp, url_prefix='/user')

@app.route('/')
def index():
    return redirect(url_for('auth.login'))

def init_db():
    """Create tables and seed default data"""
    db.create_all()

    from models import SystemSettings
    if not SystemSettings.query.first():
        db.session.add(SystemSettings())
        db.session.commit()

    from werkzeug.security import generate_password_hash
    if not Admin.query.first():
        boss = Admin(
            name='Admin',
            username='admin',
            password_hash=generate_password_hash('admin123'),
            role='boss'
        )
        db.session.add(boss)
        db.session.commit()
        print("Default admin created: username=admin password=admin123")

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True)