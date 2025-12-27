from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import HiddenField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional


class OrganizationProfileSettingsForm(FlaskForm):
    form_name = HiddenField(default='profile')

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

    submit = SubmitField(
        'Save Profile',
        render_kw={'class': 'btn btn-primary btn-lg'},
    )


class OrganizationBillingForm(FlaskForm):
    form_name = HiddenField(default='billing')

    billing_email = StringField(
        'Billing Email',
        validators=[Optional(), Email(), Length(max=120)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'Billing email (optional)'
        },
    )

    billing_address = StringField(
        'Billing Address',
        validators=[Optional(), Length(max=255)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'Billing address (optional)'
        },
    )

    submit = SubmitField(
        'Save Billing',
        render_kw={'class': 'btn btn-primary btn-lg'},
    )

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)
        billing_email = (self.billing_email.data or '').strip()
        billing_address = (self.billing_address.data or '').strip()

        # If either billing field is provided, require both.
        if billing_email or billing_address:
            if not billing_email:
                self.billing_email.errors.append('Billing email is required when billing address is provided.')
                ok = False
            if not billing_address:
                self.billing_address.errors.append('Billing address is required when billing email is provided.')
                ok = False

        return ok


class UserAvatarForm(FlaskForm):
    avatar = FileField(
        'Profile Photo',
        validators=[
            FileAllowed(['png', 'jpg', 'jpeg', 'webp'], 'Avatar must be a PNG/JPG/WEBP image.')
        ],
        render_kw={
            'class': 'form-control form-control-lg',
            'accept': '.png,.jpg,.jpeg,.webp',
        },
    )

    submit = SubmitField(
        'Upload Photo',
        render_kw={'class': 'btn btn-primary btn-lg'},
    )


class InviteMemberForm(FlaskForm):
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=120)],
        render_kw={
            'class': 'form-control',
            'placeholder': 'name@company.com',
            'autocomplete': 'email',
        },
    )

    role = SelectField(
        'Role',
        choices=[('User', 'User'), ('Admin', 'Admin')],
        validators=[DataRequired()],
        render_kw={'class': 'form-select'},
        default='User',
    )

    submit = SubmitField(
        'Invite',
        render_kw={'class': 'btn btn-primary'},
    )


class MembershipActionForm(FlaskForm):
    membership_id = HiddenField(validators=[DataRequired()])

    submit = SubmitField(
        'Remove',
        render_kw={'class': 'btn btn-sm btn-outline-danger'},
    )

class PendingInviteResendForm(FlaskForm):
    membership_id = HiddenField(validators=[DataRequired()])

    submit = SubmitField(
        'Resend invite',
        render_kw={'class': 'btn btn-sm btn-outline-primary'},
    )

class PendingInviteRevokeForm(FlaskForm):
    membership_id = HiddenField(validators=[DataRequired()])

    submit = SubmitField(
        'Revoke',
        render_kw={'class': 'btn btn-sm btn-outline-danger'},
    )
