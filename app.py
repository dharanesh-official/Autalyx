import os
from dotenv import load_dotenv

load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
from sqlalchemy import or_
import uuid
import random
import time
from flask import session
from num2words import num2words
import zipfile
from io import BytesIO
from flask_mail import Mail, Message

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'd1796a30d48ec0d90a4f5017022b0635ce64d059a27c594c6e44175a323729a8'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'autalyx@gmail.com'


db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

from payroll import calculate_payslip

MAIN_SUPERVISOR_ID = 'MAIN_SUPERVISOR'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))
    address = db.Column(db.String(200))
    date_of_joining = db.Column(db.Date, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), nullable=False)
    salary = db.Column(db.Float, nullable=False, default=0.0)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    employees = db.relationship('User', backref=db.backref('supervisor', remote_side=[id]), lazy='dynamic')
    leave_requests = db.relationship('LeaveRequest', backref='employee', lazy='dynamic')
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    team = db.Column(db.String(100))
    project = db.Column(db.String(100))
    team_leader_name = db.Column(db.String(100))
    team_leader_mobile = db.Column(db.String(20))
    letter_path = db.Column(db.String(200))

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    prefix = db.Column(db.String(10), nullable=False)
    base_role = db.Column(db.String(20), nullable=False, default='employee') # hr, supervisor, employee

class CompanyInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default="HR PRO SOLUTIONS")
    address = db.Column(db.String(200), default="123 Business Park, Tech City, Bangalore - 560100")
    email = db.Column(db.String(100), default="info@hrpro.com")
    phone = db.Column(db.String(20), default="+91 9876543210")
    gstn = db.Column(db.String(50), default="")

class Holiday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50))

class PersonalTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    task_description = db.Column(db.Text, nullable=False)

class PasswordResetOTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('otp_codes', lazy='dynamic'))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='Present') # 'Present', 'Leave'
    marked_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    user = db.relationship('User', foreign_keys=[user_id], backref='attendance_records')
    marker = db.relationship('User', foreign_keys=[marked_by])

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

@app.context_processor
def inject_company_info():
    try:
        info = CompanyInfo.query.first()
    except Exception:
        # Table might not exist yet
        info = None

    if not info:
        # Create default only if it doesn't exist (handle safely)
        # Check if table exists by inspecting exception or just try/except the creation
        try:
             # This inner try/except attempts to create the default record.
             # If table is missing, this commit will fail.
             info = CompanyInfo(name="HR PRO SOLUTIONS", address="123 Business Park, Tech City, Bangalore - 560100", email="info@hrpro.com", phone="+91 9876543210")
             db.session.add(info)
             # db.session.commit() # Commit might fail if table missing.
             # Actually, best to just return default dict if DB is not ready.
             # We rely on an init-db command or the main block to create tables.
             pass 
        except:
             db.session.rollback()
    
    # If still None (e.g. database locked or missing table), return placeholders
    if not info or not hasattr(info, 'name'):
          return dict(company={"name":"HR PRO","address":"Default Address","email":"info@hrpro.com","phone":"+91 9999999999"})
    
    # Create default roles if missing (Safely)
    try:
        if Role.query.count() == 0:
            db.session.add(Role(name='HR', prefix='HR', base_role='hr'))
            db.session.add(Role(name='Supervisor', prefix='SUP', base_role='supervisor'))
            db.session.add(Role(name='Employee', prefix='EMP', base_role='employee'))
            db.session.commit()
    except:
        db.session.rollback()
    
    # If still None (e.g. database locked), return placeholders
    # Create default roles if missing
    if Role.query.count() == 0:
        try:
            db.session.add(Role(name='HR', prefix='HR', base_role='hr'))
            db.session.add(Role(name='Supervisor', prefix='SUP', base_role='supervisor'))
            db.session.add(Role(name='Employee', prefix='EMP', base_role='employee'))
            db.session.commit()
        except: db.session.rollback()

    if not info:
         return dict(company={"name":"HR PRO","address":"Default Address","email":"info@hrpro.com","phone":"+91 9999999999"})
    
    return dict(company=info)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/login/<portal_role>', methods=['GET', 'POST'])
def login_role(portal_role):
    valid_portals = {'hr', 'supervisor', 'employee'}
    if portal_role not in valid_portals: abort(404)
    
    if current_user.is_authenticated:
        # Check if user's role maps to this portal
        user_role_obj = Role.query.filter(Role.name.ilike(current_user.role)).first()
        # Fallback: exact match if role not in DB (legacy)
        base = user_role_obj.base_role if user_role_obj else current_user.role.lower()
        
        if base == portal_role: return redirect(url_for('dashboard'))
        else: logout_user()

    if request.method == 'POST':
        user = User.query.filter_by(employee_id=request.form['employee_id'].upper()).first()
        if user and user.check_password(request.form['password']):
             # Check permission
             user_role_obj = Role.query.filter(Role.name.ilike(user.role)).first()
             base = user_role_obj.base_role if user_role_obj else user.role.lower()
             
             if base == portal_role:
                 login_user(user)
                 return redirect(url_for('dashboard'))
             else:
                 flash(f'Access denied for {portal_role.title()} portal. Your role is {user.role}.', 'error')
        else:
            flash(f'Invalid credentials.', 'error')
    return render_template('login.html', role=portal_role)

# Backward compatibility: default login goes to employee portal
@app.route('/login', methods=['GET'])
def login():
    return redirect(url_for('login_role', portal_role='employee'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if current_user.role not in ['HR', 'Supervisor', 'hr', 'supervisor']: # simple check, ideally check base_role
        # Better: check base_role
        ur = Role.query.filter(Role.name.ilike(current_user.role)).first()
        if not ur or ur.base_role not in ['hr', 'supervisor']:
             flash('You do not have permission to register users.', 'error'); return redirect(url_for('dashboard'))
    
    supervisors_base = Role.query.filter_by(base_role='supervisor').first() # Get supervisor role name? 
    # Actually need users who have a supervisor-type role
    # Find all roles with base_role='supervisor'
    sup_roles = [r.name for r in Role.query.filter_by(base_role='supervisor').all()]
    supervisors = User.query.filter(User.role.in_(sup_roles)).all() if sup_roles else []
    
    # Legacy: also check 'supervisor' string just in case
    if not supervisors: supervisors = User.query.filter_by(role='supervisor').all()
    
    roles = Role.query.all()
    
    if request.method == 'POST':
        if User.query.filter_by(employee_id=request.form['employee_id']).first():
             flash('Employee ID already exists.', 'error'); return redirect(url_for('register'))
        if User.query.filter_by(email=request.form['email']).first():
             flash('Email already exists.', 'error'); return redirect(url_for('register'))
        if User.query.filter_by(name=request.form['name']).first():
            flash('User with this Name already exists.', 'error'); return redirect(url_for('register'))
        if User.query.filter_by(phone_number=request.form['phone_number']).first():
             flash('Phone Number already exists.', 'error'); return redirect(url_for('register'))
        
        # Role logic
        new_user_role_name = request.form['role']
        
        # Security Check: Supervisors cannot create HR or Supervisor roles
        ur = Role.query.filter(Role.name.ilike(current_user.role)).first()
        if ur and ur.base_role == 'supervisor':
            target_role = Role.query.filter_by(name=new_user_role_name).first()
            if target_role and target_role.base_role != 'employee':
                flash('Supervisors can only register employees.', 'error')
                return redirect(url_for('register'))
        
        new_user = User(
            employee_id=request.form['employee_id'], name=request.form['name'], email=request.form['email'],
            phone_number=request.form['phone_number'], address=request.form['address'],
            date_of_joining=datetime.strptime(request.form['date_of_joining'], '%Y-%m-%d').date(),
            salary=float(request.form['salary']), role=new_user_role_name
        )
        new_user.set_password(request.form['password'])
        
        # Supervisor assignment
        # Logic: If I am supervisor, I am the supervisor. If I am HR, I select supervisor.
        ur = Role.query.filter(Role.name.ilike(current_user.role)).first()
        is_supervisor = ur and ur.base_role == 'supervisor'
        is_hr = ur and ur.base_role == 'hr'

        if is_supervisor:
            new_user.supervisor_id = current_user.id
        elif is_hr:
            supervisor_id = request.form.get('supervisor_id')
            if supervisor_id:
                new_user.supervisor_id = int(supervisor_id)
        

        db.session.add(new_user); db.session.commit()
        
        # Send Welcome Email
        try:
            supervisor_info = ""
            if new_user.supervisor_id:
                sup = User.query.get(new_user.supervisor_id)
                if sup:
                    supervisor_info = f"\n\nReporting Manager:\nName: {sup.name}\nEmail: {sup.email}\nPhone: {sup.phone_number}"

            msg = Message(f'Welcome to HR Pro Solutions - {new_user.name}', recipients=[new_user.email])
            msg.body = f"""Dear {new_user.name},

Welcome to the team! Your account has been successfully created.

Here are your login credentials:
Portal Role: {new_user.role}
Employee ID: {request.form['employee_id']}
Password: {request.form['password']}

Please login at: {url_for('login', _external=True)}
{supervisor_info}

We are excited to have you on board!

Best Regards,
HR Team
            """
            mail.send(msg)
            flash('New user registered and welcome email sent!', 'success')
        except Exception as e:
            print(f"Error sending welcome email: {e}")
            flash('New user registered, but failed to send welcome email.', 'warning')
            
        return redirect(url_for('dashboard'))
    return render_template('register.html', supervisors=supervisors, roles=roles)

@app.route('/dashboard')
@login_required
def dashboard():
    # Determine Role Base
    ur = Role.query.filter(Role.name.ilike(current_user.role)).first()
    base_role = ur.base_role if ur else current_user.role.lower()

    if base_role == 'employee':
        leave_requests = LeaveRequest.query.filter_by(user_id=current_user.id).order_by(LeaveRequest.start_date.desc()).all()
        return render_template('employee_dashboard.html', leave_requests=leave_requests)
    
    elif base_role == 'supervisor':
        team_members = User.query.filter_by(supervisor_id=current_user.id).order_by(User.employee_id).all()
        
        # Pending Request Logic
        if current_user.employee_id == MAIN_SUPERVISOR_ID:
            pending_requests = LeaveRequest.query.filter(LeaveRequest.status == 'Pending').order_by(LeaveRequest.start_date.desc()).all()
            processed_requests = LeaveRequest.query.filter(LeaveRequest.status != 'Pending').order_by(LeaveRequest.start_date.desc()).all()
            total_employees = User.query.count() # Main supervisor might want to see total
        else:
            team_member_ids = [member.id for member in team_members]
            pending_requests = LeaveRequest.query.filter(LeaveRequest.user_id.in_(team_member_ids), LeaveRequest.status == 'Pending').all()
            processed_requests = LeaveRequest.query.filter(LeaveRequest.user_id.in_(team_member_ids), LeaveRequest.status != 'Pending').order_by(LeaveRequest.start_date.desc()).all()
            total_employees = len(team_members)

        return render_template('supervisor_dashboard.html', pending_requests=pending_requests, processed_requests=processed_requests, 
                               total_employees=total_employees, team_members=team_members)
                               
    elif base_role == 'hr':
        search_query = request.args.get('search', '')
        role_filter = request.args.get('role', '')
        query = User.query
        if search_query:
            query = query.filter(or_(User.name.ilike(f'%{search_query}%'), User.employee_id.ilike(f'%{search_query}%')))
        if role_filter:
            query = query.filter(User.role.ilike(role_filter)) # Changed to ilike for case-insensitive matching
        
        all_employees = query.order_by(User.employee_id).all()
        total_employees_count = len(all_employees)
        
        role_counts = {}
        for e in all_employees:
             r = e.role.capitalize()
             role_counts[r] = role_counts.get(r, 0) + 1
             
        return render_template('hr_dashboard.html', all_employees=all_employees, total_employees=total_employees_count, role_counts=role_counts)
    
    else: return "<h1>Invalid Role</h1>"

@app.route('/attendance')
@login_required
def attendance():
    today = date.today()
    
    # Permission & Data Fetching
    ur = Role.query.filter(Role.name.ilike(current_user.role)).first()
    base_role = ur.base_role if ur else current_user.role.lower()

    employees = []
    is_hr = False
    stats = {'present': 0, 'leave': 0, 'cat_leave_counts': {}}
    
    search_query = request.args.get('q', '').strip()

    if base_role == 'hr':
        is_hr = True
        query = User.query
        if search_query:
            query = query.filter(or_(User.name.ilike(f'%{search_query}%'), User.employee_id.ilike(f'%{search_query}%')))
        employees = query.order_by(User.employee_id).all()
        
    elif base_role == 'supervisor':
        query = User.query.filter_by(supervisor_id=current_user.id)
        if search_query:
            query = query.filter(or_(User.name.ilike(f'%{search_query}%'), User.employee_id.ilike(f'%{search_query}%')))
        employees = query.order_by(User.employee_id).all()
    else:
        flash('Attendance access denied.', 'error')
        return redirect(url_for('dashboard'))

    # Fetch Attendance Records
    if employees:
        emp_ids = [e.id for e in employees]
        att_records = Attendance.query.filter(Attendance.date==today, Attendance.user_id.in_(emp_ids)).all()
        att_map = {r.user_id: r.status for r in att_records}
        
        for e in employees:
            status = att_map.get(e.id, 'Present')
            e.attendance_today = status
            
            if status == 'Present':
                stats['present'] += 1
            else:
                stats['leave'] += 1
                # Category breakdown (for HR usually)
                r = e.role.capitalize()
                stats['cat_leave_counts'][r] = stats['cat_leave_counts'].get(r, 0) + 1
    else:
        if not search_query:
             flash('No employees found to manage attendance.', 'warning')

    return render_template('attendance.html', employees=employees, stats=stats, is_hr=is_hr, today=today, search_query=search_query)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not current_user.check_password(current_password):
            flash('Your current password is incorrect.', 'error'); return redirect(url_for('profile'))
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error'); return redirect(url_for('profile'))
        current_user.set_password(new_password)
        db.session.commit()
        flash('Your password has been updated!', 'success'); return redirect(url_for('dashboard'))
    return render_template('profile.html')

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user_to_edit = User.query.get_or_404(user_id)
    if current_user.role != 'hr' and user_to_edit.supervisor_id != current_user.id:
        flash('You do not have permission to edit this user.', 'error')
        return redirect(url_for('dashboard'))
    # Fetch supervisors based on base_role
    sup_roles = [r.name for r in Role.query.filter_by(base_role='supervisor').all()]
    supervisors = User.query.filter(User.role.in_(sup_roles)).all() if sup_roles else []
    
    # Fallback for legacy data
    if not supervisors: supervisors = User.query.filter(User.role.ilike('supervisor')).all()
    if request.method == 'POST':
        user_to_edit.name = request.form['name']
        user_to_edit.email = request.form['email']
        user_to_edit.phone_number = request.form['phone_number']
        user_to_edit.address = request.form['address']
        user_to_edit.salary = float(request.form['salary'])
        if current_user.role == 'hr':
            user_to_edit.role = request.form['role']
            supervisor_id = request.form.get('supervisor_id')
            if supervisor_id:
                user_to_edit.supervisor_id = int(supervisor_id)
            else:
                user_to_edit.supervisor_id = None
        db.session.commit()
        flash(f'Details for {user_to_edit.name} have been updated.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_user.html', user_to_edit=user_to_edit, supervisors=supervisors, roles=Role.query.all())

@app.route('/remove_user/<int:user_id>', methods=['POST'])
@login_required
def remove_user(user_id):
    user_to_remove = User.query.get_or_404(user_id)
    can_remove = False
    # Determine Role Base
    ur = Role.query.filter(Role.name.ilike(current_user.role)).first()
    base_role = ur.base_role if ur else current_user.role.lower()

    if base_role == 'hr' and user_to_remove.id != current_user.id: can_remove = True
    if base_role == 'supervisor' and user_to_remove.supervisor_id == current_user.id: can_remove = True
    if not can_remove:
        flash('You do not have permission to remove this user.', 'error')
        return redirect(url_for('dashboard'))
    if user_to_remove.role == 'supervisor':
        for employee in user_to_remove.employees:
            employee.supervisor_id = None
            
    # Delete all related records to avoid Foreign Key errors
    LeaveRequest.query.filter_by(user_id=user_to_remove.id).delete()
    PersonalTask.query.filter_by(user_id=user_to_remove.id).delete()
    PasswordResetOTP.query.filter_by(user_id=user_to_remove.id).delete()
    
    db.session.delete(user_to_remove)
    db.session.commit()
    flash(f'User {user_to_remove.name} has been removed.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/mark_attendance', methods=['POST'])
@login_required
def mark_attendance():
    user_id = request.form.get('user_id')
    status = request.form.get('status') # 'Present' or 'Leave'
    target_date = date.today()
    
    target_user = User.query.get_or_404(user_id)
    
    # Permission Check
    is_authorized = False
    
    # Check Role Base
    ur = Role.query.filter(Role.name.ilike(current_user.role)).first()
    base_role = ur.base_role if ur else current_user.role.lower()
    
    if base_role == 'hr':
        is_authorized = True
    elif base_role == 'supervisor':
        if target_user.supervisor_id == current_user.id:
            is_authorized = True
    
    if not is_authorized:
        flash('Permission denied.', 'error')
        return redirect(url_for('dashboard'))

    # Update/Create Record
    attendance = Attendance.query.filter_by(user_id=user_id, date=target_date).first()
    if not attendance:
        attendance = Attendance(user_id=user_id, date=target_date, status=status, marked_by=current_user.id)
        db.session.add(attendance)
    else:
        attendance.status = status
        attendance.marked_by = current_user.id
    
    db.session.commit()
    
    # Email Notification if marked as Leave
    if status == 'Leave':
        try:
             msg = Message(f'Attendance Update: Marked as Leave', recipients=[target_user.email])
             msg.body = f"""Dear {target_user.name},

You have been  marked as 'Leave' for today ({target_date.strftime('%Y-%m-%d')}).

Marked by: {current_user.name} ({current_user.role})

 For further information contact your team leader or HR(if necessary only).

Regards,
HR System
             """
             mail.send(msg)
             flash(f"Marked {target_user.name} as LEAVE and sent notification email.", 'warning')
        except Exception as e:
            print(f"Email failed: {e}")
            flash(f"Marked {target_user.name} as LEAVE (Email failed).", 'warning')
    else:
        flash(f"Marked {target_user.name} as PRESENT.", 'success')
        
    return redirect(url_for('dashboard'))

@app.route('/apply_leave', methods=['GET', 'POST'])
@login_required
def apply_leave():
    if request.method == 'POST':
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        if start_date > end_date:
            flash('End date must be after start date.', 'error'); return redirect(url_for('apply_leave'))
        
        # Prepare Leave Letter Content
        rendered_html = render_template('leave_letter.html', 
                                        employee=current_user, 
                                        start_date=start_date, 
                                        end_date=end_date, 
                                        reason=request.form['reason'],
                                        team=request.form['team'],
                                        project=request.form['project'],
                                        team_leader_name=request.form['team_leader_name'],
                                        date_today=datetime.today().strftime('%Y-%m-%d'))
        
        # Save Request to DB
        new_request = LeaveRequest(
            user_id=current_user.id, start_date=start_date, end_date=end_date, reason=request.form['reason'],
            team=request.form['team'], project=request.form['project'],
            team_leader_name=request.form['team_leader_name'], team_leader_mobile=request.form['team_leader_mobile'],
            letter_path=None # PDF Generation Removed
        )
        db.session.add(new_request); db.session.commit()
        
        flash('Leave request submitted successfully!', 'success')

        # NOTIFY SUPERVISOR via Email
        try:
             supervisor = None
             if current_user.supervisor_id:
                 supervisor = User.query.get(current_user.supervisor_id)
             
             if supervisor and supervisor.email:
                 msg = Message(f'Formal Leave Application: {current_user.name}', recipients=[supervisor.email])
                 msg.body = f"Please view the attached leave application from {current_user.name}."
                 msg.html = rendered_html # Send the professional format as HTML email
                 mail.send(msg)
        except Exception as e:
            print(f"Failed to send email to supervisor: {e}")

        return redirect(url_for('dashboard'))
    return render_template('apply_leave.html')

@app.route('/respond_leave/<int:request_id>/<action>')
@login_required
def respond_leave(request_id, action):
    leave_request = LeaveRequest.query.get_or_404(request_id)
    is_authorized = False
    if current_user.employee_id == MAIN_SUPERVISOR_ID: is_authorized = True
    if leave_request.employee.supervisor_id == current_user.id: is_authorized = True
    if not is_authorized:
        flash('You do not have permission.', 'error'); return redirect(url_for('dashboard'))
    if action == 'approve':
        leave_request.status = 'Approved'; flash(f"Leave for {leave_request.employee.name} approved.", 'success')
        
        # Auto-Mark Manual Attendance for approved days
        # Iterate from start_date to end_date
        current_date_iter = leave_request.start_date
        end_date_iter = leave_request.end_date
        
        updated_any = False
        while current_date_iter <= end_date_iter:
            # Check if record exists
            existing_att = Attendance.query.filter_by(user_id=leave_request.user_id, date=current_date_iter).first()
            if not existing_att:
                new_att = Attendance(user_id=leave_request.user_id, date=current_date_iter, status='Leave', marked_by=current_user.id)
                db.session.add(new_att)
                updated_any = True
            else:
                # If exists, we force update it to Leave? 
                # User said "leave aprroved memebrs also can be manually marked as present" -> meaning Manual takes precedence potentially?
                # But here we are setting initial state. If it was already marked Present manually, do we overwrite?
                # Usually Approval overwrites. Manual Mark later can change it back.
                if existing_att.status != 'Leave':
                     existing_att.status = 'Leave'
                     existing_att.marked_by = current_user.id
                     updated_any = True
            
            current_date_iter += timedelta(days=1)
        
        if updated_any:
            # Send Notification "Auto Leave Marked"
             try:
                msg_auto = Message(f'Leave Attendance Marked', recipients=[leave_request.employee.email])
                msg_auto.body = f"""Dear {leave_request.employee.name},

Per your approved leave request, your attendance has been automatically marked as 'Leave' for {leave_request.start_date} to {leave_request.end_date}.

Regards,
HR System
                """
                mail.send(msg_auto)
             except Exception as e:
                print(f"Auto-mail failed: {e}")

    elif action == 'decline':
        leave_request.status = 'Declined'; flash(f"Leave for {leave_request.employee.name} declined.", 'error')
    
    db.session.commit()
    
    # Notify Employee (Status Update)
    try:
        emp_email = leave_request.employee.email
        status_msg = "Approved" if action == 'approve' else "Declined"
        msg = Message(f'Leave Request {status_msg}', recipients=[emp_email])
        msg.body = f"""Dear {leave_request.employee.name},

Your leave request from {leave_request.start_date} to {leave_request.end_date} has been {status_msg}.

Checked by: {current_user.name}

Regards,
HR Team
        """
        mail.send(msg)
    except Exception as e:
         print(f"Failed to send status email to employee: {e}")

    return redirect(url_for('dashboard'))

@app.route('/delete_leave_request/<int:request_id>')
@login_required
def delete_leave_request(request_id):
    leave_request = LeaveRequest.query.get_or_404(request_id)
    
    # Delete DB Record
    db.session.delete(leave_request)
    db.session.commit()
    
    flash('Leave request and associated documents permanently deleted.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/holidays', methods=['GET', 'POST'])
@login_required
def holidays():
    if current_user.role != 'hr':
        flash('You do not have permission.', 'error'); return redirect(url_for('dashboard'))
    if request.method == 'POST':
        new_holiday = Holiday(date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(), name=request.form['name'], type=request.form.get('type'))
        db.session.add(new_holiday); db.session.commit()
        flash('Holiday added!', 'success'); return redirect(url_for('holidays'))
    upcoming_holidays = Holiday.query.filter(Holiday.date >= datetime.today()).order_by(Holiday.date).all()
    return render_template('holidays.html', holidays=upcoming_holidays)

@app.route('/holidays/delete/<int:holiday_id>', methods=['POST'])
@login_required
def delete_holiday(holiday_id):
    if current_user.role != 'hr':
        flash('You do not have permission.', 'error'); return redirect(url_for('dashboard'))
    holiday = Holiday.query.get_or_404(holiday_id)
    db.session.delete(holiday); db.session.commit()
    flash('Holiday deleted.', 'success'); return redirect(url_for('holidays'))

@app.route('/roles', methods=['GET', 'POST'])
@login_required
def roles():
    # Check permission (HR Only?)
    ur = Role.query.filter(Role.name.ilike(current_user.role)).first()
    is_hr = ur and ur.base_role == 'hr'
    if not is_hr:
        flash('You do not have permission.', 'error'); return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        if 'delete_id' in request.form:
            role_to_delete = db.session.get(Role, request.form['delete_id'])
            # Don't delete seeded roles? Or allow.
            if role_to_delete: 
                db.session.delete(role_to_delete); db.session.commit(); flash('Role removed.', 'success')
        else:
            # Handle duplicates
            try:
                new_role = Role(name=request.form['name'], prefix=request.form['prefix'], base_role=request.form.get('base_role', 'employee'))
                db.session.add(new_role); db.session.commit()
                flash('Role added!', 'success')
            except Exception as e:
                db.session.rollback()
                flash('Error adding role. Name must be unique.', 'error')
        return redirect(url_for('roles'))
    all_roles = Role.query.all()
    return render_template('roles.html', roles=all_roles)

@app.route('/payslip')
@login_required
def view_payslip():
    today = datetime.today()
    payslip_data = calculate_payslip(current_user, today.year, today.month, db, Holiday, LeaveRequest)
    return render_template('payslip.html', payslip=payslip_data)

@app.route('/payroll_report')
@login_required
def payroll_report():
    if current_user.role not in ['hr', 'supervisor']:
        flash('You do not have permission.', 'error'); return redirect(url_for('dashboard'))
    today = datetime.today()
    search_query = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    view_type = request.args.get('view_type', 'month')
    
    selected_month = request.args.get('selected_month')
    selected_week = request.args.get('selected_week')
    selected_date = request.args.get('selected_date')

    today = datetime.today()
    target_date = today

    # Determine target date/month
    if view_type == 'month' and selected_month:
        try:
            target_date = datetime.strptime(selected_month, '%Y-%m')
        except:
             pass 
    elif view_type == 'week' and selected_week:
        try:
            # Parse ISO week
            year, week_num = map(int, selected_week.split('-W'))
            target_date = datetime.strptime(f'{year}-W{week_num}-1', "%Y-W%W-%w")
        except:
             pass
    elif view_type == 'day' and selected_date:
        try: 
             target_date = datetime.strptime(selected_date, '%Y-%m-%d')
        except:
             pass
    
    # Validation: Ensure not future (simple check)
    if target_date > datetime.today():
         # If future, clamp to today? Or handle logic inside. 
         # For simplicity, if month is future, fallback to current or clamp.
         # Actually prompt said "upto current only", assuming UI handles it or we clamp.
         if target_date.year > today.year or (target_date.year == today.year and target_date.month > today.month):
             target_date = today

    query = User.query
    # Supervisors should not see HR salaries as HR is a higher role
    if current_user.role == 'supervisor':
        query = query.filter(User.role != 'hr')
    
    if search_query:
        query = query.filter(or_(User.name.ilike(f'%{search_query}%'), User.employee_id.ilike(f'%{search_query}%')))
    if role_filter:
        query = query.filter(User.role == role_filter)
    employees = query.order_by(User.employee_id).all()
    
    payroll_data = []
    
    if view_type == 'month':
        month_year = target_date.strftime("%B %Y")
    elif view_type == 'week':
        # Show Week info
        month_year = f"Week {target_date.strftime('%W, %Y')}" 
    else:
         month_year = target_date.strftime("%d %B %Y")

    total_gross = 0
    total_deductions = 0
    total_net = 0
    
    # Data for charts
    role_salary = {}

    for employee in employees:
        # Calculate payslip based on selected period's month
        # Note: 'calculate_payslip' is monthly. For specific weeks, we estimate based on that month's data.
        payslip = calculate_payslip(employee, target_date.year, target_date.month, db, Holiday, LeaveRequest)
        payslip['employee_id'] = employee.employee_id
        payslip['user_id'] = employee.id
        
        # Adjust based on view_type
        if view_type == 'week':
            payslip['gross_salary'] /= 4
            payslip['deductions'] /= 4
            payslip['net_salary'] /= 4
            payslip['period_label'] = "Weekly Estimate"
        elif view_type == 'day':
            # Use per_day_salary as calculated in payslip
            payslip['gross_salary'] = payslip['per_day_salary']
            if payslip['total_payable_days'] > 0:
                payslip['deductions'] = payslip['deductions'] / payslip['total_payable_days'] # Average daily deduction
            else:
                payslip['deductions'] = 0
            payslip['net_salary'] = payslip['gross_salary'] - payslip['deductions']
            payslip['period_label'] = "Daily Rate"
        else:
            payslip['period_label'] = "Monthly Salary"

        payroll_data.append(payslip)
        
        # Accumulate totals
        total_gross += payslip['gross_salary']
        total_deductions += payslip['deductions']
        total_net += payslip['net_salary']
        
        # Accumulate chart data (Salary by Role)
        r = employee.role.capitalize()
        role_salary[r] = role_salary.get(r, 0) + payslip['net_salary']

    # New counts for UI
    total_employees = len(employees)
    role_counts = {}
    for e in employees:
        r = e.role.capitalize()
        role_counts[r] = role_counts.get(r, 0) + 1

    return render_template('payroll_report.html', 
                           payroll_data=payroll_data, 
                           month_year=month_year, 
                           view_type=view_type,
                           total_gross=total_gross,
                           total_deductions=total_deductions,
                           total_net=total_net,
                           role_salary=role_salary,
                           total_employees=total_employees,
                           role_counts=role_counts,
                           current_date=datetime.today().strftime('%Y-%m-%d'),
                           current_week=datetime.today().strftime('%Y-W%W'))

@app.route('/download_payslip/<int:user_id>')
@login_required
def download_payslip(user_id):
    if current_user.role not in ['hr', 'supervisor'] and current_user.id != user_id:
         flash('You do not have permission.', 'error'); return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    today = datetime.today()
    
    # Calculate payslip data (always monthly for the official slip)
    payslip = calculate_payslip(user, today.year, today.month, db, Holiday, LeaveRequest)
    payslip['employee_id'] = user.employee_id
    
    # Convert net pay to words
    net_pay_words = num2words(payslip['net_salary'], lang='en_IN').title().replace(',', '') + " Rupees"

    rendered_html = render_template('payslip_pdf.html', 
                                    payslip=payslip, 
                                    role=user.role,
                                    date_today=today.strftime('%d-%b-%Y'),
                                    net_pay_words=net_pay_words)
    
    pdf_filename = f"Payslip_{user.employee_id}_{today.strftime('%b_%Y')}.pdf"
    
    # Generate PDF in memory/temp and stream it? Or just return response
    # For simplicity and speed, we render to a BytesIO object or just return as response
    from io import BytesIO
    from flask import make_response
    # IMPORTANT: 'HTML' needs weasyprint. If missing, this will fail. Rolling back code means restoring this risk.
    # Assuming user has weasyprint or wants the code back regardless.
    try:
        from weasyprint import HTML
        pdf_file = BytesIO()
        HTML(string=rendered_html).write_pdf(pdf_file)
        pdf_file.seek(0)
        
        response = make_response(pdf_file.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={pdf_filename}'
        return response
    except ImportError:
         # Fallback to Browser Print if WeasyPrint is missing (Common on shared hosting)
         # We just return the rendered HTML directly. The template should have print styles.
         return rendered_html

@app.route('/download_all_payslips')
@login_required
def download_all_payslips():
    if current_user.role not in ['hr', 'supervisor']:
        flash('You do not have permission.', 'error'); return redirect(url_for('dashboard'))

    role_filter = request.args.get('role', '')
    view_type = request.args.get('view_type', 'month')
    today = datetime.today()

    query = User.query
    if current_user.role == 'supervisor':
        query = query.filter(User.role != 'hr')
    if role_filter:
        query = query.filter(User.role == role_filter)
    
    employees = query.order_by(User.employee_id).all()
    
    from io import BytesIO
    try:
        from weasyprint import HTML
    except ImportError:
        flash("PDF generation library (WeasyPrint) missing.", "error")
        return redirect(url_for('payroll_report'))

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for employee in employees:
            # Calculate payslip
            payslip = calculate_payslip(employee, today.year, today.month, db, Holiday, LeaveRequest)
            payslip['employee_id'] = employee.employee_id
            
            # Adjust based on view_type (Apply same logic as report)
            if view_type == 'week':
                payslip['gross_salary'] /= 4; payslip['deductions'] /= 4; payslip['net_salary'] /= 4
                period_label = "Weekly Estimate"
            elif view_type == 'day':
                payslip['gross_salary'] = payslip['per_day_salary']
                if payslip['total_payable_days'] > 0: payslip['deductions'] = payslip['deductions'] / payslip['total_payable_days']
                else: payslip['deductions'] = 0
                payslip['net_salary'] = payslip['gross_salary'] - payslip['deductions']
                period_label = "Daily Rate"
            else:
                period_label = "Monthly Salary"
            
            payslip['period_label'] = period_label 
            
            # Generate PDF
            net_pay_words = num2words(payslip['net_salary'], lang='en_IN').title().replace(',', '') + " Rupees"
            rendered_html = render_template('payslip_pdf.html', payslip=payslip, role=employee.role, date_today=today.strftime('%d-%b-%Y'), net_pay_words=net_pay_words)
            
            pdf_io = BytesIO()
            HTML(string=rendered_html).write_pdf(pdf_io)
            
            filename = f"{employee.employee_id}_{employee.name.replace(' ', '_')}_{view_type}.pdf"
            zip_file.writestr(filename, pdf_io.getvalue())
            
    zip_buffer.seek(0)
    filename = f"Payslips_{view_type}_{today.strftime('%b_%Y')}.zip"
    
    from flask import send_file
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=filename)

@app.route('/calendar')
@login_required
def view_calendar(): return render_template('calendar.html')

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    new_task = PersonalTask(user_id=current_user.id, date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(), task_description=request.form['task_description'])
    db.session.add(new_task); db.session.commit()
    flash('Task added!', 'success'); return redirect(url_for('view_calendar'))


@app.route('/api/events')
@login_required
def api_events():
    events = []
    start = request.args.get('start', '').split('T')[0]
    end = request.args.get('end', '').split('T')[0]
    try:
        start_date = datetime.strptime(start, '%Y-%m-%d').date()
        end_date = datetime.strptime(end, '%Y-%m-%d').date()
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() == 6:
                events.append({
                    'title': 'Sunday Holiday', 'start': current_date.isoformat(), 'allDay': True,
                    'backgroundColor': '#ffe5e5', 'borderColor': '#ffe5e5', 'display': 'background'
                })
            current_date += timedelta(days=1)
    except (ValueError, TypeError): pass

    holidays = Holiday.query.all()
    for h in holidays:
        event_data = {'title': h.name, 'start': h.date.isoformat(), 'allDay': True}
        if h.type == 'company_event':
            event_data['backgroundColor'] = '#D90429'; event_data['borderColor'] = '#D90429'
        else:
            event_data['display'] = 'list-item'; event_data['backgroundColor'] = '#e76f51'; event_data['borderColor'] = '#e76f51'
        events.append(event_data)
    
    
    leaves_query = LeaveRequest.query.filter_by(status='Approved')
    if current_user.role == 'hr' or current_user.employee_id == MAIN_SUPERVISOR_ID:
        leaves = leaves_query.all()
    elif current_user.role == 'supervisor':
        team_member_ids = [member.id for member in current_user.employees]
        team_member_ids.append(current_user.id) 
        leaves = leaves_query.filter(LeaveRequest.user_id.in_(team_member_ids)).all()
    else:
        leaves = leaves_query.filter_by(user_id=current_user.id).all()

    for l in leaves: events.append({'title': f"On Leave: {l.employee.name}", 'start': l.start_date.isoformat(), 'end': l.end_date.isoformat(), 'backgroundColor': '#2a9d8f', 'borderColor': '#2a9d8f'})
    
    tasks = PersonalTask.query.filter_by(user_id=current_user.id).all()
    for t in tasks: events.append({'title': t.task_description, 'start': t.date.isoformat(), 'allDay': True, 'backgroundColor': '#264653', 'borderColor': '#264653'})
    
    return jsonify(events)

@app.cli.command("init-db")
def init_db_command():
    """Clears the existing data and creates new tables."""
    db.create_all()
    print("Initialized the database.")

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'hr':
        flash('Permission denied', 'error'); return redirect(url_for('dashboard'))
    
    info = CompanyInfo.query.first()
    if not info:
        info = CompanyInfo()
        db.session.add(info); db.session.commit()
    
    if request.method == 'POST':
        info.name = request.form['name']
        info.address = request.form['address']
        info.email = request.form['email']
        info.phone = request.form['phone']
        info.gstn = request.form.get('gstn', '')
        db.session.commit()
        flash('Company details updated!', 'success')
        return redirect(url_for('settings'))
    
    return render_template('settings.html', info=info)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            # Generate 6-digit OTP
            otp = f"{random.randint(100000, 999999)}"
            
            # Save to DB
            new_otp = PasswordResetOTP(user_id=user.id, otp_code=otp)
            db.session.add(new_otp)
            db.session.commit()
            
            # Store ID in session for next steps
            session['reset_user_id'] = user.id
            session['otp_verified'] = False
            
            # SEND EMAIL
            try:
                msg = Message('Password Reset OTP', recipients=[email])
                msg.body = f"Your OTP for password reset is: {otp}\n\nThis code expires in 10 minutes."
                mail.send(msg)
                flash(f'OTP has been sent to {email}.', 'info')
            except Exception as e:
                print(f"Mail Error: {e}")
                flash(f'Error sending email. (Simulated OTP: {otp})', 'warning')
                
            return redirect(url_for('verify_otp'))
        else:
            flash('Email not found.', 'error')
            return redirect(url_for('forgot_password'))
            
    return render_template('forgot_password.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reset_user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        entered_otp = request.form['otp']
        user_id = session['reset_user_id']
        
        # Check latest OTP for user
        otp_record = PasswordResetOTP.query.filter_by(user_id=user_id).order_by(PasswordResetOTP.created_at.desc()).first()
        
        if otp_record and otp_record.otp_code == entered_otp:
            # Check expiry (e.g., 10 mins validity for entering)
            if (datetime.utcnow() - otp_record.created_at).total_seconds() > 600:
                flash('OTP has expired. Please resend.', 'error')
                return redirect(url_for('verify_otp'))
                
            otp_record.is_verified = True
            db.session.commit()
            session['otp_verified'] = True
            flash('OTP Verified! Set your new password.', 'success')
            return redirect(url_for('reset_new_password'))
        else:
            flash('Invalid OTP. Please try again.', 'error')
            
    return render_template('verify_otp.html')

@app.route('/resend_otp')
def resend_otp():
    if 'reset_user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['reset_user_id']
    user = User.query.get(user_id)
    
    # Check time since last OTP
    last_otp = PasswordResetOTP.query.filter_by(user_id=user_id).order_by(PasswordResetOTP.created_at.desc()).first()
    if last_otp and (datetime.utcnow() - last_otp.created_at).total_seconds() < 120:
        flash('Please wait 2 minutes before resending.', 'warning')
        return redirect(url_for('verify_otp'))
        
    # Generate New OTP
    otp = f"{random.randint(100000, 999999)}"
    new_otp = PasswordResetOTP(user_id=user.id, otp_code=otp)
    db.session.add(new_otp)
    db.session.commit()
    
    # SEND EMAIL
    try:
        msg = Message('Password Reset OTP (Resent)', recipients=[user.email])
        msg.body = f"Your new OTP is: {otp}\n\nThis code expires in 10 minutes."
        mail.send(msg)
        flash('New OTP sent to your email!', 'success')
    except Exception as e:
        print(f"Mail Error: {e}")
        flash(f'Error sending email. (Simulated OTP: {otp})', 'warning')

    return redirect(url_for('verify_otp'))

@app.route('/reset_new_password', methods=['GET', 'POST'])
def reset_new_password():
    if 'reset_user_id' not in session or not session.get('otp_verified'):
        flash('Session expired or unauthorized.', 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        password = request.form['password']
        confirm = request.form['confirm_password']
        
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('reset_new_password'))
            
        user = User.query.get(session['reset_user_id'])
        user.set_password(password)
        db.session.commit()
        
        # Cleanup
        session.pop('reset_user_id', None)
        session.pop('otp_verified', None)
        
        flash('Password updated successfully! Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('reset_password.html')

@app.route('/strategy')
@login_required
def strategy():
    return render_template('strategy.html')

@app.route('/manage_categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if current_user.role != 'hr': # checking base_role usually better but 'hr' works for main admin
        flash('Access denied', 'error'); return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if 'delete_id' in request.form:
            # Delete Logic
            rid = request.form.get('delete_id')
            role_to_del = Role.query.get(rid)
            if role_to_del:
                db.session.delete(role_to_del)
                db.session.commit()
                flash('Category removed.', 'success')
        else:
            # Add Logic
            name = request.form.get('name')
            prefix = request.form.get('prefix')
            if name and prefix:
                existing = Role.query.filter_by(name=name).first()
                if existing:
                    flash('Category already exists.', 'error')
                else:
                    # Default base_role logic: 
                    # If name contains 'supervisor', base='supervisor', if 'hr', base='hr', else 'employee'
                    base = 'employee'
                    if 'supervisor' in name.lower(): base = 'supervisor'
                    if 'hr' in name.lower() or 'human resource' in name.lower(): base = 'hr'
                    
                    new_role = Role(name=name, prefix=prefix, base_role=base)
                    db.session.add(new_role)
                    db.session.commit()
                    flash(f'Category {name} added.', 'success')
    
    categories = Role.query.all()
    return render_template('categories.html', categories=categories)

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)