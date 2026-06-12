# authentication/email_service.py

import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

FROM_EMAIL = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@hoppers.app")


def send_registration_pin(email: str, business_name: str, pin: str) -> None:
    subject = "Verify your email — Hoppers Business Platform"

    message = f"""Hello,

You requested to register "{business_name}" on the Hoppers Business Platform.

Your verification PIN is:

    {pin}

This PIN expires in 30 minutes.

If you did not request this, you can safely ignore this email.

— Hoppers Platform
"""

    html_message = f"""
<div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
  <h2 style="color: #0f172a; margin-bottom: 8px;">Verify your email</h2>
  <p style="color: #475569;">
    You requested to register <strong>{business_name}</strong>
    on the Hoppers Business Platform.
  </p>
  <div style="
    background: #f1f5f9;
    border-radius: 12px;
    padding: 32px;
    text-align: center;
    margin: 24px 0;
  ">
    <p style="color: #64748b; font-size: 13px; margin: 0 0 8px;">Your verification PIN</p>
    <p style="
      font-size: 40px;
      font-weight: 700;
      letter-spacing: 10px;
      color: #0f172a;
      margin: 0;
      font-family: monospace;
    ">{pin}</p>
    <p style="color: #94a3b8; font-size: 12px; margin: 12px 0 0;">Expires in 30 minutes</p>
  </div>
  <p style="color: #94a3b8; font-size: 12px;">
    If you did not request this, ignore this email.
  </p>
</div>
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Registration PIN sent to %s", email)
    except Exception as exc:
        logger.error("Failed to send registration PIN to %s: %s", email, exc)
        raise


def send_employee_verification_pin(
    email: str,
    employee_name: str,
    business_name: str,
    pin: str,
    temporary_password: str | None = None,
) -> None:
    subject = f"Welcome to {business_name} — verify your email"

    password_line = (
        f"Your temporary password is: {temporary_password}\n"
        if temporary_password else ""
    )

    message = f"""Hello {employee_name},

Your account has been created on {business_name}'s management system.

{password_line}
Your email verification PIN is:

    {pin}

Please enter this PIN when you first log in to verify your email address.
This PIN does not expire.

— {business_name} Management
"""

    password_html = (
        f"""
        <tr>
          <td style="padding: 8px 0; color: #64748b; font-size: 13px;">Temporary password</td>
          <td style="padding: 8px 0; font-weight: 600; font-family: monospace;">{temporary_password}</td>
        </tr>
        """
        if temporary_password else ""
    )

    html_message = f"""
<div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
  <h2 style="color: #0f172a; margin-bottom: 8px;">Welcome, {employee_name}</h2>
  <p style="color: #475569;">
    Your account has been created on
    <strong>{business_name}</strong>'s management system.
  </p>

  <table style="width:100%; margin: 16px 0; border-collapse: collapse;">
    {password_html}
  </table>

  <p style="color: #475569; margin-top: 16px;">
    Please verify your email address using this PIN when you first log in:
  </p>

  <div style="
    background: #f1f5f9;
    border-radius: 12px;
    padding: 32px;
    text-align: center;
    margin: 16px 0;
  ">
    <p style="color: #64748b; font-size: 13px; margin: 0 0 8px;">Email verification PIN</p>
    <p style="
      font-size: 40px;
      font-weight: 700;
      letter-spacing: 10px;
      color: #0f172a;
      margin: 0;
      font-family: monospace;
    ">{pin}</p>
    <p style="color: #94a3b8; font-size: 12px; margin: 12px 0 0;">This PIN does not expire</p>
  </div>

  <p style="color: #94a3b8; font-size: 12px;">
    If you were not expecting this email, contact your manager.
  </p>
</div>
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Employee verification PIN sent to %s", email)
    except Exception as exc:
        logger.error(
            "Failed to send employee verification PIN to %s: %s", email, exc
        )
        raise


def send_password_reset_pin(email: str, name: str, pin: str) -> None:
    subject = "Reset your Hoppers password"

    message = f"""Hello {name},

We received a request to reset the password for your Hoppers account.

Your password reset PIN is:

    {pin}

This PIN expires in 15 minutes.

If you did not request a password reset, you can safely ignore this email.
Your password will not be changed.

— Hoppers Platform
"""

    html_message = f"""
<div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
  <h2 style="color: #0f172a; margin-bottom: 8px;">Reset your password</h2>
  <p style="color: #475569;">
    We received a request to reset the password for your Hoppers account
    (<strong>{email}</strong>).
  </p>
  <div style="
    background: #f1f5f9;
    border-radius: 12px;
    padding: 32px;
    text-align: center;
    margin: 24px 0;
  ">
    <p style="color: #64748b; font-size: 13px; margin: 0 0 8px;">Your password reset PIN</p>
    <p style="
      font-size: 40px;
      font-weight: 700;
      letter-spacing: 10px;
      color: #0f172a;
      margin: 0;
      font-family: monospace;
    ">{pin}</p>
    <p style="color: #94a3b8; font-size: 12px; margin: 12px 0 0;">Expires in 15 minutes</p>
  </div>
  <p style="color: #475569; font-size: 14px;">
    If you did not request this, your password will not be changed.
    You can safely ignore this email.
  </p>
</div>
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Password reset PIN sent to %s", email)
    except Exception as exc:
        logger.error("Failed to send password reset PIN to %s: %s", email, exc)
        raise