from datetime import date
from app import app, db, User
def ensure_user(employee_id, name, email, doj, salary, role, password):
    user = User.query.filter_by(employee_id=employee_id).first()
    if user:
        return False
    u = User(
        employee_id=employee_id,
        name=name,
        email=email,
        date_of_joining=doj,
        salary=salary,
        role=role,
    )
    u.set_password(password)
    db.session.add(u)
    return True

with app.app_context():
    created_any = False
    created_any |= ensure_user(
        employee_id="HR001",
        name="HR Admin",
        email="hr@company.com",
        doj=date(2025, 9, 24),
        salary=80000,
        role="hr",
        password="hr_password",
    )
    created_any |= ensure_user(
        employee_id="MAIN_SUPERVISOR",
        name="Main Supervisor",
        email="supervisor@company.com",
        doj=date(2025, 9, 24),
        salary=90000,
        role="supervisor",
        password="supervisor_password",
    )
    if created_any:
        db.session.commit()
        print("HR and Main Supervisor users created successfully.")
    else:
        print("Admin users already exist. No changes made.")
