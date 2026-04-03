"""
Run this once to seed 10 test users with various pass states for testing.
Usage: python seed_test_data.py
"""
from app import app, db
from models import User, Pass, PassUsageLog, MealCount, OneTimeCollection
from werkzeug.security import generate_password_hash
from datetime import date, timedelta, time
import qrcode, io, base64

def make_qr(user_id):
    qr = qrcode.make(str(user_id))
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()

def seed():
    with app.app_context():

        # ── 10 Test Users ─────────────────────────────────────────────────────
        test_users = [
            # name,          branch,    sem, institute,       mobile,        type
            ("Raj Patel",    "CE",      "5", "Atmiya Uni",   "9876543201", "student"),
            ("Priya Shah",   "IT",      "3", "Atmiya Uni",   "9876543202", "student"),
            ("Amit Desai",   "ME",      "7", "Atmiya Uni",   "9876543203", "student"),
            ("Neha Joshi",   "EC",      "1", "Atmiya Uni",   "9876543204", "student"),
            ("Karan Modi",   "CE",      "5", "Atmiya Uni",   "9876543205", "student"),
            ("Sonal Mehta",  "IT",      "3", "Atmiya Uni",   "9876543206", "student"),
            ("Dev Trivedi",  "MBA",     "2", "Atmiya Uni",   "9876543207", "student"),
            ("Ritu Sharma",  "BCA",     "4", "Atmiya Uni",   "9876543208", "student"),
            ("Prof. Verma",  "CSE",     "0", "Atmiya Uni",   "9876543209", "faculty"),
            ("Prof. Nair",   "Physics", "0", "Atmiya Uni",   "9876543210", "faculty"),
        ]

        created_users = []
        for name, branch, sem, inst, mobile, utype in test_users:
            # Check if already exists
            existing = User.query.filter_by(mobile=mobile).first()
            if existing:
                created_users.append(existing)
                continue

            u = User(name=name, branch=branch, sem=sem, institute=inst,
                     mobile=mobile, user_type=utype,
                     password_hash=generate_password_hash(mobile))
            db.session.add(u)
            db.session.flush()
            u.qr_code = make_qr(u.id)
            created_users.append(u)

        db.session.commit()
        print(f"Created/found {len(created_users)} users")

        today = date.today()

        # ── Passes with different states ──────────────────────────────────────
        pass_configs = [
            # (user_index, pass_type, start_offset, used_slots, total_slots)
            # Normal healthy pass
            (0, "Both",   -5,  10, 60),   # Raj   - healthy Both pass
            (1, "Lunch",  -5,  25, 30),   # Priya - half used Lunch
            (2, "Dinner", -5,  28, 30),   # Amit  - 2 slots left (LOW!)
            (3, "Both",   -5,  55, 60),   # Neha  - 5 slots left (LOW!)
            (4, "Lunch",  -5,   0, 30),   # Karan - fresh pass
            (5, "Both",   -5,  58, 60),   # Sonal - 2 slots left (LOW!)
            (6, "Dinner", -35,  30, 30),  # Dev   - expired by slots
            (7, "Both",   -41,   5, 60),  # Ritu  - expired by date
            (8, "Lunch",  -5,   3, 30),   # Prof Verma - mostly unused
            (9, "Both",   -5,  20, 60),   # Prof Nair - healthy
        ]

        for i, pass_type, start_offset, used, total in pass_configs:
            user = created_users[i]

            # Skip if already has passes
            if Pass.query.filter_by(user_id=user.id).first():
                continue

            start = today + timedelta(days=start_offset)
            end   = start + timedelta(days=40)

            status = 'Active'
            if used >= total or end < today:
                status = 'Expired'

            from models import SystemSettings
            s = SystemSettings.query.first()
            if user.user_type == 'student':
                amount = float(s.student_both) if pass_type == 'Both' else float(s.student_price)
            else:
                amount = float(s.faculty_both) if pass_type == 'Both' else float(s.faculty_price)

            p = Pass(user_id=user.id, pass_type=pass_type,
                     start_date=start, end_date=end,
                     total_slots=total, used_slots=used,
                     status=status, amount_paid=amount)
            db.session.add(p)

        db.session.commit()
        print("Passes created")

        # ── Some meal count history (last 7 days) ─────────────────────────────
        categories = [
            ('Hostel',      'Lunch',  45),
            ('Hostel',      'Dinner', 50),
            ('StudentPass', 'Lunch',  30),
            ('StudentPass', 'Dinner', 25),
            ('FacultyPass', 'Lunch',  8),
            ('FacultyPass', 'Dinner', 5),
            ('OneTime',     'Lunch',  12),
            ('OneTime',     'Dinner', 8),
            ('SpecialGuest','Lunch',  3),
        ]

        for day_offset in range(-7, 0):
            d = today + timedelta(days=day_offset)
            for cat, meal, base_count in categories:
                import random
                count = base_count + random.randint(-5, 5)
                existing = MealCount.query.filter_by(
                    entry_date=d, meal_type=meal, category=cat).first()
                if not existing:
                    db.session.add(MealCount(
                        entry_date=d, meal_type=meal, category=cat, count=max(0, count)
                    ))

            # One time cash
            if not OneTimeCollection.query.filter_by(date=d).first():
                from models import SystemSettings
                s = SystemSettings.query.first()
                db.session.add(OneTimeCollection(
                    date=d, meal_type='Lunch',
                    amount=float(s.one_time_price) * random.randint(8, 15)
                ))

        db.session.commit()
        print("History seeded")

        # ── Print summary ──────────────────────────────────────────────────────
        print("\n=== TEST USERS ===")
        for u in created_users:
            p = Pass.query.filter_by(user_id=u.id).order_by(Pass.id.desc()).first()
            if p:
                remaining = p.total_slots - p.used_slots
                print(f"ID:{u.id:3d}  {u.name:20s}  {p.pass_type:6s}  {p.status:7s}  {remaining:2d} slots  mobile:{u.mobile}")
            else:
                print(f"ID:{u.id:3d}  {u.name:20s}  NO PASS  mobile:{u.mobile}")

        print("\nDone! Login as any user with their mobile number as password.")
        print(f"\nLow slot users to test alerts:")
        for u in created_users:
            p = Pass.query.filter_by(user_id=u.id, status='Active').first()
            if p and (p.total_slots - p.used_slots) <= 5:
                print(f"  {u.name} — {p.total_slots - p.used_slots} slots left")

if __name__ == '__main__':
    seed()