from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app.auth import bp
from app.auth.forms import LoginForm, SignupForm
from app.models import User, Organization
from app import db

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        password = form.password.data

        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            flash('Welcome back! You have been successfully signed in.', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email address or password. Please try again.', 'error')
    
    return render_template('auth/login.html', form=form, title='Sign In')

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = SignupForm()
    
    if form.validate_on_submit():
        organization_name = form.organization_name.data.strip()
        full_name = form.full_name.data.strip()
        email = form.email.data.lower().strip()
        password = form.password.data
        
        try:
            organization = Organization(
                name=organization_name,
                contact_email=email
            )
            db.session.add(organization)
            db.session.flush()  # assigns organization.id

            user = User(
                email=email,
                full_name=full_name,
                role='Admin',
                organization_id=organization.id
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Your organization and admin account were created! You can now sign in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating your account. Please try again.', 'error')
    
    return render_template('auth/signup.html', form=form, title='Create Account')

@bp.route('/logout', methods=['POST'])
def logout():
    """User logout route."""
    if current_user.is_authenticated:
        logout_user()
        flash('You have been successfully signed out.', 'info')
    return redirect(url_for('main.index'))