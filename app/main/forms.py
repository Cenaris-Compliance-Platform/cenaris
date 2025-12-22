from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Length, Optional


class OrganizationSettingsForm(FlaskForm):
    name = StringField(
        'Organization Name',
        validators=[DataRequired(), Length(min=2, max=100)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'Organization name'
        },
    )

    abn = StringField(
        'ABN',
        validators=[Optional(), Length(max=20)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'ABN (optional)'
        },
    )

    address = StringField(
        'Address',
        validators=[Optional(), Length(max=255)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'Address (optional)'
        },
    )

    contact_email = StringField(
        'Contact Email',
        validators=[Optional(), Email(), Length(max=120)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'Contact email (optional)'
        },
    )

    logo = FileField(
        'Organization Logo',
        validators=[
            FileAllowed(['png', 'jpg', 'jpeg', 'webp'], 'Logo must be a PNG/JPG/WEBP image.')
        ],
        render_kw={
            'class': 'form-control form-control-lg',
            'accept': '.png,.jpg,.jpeg,.webp'
        },
    )

    theme = RadioField(
        'Theme',
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='light',
        validators=[DataRequired()],
    )

    submit = SubmitField(
        'Save Settings',
        render_kw={'class': 'btn btn-primary btn-lg'},
    )
