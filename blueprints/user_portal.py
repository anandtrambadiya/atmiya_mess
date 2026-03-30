from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from models import db, User, Pass, PassUsageLog
from datetime import date
from functools import wraps

user_bp = Blueprint('user', __name__)

def user_portal_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_type') != 'user':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@user_bp.route('/dashboard')
@user_portal_required
def dashboard():
    user = current_user

    # Expire old passes
    for p in user.passes:
        if p.status == 'Active' and (p.end_date < date.today() or p.used_slots >= p.total_slots):
            p.status = 'Expired'
    db.session.commit()

    active_pass = Pass.query.filter_by(user_id=user.id, status='Active').order_by(Pass.id.desc()).first()
    recent_logs = PassUsageLog.query.filter_by(user_id=user.id).order_by(PassUsageLog.id.desc()).limit(10).all()

    # Alert: low slots
    alert = None
    if active_pass:
        remaining = active_pass.total_slots - active_pass.used_slots
        from datetime import timedelta
        days_left = (active_pass.end_date - date.today()).days
        if remaining <= 5:
            alert = f'Only {remaining} meals remaining on your pass!'
        elif days_left <= 5:
            alert = f'Your pass expires in {days_left} days!'

    return render_template('user/dashboard.html', 
                           user=user, active_pass=active_pass,
                           recent_logs=recent_logs, alert=alert)

@user_bp.route('/qr')
@user_portal_required
def show_qr():
    return render_template('user/qr.html', user=current_user)

@user_bp.route('/update_password', methods=['POST'])
@user_portal_required
def update_password():
    from werkzeug.security import generate_password_hash, check_password_hash
    user = current_user
    new_pass = request.form.get('new_password')
    confirm = request.form.get('confirm_password')

    if new_pass != confirm:
        flash('Passwords do not match', 'error')
    elif len(new_pass) < 4:
        flash('Password too short', 'error')
    else:
        user.password_hash = generate_password_hash(new_pass)
        db.session.commit()
        flash('Password updated successfully', 'success')

    return redirect(url_for('user.dashboard'))
