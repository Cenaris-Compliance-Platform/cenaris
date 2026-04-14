from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import BooleanField, HiddenField, IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional


class OrganizationProfileSettingsForm(FlaskForm):
    form_name = HiddenField(default='profile')

    name = StringField(
        'Organisation Name',
        validators=[DataRequired(), Length(min=2, max=100)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'Organisation name'
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

    acn = StringField(
        'ACN',
        validators=[Optional(), Length(max=20)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'ACN (optional)'
        },
    )

    contact_number = StringField(
        'Contact Number',
        validators=[Optional(), Length(max=40)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'Contact number (optional)'
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


class OrganizationMonthlyReportForm(FlaskForm):
    form_name = HiddenField(default='monthly_reports')

    monthly_report_enabled = BooleanField(
        'Enable monthly report delivery',
        render_kw={'class': 'form-check-input'},
    )

    monthly_report_recipient_email = StringField(
        'Monthly report recipient email',
        validators=[Optional(), Email(), Length(max=120)],
        render_kw={
            'class': 'form-control form-control-lg',
            'placeholder': 'reports@company.com',
            'autocomplete': 'email',
        },
    )

    submit = SubmitField(
        'Save Monthly Report Settings',
        render_kw={'class': 'btn btn-primary btn-lg'},
    )

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)

        enabled = bool(self.monthly_report_enabled.data)
        recipient = (self.monthly_report_recipient_email.data or '').strip()
        if enabled and not recipient:
            self.monthly_report_recipient_email.errors.append(
                'Recipient email is required when monthly report delivery is enabled.'
            )
            ok = False

        return ok


class OrganizationBillingAccessForm(FlaskForm):
    form_name = HiddenField(default='billing_access')

    billing_plan_code = SelectField(
        'Plan',
        choices=[
            ('starter', 'Starter'),
            ('team', 'Team'),
            ('scale', 'Scale'),
            ('enterprise', 'Enterprise'),
        ],
        validators=[DataRequired()],
        render_kw={'class': 'form-select'},
        default='starter',
    )

    billing_status = SelectField(
        'Billing Status',
        choices=[
            ('inactive', 'Inactive'),
            ('active', 'Active'),
            ('trialing', 'Trialing'),
            ('past_due', 'Past Due'),
            ('canceled', 'Canceled'),
        ],
        validators=[DataRequired()],
        render_kw={'class': 'form-select'},
        default='active',
    )

    billing_internal_override = BooleanField(
        'Internal override (org-wide)',
        render_kw={'class': 'form-check-input'},
    )

    billing_demo_override_enabled = BooleanField(
        'Demo override enabled (no auto-expiry)',
        render_kw={'class': 'form-check-input'},
    )

    billing_override_reason = StringField(
        'Override reason',
        validators=[Optional(), Length(max=255)],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Reason for internal/demo override (optional)',
        },
    )

    submit = SubmitField(
        'Save Billing Access',
        render_kw={'class': 'btn btn-warning'},
    )


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


class UserProfileForm(FlaskForm):
    first_name = StringField(
        'First Name',
        validators=[DataRequired(), Length(min=1, max=60)],
        render_kw={
            'class': 'form-control form-control-lg',
            'autocomplete': 'given-name',
            'placeholder': 'First name',
        },
    )

    last_name = StringField(
        'Last Name',
        validators=[Optional(), Length(max=60)],
        render_kw={
            'class': 'form-control form-control-lg',
            'autocomplete': 'family-name',
            'placeholder': 'Last name (optional)',
        },
    )

    submit = SubmitField(
        'Save',
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
        # Populated dynamically per-organization with (role_id, role_name)
        choices=[],
        validators=[DataRequired()],
        render_kw={'class': 'form-select'},
        default='',
    )

    department_id = SelectField(
        'Department',
        choices=[('', 'Select department')],
        validators=[Optional()],
        render_kw={'class': 'form-select'},
        default='',
    )

    new_department_name = StringField(
        'New Department',
        validators=[Optional(), Length(max=80)],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Create new department (optional)',
            'autocomplete': 'off',
        },
    )

    new_department_color = SelectField(
        'Color',
        choices=[
            ('primary', 'Blue'),
            ('secondary', 'Gray'),
            ('success', 'Green'),
            ('info', 'Teal'),
            ('warning', 'Yellow'),
            ('danger', 'Red'),
            ('dark', 'Dark'),
        ],
        validators=[Optional()],
        render_kw={'class': 'form-select'},
        default='primary',
    )

    submit = SubmitField(
        'Invite',
        render_kw={'class': 'btn btn-primary'},
    )

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)

        dept_id = (self.department_id.data or '').strip()
        new_dept = (self.new_department_name.data or '').strip()

        # Require either selecting a department OR providing a new department name.
        if not dept_id and not new_dept:
            self.department_id.errors.append('Please select a department (or create one) before inviting.')
            ok = False

        return ok


class MembershipActionForm(FlaskForm):
    membership_id = HiddenField(validators=[DataRequired()])
    action = HiddenField(validators=[DataRequired()])  # 'disable' or 'delete'

    submit = SubmitField(
        'Remove',
        render_kw={'class': 'btn btn-sm btn-outline-danger'},
    )


class UpdateMemberRoleForm(FlaskForm):
    membership_id = HiddenField(validators=[DataRequired()])
    role_id = SelectField(
        'Role',
        choices=[],
        validators=[DataRequired()],
        render_kw={'class': 'form-select form-select-sm'},
        default='',
    )

    submit = SubmitField(
        'Update role',
        render_kw={'class': 'btn btn-sm btn-primary'},
    )


class UpdateMemberDepartmentForm(FlaskForm):
    membership_id = HiddenField(validators=[DataRequired()])
    department_id = SelectField(
        'Department',
        choices=[('', 'Unassigned')],
        validators=[Optional()],
        render_kw={'class': 'form-select form-select-sm'},
        default='',
    )

    submit = SubmitField(
        'Update department',
        render_kw={'class': 'btn btn-sm btn-primary'},
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


class InitializeComplianceDataForm(FlaskForm):
    submit = SubmitField(
        'Initialize NDIS Data',
        render_kw={'class': 'btn btn-outline-success'},
    )


class CreateDepartmentForm(FlaskForm):
    name = StringField(
        'Department name',
        validators=[DataRequired(), Length(max=80)],
        render_kw={
            'class': 'form-control',
            'placeholder': 'e.g., Finance',
            'autocomplete': 'off',
        },
    )

    color = SelectField(
        'Color',
        choices=[
            ('primary', 'Blue'),
            ('secondary', 'Gray'),
            ('success', 'Green'),
            ('info', 'Teal'),
            ('warning', 'Yellow'),
            ('danger', 'Red'),
            ('dark', 'Dark'),
        ],
        validators=[DataRequired()],
        default='primary',
        render_kw={'class': 'form-select'},
    )


class EditDepartmentForm(FlaskForm):
    name = StringField(
        'Department name',
        validators=[DataRequired(), Length(max=80)],
        render_kw={'class': 'form-control', 'autocomplete': 'off'},
    )

    color = SelectField(
        'Color',
        choices=[
            ('primary', 'Blue'),
            ('secondary', 'Gray'),
            ('success', 'Green'),
            ('info', 'Teal'),
            ('warning', 'Yellow'),
            ('danger', 'Red'),
            ('dark', 'Dark'),
        ],
        validators=[DataRequired()],
        render_kw={'class': 'form-select'},
    )


class OrganizationAISettingsForm(FlaskForm):
    policy_draft_use_llm = BooleanField('Enable LLM policy drafting')

    max_query_chars = IntegerField(
        'Max query chars',
        validators=[DataRequired()],
        render_kw={'class': 'form-control', 'min': 100, 'max': 5000},
    )
    max_top_k = IntegerField(
        'Max top_k',
        validators=[DataRequired()],
        render_kw={'class': 'form-control', 'min': 1, 'max': 20},
    )
    max_citation_text_chars = IntegerField(
        'Max citation chars',
        validators=[DataRequired()],
        render_kw={'class': 'form-control', 'min': 100, 'max': 5000},
    )
    max_answer_chars = IntegerField(
        'Max RAG answer chars',
        validators=[DataRequired()],
        render_kw={'class': 'form-control', 'min': 200, 'max': 10000},
    )
    max_policy_draft_chars = IntegerField(
        'Max policy draft chars',
        validators=[DataRequired()],
        render_kw={'class': 'form-control', 'min': 500, 'max': 20000},
    )
    rag_rate_limit = StringField(
        'RAG rate limit',
        validators=[DataRequired(), Length(max=40)],
        render_kw={'class': 'form-control', 'placeholder': 'e.g. 20 per minute'},
    )
    policy_rate_limit = StringField(
        'Policy rate limit',
        validators=[DataRequired(), Length(max=40)],
        render_kw={'class': 'form-control', 'placeholder': 'e.g. 10 per minute'},
    )

    submit = SubmitField(
        'Save AI Controls',
        render_kw={'class': 'btn btn-primary'},
    )

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)

        def _bounded(field, minimum: int, maximum: int, label: str):
            nonlocal ok
            val = field.data
            if val is None or int(val) < minimum or int(val) > maximum:
                field.errors.append(f'{label} must be between {minimum} and {maximum}.')
                ok = False

        _bounded(self.max_query_chars, 100, 5000, 'Max query chars')
        _bounded(self.max_top_k, 1, 20, 'Max top_k')
        _bounded(self.max_citation_text_chars, 100, 5000, 'Max citation chars')
        _bounded(self.max_answer_chars, 200, 10000, 'Max RAG answer chars')
        _bounded(self.max_policy_draft_chars, 500, 20000, 'Max policy draft chars')
        return ok


class OrganizationAIUsageRetentionForm(FlaskForm):
    days = IntegerField(
        'Retention (days)',
        validators=[DataRequired()],
        render_kw={'class': 'form-control', 'min': 1, 'max': 3650},
    )
    dry_run = BooleanField('Dry run only (recommended first)', default=True)
    submit = SubmitField(
        'Run Retention',
        render_kw={'class': 'btn btn-outline-warning'},
    )

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)
        val = self.days.data
        if val is None or int(val) < 1 or int(val) > 3650:
            self.days.errors.append('Retention days must be between 1 and 3650.')
            ok = False
        return ok


class DeleteDepartmentForm(FlaskForm):
    """CSRF-protected delete form."""
    pass
