from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Admin, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        portal = request.form.get('portal')  # 'admin' or 'user'
        
        if portal == 'admin':
            username = request.form.get('username')
            password = request.form.get('password')
            admin = Admin.query.filter_by(username=username).first()
            if admin and check_password_hash(admin.password_hash, password):
                session['user_type'] = 'admin'
                login_user(admin)
                return redirect(url_for('staff.dashboard'))
            flash('Invalid credentials', 'error')

        elif portal == 'user':
            user_id = request.form.get('user_id')
            mobile = request.form.get('mobile')
            user = User.query.filter_by(id=user_id, mobile=mobile).first()
            # If user has set a password, check it; else use mobile as password
            if user:
                password_input = request.form.get('password', '')
                if user.password_hash:
                    if not check_password_hash(user.password_hash, password_input):
                        flash('Invalid credentials', 'error')
                        return render_template('login.html')
                session['user_type'] = 'user'
                login_user(user)
                return redirect(url_for('user.dashboard'))
            flash('Invalid ID or mobile number', 'error')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    user_type = session.get('user_type')
    session.clear()
    logout_user()
    return redirect(url_for('auth.login'))