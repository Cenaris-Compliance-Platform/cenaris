from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, RadioField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional


class OnboardingOrganizationForm(FlaskForm):
    organization_name = StringField(
        'Legal Organisation Name',
        validators=[DataRequired(), Length(min=2, max=100)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Your organisation name'},
    )

    trading_name = StringField(
        'Trading Name (if different)',
        validators=[Optional(), Length(max=100)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Trading name (optional)'},
    )

    abn = StringField(
        'ABN (required)',
        validators=[DataRequired(), Length(max=20)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'ABN'},
    )

    acn = StringField(
        'ACN (optional)',
        validators=[Optional(), Length(max=20)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'ACN (optional)'},
    )

    organization_type = SelectField(
        'Organisation Type',
        choices=[
            ('', 'Select...'),
            ('sole_trader', 'Sole Trader'),
            ('company', 'Company'),
            ('not_for_profit', 'Not-for-Profit'),
            ('partnership', 'Partnership'),
            ('trust', 'Trust'),
            ('government', 'Government / Public Sector'),
        ],
        validators=[DataRequired()],
        render_kw={'class': 'form-select minimal-select'},
    )

    industry = SelectField(
        'Primary Industry / Sector',
        choices=[
            ('', 'Select...'),
            ('ndis', 'NDIS'),
            ('aged_care', 'Aged Care'),
            ('health', 'Health'),
            ('education', 'Education'),
            ('corporate', 'Corporate'),
            ('other', 'Other'),
        ],
        validators=[DataRequired()],
        render_kw={'class': 'form-select minimal-select'},
    )

    address = StringField(
        'Registered Address / Principal Place of Business',
        validators=[DataRequired(), Length(max=255)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Address'},
    )

    contact_email = StringField(
        'Primary Business Email',
        validators=[DataRequired(), Email(), Length(max=120)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Business email'},
    )

    operates_in_australia = BooleanField(
        'Organisation operates in Australia',
        validators=[DataRequired(message='You must confirm your organisation operates in Australia.')],
        render_kw={'class': 'form-check-input'},
    )

    platform_disclaimer_ack = BooleanField(
        'I understand Cenaris is not an auditor, not a compliance guarantee, and is a decision-support platform',
        validators=[DataRequired(message='You must acknowledge the platform disclaimer to continue.')],
        render_kw={'class': 'form-check-input'},
    )

    responsibility_ack = BooleanField(
        'I confirm my organisation is responsible for the accuracy of uploaded materials',
        validators=[DataRequired(message='You must confirm responsibility for uploaded materials to continue.')],
        render_kw={'class': 'form-check-input'},
    )

    authority_to_upload_ack = BooleanField(
        'I confirm my organisation has authority to upload documents',
        validators=[DataRequired(message='You must confirm authority to upload documents to continue.')],
        render_kw={'class': 'form-check-input'},
    )

    data_processing_ack = BooleanField(
        'I acknowledge how data is stored and processed for the service',
        validators=[DataRequired(message='You must acknowledge data storage and processing to continue.')],
        render_kw={'class': 'form-check-input'},
    )

    accept_terms = BooleanField(
        'I agree to the Terms and Conditions, Privacy Policy, and Disclaimer',
        validators=[DataRequired(message='You must accept the Terms, Privacy Policy, and Disclaimer to continue.')],
        render_kw={'class': 'form-check-input'},
    )

    submit = SubmitField('Continue', render_kw={'class': 'btn btn-primary btn-lg w-100'})


class OnboardingBillingForm(FlaskForm):
    billing_email = StringField(
        'Billing Email',
        validators=[DataRequired(), Email(), Length(max=120)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'billing@company.com'},
    )

    billing_address = StringField(
        'Billing Address',
        validators=[DataRequired(), Length(max=255)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Billing address'},
    )

    submit = SubmitField('Continue', render_kw={'class': 'btn btn-primary btn-lg w-100'})


class OnboardingLogoForm(FlaskForm):
    logo = FileField(
        'Organization Logo',
        validators=[FileAllowed(['png', 'jpg', 'jpeg', 'webp'], 'Logo must be a PNG/JPG/WEBP image.')],
        render_kw={'class': 'form-control form-control-lg', 'accept': '.png,.jpg,.jpeg,.webp'},
    )
    submit = SubmitField('Continue', render_kw={'class': 'btn btn-primary btn-lg w-100'})


class OnboardingThemeForm(FlaskForm):
    theme = RadioField(
        'Theme',
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='light',
        validators=[DataRequired()],
    )
    submit = SubmitField('Finish Setup', render_kw={'class': 'btn btn-primary btn-lg w-100'})
