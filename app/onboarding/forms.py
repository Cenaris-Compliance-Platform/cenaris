from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, RadioField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional


class OnboardingOrganizationForm(FlaskForm):
    organization_name = StringField(
        'Legal Organization Name',
        validators=[DataRequired(), Length(min=2, max=100)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Your organization name'},
    )

    trading_name = StringField(
        'Trading Name (if different)',
        validators=[Optional(), Length(max=100)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Trading name (optional)'},
    )

    abn = StringField(
        'ABN / ACN',
        validators=[DataRequired(), Length(max=20)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'ABN / ACN'},
    )

    organization_type = SelectField(
        'Organization Type',
        choices=[
            ('', 'Select...'),
            ('sole_trader', 'Sole trader'),
            ('company', 'Company'),
            ('not_for_profit', 'Not-for-profit'),
            ('trust_partnership', 'Trust / partnership'),
        ],
        validators=[DataRequired()],
        render_kw={'class': 'form-select form-select-lg'},
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
        render_kw={'class': 'form-select form-select-lg'},
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
