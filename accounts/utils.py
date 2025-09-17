# accounts/utils.py
import random
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import LoginOTP, User

OTP_TTL_SECONDS = 10 * 60           # 10 minutes
OTP_RESEND_COOLDOWN_SECONDS = 60     # 1 minute between sends to the same user

def generate_otp_code(length: int = 6) -> str:
    return "".join(random.choices("0123456789", k=length))

def mask_email(email: str | None) -> str:
    if not email:
        return ""
    name, _, domain = email.partition("@")
    if not domain:
        return email
    masked = (name[0] + "*" * max(1, len(name) - 2) + name[-1]) if len(name) > 2 else name[0] + "*"
    return f"{masked}@{domain}"

def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    if len(phone) <= 4:
        return "*" * len(phone)
    return "*" * (len(phone) - 4) + phone[-4:]

def deliver_email_otp(user: User, code: str, purpose: str = "Verification") -> None:
    if not user.email:
        return
    subject = f"{purpose} OTP"
    message = f"Your {purpose.lower()} one-time passcode is: {code}. It expires in {OTP_TTL_SECONDS // 60} minutes."
    send_mail(subject, message, getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"), [user.email], fail_silently=True)

def deliver_sms_otp(user: User, code: str, purpose: str = "Verification") -> None:
    """
    Stub for SMS provider integration (e.g., Twilio).
    Replace this with an actual SMS client call. For now we just "simulate".
    """
    if not user.phone:
        return
    # Example: twilio_client.messages.create(to=user.phone, body=..., from_=TWILIO_NUMBER)
    print(f"[SMS → {user.phone}] {purpose} OTP is {code} (simulated)")

def can_send_new_otp(user: User) -> bool:
    last = LoginOTP.objects.filter(user=user).order_by("-created_at").first()
    if not last:
        return True
    return (timezone.now() - (last.last_sent_at or last.created_at)) >= timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)

def send_login_otp(user: User, purpose: str = "Verification") -> tuple[LoginOTP, str]:
    """
    Creates a fresh OTP, stores it, and tries to deliver via Email and SMS.
    Returns (otp_obj, destinations_string)
    """
    if not can_send_new_otp(user):
        raise ValueError("Please wait a minute before requesting another OTP.")

    code = generate_otp_code()
    expires_at = timezone.now() + timedelta(seconds=OTP_TTL_SECONDS)

    otp = LoginOTP.objects.create(
        user=user,
        code=code,
        expires_at=expires_at,
        sent_count=1,
        last_sent_at=timezone.now(),
    )

    # Deliver through both channels if present
    deliver_email_otp(user, code, purpose=purpose)
    deliver_sms_otp(user, code, purpose=purpose)

    dest_parts = []
    if user.email:
        dest_parts.append(mask_email(user.email))
    if user.phone:
        dest_parts.append(mask_phone(user.phone))
    return otp, " and ".join(dest_parts) if dest_parts else "your registered contacts"


# accounts/utils.py (add these or reuse your previous helpers)
import random
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

OTP_TTL_SECONDS = 10 * 60
OTP_RESEND_COOLDOWN_SECONDS = 60

def generate_otp_code(length: int = 6) -> str:
    return "".join(random.choices("0123456789", k=length))

def mask_email(email: str | None) -> str:
    if not email:
        return ""
    name, _, domain = email.partition("@")
    if not domain: return email
    masked = (name[0] + "*" * max(1, len(name)-2) + name[-1]) if len(name) > 2 else name[0] + "*"
    return f"{masked}@{domain}"

def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    if len(phone) <= 4:
        return "*" * len(phone)
    return "*" * (len(phone)-4) + phone[-4:]

def deliver_email_raw(email: str | None, code: str, purpose: str = "Registration") -> None:
    if not email:
        return
    subject = f"{purpose} OTP"
    message = f"Your {purpose.lower()} one-time passcode is: {code}. It expires in {OTP_TTL_SECONDS // 60} minutes."
    send_mail(subject, message, getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"), [email], fail_silently=True)

def deliver_sms_raw(phone: str | None, code: str, purpose: str = "Registration") -> None:
    if not phone:
        return
    # Plug your SMS provider here (Twilio, etc.)
    print(f"[SMS → {phone}] {purpose} OTP is {code} (simulated)")


# add these imports
import re
from django.utils.text import slugify
from accounts.models import User

def username_from_email(email: str, max_len: int = 30) -> str:
    """
    Build a unique, URL-safe username from the email's local-part.
    """
    local = (email or "").split("@")[0]
    base = slugify(local).lower()
    base = re.sub(r"[^a-z0-9._-]", "", base) or "user"
    # leave room for numeric suffixes
    base = base[: max_len - 4]

    candidate = base
    i = 0
    while User.objects.filter(username__iexact=candidate).exists():
        i += 1
        candidate = f"{base}{i}"
    return candidate

