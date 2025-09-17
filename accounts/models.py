from django.contrib.auth.models import AbstractUser
from django.db import models
from common.enums import Zone
from django.utils import timezone
import uuid
from django.db import models
from django.utils import timezone
from common.enums import Zone, IndianState  

class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN   = "ADMIN",   "Admin"
        TEACHER = "TEACHER", "Teacher"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.STUDENT)

    medical_id = models.CharField(max_length=64, unique=True)
    phone      = models.CharField(max_length=20, unique=True)
    zone       = models.CharField(max_length=16, choices=Zone.choices)

    state = models.CharField(
        max_length=40,
        choices=IndianState.choices,
        default=IndianState.MAHARASHTRA,
        help_text="Indian state or union territory"
    )
    email = models.EmailField(unique=True, null=True, blank=True)


    medical_id_proof = models.FileField(upload_to="id_proofs/", blank=True, null=True)
    subspecialty = models.CharField(max_length=128, blank=True)
    is_verified = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    def __str__(self):
        return f"{self.username} • {self.zone} • {self.state} • {self.role}"


class PendingRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payload = models.JSONField()  # holds username/email/phone/medical_id/zone/role/subspecialty
    email = models.EmailField(blank=True, null=True)
    medical_id_proof = models.FileField(upload_to="id_proofs/pending/", null=True, blank=True)

    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None


class RegistrationOTP(models.Model):
    pending = models.ForeignKey(PendingRegistration, on_delete=models.CASCADE, related_name="otps")
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveIntegerField(default=0)
    attempt_count = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["pending", "code", "expires_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at


class LoginOTP(models.Model):
    """
    One-time passcode for passwordless or step-up email verification.
    We always send the OTP to the user's email, regardless of how they identified (username/mobile/email).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_otps")
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_count = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["user", "code", "expires_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])
