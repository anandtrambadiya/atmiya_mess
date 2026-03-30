from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from models import db, User, Pass, PassUsageLog, MealCount, OneTimeCollection, SystemSettings
from datetime import datetime, date, time
from functools import wraps

staff_bp = Blueprint('staff', __name__)

def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_type') != 'admin':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def get_current_meal():
    settings = SystemSettings.query.first()
    now = datetime.now().time()
    
    def parse(t): 
        h, m = map(int, t.split(':'))
        return time(h, m)
    
    if parse(settings.lunch_start) <= now <= parse(settings.lunch_end):
        return 'Lunch'
    if parse(settings.dinner_start) <= now <= parse(settings.dinner_end):
        return 'Dinner'
    return 'Closed'

def update_meal_count(entry_date, meal_type, category, increment=1):
    record = MealCount.query.filter_by(
        entry_date=entry_date,
        meal_type=meal_type,
        category=category
    ).first()
    if record:
        record.count += increment
    else:
        record = MealCount(
            entry_date=entry_date,
            meal_type=meal_type,
            category=category,
            count=max(0, increment)
        )
        db.session.add(record)
    db.session.commit()

def get_today_stats():
    today = date.today()
    meal = get_current_meal()
    categories = ['Hostel', 'OneTime', 'StudentPass', 'FacultyPass', 'SpecialGuest']
    
    stats = {'Lunch': {}, 'Dinner': {}}
    for m in ['Lunch', 'Dinner']:
        total = 0
        for cat in categories:
            record = MealCount.query.filter_by(
                entry_date=today, meal_type=m, category=cat
            ).first()
            val = record.count if record else 0
            stats[m][cat] = val
            total += val
        stats[m]['Total'] = total
    
    # Cash
    from sqlalchemy import func
    pass_cash = db.session.query(func.sum(Pass.amount_paid)).filter(
        db.cast(Pass.start_date, db.Date) == today
    ).scalar() or 0

    ot_cash = db.session.query(func.sum(OneTimeCollection.amount)).filter(
        OneTimeCollection.date == today
    ).scalar() or 0

    return {
        'stats': stats,
        'current_meal': meal,
        'pass_cash': float(pass_cash),
        'ot_cash': float(ot_cash),
        'total_cash': float(pass_cash) + float(ot_cash)
    }



@staff_bp.route('/scan')
@staff_required
def scan():
    return render_template('staff/scan.html')

@staff_bp.route('/api/user/<int:user_id>')
@staff_required
def api_user(user_id):
    """Returns user + pass info as JSON for QR scan"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'found': False, 'message': 'User not found'})

    for p in user.passes:
        if p.status == 'Active' and (p.end_date < date.today() or p.used_slots >= p.total_slots):
            p.status = 'Expired'
    db.session.commit()

    active_pass = Pass.query.filter_by(user_id=user.id, status='Active').order_by(Pass.id.desc()).first()
    meal = get_current_meal()

    pass_data = None
    if active_pass:
        remaining = active_pass.total_slots - active_pass.used_slots
        already_used = PassUsageLog.query.filter_by(
            user_id=user.id, date=date.today(), meal_type=meal
        ).first() if meal != 'Closed' else None

        pass_data = {
            'id': active_pass.id,
            'pass_type': active_pass.pass_type,
            'remaining': remaining,
            'total_slots': active_pass.total_slots,
            'used_slots': active_pass.used_slots,
            'end_date': active_pass.end_date.strftime('%d %b %Y'),
            'already_used_today': already_used is not None,
        }

    return jsonify({
        'found': True,
        'user': {
            'id': user.id,
            'name': user.name,
            'user_type': user.user_type,
            'branch': user.branch or '',
        },
        'active_pass': pass_data,
        'current_meal': meal,
    })

@staff_bp.route('/dashboard')
@staff_required
def dashboard():
    data = get_today_stats()
    return render_template('staff/dashboard.html', data=data, current_user=current_user)

@staff_bp.route('/search', methods=['GET', 'POST'])
@staff_required
def search():
    user = None
    active_pass = None
    error = None

    uid = request.args.get('uid') or request.form.get('uid')
    name_q = request.args.get('name')

    if uid:
        user = User.query.get(uid)
        if not user:
            error = 'User not found'
    elif name_q:
        users = User.query.filter(User.name.ilike(f'%{name_q}%')).all()
        return render_template('staff/search_results.html', users=users, query=name_q)

    if user:
        # Expire old passes
        for p in user.passes:
            if p.status == 'Active' and (p.end_date < date.today() or p.used_slots >= p.total_slots):
                p.status = 'Expired'
        db.session.commit()

        active_pass = Pass.query.filter_by(user_id=user.id, status='Active').order_by(Pass.id.desc()).first()

    meal = get_current_meal()
    return render_template('staff/user_detail.html', 
                           user=user, active_pass=active_pass, 
                           meal=meal, error=error)

@staff_bp.route('/allow/<int:user_id>', methods=['POST'])
@staff_required
def allow_meal(user_id):
    meal = get_current_meal()
    if meal == 'Closed':
        return jsonify({'success': False, 'message': 'Mess is closed now'})

    user = User.query.get_or_404(user_id)
    active_pass = Pass.query.filter_by(user_id=user_id, status='Active').order_by(Pass.id.desc()).first()

    if not active_pass:
        return jsonify({'success': False, 'message': 'No active pass found'})

    today = date.today()

    # Check pass type
    if active_pass.pass_type == 'Lunch' and meal != 'Lunch':
        return jsonify({'success': False, 'message': 'Lunch pass only'})
    if active_pass.pass_type == 'Dinner' and meal != 'Dinner':
        return jsonify({'success': False, 'message': 'Dinner pass only'})

    # Check already used today
    already = PassUsageLog.query.filter_by(
        user_id=user_id, date=today, meal_type=meal
    ).first()
    if already:
        return jsonify({'success': False, 'message': 'Meal already used today'})

    # Sunday dinner = 2 slots
    slots = 2 if (meal == 'Dinner' and today.weekday() == 6) else 1

    if active_pass.used_slots + slots > active_pass.total_slots:
        return jsonify({'success': False, 'message': 'Not enough slots remaining'})

    # Deduct slots
    active_pass.used_slots += slots

    # Log usage
    log = PassUsageLog(
        user_id=user_id,
        pass_id=active_pass.id,
        date=today,
        meal_type=meal,
        slots_used=slots,
        entry_time=datetime.now().time(),
        admin_id=current_user.id
    )
    db.session.add(log)

    # Auto expire if finished
    if active_pass.used_slots >= active_pass.total_slots:
        active_pass.status = 'Expired'

    # Update meal count
    category = 'StudentPass' if user.user_type == 'student' else 'FacultyPass'
    update_meal_count(today, meal, category)

    db.session.commit()

    remaining = active_pass.total_slots - active_pass.used_slots
    return jsonify({
        'success': True, 
        'message': f'✓ Meal Allowed — {remaining} slots remaining',
        'remaining': remaining
    })

@staff_bp.route('/undo', methods=['POST'])
@staff_required
def undo():
    """Undo last meal action"""
    last_log = PassUsageLog.query.filter_by(
        date=date.today()
    ).order_by(PassUsageLog.id.desc()).first()

    if not last_log:
        return jsonify({'success': False, 'message': 'Nothing to undo'})

    # Restore slots
    p = Pass.query.get(last_log.pass_id)
    if p:
        p.used_slots -= last_log.slots_used
        if p.status == 'Expired' and p.used_slots < p.total_slots:
            p.status = 'Active'

    # Undo meal count
    user = User.query.get(last_log.user_id)
    category = 'StudentPass' if user.user_type == 'student' else 'FacultyPass'
    update_meal_count(last_log.date, last_log.meal_type, category, increment=-1)

    db.session.delete(last_log)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Last action undone'})

@staff_bp.route('/manual_count', methods=['POST'])
@staff_required
def manual_count():
    category = request.form.get('category')  # Hostel / OneTime / SpecialGuest
    meal = get_current_meal()

    if meal == 'Closed':
        return jsonify({'success': False, 'message': 'Mess is closed'})

    today = date.today()
    update_meal_count(today, meal, category)

    if category == 'OneTime':
        settings = SystemSettings.query.first()
        ot = OneTimeCollection(
            date=today,
            meal_type=meal,
            amount=settings.one_time_price,
            admin_id=current_user.id
        )
        db.session.add(ot)
        db.session.commit()

    data = get_today_stats()
    return jsonify({'success': True, 'data': data})

@staff_bp.route('/stats')
@staff_required
def live_stats():
    """Returns live stats as JSON for auto-refresh"""
    return jsonify(get_today_stats())

# ── User Management ──────────────────────────────
@staff_bp.route('/users')
@staff_required
def users():
    all_users = User.query.order_by(User.id.desc()).all()
    return render_template('staff/users.html', users=all_users)

@staff_bp.route('/users/add', methods=['GET', 'POST'])
@staff_required
def add_user():
    if request.method == 'POST':
        import qrcode, io, base64
        
        user = User(
            name=request.form['name'],
            branch=request.form.get('branch'),
            sem=request.form.get('sem'),
            institute=request.form.get('institute'),
            mobile=request.form['mobile'],
            user_type=request.form['user_type']
        )
        db.session.add(user)
        db.session.flush()  # get user.id before commit

        # Generate QR code
        qr = qrcode.make(str(user.id))
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        user.qr_code = base64.b64encode(buf.getvalue()).decode()

        db.session.commit()
        flash(f'User added! ID: {user.id}', 'success')

        if request.form.get('create_pass') == 'yes':
            return redirect(url_for('staff.add_pass', user_id=user.id))
        return redirect(url_for('staff.search') + f'?uid={user.id}')

    return render_template('staff/add_user.html')

@staff_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@staff_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.name = request.form['name']
        user.branch = request.form.get('branch')
        user.sem = request.form.get('sem')
        user.institute = request.form.get('institute')
        user.mobile = request.form['mobile']
        db.session.commit()
        flash('User updated', 'success')
        return redirect(url_for('staff.search') + f'?uid={user_id}')
    return render_template('staff/edit_user.html', user=user)

@staff_bp.route('/users/<int:user_id>/pass', methods=['GET', 'POST'])
@staff_required
def add_pass(user_id):
    user = User.query.get_or_404(user_id)
    settings = SystemSettings.query.first()

    if request.method == 'POST':
        pass_type = request.form['pass_type']
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = start_date.replace(day=start_date.day) 
        from datetime import timedelta
        end_date = start_date + timedelta(days=40)

        total_slots = 60 if pass_type == 'Both' else 30

        # Calculate amount
        if user.user_type == 'student':
            amount = float(settings.student_both) if pass_type == 'Both' else float(settings.student_price)
        else:
            amount = float(settings.faculty_both) if pass_type == 'Both' else float(settings.faculty_price)

        new_pass = Pass(
            user_id=user_id,
            pass_type=pass_type,
            start_date=start_date,
            end_date=end_date,
            total_slots=total_slots,
            used_slots=0,
            status='Active',
            amount_paid=amount
        )
        db.session.add(new_pass)
        db.session.commit()
        flash('Pass created successfully!', 'success')
        return redirect(url_for('staff.search') + f'?uid={user_id}')

    from datetime import date
    return render_template('staff/add_pass.html', user=user, settings=settings, today=date.today().isoformat())