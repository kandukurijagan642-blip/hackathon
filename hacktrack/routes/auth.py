from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
import datetime

from database import db
from models import User, ActivityLog

auth_bp = Blueprint('auth', __name__)

def log_activity(user_id, action, details=None):
    """Utility to log user activities for audit trail"""
    try:
        ip = request.remote_addr
        log = ActivityLog(user_id=user_id, action=action, ip_address=ip, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_by_role(current_user.role)
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid email or password. Please try again.', 'danger')
            return render_template('auth/login.html')
            
        login_user(user, remember=remember)
        log_activity(user.id, "User Login", f"Successful login from IP: {request.remote_addr}")
        
        flash(f'Welcome back, {user.name}!', 'success')
        
        next_page = request.args.get('next') or request.form.get('next')
        if next_page and next_page.startswith('/') and not next_page.startswith('//'):
            return redirect(next_page)
            
        return redirect_by_role(user.role)
        
    return render_template('auth/login.html')

@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    if request.method == 'POST':
        log_activity(current_user.id, "User Logout")
        logout_user()
        flash('You have been logged out successfully.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/logout_confirm.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a secure reset token (valid for 1 hour)
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            # Send password reset email via mock channel
            from utils import send_mock_email
            email_body = f"Hello {user.name},\n\nClick the link below to reset your HackTrack password:\n{reset_url}\n\nIf you did not request this, please ignore this email.\n\nBest regards,\nHackTrack Team"
            send_mock_email(user.email, "Reset Your HackTrack Password", email_body)
            
            log_activity(user.id, "Forgot Password Requested", f"Reset token generated for {email}")
            flash('A password reset link has been sent to your email address.', 'info')
        else:
            flash('If that email exists in our records, a reset link has been sent.', 'info')
            
        return render_template('auth/forgot_password.html')
        
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except (SignatureExpired, BadTimeSignature):
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
        
    user = User.query.filter_by(email=email).first_or_404()
    
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'warning')
            return render_template('auth/reset_password.html', token=token)
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)
            
        user.password = generate_password_hash(password)
        db.session.commit()
        
        log_activity(user.id, "Password Reset Success", "User successfully reset their password via token")
        flash('Your password has been reset successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', token=token)

def redirect_by_role(role):
    if role == 'Admin':
        return redirect(url_for('admin.dashboard'))
    elif role == 'Organizer':
        return redirect(url_for('organizer.dashboard'))
    elif role == 'Judge':
        return redirect(url_for('judge.dashboard'))
    elif role == 'Leader':
        return redirect(url_for('leader.dashboard'))
    else:
        return redirect(url_for('auth.login'))
