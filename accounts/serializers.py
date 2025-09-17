import re
from django.contrib.auth import get_user_model
from rest_framework import serializers
from accounts.models import User
from django.contrib.auth import get_user_model
from rest_framework import serializers
from exams.models import QuizAttempt, QuizStageAttempt, QuizStage
from .models import User
from rest_framework import serializers
from accounts.models import User
from rest_framework import serializers
from accounts.models import User
from common.enums import IndianState
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from common.enums import Zone
from rest_framework import serializers
from .models import User, PendingRegistration
from django.contrib.auth.password_validation import validate_password

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserSerializer(serializers.ModelSerializer):
    state = serializers.ChoiceField(choices=IndianState.choices, required=False)  # ← ADD

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "phone", "zone", "state",  # ← include state
            "role", "subspecialty", "is_verified", "first_name", "last_name", "avatar",
        ]


from rest_framework import serializers

class LoginEmailPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)



class UserListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    medical_id = serializers.CharField(read_only=True)
    medical_id_proof_url = serializers.SerializerMethodField()

    def get_status(self, obj):
        scope = (self.context.get("scope") or "any").lower()
        has_quiz  = bool(getattr(obj, "has_quiz_attempt", False))
        has_stage = bool(getattr(obj, "has_stage_attempt", False))
        if scope == "quiz":
            used = has_quiz
        elif scope == "stage":
            used = has_stage
        else:
            used = has_quiz or has_stage
        return "used" if used else "unused"

    def get_medical_id_proof_url(self, obj):
        f = getattr(obj, "medical_id_proof", None)
        if not f:
            return None
        url = getattr(f, "url", None)
        if not url:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "zone", "is_verified",
            "medical_id", "medical_id_proof_url",  # ← added
            "status",
        ]

class LoginStartSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # username OR email OR mobile

class LoginVerifySerializer(serializers.Serializer):
    identifier = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)
    device_fingerprint = serializers.CharField(required=False, allow_blank=True)

def resolve_user_by_identifier(identifier: str) -> User:
    identifier = (identifier or "").strip()
    # email?
    if EMAIL_RE.match(identifier):
        qs = User.objects.filter(email__iexact=identifier)
        if not qs.exists():
            raise serializers.ValidationError("No account found for this email.")
        if qs.count() > 1:
            raise serializers.ValidationError("Multiple accounts share this email. Contact support.")
        return qs.first()
    # mobile?
    user = User.objects.filter(phone=identifier).first()
    if user:
        return user
    # username?
    user = User.objects.filter(username__iexact=identifier).first()
    if user:
        return user
    raise serializers.ValidationError("No account found for this identifier.")


class LoginIdentifierPasswordSerializer(serializers.Serializer):
    identifier = serializers.CharField()            # username OR email OR phone
    password   = serializers.CharField(trim_whitespace=False)


class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = [
            "username", "password", "email", "phone", "medical_id",
            "zone", "state", "role", "subspecialty", "avatar"
        ]

    def validate(self, attrs):
        # Email is now compulsory
        if not attrs.get("email"):
            raise serializers.ValidationError("Email is required.")
        return attrs

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated):
        from accounts.utils import username_from_email  # local import avoids cycles
        password = validated.pop("password")
        email = validated.get("email", "").lower()
        # Generate username if not provided
        username = (validated.get("username") or "").strip() or username_from_email(email)
        validated["username"] = username
        validated["email"] = email

        user = User.objects.create_user(**validated)
        user.is_verified = False
        user.set_password(password)
        user.save(update_fields=["password", "is_verified"])
        return user



class RegisterStartSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    medical_id = serializers.CharField()
    zone = serializers.ChoiceField(choices=Zone.choices,required=False)
    state = serializers.ChoiceField(choices=IndianState.choices, required=False)  # ← ADD
    role = serializers.ChoiceField(choices=User.Roles.choices, required=False)
    subspecialty = serializers.CharField(required=False, allow_blank=True)
    medical_id_proof = serializers.FileField(required=False, allow_null=True)


    def validate(self, attrs):
        # Email is compulsory in the start step too
        email = attrs.get("email")
        if not email:
            raise serializers.ValidationError("Email is required.")

        # Uniqueness checks (only check username if provided)
        username = (attrs.get("username") or "").strip()
        if username and User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("Username already taken.")
        if User.objects.filter(medical_id=attrs["medical_id"]).exists():
            raise serializers.ValidationError("Medical ID already registered.")
        phone = attrs.get("phone")
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("Phone already registered.")
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Email already in use.")
        return attrs


class RegisterVerifySerializer(serializers.Serializer):
    reg_token = serializers.UUIDField()
    code = serializers.CharField(min_length=6, max_length=6)


class RegisterCompleteSerializer(serializers.Serializer):
    reg_token = serializers.UUIDField()
    password = serializers.CharField(trim_whitespace=False)
    zone = serializers.ChoiceField(choices=Zone.choices,required=False)

    def validate_password(self, value):
        validate_password(value)
        return value


from common.enums import IndianState

class AdminCreateUserSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    medical_id = serializers.CharField()
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    zone = serializers.ChoiceField(choices=Zone.choices)
    state = serializers.ChoiceField(choices=IndianState.choices, required=False)
    role = serializers.ChoiceField(choices=User.Roles.choices, required=False)
    subspecialty = serializers.CharField(required=False, allow_blank=True)
    is_verified = serializers.BooleanField(required=False)
    medical_id_proof = serializers.FileField(required=False, allow_null=True)


    def validate(self, data):
        # only check username uniqueness if provided
        username = (data.get("username") or "").strip()
        if username and User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Username already taken.")
        if User.objects.filter(medical_id=data["medical_id"]).exists():
            raise ValidationError("Medical ID already registered.")
        if data.get("phone") and User.objects.filter(phone=data["phone"]).exists():
            raise ValidationError("Phone already registered.")
        # email is compulsory for admin create now
        if not data.get("email"):
            raise ValidationError("Email is required.")
        if User.objects.filter(email__iexact=data["email"]).exists():
            raise ValidationError("Email already in use.")
        return data




# accounts/serializers.py (or wherever UserListSerializer lives)
from rest_framework import serializers
from accounts.models import User

class UserListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    # extra fields you asked for
    medical_id = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)
    subspecialty = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    medical_id_proof_url = serializers.SerializerMethodField()

    def get_status(self, obj):
        scope = (self.context.get("scope") or "any").lower()
        has_quiz  = bool(getattr(obj, "has_quiz_attempt", False))
        has_stage = bool(getattr(obj, "has_stage_attempt", False))
        if scope == "quiz":
            used = has_quiz
        elif scope == "stage":
            used = has_stage
        else:
            used = has_quiz or has_stage
        return "used" if used else "unused"

    def _abs_url(self, file_field):
        if not file_field:
            return None
        url = getattr(file_field, "url", None)
        if not url:
            return None
        req = self.context.get("request")
        return req.build_absolute_uri(url) if req else url

    def get_avatar_url(self, obj):
        return self._abs_url(getattr(obj, "avatar", None))

    def get_medical_id_proof_url(self, obj):
        return self._abs_url(getattr(obj, "medical_id_proof", None))

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "zone", "state", "is_verified",
            # newly included:
            "medical_id", "phone", "subspecialty",
            "avatar_url", "medical_id_proof_url",
            
            "status",
        ]





class QuizAttemptSummarySerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source="quiz.title", read_only=True)
    class Meta:
        model = QuizAttempt
        fields = ["id", "quiz_id", "quiz_title", "status", "started_at",
                  "submitted_at", "percent", "obtained_marks",
                  "total_marks", "time_taken_seconds"]

class StageAttemptSummarySerializer(serializers.ModelSerializer):
    stage_title = serializers.CharField(source="stage.title", read_only=True)
    stage_order = serializers.IntegerField(source="stage.order", read_only=True)
    class Meta:
        model = QuizStageAttempt
        fields = ["id", "stage_id", "stage_title", "stage_order",
                  "started_at", "submitted_at", "percent",
                  "obtained_marks", "total_marks", "time_taken_seconds"]
