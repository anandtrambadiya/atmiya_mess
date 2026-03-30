from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date

db = SQLAlchemy()

class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'staff' or 'boss'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100))
    sem = db.Column(db.String(10))
    institute = db.Column(db.String(100))
    mobile = db.Column(db.String(15), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)  # student / faculty
    password_hash = db.Column(db.String(255))  # optional, can update later
    qr_code = db.Column(db.Text)  # base64 QR image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    passes = db.relationship('Pass', backref='user', lazy=True)

class Pass(db.Model):
    __tablename__ = 'passes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pass_type = db.Column(db.String(20), nullable=False)  # Lunch / Dinner / Both
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    used_slots = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='Active')  # Active / Expired
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PassUsageLog(db.Model):
    __tablename__ = 'pass_usage_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pass_id = db.Column(db.Integer, db.ForeignKey('passes.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(10), nullable=False)
    slots_used = db.Column(db.Integer, default=1)
    entry_time = db.Column(db.Time)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'))

class MealCount(db.Model):
    __tablename__ = 'meal_count'
    id = db.Column(db.Integer, primary_key=True)
    entry_date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    count = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint('entry_date', 'meal_type', 'category', name='uq_meal_count'),
    )

class OneTimeCollection(db.Model):
    __tablename__ = 'one_time_collection'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    student_price = db.Column(db.Numeric(10, 2), default=1500)
    faculty_price = db.Column(db.Numeric(10, 2), default=2000)
    student_both = db.Column(db.Numeric(10, 2), default=2500)
    faculty_both = db.Column(db.Numeric(10, 2), default=3500)
    one_time_price = db.Column(db.Numeric(10, 2), default=80)
    lunch_start = db.Column(db.String(5), default='11:30')
    lunch_end = db.Column(db.String(5), default='14:30')
    dinner_start = db.Column(db.String(5), default='19:00')
    dinner_end = db.Column(db.String(5), default='21:30')

class DailyNote(db.Model):
    __tablename__ = 'daily_notes'
    id = db.Column(db.Integer, primary_key=True)
    note_date = db.Column(db.Date, nullable=False, unique=True)
    label = db.Column(db.String(100))
    is_holiday = db.Column(db.Boolean, default=False)