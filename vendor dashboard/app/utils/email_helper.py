# Send email to vendor (e.g. on approval) - uses app config
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def send_email(to_email, subject, body_text, body_html=None):
    """Send email if MAIL_SERVER is configured. Otherwise no-op."""
    mail_server = (current_app.config.get('MAIL_SERVER') or '').strip()
    if not mail_server:
        current_app.logger.warning('Email not sent: MAIL_SERVER not set. Set in .env for MailHog (MAIL_SERVER=localhost, MAIL_PORT=1025, MAIL_USE_TLS=0).')
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@genspark.com')
        msg['To'] = to_email
        msg.attach(MIMEText(body_text, 'plain'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html'))
        port = current_app.config.get('MAIL_PORT', 587)
        use_tls = current_app.config.get('MAIL_USE_TLS')
        with smtplib.SMTP(mail_server, port) as server:
            if use_tls:
                server.starttls()
            if current_app.config.get('MAIL_USERNAME'):
                server.login(
                    current_app.config['MAIL_USERNAME'],
                    current_app.config.get('MAIL_PASSWORD', '')
                )
            server.sendmail(msg['From'], to_email, msg.as_string())
        current_app.logger.info(f'Email sent to {to_email}')
        return True
    except Exception as e:
        current_app.logger.exception(f'Email send failed to {to_email}: {e}')
        return False


def send_vendor_approval_email(vendor):
    """Notify vendor at their email that their account was approved."""
    to = vendor.user.email
    name = vendor.user.name or 'Vendor'
    shop = vendor.shop_name or 'Your shop'
    subject = 'GenSpark – Vendor Account Approved'
    base = current_app.config.get('PREFERRED_URL', 'http://127.0.0.1:5000')
    text = f"""Dear {name},

We are pleased to inform you that your vendor account for "{shop}" has been approved by our administration team.

You may now log in to the vendor dashboard to manage orders, inventory, assembly, and earnings.

Login URL: {base}/auth/login

If you have any questions, please do not hesitate to contact us.

Yours sincerely,
GenSpark Team
"""
    html = f"""
    <p>Dear {name},</p>
    <p>We are pleased to inform you that your vendor account for <strong>{shop}</strong> has been approved by our administration team.</p>
    <p>You may now log in to the vendor dashboard to manage orders, inventory, assembly, and earnings.</p>
    <p><a href="{base}/auth/login">Log in to GenSpark</a></p>
    <p>If you have any questions, please do not hesitate to contact us.</p>
    <p>Yours sincerely,<br>GenSpark Team</p>
    """
    return send_email(to, subject, text, html)


def send_one_time_password_email(to_email, name, one_time_password, role_type='user'):
    """Email user/vendor their one-time password; ask them to login and change password.
    role_type: 'user' or 'vendor'
    """
    portal_url = current_app.config.get('FRONTEND_URL') or current_app.config.get('PREFERRED_URL', 'http://127.0.0.1:5000')
    role_label = 'Vendor' if role_type == 'vendor' else 'User'
    subject = f'GenSpark – Your {role_label} Account and One-Time Password'
    text = f"""Dear {name or 'User'},

Your GenSpark {role_label} account has been created. Please use the one-time password below to sign in for the first time.

One-time password: {one_time_password}

After logging in, you will be required to set a new password of your choice. This step is mandatory for security purposes.

Portal login: {portal_url}

Please do not share this password with anyone. If you did not request this account, please contact our support team.

Yours sincerely,
GenSpark Team
"""
    html = f"""
    <p>Dear <strong>{name or 'User'}</strong>,</p>
    <p>Your GenSpark <strong>{role_label}</strong> account has been created. Please use the one-time password below to sign in for the first time.</p>
    <p><strong>One-time password:</strong> <code style="background:#f0f0f0;padding:4px 8px;border-radius:4px;">{one_time_password}</code></p>
    <p>After logging in, you will be required to set a new password of your choice. This step is mandatory for security purposes.</p>
    <p><a href="{portal_url}">Log in to the portal</a></p>
    <p>Please do not share this password with anyone. If you did not request this account, please contact our support team.</p>
    <p>Yours sincerely,<br>GenSpark Team</p>
    """
    return send_email(to_email, subject, text, html)


def send_registration_verification_email(to_email, name, one_time_password, verify_url, role_type='user'):
    """Used for self-service registration from frontend.

    Sends one-time password + email verification link.
    """
    role_label = 'Vendor' if role_type == 'vendor' else 'User'
    subject = f'GenSpark – Verify Your {role_label} Account'
    text = f"""Dear {name or 'User'},

Thank you for registering for a GenSpark {role_label} account.

Before you can log in, please verify your email address by opening the link below:
{verify_url}

Your one-time password (for first login) is:
{one_time_password}

After your email is verified, you will be able to sign in using this one-time password and then set a new password of your choice.

If you did not request this account, you can safely ignore this email.

Yours sincerely,
GenSpark Team
"""
    html = f"""
    <p>Dear <strong>{name or 'User'}</strong>,</p>
    <p>Thank you for registering for a GenSpark <strong>{role_label}</strong> account.</p>
    <p>Before you can log in, please verify your email address by clicking the button below:</p>
    <p><a href="{verify_url}" style="display:inline-block;padding:8px 16px;background:#2563eb;color:#fff;text-decoration:none;border-radius:4px;">Verify Email</a></p>
    <p>If the button does not work, copy and paste this link into your browser:</p>
    <p><code style="background:#f0f0f0;padding:4px 8px;border-radius:4px;word-break:break-all;">{verify_url}</code></p>
    <p>Your one-time password for the first login is:</p>
    <p><strong>One-time password:</strong> <code style="background:#f0f0f0;padding:4px 8px;border-radius:4px;">{one_time_password}</code></p>
    <p>After your email is verified, you will be able to sign in using this one-time password and then set a new password of your choice.</p>
    <p>If you did not request this account, you can safely ignore this email.</p>
    <p>Yours sincerely,<br>GenSpark Team</p>
    """
    return send_email(to_email, subject, text, html)
