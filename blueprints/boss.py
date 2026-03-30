from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import login_required, current_user
from models import db, User, Pass, PassUsageLog, MealCount, OneTimeCollection, SystemSettings, DailyNote
from datetime import datetime, date
from functools import wraps
from sqlalchemy import func
from zoneinfo import ZoneInfo
import io

IST = ZoneInfo("Asia/Kolkata")

def today_ist():
    return datetime.now(IST).date()

boss_bp = Blueprint('boss', __name__)

def boss_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_type') != 'admin' or current_user.role != 'boss':
            flash('Boss access required', 'error')
            return redirect(url_for('staff.dashboard'))
        return f(*args, **kwargs)
    return decorated

# ── Settings ─────────────────────────────────────
@boss_bp.route('/settings', methods=['GET', 'POST'])
@boss_required
def settings():
    s = SystemSettings.query.first()
    if request.method == 'POST':
        s.student_price = request.form['student_price']
        s.faculty_price = request.form['faculty_price']
        s.student_both = request.form['student_both']
        s.faculty_both = request.form['faculty_both']
        s.one_time_price = request.form['one_time_price']
        s.lunch_start = request.form['lunch_start']
        s.lunch_end = request.form['lunch_end']
        s.dinner_start = request.form['dinner_start']
        s.dinner_end = request.form['dinner_end']
        db.session.commit()
        flash('Settings saved', 'success')
    return render_template('boss/settings.html', s=s)

# ── Analysis: Daily ───────────────────────────────
@boss_bp.route('/analysis/daily')
@boss_required
def analysis_daily():
    selected = request.args.get('date', today_ist().isoformat())
    sel_date = datetime.strptime(selected, '%Y-%m-%d').date()

    categories = ['Hostel', 'OneTime', 'StudentPass', 'FacultyPass', 'SpecialGuest']
    stats = {}
    grand_total = 0

    for meal in ['Lunch', 'Dinner']:
        stats[meal] = {}
        meal_total = 0
        for cat in categories:
            r = MealCount.query.filter_by(entry_date=sel_date, meal_type=meal, category=cat).first()
            val = r.count if r else 0
            stats[meal][cat] = val
            meal_total += val
        stats[meal]['Total'] = meal_total
        grand_total += meal_total

    # Cash
    pass_cash = db.session.query(func.sum(Pass.amount_paid)).filter(
        db.cast(Pass.start_date, db.Date) == sel_date
    ).scalar() or 0
    ot_cash = db.session.query(func.sum(OneTimeCollection.amount)).filter(
        OneTimeCollection.date == sel_date
    ).scalar() or 0

    # Compare with previous day
    from datetime import timedelta
    prev_date = sel_date - timedelta(days=1)
    prev_total = db.session.query(func.sum(MealCount.count)).filter(
        MealCount.entry_date == prev_date
    ).scalar() or 0

    note = DailyNote.query.filter_by(note_date=sel_date).first()

    return render_template('boss/analysis_daily.html',
        selected=selected, stats=stats, categories=categories,
        grand_total=grand_total, pass_cash=float(pass_cash),
        ot_cash=float(ot_cash), total_cash=float(pass_cash)+float(ot_cash),
        prev_total=prev_total, prev_date=prev_date, note=note
    )

# ── Analysis: Range ───────────────────────────────
@boss_bp.route('/analysis/range')
@boss_required
def analysis_range():
    from_str = request.args.get('from', today_ist().replace(day=1).isoformat())
    to_str = request.args.get('to', today_ist().isoformat())
    meal_filter = request.args.get('meal', 'All')

    from_date = datetime.strptime(from_str, '%Y-%m-%d').date()
    to_date = datetime.strptime(to_str, '%Y-%m-%d').date()

    query = db.session.query(
        MealCount.entry_date,
        MealCount.meal_type,
        func.sum(MealCount.count).label('total')
    ).filter(
        MealCount.entry_date.between(from_date, to_date)
    )
    if meal_filter != 'All':
        query = query.filter(MealCount.meal_type == meal_filter)

    rows = query.group_by(MealCount.entry_date, MealCount.meal_type)\
                .order_by(MealCount.entry_date.desc()).all()

    # Category breakdown
    cat_query = db.session.query(
        MealCount.category,
        func.sum(MealCount.count).label('total')
    ).filter(MealCount.entry_date.between(from_date, to_date))
    if meal_filter != 'All':
        cat_query = cat_query.filter(MealCount.meal_type == meal_filter)
    cat_breakdown = cat_query.group_by(MealCount.category).all()

    pass_cash = db.session.query(func.sum(Pass.amount_paid)).filter(
        db.cast(Pass.start_date, db.Date).between(from_date, to_date)
    ).scalar() or 0
    ot_cash = db.session.query(func.sum(OneTimeCollection.amount)).filter(
        OneTimeCollection.date.between(from_date, to_date)
    ).scalar() or 0

    return render_template('boss/analysis_range.html',
        rows=rows, from_str=from_str, to_str=to_str,
        meal_filter=meal_filter, cat_breakdown=cat_breakdown,
        pass_cash=float(pass_cash), ot_cash=float(ot_cash),
        total_cash=float(pass_cash)+float(ot_cash)
    )

# ── Analysis: Monthly ─────────────────────────────
@boss_bp.route('/analysis/monthly')
@boss_required
def analysis_monthly():
    month = int(request.args.get('month', today_ist().month))
    year = int(request.args.get('year', today_ist().year))

    rows = db.session.query(
        MealCount.entry_date,
        func.sum(db.case((MealCount.meal_type == 'Lunch', MealCount.count), else_=0)).label('lunch'),
        func.sum(db.case((MealCount.meal_type == 'Dinner', MealCount.count), else_=0)).label('dinner'),
        func.sum(MealCount.count).label('total')
    ).filter(
        func.extract('month', MealCount.entry_date) == month,
        func.extract('year', MealCount.entry_date) == year
    ).group_by(MealCount.entry_date).order_by(MealCount.entry_date).all()

    pass_cash = db.session.query(func.sum(Pass.amount_paid)).filter(
        func.extract('month', Pass.start_date) == month,
        func.extract('year', Pass.start_date) == year
    ).scalar() or 0
    ot_cash = db.session.query(func.sum(OneTimeCollection.amount)).filter(
        func.extract('month', OneTimeCollection.date) == month,
        func.extract('year', OneTimeCollection.date) == year
    ).scalar() or 0

    total_meals = sum(r.total for r in rows)
    avg_meals = round(total_meals / len(rows), 1) if rows else 0
    busiest = max(rows, key=lambda r: r.total) if rows else None
    slowest = min(rows, key=lambda r: r.total) if rows else None

    # Chart data
    chart_labels = [r.entry_date.strftime('%d') for r in rows]
    chart_lunch = [int(r.lunch) for r in rows]
    chart_dinner = [int(r.dinner) for r in rows]

    return render_template('boss/analysis_monthly.html',
        rows=rows, month=month, year=year,
        pass_cash=float(pass_cash), ot_cash=float(ot_cash),
        total_cash=float(pass_cash)+float(ot_cash),
        total_meals=total_meals, avg_meals=avg_meals,
        busiest=busiest, slowest=slowest,
        chart_labels=chart_labels,
        chart_lunch=chart_lunch, chart_dinner=chart_dinner
    )

# ── Export Excel ──────────────────────────────────
@boss_bp.route('/export/monthly')
@boss_required
def export_monthly():
    import openpyxl
    month = int(request.args.get('month', today_ist().month))
    year = int(request.args.get('year', today_ist().year))

    rows = db.session.query(
        MealCount.entry_date,
        func.sum(db.case((MealCount.meal_type == 'Lunch', MealCount.count), else_=0)).label('lunch'),
        func.sum(db.case((MealCount.meal_type == 'Dinner', MealCount.count), else_=0)).label('dinner'),
        func.sum(MealCount.count).label('total')
    ).filter(
        func.extract('month', MealCount.entry_date) == month,
        func.extract('year', MealCount.entry_date) == year
    ).group_by(MealCount.entry_date).order_by(MealCount.entry_date).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Monthly Report"
    ws.append(['Date', 'Day', 'Lunch', 'Dinner', 'Total'])

    for r in rows:
        ws.append([
            r.entry_date.strftime('%Y-%m-%d'),
            r.entry_date.strftime('%A'),
            int(r.lunch), int(r.dinner), int(r.total)
        ])

    # Cash sheet
    ws2 = wb.create_sheet("Revenue")
    pass_cash = db.session.query(func.sum(Pass.amount_paid)).filter(
        func.extract('month', Pass.start_date) == month,
        func.extract('year', Pass.start_date) == year
    ).scalar() or 0
    ot_cash = db.session.query(func.sum(OneTimeCollection.amount)).filter(
        func.extract('month', OneTimeCollection.date) == month,
        func.extract('year', OneTimeCollection.date) == year
    ).scalar() or 0
    ws2.append(['Type', 'Amount'])
    ws2.append(['Pass Revenue', float(pass_cash)])
    ws2.append(['OneTime Revenue', float(ot_cash)])
    ws2.append(['Total', float(pass_cash) + float(ot_cash)])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    import calendar
    month_name = calendar.month_name[month]
    return send_file(buf, as_attachment=True,
                     download_name=f'atmiya_mess_{month_name}_{year}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ── User History (boss only) ──────────────────────
@boss_bp.route('/users/<int:user_id>/history')
@boss_required
def user_history(user_id):
    user = User.query.get_or_404(user_id)
    passes = Pass.query.filter_by(user_id=user_id).order_by(Pass.id.desc()).all()
    logs = PassUsageLog.query.filter_by(user_id=user_id).order_by(PassUsageLog.id.desc()).limit(50).all()
    return render_template('boss/user_history.html', user=user, passes=passes, logs=logs)

# ── Daily Note (holiday marker) ───────────────────
@boss_bp.route('/notes', methods=['POST'])
@boss_required
def save_note():
    note_date = datetime.strptime(request.form['note_date'], '%Y-%m-%d').date()
    label = request.form.get('label', '')
    is_holiday = request.form.get('is_holiday') == 'on'

    note = DailyNote.query.filter_by(note_date=note_date).first()
    if note:
        note.label = label
        note.is_holiday = is_holiday
    else:
        note = DailyNote(note_date=note_date, label=label, is_holiday=is_holiday)
        db.session.add(note)
    db.session.commit()
    flash('Note saved', 'success')
    return redirect(request.referrer or url_for('boss.analysis_daily'))