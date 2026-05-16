# Auth routes - Login, Signup, Logout
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app import db
from app.models import User, Role


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        if current_user.is_vendor:
            return redirect(url_for('vendor.dashboard'))
        return redirect(url_for('admin.dashboard'))  # customer can go to a customer panel later
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if user.status != 'active':
                if user.status == 'pending_email':
                    flash('Please verify your email address before logging in.', 'warning')
                else:
                    flash('Your account is blocked. Contact admin.', 'danger')
                return render_template('auth/login.html')
            login_user(user)
            flash('Login successful.', 'success')
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            if user.is_vendor:
                return redirect(url_for('vendor.dashboard'))
            return redirect(url_for('admin.dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role_name = request.form.get('role', 'customer')
        if not name or not email or not password:
            flash('Name, email and password are required.', 'danger')
            return render_template('auth/signup.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/signup.html')
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role.query.filter_by(name='customer').first()
        user = User(name=name, email=email, role_id=role.id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. You can login now.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/signup.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
