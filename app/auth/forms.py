from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional, Regexp
from app.models import User

class LoginForm(FlaskForm):
    """Login form for user authentication."""
    email = StringField('Email Address', validators=[
        DataRequired(message='Email is required.'),
        Email(message='Please enter a valid email address.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your email address',
        'autocomplete': 'email'
    })
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your password',
        'autocomplete': 'current-password'
    })
    
    remember_me = BooleanField('Remember me', render_kw={
        'class': 'form-check-input'
    })
    
    submit = SubmitField('Sign In', render_kw={
        'class': 'btn btn-primary btn-lg w-100'
    })

class RegisterForm(FlaskForm):
    """Registration form (creates org workspace + admin)."""

    organization_name = StringField('Legal Organization Name', validators=[
        DataRequired(message='Organization name is required.'),
        Length(min=2, max=100, message='Organization name must be between 2 and 100 characters.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Legal organization name',
        'autocomplete': 'organization'
    })

    abn = StringField('ABN / ACN', validators=[
        DataRequired(message='ABN / ACN is required.'),
        Length(max=20, message='ABN / ACN must be less than 20 characters.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'ABN / ACN',
        'autocomplete': 'off'
    })
    first_name = StringField('First Name', validators=[
        DataRequired(message='First name is required.'),
        Length(min=1, max=60, message='First name must be 60 characters or less.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'First name',
        'autocomplete': 'given-name'
    })

    last_name = StringField('Last Name', validators=[
        DataRequired(message='Last name is required.'),
        Length(min=1, max=60, message='Last name must be 60 characters or less.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Last name',
        'autocomplete': 'family-name'
    })

    title = StringField('Role / Title', validators=[
        DataRequired(message='Role/title is required.'),
        Length(max=80, message='Role/title must be 80 characters or less.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'e.g. Director, Practice Manager',
        'autocomplete': 'organization-title'
    })

    mobile_number = StringField('Mobile Number (optional)', validators=[
        Optional(),
        Length(max=40, message='Mobile number must be 40 characters or less.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Optional (for security alerts / MFA later)',
        'autocomplete': 'tel'
    })

    time_zone = SelectField(
        'Time Zone',
        choices=[
            ('Australia/Sydney', 'Australia/Sydney'),
            ('Australia/Melbourne', 'Australia/Melbourne'),
            ('Australia/Brisbane', 'Australia/Brisbane'),
            ('Australia/Perth', 'Australia/Perth'),
            ('Australia/Adelaide', 'Australia/Adelaide'),
            ('Australia/Hobart', 'Australia/Hobart'),
        ],
        default='Australia/Sydney',
        validators=[DataRequired(message='Time zone is required.')],
        render_kw={'class': 'form-select form-select-lg'},
    )

    email = StringField('Email Address', validators=[
        DataRequired(message='Email is required.'),
        Email(message='Please enter a valid email address.'),
        Length(max=120, message='Email must be less than 120 characters.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your email address',
        'autocomplete': 'email'
    })
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required.'),
        Length(min=8, message='Password must be at least 8 characters long.'),
        Regexp(r'.*[A-Za-z].*', message='Password must contain at least one letter.'),
        Regexp(r'.*\d.*', message='Password must contain at least one number.'),
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Min. 8 characters, letter + number',
        'autocomplete': 'new-password'
    })
    
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password.'),
        EqualTo('password', message='Passwords must match.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Confirm your password',
        'autocomplete': 'new-password'
    })
    
    submit = SubmitField('Create Account', render_kw={
        'class': 'btn btn-primary btn-lg w-100'
    })

    accept_terms = BooleanField('I agree to the Terms and Conditions, Privacy Policy, and Disclaimer', validators=[
        DataRequired(message='You must accept the Terms, Privacy Policy, and Disclaimer to continue.')
    ], render_kw={'class': 'form-check-input'})
    
    def validate_email(self, field):
        """Check if email is already registered."""
        user = User.query.filter_by(email=field.data.lower().strip()).first()
        if user:
            raise ValidationError('This email address is already registered. Please use a different email or sign in.')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email Address', validators=[
        DataRequired(message='Email is required.'),
        Email(message='Please enter a valid email address.'),
        Length(max=120, message='Email must be less than 120 characters.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your email address',
        'autocomplete': 'email'
    })
    submit = SubmitField('Send Reset Link', render_kw={'class': 'btn btn-primary btn-lg w-100'})


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(message='Password is required.'),
        Length(min=6, message='Password must be at least 6 characters long.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Create a new password (min. 6 characters)',
        'autocomplete': 'new-password'
    })

    password_confirm = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your password.'),
        EqualTo('password', message='Passwords must match.')
    ], render_kw={
        'class': 'form-control form-control-lg',
        'placeholder': 'Confirm your new password',
        'autocomplete': 'new-password'
    })

    submit = SubmitField('Reset Password', render_kw={'class': 'btn btn-primary btn-lg w-100'})