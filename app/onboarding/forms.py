from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Length, Optional


class OnboardingOrganizationForm(FlaskForm):
    organization_name = StringField(
        'Organization Name',
        validators=[DataRequired(), Length(min=2, max=100)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Your organization name'},
    )

    abn = StringField(
        'ABN',
        validators=[Optional(), Length(max=20)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'ABN (optional)'},
    )

    address = StringField(
        'Address',
        validators=[Optional(), Length(max=255)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Address (optional)'},
    )

    contact_email = StringField(
        'Contact Email',
        validators=[Optional(), Email(), Length(max=120)],
        render_kw={'class': 'form-control form-control-lg', 'placeholder': 'Contact email (optional)'},
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
