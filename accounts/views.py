# accounts/views.py
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import authenticate
from accounts.utils import username_from_email

from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import AdminCreateUserSerializer
from accounts.models import User, LoginOTP
from accounts.models import PendingRegistration, RegistrationOTP  # ensure these models exist

from .serializers import (
    UserSerializer,
    LoginStartSerializer,
    LoginVerifySerializer,
    LoginIdentifierPasswordSerializer,
    RegisterSerializer,
    RegisterStartSerializer,
    RegisterVerifySerializer,
    RegisterCompleteSerializer,
)
from .serializers import resolve_user_by_identifier

# utils for login OTP delivery
from .utils import (
    send_login_otp,           # (user, purpose) -> (otp_obj, masked_dests)
    mask_email, mask_phone,
    # registration helpers
    generate_otp_code,
    deliver_email_raw,
    deliver_sms_raw,
    OTP_TTL_SECONDS,
    OTP_RESEND_COOLDOWN_SECONDS,
)


import os
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PendingRegistration, RegistrationOTP, User
from .serializers import (
    RegisterStartSerializer, RegisterVerifySerializer, RegisterCompleteSerializer, UserSerializer
)
from .utils import (
    generate_otp_code, OTP_TTL_SECONDS, deliver_email_raw, deliver_sms_raw,
    mask_email, mask_phone
)
from django.conf import settings


from django.db.models import Exists, OuterRef
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from exams.models import Quiz, QuizStage, QuizAttempt, QuizStageAttempt, AttemptAnswer, StageAttemptItem
from .serializers import (
    UserListSerializer,
    QuizAttemptSummarySerializer,
    StageAttemptSummarySerializer,
)
from .serializers import LoginEmailPasswordSerializer
from .models import User
from .permissions import IsAdminOrTeacher, IsStudent
from django.db import models
from django.db.models import Exists, OuterRef, Value, BooleanField
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models
from django.db.models import Exists, OuterRef, Value, BooleanField
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import User
from exams.models import Quiz, QuizStage, QuizAttempt, QuizStageAttempt
from .serializers import (
    UserListSerializer,
    QuizAttemptSummarySerializer,
    StageAttemptSummarySerializer,
)
from .permissions import IsAdminOrTeacher
from django.db.models import Count, Avg, Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from accounts.models import User
from exams.models import Quiz, QuizStage, QuizAttempt, QuizStageAttempt


class LoginStartView(APIView):
    """
    POST /api/auth/otp/start
    Body: { "identifier": "<username|email|phone>" }
    Sends OTP to the user's email and/or phone.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = LoginStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = resolve_user_by_identifier(ser.validated_data["identifier"])

        # Throttled send via utility; creates LoginOTP row
        try:
            otp, destinations = send_login_otp(user, purpose="Login")
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        resp = {
            "detail": f"OTP sent to {destinations}.",
            "expires_in": (otp.expires_at - timezone.now()).seconds,
        }
        if getattr(settings, "DEBUG", False):
            resp["debug_otp"] = otp.code  # convenient for local testing
        return Response(resp, status=status.HTTP_200_OK)




class LoginEmailPasswordView(APIView):
    """
    POST /api/auth/login/email
    Body: { "email": "user@example.com", "password": "secret" }

    Returns JWT access/refresh on success.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = LoginEmailPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        email = ser.validated_data["email"].strip().lower()
        password = ser.validated_data["password"]

        # resolve user by email (case-insensitive)
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise ValidationError("Invalid email or password.")

        if not user.is_active:
            raise ValidationError("This account is inactive.")

        # authenticate using the user's username + provided password
        auth_user = authenticate(request, username=user.username, password=password)
        if not auth_user:
            raise ValidationError("Invalid email or password.")

        refresh = RefreshToken.for_user(auth_user)
        return Response(
            {
                "user": UserSerializer(auth_user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class LoginVerifyView(APIView):
    """
    POST /api/auth/otp/verify
    Body: { "identifier": "<username|email|phone>", "code": "123456" }
    Verifies OTP and returns JWTs.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = LoginVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = resolve_user_by_identifier(ser.validated_data["identifier"])
        code = ser.validated_data["code"].strip()

        now = timezone.now()
        otp = (
            LoginOTP.objects
            .filter(user=user, code=code, is_used=False, expires_at__gte=now)
            .order_by("-created_at").first()
        )
        if not otp:
            last = LoginOTP.objects.filter(user=user).order_by("-created_at").first()
            if last:
                last.attempt_count = (last.attempt_count or 0) + 1
                last.save(update_fields=["attempt_count"])
            raise ValidationError("Invalid or expired code.")

        # mark used, optionally set user.verified
        otp.is_used = True
        otp.save(update_fields=["is_used"])

        # Issue JWTs
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class LoginAnyIdentifierView(APIView):
    """
    POST /api/auth/login
    Body: { "identifier": "<username|email|phone>", "password": "<password>" }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = LoginIdentifierPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        identifier = ser.validated_data["identifier"].strip()
        password = ser.validated_data["password"]

        user = resolve_user_by_identifier(identifier)
        if not user:
            raise ValidationError("Invalid credentials.")

        auth_user = authenticate(request, username=user.username, password=password)
        if not auth_user:
            raise ValidationError("Invalid credentials.")
        if not auth_user.is_active:
            raise ValidationError("This account is inactive.")

        refresh = RefreshToken.for_user(auth_user)
        return Response(
            {
                "user": UserSerializer(auth_user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )



class DirectRegisterView(APIView):
    """
    POST /api/auth/register
    Body: RegisterSerializer fields
    Creates user right away, sends OTP for confirmation, returns user info.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()

        try:
            _, destinations = send_login_otp(user, purpose="Registration")
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        payload = UserSerializer(user).data
        msg = f"User registered. OTP sent to {destinations}."
        if getattr(settings, "DEBUG", False):
            last_code = LoginOTP.objects.filter(user=user).order_by("-created_at").first().code
            payload["debug_otp"] = last_code

        return Response({"detail": msg, "user": payload}, status=status.HTTP_201_CREATED)


def _registration_can_resend(last_otp):
    if not last_otp:
        return True
    last = last_otp.last_sent_at or last_otp.created_at
    return (timezone.now() - last).total_seconds() >= 60


class RegisterStartView(APIView):
    """
    POST /api/auth/register/start
    multipart/form-data supported (for medical_id_proof)
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # ⬅️ important

    def post(self, request):
        ser = RegisterStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        # separate the file from JSON payload (can't store file in JSONField)
        data = ser.validated_data.copy()
        proof_file = data.pop("medical_id_proof", None)

        pending = PendingRegistration.objects.create(
            payload=data,
            email=data.get("email"),
            phone=data.get("phone"),
        )
        if proof_file:
            pending.medical_id_proof = proof_file
            pending.save(update_fields=["medical_id_proof"])

        code = generate_otp_code()
        RegistrationOTP.objects.create(
            pending=pending,
            code=code,
            expires_at=timezone.now() + timedelta(seconds=OTP_TTL_SECONDS),
            sent_count=1,
            last_sent_at=timezone.now(),
        )

        deliver_email_raw(pending.email, code, "Registration")
        deliver_sms_raw(pending.phone, code, "Registration")

        destinations = " and ".join([x for x in [mask_email(pending.email), mask_phone(pending.phone)] if x])
        resp = {
            "detail": f"OTP sent to {destinations or 'your contacts'}.",
            "reg_token": str(pending.id),
            "expires_in": OTP_TTL_SECONDS,
        }
        if getattr(settings, "DEBUG", False):
            resp["debug_otp"] = code
        return Response(resp, status=status.HTTP_200_OK)


class RegisterResendView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        reg_token = request.data.get("reg_token")
        try:
            pending = PendingRegistration.objects.get(id=reg_token)
        except PendingRegistration.DoesNotExist:
            return Response({"detail": "Invalid registration token."}, status=400)

        last = pending.otps.order_by("-created_at").first()
        if not _registration_can_resend(last):
            return Response({"detail": "Please wait a minute before requesting another OTP."}, status=429)

        code = generate_otp_code()
        RegistrationOTP.objects.create(
            pending=pending,
            code=code,
            expires_at=timezone.now() + timedelta(seconds=OTP_TTL_SECONDS),
            sent_count=(1 if not last else last.sent_count + 1),
            last_sent_at=timezone.now(),
        )
        deliver_email_raw(pending.email, code, "Registration")
        deliver_sms_raw(pending.phone, code, "Registration")

        resp = {"detail": "OTP resent."}
        if getattr(settings, "DEBUG", False):
            resp["debug_otp"] = code
        return Response(resp, status=200)


class RegisterVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        ser = RegisterVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reg_token = ser.validated_data["reg_token"]
        code = ser.validated_data["code"]

        try:
            pending = PendingRegistration.objects.get(id=reg_token)
        except PendingRegistration.DoesNotExist:
            return Response({"detail": "Invalid registration token."}, status=400)

        otp = (RegistrationOTP.objects
               .filter(pending=pending, code=code, is_used=False, expires_at__gte=timezone.now())
               .order_by("-created_at").first())
        if not otp:
            latest = pending.otps.order_by("-created_at").first()
            if latest:
                latest.attempt_count = (latest.attempt_count or 0) + 1
                latest.save(update_fields=["attempt_count"])
            return Response({"detail": "Invalid or expired OTP."}, status=400)

        otp.is_used = True
        otp.save(update_fields=["is_used"])
        pending.verified_at = timezone.now()
        pending.save(update_fields=["verified_at"])

        return Response({"detail": "OTP verified. You may complete registration now."}, status=200)


class RegisterCompleteView(APIView):
    """
    Moves PendingRegistration.medical_id_proof -> User.medical_id_proof
    """
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        ser = RegisterCompleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        reg_token = ser.validated_data["reg_token"]
        password = ser.validated_data["password"]

        try:
            pending = PendingRegistration.objects.select_for_update().get(id=reg_token)
        except PendingRegistration.DoesNotExist:
            return Response({"detail": "Invalid registration token."}, status=400)

        if not pending.verified_at:
            return Response({"detail": "OTP not verified."}, status=400)

        data = pending.payload

        if not data.get("email"):
            return Response({"detail": "Email is required."}, status=400)

        # uniqueness checks
        username_in = (data.get("username") or "").strip()
        if username_in and User.objects.filter(username__iexact=username_in).exists():
            return Response({"detail": "Username already taken."}, status=400)
        if User.objects.filter(medical_id=data["medical_id"]).exists():
            return Response({"detail": "Medical ID already registered."}, status=400)
        if data.get("phone") and User.objects.filter(phone=data["phone"]).exists():
            return Response({"detail": "Phone already registered."}, status=400)
        if data.get("email") and User.objects.filter(email__iexact=data["email"]).exists():
            return Response({"detail": "Email already in use."}, status=400)

        # auto-generate username if missing
        email = data["email"].lower()
        username_final = username_in or username_from_email(email)

        user = User.objects.create_user(
            username=username_final,
            email=email,
            phone=data.get("phone") or "",
            medical_id=data["medical_id"],
            # zone=data["zone"] or None,
            state=data.get("state") or None,
            role=data.get("role") or User.Roles.STUDENT,
            subspecialty=data.get("subspecialty") or "",
            is_verified=bool(data.get("is_verified", True)),
        )

        user.set_password(password)

        # ⬇️ move file from pending → user field (new path: id_proofs/)
        if pending.medical_id_proof:
            base = os.path.basename(pending.medical_id_proof.name)  # keep original filename
            user.medical_id_proof.save(base, pending.medical_id_proof.file, save=False)

        user.save(update_fields=["password", "is_verified", "medical_id_proof"])

        # delete the temp file linked to pending (storage cleanup of the old path)
        if pending.medical_id_proof:
            try:
                pending.medical_id_proof.delete(save=False)
            except Exception:
                pass

        pending.delete()

        refresh = RefreshToken.for_user(user)
        tokens = {"access": str(refresh.access_token), "refresh": str(refresh)}
        return Response(
            {"detail": "Account created.", "user": UserSerializer(user).data, "tokens": tokens},
            status=201,
        )


class AdminDirectRegisterView(APIView):
    """
    POST /api/auth/register/admin
    Content-Type: multipart/form-data or JSON
    Body:
      username, password, medical_id, zone, [role], [email], [phone],
      [subspecialty], [is_verified], [medical_id_proof]
    Behavior:
      - Requires request.user.is_staff OR role=ADMIN.
      - Creates the user immediately; no OTP steps.
      - Optional ?issue_tokens=true to also return JWTs for the created user.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        # gate
        role = getattr(request.user, "role", "").upper()
        if not (request.user.is_staff or role == "ADMIN"):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        ser = AdminCreateUserSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        email = data["email"].lower()
        username_final = (data.get("username") or "").strip() or username_from_email(email)

        user = User.objects.create_user(
            username=username_final,
            email=email,
            phone=data.get("phone") or "",
            medical_id=data["medical_id"],
            zone=data["zone"],
            role=data.get("role") or User.Roles.STUDENT,
            subspecialty=data.get("subspecialty") or "",
            is_verified=bool(data.get("is_verified", True)),
        )

        user.set_password(data["password"])

        proof = data.get("medical_id_proof")
        if proof:
            # saved to upload_to="id_proofs/"
            user.medical_id_proof.save(proof.name, proof, save=False)

        user.save(update_fields=["password", "is_verified", "medical_id_proof"])

        payload = {"detail": "User created.", "user": UserSerializer(user).data}

        # optionally issue tokens (useful if you’re creating + signing them in)
        issue_tokens = str(request.query_params.get("issue_tokens", "false")).lower() in ("1", "true", "yes")
        if issue_tokens:
            refresh = RefreshToken.for_user(user)
            payload["tokens"] = {"access": str(refresh.access_token), "refresh": str(refresh)}

        return Response(payload, status=status.HTTP_201_CREATED)




def _get_active_quiz_and_stage():
    """Return (quiz, stage) where quiz.is_active=True and stage is current/in-window/first."""
    quiz = Quiz.objects.filter(is_active=True).first()
    if not quiz:
        return None, None
    now = timezone.now()
    stage = (
        quiz.stages.filter(is_current=True).order_by("order").first()
        or quiz.stages.filter(start_at__lte=now, end_at__gte=now).order_by("order").first()
        or quiz.stages.order_by("order").first()
    )
    return quiz, stage


class UsersViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/users/?role=STUDENT|TEACHER|ADMIN|ALL
                  &participated=none|quiz|stage|any
                  &quiz_id=<uuid>&stage_id=<uuid>&q=<text>
                  &zone=<ZONE>
                  &status=used|unused
                  &scope=quiz|stage|any

    Notes:
      - If 'scope' is missing, it is derived:
          scope = participated if it's 'quiz' or 'stage', else 'any'.
      - 'status' applies inside the chosen scope:
          * scope=quiz  -> used = has_quiz_attempt
          * scope=stage -> used = has_stage_attempt
          * scope=any   -> used = has_quiz_attempt or has_stage_attempt
    """
    queryset = User.objects.all().order_by("username")
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        role = (request.query_params.get("role") or "STUDENT").upper()
        participated = (request.query_params.get("participated") or "").lower()
        zone = (request.query_params.get("zone") or "").upper()
        status_filter = (request.query_params.get("status") or "").lower()
        scope_qp = (request.query_params.get("scope") or "").lower()
        state = (request.query_params.get("state") or "").upper()

        # ---- scope decision (do NOT touch qs here) ----
        if scope_qp in ("quiz", "stage", "any"):
            scope = scope_qp
        elif participated in ("quiz", "stage"):
            scope = participated
        else:
            scope = "any"

        # ---- resolve quiz & stage (unchanged) ----
        quiz_id = request.query_params.get("quiz_id")
        stage_id = request.query_params.get("stage_id")
        if quiz_id:
            quiz = get_object_or_404(Quiz, pk=quiz_id)
        else:
            quiz, _ = _get_active_quiz_and_stage()
        if stage_id:
            stage = get_object_or_404(QuizStage, pk=stage_id)
        else:
            _, stage = _get_active_quiz_and_stage()

        # ---- build queryset THEN apply filters ----
        qs = self.get_queryset()

        if role != "ALL":
            qs = qs.filter(role=role)

        if zone:
            qs = qs.filter(zone=zone)

        # ✅ state filter belongs here (after qs exists)
        if state:
            qs = qs.filter(state=state)

        # quick search
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(
                models.Q(username__icontains=q) |
                models.Q(first_name__icontains=q) |
                models.Q(last_name__icontains=q) |
                models.Q(email__icontains=q) |
                models.Q(phone__icontains=q) |
                models.Q(medical_id__icontains=q)
            )


        # annotate participation flags
        if quiz:
            qs = qs.annotate(
                has_quiz_attempt=Exists(
                    QuizAttempt.objects.filter(quiz=quiz, user=OuterRef("pk"))
                )
            )
        else:
            qs = qs.annotate(has_quiz_attempt=Value(False, output_field=BooleanField()))

        if stage:
            qs = qs.annotate(
                has_stage_attempt=Exists(
                    QuizStageAttempt.objects.filter(stage=stage, attempt__user=OuterRef("pk"))
                )
            )
        else:
            qs = qs.annotate(has_stage_attempt=Value(False, output_field=BooleanField()))

        # base "participated" filter
        if participated == "quiz":
            qs = qs.filter(has_quiz_attempt=True)
        elif participated == "stage":
            qs = qs.filter(has_stage_attempt=True)
        elif participated == "any":
            qs = qs.filter(
                models.Q(has_quiz_attempt=True) | models.Q(has_stage_attempt=True)
            )
        elif participated == "none":
            qs = qs.filter(has_quiz_attempt=False, has_stage_attempt=False)

        # status filter inside chosen scope
        if status_filter in ("used", "unused"):
            if scope == "quiz":
                flag_field = "has_quiz_attempt"
            elif scope == "stage":
                flag_field = "has_stage_attempt"
            else:
                # scope = any → expand explicitly
                if status_filter == "used":
                    qs = qs.filter(
                        models.Q(has_quiz_attempt=True) | models.Q(has_stage_attempt=True)
                    )
                else:
                    qs = qs.filter(
                        models.Q(has_quiz_attempt=False) & models.Q(has_stage_attempt=False)
                    )
                flag_field = None

            if flag_field:
                qs = qs.filter(**{flag_field: (status_filter == "used")})

        # paginate & serialize — keep DRF context so serializer sees `request`
        ctx = self.get_serializer_context()
        ctx["scope"] = scope
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True, context=ctx)
            return self.get_paginated_response(ser.data)

        ser = self.get_serializer(qs, many=True, context=ctx)
        return Response(ser.data)

    @action(detail=False, methods=["get"], url_path="active-counts")
    def active_counts(self, request):
        """
        GET /api/users/active-counts/?role=STUDENT|TEACHER|ADMIN|ALL
        Returns totals for the active quiz/current stage.
        """
        role = (request.query_params.get("role") or "STUDENT").upper()
        quiz, stage = _get_active_quiz_and_stage()

        base = self.get_queryset()
        if role != "ALL":
            base = base.filter(role=role)

        totals = base.count()

        if quiz:
            participated_quiz = base.filter(quiz_attempts__quiz=quiz).distinct().count()
        else:
            participated_quiz = 0

        if stage:
            participated_stage = base.filter(
                quiz_attempts__stage_attempts__stage=stage
            ).distinct().count()
        else:
            participated_stage = 0

        payload = {
            "active_quiz_id": str(quiz.id) if quiz else None,
            "active_stage_id": str(stage.id) if stage else None,
            "total_users": totals,
            "participated_quiz": participated_quiz,
            "participated_stage": participated_stage,
        }
        return Response(payload, status=200)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """
        GET /api/users/{user_id}/history/?quiz_id=<optional>
        Admin/Teacher can view anyone; students only themselves.
        """
        if not (IsAdminOrTeacher().has_permission(request, self) or str(request.user.id) == str(pk)):
            return Response({"detail": "Forbidden"}, status=403)

        user = get_object_or_404(User, pk=pk)
        quiz_id = request.query_params.get("quiz_id")

        qa_qs = (
            QuizAttempt.objects
            .filter(user=user)
            .select_related("quiz")
            .order_by("-created_at")
        )
        if quiz_id:
            qa_qs = qa_qs.filter(quiz_id=quiz_id)

        out = []
        for qa in qa_qs:
            sa_qs = (
                QuizStageAttempt.objects
                .filter(attempt=qa)
                .select_related("stage")
                .order_by("stage__order")
            )
            out.append({
                "quiz_attempt": QuizAttemptSummarySerializer(qa).data,
                "stage_attempts": StageAttemptSummarySerializer(sa_qs, many=True).data,
            })

        return Response({"user_id": str(user.id), "items": out}, status=200)



class StageUserAnswersView(viewsets.ViewSet):
    """
    Admin/Teacher: fetch a user's answers for a given stage.
    GET /api/stages/{stage_id}/users/{user_id}/answers/
    """
    permission_classes = [IsAdminOrTeacher]

    def list(self, request, stage_id=None, user_id=None):
        stage = get_object_or_404(QuizStage, pk=stage_id)
        attempt = QuizAttempt.objects.filter(quiz=stage.quiz, user_id=user_id).first()
        if not attempt:
            return Response({
                "attempt_given": False,
                "stage_attempt_given": False,
                "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order},
                "items": [],
                "detail": "No quiz attempt for this user."
            }, status=200)

        sa = QuizStageAttempt.objects.filter(attempt=attempt, stage=stage).first()
        if not sa:
            return Response({
                "attempt_given": True,
                "stage_attempt_given": False,
                "attempt_id": str(attempt.id),
                "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order},
                "items": [],
                "detail": "User did not start this stage."
            }, status=200)

        # build items (similar to your MyStageAnswersView, but for admin)
        items = (
            StageAttemptItem.objects
            .filter(stage_attempt=sa)
            .select_related("question")
            .order_by("order", "id")
        )
        answers = (
            AttemptAnswer.objects
            .filter(stage_attempt=sa)
            .select_related("selected_option", "question")
            .order_by("id")
        )
        by_qid = {}
        for a in answers:
            by_qid.setdefault(str(a.question_id), []).append(a)

        payload_items, total_awarded, total_time = [], 0.0, 0
        for it in items:
            q = it.question
            qid = str(q.id)
            rows = by_qid.get(qid, [])
            given_option_ids = [str(r.selected_option_id) for r in rows if r.selected_option_id]
            given_text   = (rows[0].answer_text   if rows and rows[0].answer_text   else "")
            given_number = (rows[0].answer_number if rows and rows[0].answer_number is not None else None)
            given_bool   = (rows[0].answer_bool   if rows and rows[0].answer_bool   is not None else None)
            q_awarded    = float(sum([r.awarded_marks for r in rows]) or 0.0)
            q_is_correct = bool(rows[0].is_correct) if rows else False
            q_time_spent = int(sum([int(r.time_spent_seconds or 0) for r in rows]) or 0)

            total_awarded += q_awarded
            total_time += q_time_spent

            # options with correctness
            opts = list(q.options.all().order_by("order", "id").values("id", "text", "is_correct"))
            options = [{"id": str(o["id"]), "text": o["text"], "is_correct": bool(o["is_correct"])} for o in opts]
            correct_ids = [str(o["id"]) for o in opts if o["is_correct"]]

            payload_items.append({
                "order": it.order,
                "marks": float(it.marks),
                "negative_marks": float(it.negative_marks),
                "time_limit_seconds": int(it.time_limit_seconds),
                "question": {"id": qid, "text": q.text, "question_type": q.question_type},
                "options": options,
                "correct_option_ids": correct_ids,
                "given_option_ids": given_option_ids,
                "given_text": given_text,
                "given_number": given_number,
                "given_bool": given_bool,
                "is_correct": q_is_correct,
                "awarded_marks": q_awarded,
                "time_spent_seconds": q_time_spent,
            })

        return Response({
            "user_id": str(user_id),
            "attempt_id": str(attempt.id),
            "stage_attempt_id": str(sa.id),
            "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order},
            "totals": {
                "questions": len(payload_items),
                "awarded_marks": float(total_awarded),
                "stage_obtained_marks": float(sa.obtained_marks),
                "stage_total_marks": float(sa.total_marks),
                "stage_percent": float(sa.percent),
                "time_spent_seconds_sum": int(total_time),
                "time_taken_seconds_stage": int(sa.time_taken_seconds or 0),
                "submitted_at": sa.submitted_at,
            },
            "items": payload_items,
        }, status=200)



class AdminDashboardSummaryView(APIView):
    """
    GET /api/admin/dashboard/summary/
      ?quiz_id=<uuid>        # optional
      &stage_id=<uuid>       # optional

    Defaults:
      - If neither is provided → uses the single active quiz (is_active=True)
        and its current stage (is_current) or first stage in order.
      - If multiple active quizzes exist, returns 400 to avoid ambiguity.

    Tiles:
      - total_participants: # of STUDENT users (excludes is_staff/admin/teacher)
      - attempts_used:
          * quiz:  QuizAttempt rows for the chosen quiz (students only)
          * stage: QuizStageAttempt rows for the chosen stage (students only)
      - overall_pass_rate (for the chosen quiz, submitted attempts only):
          * pass_rate_percent = passed/submitted * 100
          * avg_percent = average of attempt.percent
    """
    permission_classes = [permissions.IsAuthenticated]

    # Only Admin/Teacher/Staff may see the dashboard
    def _ensure_admin(self, request):
        role = getattr(request.user, "role", "").upper()
        if not (request.user.is_staff or role in ("ADMIN", "TEACHER")):
            raise ValidationError("Forbidden: admin/teacher access only.")

    def _resolve_quiz_stage(self, request):
        quiz_id = request.query_params.get("quiz_id")
        stage_id = request.query_params.get("stage_id")

        if stage_id:
            stage = QuizStage.objects.select_related("quiz").filter(pk=stage_id).first()
            if not stage:
                raise ValidationError("Invalid stage_id.")
            return stage.quiz, stage

        if quiz_id:
            quiz = Quiz.objects.filter(pk=quiz_id).first()
            if not quiz:
                raise ValidationError("Invalid quiz_id.")
            stage = (
                quiz.stages.filter(is_current=True).order_by("order").first()
                or quiz.stages.order_by("order").first()
            )
            if not stage:
                raise ValidationError("No stages configured for that quiz.")
            return quiz, stage

        # Fall back to the *single* active quiz
        active = list(Quiz.objects.filter(is_active=True))
        if not active:
            return None, None
        if len(active) > 1:
            raise ValidationError("Multiple active quizzes found. Pass quiz_id explicitly.")
        quiz = active[0]
        stage = (
            quiz.stages.filter(is_current=True).order_by("order").first()
            or quiz.stages.order_by("order").first()
        )
        return quiz, stage

    def get(self, request):
        self._ensure_admin(request)

        # ---------------------------
        # Resolve quiz + stage
        # ---------------------------
        quiz, stage = self._resolve_quiz_stage(request)

        # ---------------------------
        # Participants (students only)
        # ---------------------------
        students = User.objects.filter(
            role=User.Roles.STUDENT,
            is_staff=False,
            is_active=True,
        )
        total_participants = students.count()

        # ---------------------------
        # Attempts used (students only)
        # ---------------------------
        attempts_used_quiz = 0
        attempts_used_stage = 0
        participants_quiz = 0
        participants_stage = 0

        if quiz:
            qa_qs = QuizAttempt.objects.filter(quiz=quiz, user__role=User.Roles.STUDENT)
            attempts_used_quiz = qa_qs.count()
            participants_quiz = qa_qs.values("user_id").distinct().count()

        if stage:
            sa_qs = QuizStageAttempt.objects.filter(
                stage=stage,
                attempt__user__role=User.Roles.STUDENT,
            )
            attempts_used_stage = sa_qs.count()
            participants_stage = sa_qs.values("attempt__user_id").distinct().count()

        # ---------------------------
        # Overall pass rate (quiz, submitted only)
        # ---------------------------
        pass_rate_percent = 0.0
        avg_percent = 0.0
        submitted_count = 0
        passed_count = 0

        if quiz:
            submitted = QuizAttempt.objects.filter(
                quiz=quiz,
                submitted_at__isnull=False,
                user__role=User.Roles.STUDENT,
            )
            submitted_count = submitted.count()
            if submitted_count:
                passed_count = submitted.filter(is_passed=True).count()
                pass_rate_percent = round((passed_count / submitted_count) * 100.0, 2)
                avg_val = submitted.aggregate(a=Avg("percent"))["a"] or 0
                # percent is Decimal → to float
                avg_percent = round(float(avg_val), 2)

        payload = {
            "quiz": (
                {"id": str(quiz.id), "title": quiz.title, "is_active": quiz.is_active}
                if quiz else None
            ),
            "stage": (
                {
                    "id": str(stage.id),
                    "title": stage.title,
                    "order": stage.order,
                    "is_current": bool(getattr(stage, "is_current", False)),
                    "start_at": stage.start_at,
                    "end_at": stage.end_at,
                }
                if stage else None
            ),
            "totals": {
                "total_participants": total_participants,        # students only
                "participants_quiz": participants_quiz,          # distinct students with a QuizAttempt (chosen quiz)
                "participants_stage": participants_stage,        # distinct students with a StageAttempt (chosen stage)
            },
            "attempts_used": {
                "quiz": attempts_used_quiz,                      # student attempts on chosen quiz
                "stage": attempts_used_stage,                    # student stage attempts on chosen stage
            },
            "performance": {
                "submitted_attempts": submitted_count,           # chosen quiz only
                "passed_attempts": passed_count,
                "pass_rate_percent": pass_rate_percent,          # passed/submitted * 100
                "avg_percent": avg_percent,                      # mean of 'percent' across submitted attempts
            },
        }
        return Response(payload, status=status.HTTP_200_OK)

