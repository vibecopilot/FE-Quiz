import io, json, hashlib, re, random
from django.db.models import Q, Sum, F, Count, Subquery, OuterRef, Window, Prefetch
from django.db.models.functions import Rank, Coalesce
from datetime import timedelta
from math import ceil
from django.apps import apps
import pandas as pd
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from common.enums import AttemptStatus, Difficulty, QuestionType, Zone
from rest_framework import permissions

class IsAdminOrTeacher(permissions.BasePermission):
    """
    Allow only authenticated users whose User.role is ADMIN or TEACHER.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        # adapt these to your actual role constants if different
        return getattr(user, "role", "").upper() in {"ADMIN", "TEACHER"}



from .models import (
    AccessToken,
    AntiCheatEventLog,
    AttemptAnswer,
    LeaderboardEntry,
    Question,
    QuestionExposureLog,
    QuestionOption,
    Quiz,
    QuizAttempt,
    QuizStage,
    QuizStageAttempt,
    StageAdmission,        
    StageAttemptItem,
    StageQuestion,
    StageRandomRule,
)
from django.apps import apps
from .permissions import (
    AdminCanWrite_TeacherCanManageStageQuestion,
    IsAdmin,
    IsAdminOrReadOnly,
    IsStudent,
    IsTeacher,
)
from .serializers import (
    AttemptAnswerSerializer,
    ExcelUploadSerializer,
    LeaderboardEntrySerializer,
    QuestionBulkCreateItemSerializer,
    QuestionCreateSerializer,
    QuestionOptionSerializer,
    QuestionSerializer,
    QuizSerializer,
    QuizStageAttemptSerializer,
    QuizStageSerializer,
    StageQuestionBulkAddSerializer,
    StageQuestionSerializer,
    StageRandomRuleSerializer,
)
from django.apps import apps
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import permissions
from django.shortcuts import get_object_or_404
import hashlib
from django.apps import apps
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from rest_framework.exceptions import PermissionDenied, ValidationError
import hashlib
from django.db.models import Sum, Count
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.exceptions import ValidationError

from common.enums import AttemptStatus, QuestionType
from .models import (
    AttemptAnswer,
    Question,
    QuestionOption,
    QuizStageAttempt,
    StageAttemptItem,
)
from .permissions import IsStudent
from django.conf import settings  


from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Count, Subquery, OuterRef, F, Window
from django.db.models.functions import Rank, Coalesce
from exams.models import QuizStage, LeaderboardEntry, AntiCheatEventLog
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Count, Subquery, OuterRef, F, Window
from django.db.models.functions import Rank, Coalesce
from exams.models import Quiz, QuizStage, LeaderboardEntry, AntiCheatEventLog
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.utils import timezone
from django.db.models import Count, Subquery, OuterRef, F, Window
from django.db.models.functions import Rank, Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Subquery, OuterRef, F, Window
from django.db.models.functions import Rank, Coalesce
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from exams.models import Quiz, QuizStage, LeaderboardEntry, AntiCheatEventLog
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.apps import apps
from django.db import transaction
from django.db.models import Sum
import hashlib
from django.shortcuts import get_object_or_404
from exams.models import (
    QuizAttempt, QuizStageAttempt, AntiCheatEventLog,
    AttemptAnswer, StageAttemptItem, Question, QuestionOption
)
from django.db.models import Count, Subquery, OuterRef, F, Window
from django.db.models.functions import Rank, Coalesce
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from exams.models import LeaderboardEntry, AntiCheatEventLog
from rest_framework.exceptions import ValidationError
from exams.models import QuizAttempt
from common.enums import AttemptStatus, QuestionType
from .permissions import IsStudent

# exams/views.py (near other helpers)
from django.db.models import Count, Sum

STAGE_DQ_THRESHOLD = 3  # "more than 2"

def _stage_anticheat_counts(attempt: QuizAttempt, stage: QuizStage) -> dict[str, int]:
    qs = (AntiCheatEventLog.objects
          .filter(attempt=attempt, details__stage_id=str(stage.id))
          .values("code")
          .annotate(n=Count("id"))
          .order_by("code"))
    return {row["code"]: row["n"] for row in qs}

def _check_and_mark_stage_disqualification(sa: QuizStageAttempt) -> tuple[bool, dict]:
    """
    Returns (disqualified, counts_by_code). Disqualifies the stage attempt
    if total events for this stage reach the threshold.
    """
    counts = _stage_anticheat_counts(sa.attempt, sa.stage)
    total  = sum(counts.values())
    if not sa.is_disqualified and total >= STAGE_DQ_THRESHOLD:
        sa.is_disqualified = True
        # optional: auto-submit timestamp for audit
        if not sa.submitted_at:
            sa.mark_submitted()
        sa.save(update_fields=["is_disqualified", "submitted_at", "time_taken_seconds"])
    return sa.is_disqualified, counts

ALLOW_SECOND_START_DEV = getattr(settings, "QUIZ_ALLOW_SECOND_START_DEV", False)
ANTICHEAT_DISABLED = getattr(settings, "ANTICHEAT_DISABLED", False)

User = get_user_model()

from rest_framework.exceptions import APIException

class Conflict(APIException):
    status_code = 409
    default_detail = "Conflict"
    default_code = "conflict"

def _assert_single_attempt(quiz, user):
    """
    Ensure at most ONE QuizAttempt exists for (quiz, user).
    Returns the single attempt or None. Raises 409 if duplicates exist.
    """
    qs = QuizAttempt.objects.filter(quiz=quiz, user=user).order_by("created_at")
    cnt = qs.count()
    if cnt == 0:
        return None
    if cnt > 1:
        raise Conflict("Multiple attempts detected for this quiz. Paper will not be served. Contact support.")
    return qs.first()


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

def _seed(request, key: str, rotate: str = "day"):
    now = timezone.now()
    if rotate == "hour":
        stamp = now.strftime("%Y-%m-%d-%H")
    elif rotate == "week":
        iso = now.isocalendar()
        stamp = f"{iso.year}-W{iso.week:02d}"
    elif rotate == "none":
        stamp = ""
    else:
        stamp = now.strftime("%Y-%m-%d")
    base = f"{key}:{getattr(request.user, 'pk', 'anon')}:{stamp}"
    secret = getattr(request, "secret", None) or (getattr(User, "__name__", "") or "ndq")
    return hashlib.sha256((base + ":" + secret)[:128].encode()).hexdigest()[:16]

def _hash_int(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)

def _pick_consistent(ids, k, user_id, stage_id, salt=""):
    ranked = sorted(ids, key=lambda qid: _hash_int(f"{user_id}:{stage_id}:{qid}:{salt}"))
    return ranked[:k]

def _stage_quota_from_quiz(quiz: Quiz, stage: QuizStage) -> dict:
    stage_total = stage.question_count or quiz.question_count
    q_total = quiz.question_count or stage_total
    easy = int(getattr(quiz, "easy_count", 0) or 0)
    medium = int(getattr(quiz, "medium_count", 0) or 0)
    hard = int(getattr(quiz, "hard_count", 0) or 0)
    tot = max(1, easy + medium + hard)
    def part(x): return round((x / tot) * stage_total)
    e = part(easy)
    m = part(medium)
    h = max(0, stage_total - e - m)
    return {"easy": e, "medium": m, "hard": h}

def _bank_for_stage(stage: QuizStage):
    qs = Question.objects.filter(is_active=True)
    rr = getattr(stage, "random_rule", None)
    if rr:
        if rr.difficulties:
            qs = qs.filter(difficulty__in=rr.difficulties)
        if rr.subspecialties:
            qs = qs.filter(subspecialty__in=rr.subspecialties)
        if rr.region_hints:
            qs = qs.filter(region_hint__in=rr.region_hints)
        if rr.tags_any:
            q = Q()
            for t in rr.tags_any:
                q |= Q(tags__icontains=t)
            qs = qs.filter(q)
    return qs

class SmallPage(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200




ANTICHEAT_THRESHOLDS = {
    "TAB_BLUR": 3,
    "FULLSCREEN_EXIT": 2,
    "VISIBILITY_HIDDEN": 3,
    "RELOAD": 2,
    "DEVTOOLS_OPEN": 2,
    "MULTI_TAB": 2,
    "MULTI_DEVICE": 2,
    "COPY": 4,
    "PASTE": 4,
    "SCREENSHOT": 2,
    "STAGE_OPEN": 2,
}
STAGE_DQ_THRESHOLD = 3


def _apply_anticheat_policy(attempt: QuizAttempt) -> dict:
    """
    Recompute attempt-level counters and auto-DQ when a threshold is reached.
    Returns: {"disqualified": bool, "code": <str or None>, "counts": {code: n, ...}}
    """
    qs = AntiCheatEventLog.objects.filter(attempt=attempt)
    counts = dict(qs.values("code").annotate(n=Count("id")).values_list("code", "n"))

    # already DQ?
    if attempt.status == AttemptStatus.DISQUALIFIED:
        return {"disqualified": True, "code": attempt.disqualified_reason or "DISQUALIFIED", "counts": counts}

    for code, thr in ANTICHEAT_THRESHOLDS.items():
        if counts.get(code, 0) >= thr:
            attempt.status = AttemptStatus.DISQUALIFIED
            attempt.disqualified_reason = f"Anticheat threshold reached: {code}"
            attempt.submitted_at = attempt.submitted_at or timezone.now()
            attempt.save(update_fields=["status", "disqualified_reason", "submitted_at"])
            return {"disqualified": True, "code": code, "counts": counts}

    return {"disqualified": False, "code": None, "counts": counts}

# ------------------------- helper: stage DQ & counts ---------------------
def _stage_anticheat_counts(attempt: QuizAttempt, stage_id) -> dict[str, int]:
    """Per-stage counts (using details.stage_id attached at log time)."""
    qs = (AntiCheatEventLog.objects
          .filter(attempt=attempt, details__stage_id=str(stage_id))
          .values("code")
          .annotate(n=Count("id"))
          .order_by("code"))
    return {row["code"]: row["n"] for row in qs}

def _check_and_mark_stage_disqualification(sa: QuizStageAttempt) -> tuple[bool, dict]:
    """
    If per-stage total events >= threshold, mark the stage attempt as disqualified
    and finalize timestamps.
    """
    counts = _stage_anticheat_counts(sa.attempt, sa.stage_id)
    total = sum(counts.values())
    if not getattr(sa, "is_disqualified", False) and total >= STAGE_DQ_THRESHOLD:
        sa.is_disqualified = True
        if not sa.submitted_at:
            sa.mark_submitted()
        sa.save(update_fields=["is_disqualified", "submitted_at", "time_taken_seconds"])
    return bool(getattr(sa, "is_disqualified", False)), counts

# ----------------------------- helper: logs ------------------------------
def _serialize_logs(qs):
    return [{
        "id": str(log.id),
        "code": log.code,
        "details": log.details,
        "occurred_at": log.occurred_at,
    } for log in qs]

def _all_attempt_logs(attempt: QuizAttempt):
    return _serialize_logs(
        AntiCheatEventLog.objects.filter(attempt=attempt).order_by("occurred_at")
    )

def _stage_logs(attempt: QuizAttempt, stage_id):
    return _serialize_logs(
        AntiCheatEventLog.objects
        .filter(attempt=attempt, details__stage_id=str(stage_id))
        .order_by("occurred_at")
    )

# ============================ AntiCheatReport ============================
class AntiCheatReportView(APIView):
    """
    POST /api/anticheat/report/
    Body:
      {
        "attempt_id": "<uuid>"        # OR "stage_attempt_id": "<uuid>"
        "code": "TAB_BLUR",
        "details": { ... }            # optional
      }

    Behavior:
      - always logs the event
      - if thresholds are reached:
          * disqualifies the quiz attempt
          * disqualifies the current stage attempt (if provided)
          * returns ALL anti-cheat logs (attempt-wide + per-stage)
      - otherwise returns counts & flags (no logs dump)
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request):
        code = (request.data.get("code") or "").upper().strip()
        if not code:
            raise ValidationError("code is required.")

        sa = None
        if request.data.get("attempt_id"):
            attempt = get_object_or_404(QuizAttempt, pk=request.data["attempt_id"], user=request.user)
        elif request.data.get("stage_attempt_id"):
            sa = get_object_or_404(QuizStageAttempt, pk=request.data["stage_attempt_id"], attempt__user=request.user)
            attempt = sa.attempt
        else:
            raise ValidationError("Provide attempt_id or stage_attempt_id.")

        # ensure stage markers in details when stage present
        details = request.data.get("details") or {}
        if sa:
            details = {**details, "stage_attempt_id": str(sa.id), "stage_id": str(sa.stage_id)}

        AntiCheatEventLog.objects.create(attempt=attempt, code=code, details=details)

        # attempt-level check
        outcome = _apply_anticheat_policy(attempt)  # {"disqualified", "code", "counts"}

        # stage-level check (if relevant)
        stage_disq, stage_counts = (None, None)
        if sa:
            stage_disq, stage_counts = _check_and_mark_stage_disqualification(sa)

        # if attempt got DQ just now, also DQ the stage attempt (if not already)
        if outcome["disqualified"] and sa and not getattr(sa, "is_disqualified", False):
            sa.is_disqualified = True
            if not sa.submitted_at:
                sa.mark_submitted()
            sa.save(update_fields=["is_disqualified", "submitted_at", "time_taken_seconds"])

        # response
        resp = {
            "ok": True,
            "attempt_id": str(attempt.id),
            "attempt_status": attempt.status,
            "attempt_disqualified": bool(outcome["disqualified"]),
            "attempt_disqualified_code": outcome["code"],
            "attempt_counts": outcome["counts"],
        }
        if sa:
            resp.update({
                "stage_attempt_id": str(sa.id),
                "stage_disqualified": bool(stage_disq),
                "stage_counts": stage_counts or {},
            })

        # include complete logs ONLY if we are disqualified (attempt or stage)
        if outcome["disqualified"] or bool(stage_disq):
            resp["attempt_logs"] = _all_attempt_logs(attempt)
            if sa:
                resp["stage_logs"] = _stage_logs(attempt, sa.stage_id)

        return Response(resp, status=status.HTTP_200_OK)

class AnswerUpsertView(APIView):
    """
    POST /api/answers/upsert/
    (unchanged docstring…)
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @transaction.atomic
    def post(self, request):
        sa = get_object_or_404(
            QuizStageAttempt,
            pk=request.data.get("stage_attempt_id"),
            attempt__user=request.user,
        )

        # hard-block if already disqualified (attempt or stage) → return full logs
        if sa.is_disqualified or sa.attempt.status == AttemptStatus.DISQUALIFIED:
            attempt = sa.attempt
            attempt_outcome = _apply_anticheat_policy(attempt)  # ensures counts are fresh
            _, stage_counts = _check_and_mark_stage_disqualification(sa)
            return Response({
                "disqualified": True,
                "reason": attempt.disqualified_reason or "Stage disqualified due to anti-cheat.",
                "attempt_id": str(attempt.id),
                "attempt_status": attempt.status,
                "attempt_counts": attempt_outcome["counts"],
                "attempt_logs": _all_attempt_logs(attempt),
                "stage_attempt_id": str(sa.id),
                "stage_counts": stage_counts,
                "stage_logs": _stage_logs(attempt, sa.stage_id),
            }, status=status.HTTP_403_FORBIDDEN)

        # soft pre-check: if per-stage totals already over limit, block now (with logs)
        stage_dq, stage_counts = _check_and_mark_stage_disqualification(sa)
        if stage_dq:
            attempt = sa.attempt
            attempt_outcome = _apply_anticheat_policy(attempt)  # refresh counts
            return Response({
                "disqualified": True,
                "reason": "Stage disqualified due to anti-cheat.",
                "attempt_id": str(attempt.id),
                "attempt_status": attempt.status,
                "attempt_counts": attempt_outcome["counts"],
                "attempt_logs": _all_attempt_logs(attempt),
                "stage_attempt_id": str(sa.id),
                "stage_counts": stage_counts,
                "stage_logs": _stage_logs(attempt, sa.stage_id),
            }, status=status.HTTP_403_FORBIDDEN)

        attempt = sa.attempt
        if attempt.status != AttemptStatus.STARTED:
            raise ValidationError("Attempt is not active.")

        q = get_object_or_404(Question, pk=request.data.get("question_id"))
        if not StageAttemptItem.objects.filter(stage_attempt=sa, question=q).exists():
            raise ValidationError("Question is not part of this stage attempt.")

        qtype = q.question_type
        bookmark = request.data.get("bookmark")
        final = request.data.get("final")
        inc_time = int(request.data.get("time_spent_seconds", 0) or 0)
        no_ans_flag = bool(request.data.get("no_ans", False))

        def _apply_flags_and_time(objs):
            objs = objs if isinstance(objs, list) else [objs]
            if not objs:
                return
            for obj in objs:
                if bookmark is not None:
                    obj.bookmark = bool(bookmark)
                if final is not None:
                    obj.final = bool(final)
                if inc_time:
                    obj.time_spent_seconds = int(obj.time_spent_seconds or 0) + inc_time
            AttemptAnswer.objects.bulk_update(objs, ["bookmark", "final", "time_spent_seconds"])

        def _score_single(selected: QuestionOption | None):
            it = StageAttemptItem.objects.get(stage_attempt=sa, question=q)
            marks = float(it.marks)
            neg = float(it.negative_marks) if sa.stage.is_negative_makring else 0.0  # ← gate
            if selected is None:
                return False, 0.0
            return (bool(selected.is_correct), (marks if selected.is_correct else -neg))

        def _score_multi(selected_ids: set[str]):
            it = StageAttemptItem.objects.get(stage_attempt=sa, question=q)
            marks = float(it.marks)
            neg = float(it.negative_marks) if sa.stage.is_negative_makring else 0.0  # ← gate
            if not selected_ids:
                return False, 0.0
            correct_ids = set(map(str, q.options.filter(is_correct=True).values_list("id", flat=True)))
            ok = (selected_ids == correct_ids)
            return ok, (marks if ok else -neg)


        # ---- explicit no_ans ----
        if no_ans_flag:
            AttemptAnswer.objects.filter(stage_attempt=sa, question=q).delete()
            ans = AttemptAnswer.objects.create(
                stage_attempt=sa, question=q, order=1, no_ans=True,
                is_correct=False, awarded_marks=0,
                bookmark=bool(bookmark) if bookmark is not None else False,
                final=bool(final) if final is not None else False,
                time_spent_seconds=inc_time or 0,
            )
            updated_rows = [ans]
        else:
            # ---- type branches ----
            if qtype in [QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE,
                         QuestionType.NUMBER, QuestionType.TEXT]:
                AttemptAnswer.objects.filter(stage_attempt=sa, question=q).delete()

                selected = None
                if request.data.get("selected_option"):
                    selected = get_object_or_404(QuestionOption, pk=request.data["selected_option"], question=q)

                ans = AttemptAnswer.objects.create(
                    stage_attempt=sa, question=q, selected_option=selected,
                    answer_text=request.data.get("answer_text", ""),
                    answer_number=request.data.get("answer_number"),
                    answer_bool=request.data.get("answer_bool"),
                    order=1, no_ans=False,
                )
                correct, awarded = _score_single(selected)
                ans.is_correct = bool(correct)
                ans.awarded_marks = float(awarded)
                if bookmark is not None:
                    ans.bookmark = bool(bookmark)
                if final is not None:
                    ans.final = bool(final)
                if inc_time:
                    ans.time_spent_seconds = int(ans.time_spent_seconds or 0) + inc_time
                ans.save()
                updated_rows = [ans]
            else:
                # MULTI
                replace = True if str(request.data.get("replace", True)).lower() in ("true", "1") else False

                if "selected_options" in request.data:
                    new_ids = set(map(str, request.data.get("selected_options") or []))
                    valid_ids = set(map(str, q.options.filter(id__in=new_ids).values_list("id", flat=True)))
                    if new_ids - valid_ids:
                        raise ValidationError("One or more selected_options don't belong to the question.")

                    existing = list(AttemptAnswer.objects.filter(stage_attempt=sa, question=q))
                    existing_ids = {str(a.selected_option_id) for a in existing if a.selected_option_id}

                    to_delete = [a.id for a in existing if str(a.selected_option_id) not in new_ids]
                    if to_delete:
                        AttemptAnswer.objects.filter(id__in=to_delete).delete()

                    to_create = []
                    for oid in (new_ids - existing_ids):
                        to_create.append(AttemptAnswer(
                            stage_attempt=sa, question=q, selected_option_id=oid, order=1, no_ans=False
                        ))
                    if to_create:
                        AttemptAnswer.objects.bulk_create(to_create)
                else:
                    oid = request.data.get("selected_option")
                    if not oid:
                        raise ValidationError("Provide selected_option or selected_options for multi-select.")
                    get_object_or_404(QuestionOption, pk=oid, question=q)

                    if replace:
                        AttemptAnswer.objects.filter(stage_attempt=sa, question=q).delete()
                        AttemptAnswer.objects.create(
                            stage_attempt=sa, question=q, selected_option_id=oid, order=1, no_ans=False
                        )
                    else:
                        row, created = AttemptAnswer.objects.get_or_create(
                            stage_attempt=sa, question=q, selected_option_id=oid,
                            defaults={"order": 1, "no_ans": False},
                        )
                        if not created:
                            row.delete()

                rows = list(AttemptAnswer.objects.filter(stage_attempt=sa, question=q).order_by("id"))
                selected_ids = {str(r.selected_option_id) for r in rows if r.selected_option_id}

                correct, award_total = _score_multi(selected_ids)
                if rows:
                    for i, r in enumerate(rows):
                        r.is_correct = bool(correct)
                        r.awarded_marks = float(award_total if i == 0 else 0.0)
                        r.no_ans = False
                    AttemptAnswer.objects.bulk_update(rows, ["is_correct", "awarded_marks", "no_ans"])
                    _apply_flags_and_time(rows)
                updated_rows = rows

        # ---- recompute stage aggregates ----
        agg = AttemptAnswer.objects.filter(stage_attempt=sa).aggregate(s=Sum("awarded_marks"))
        sa.obtained_marks = float(agg["s"] or 0)
        tot = sa.items.aggregate(s=Sum("marks"))["s"] or 0
        sa.total_marks = float(tot)
        sa.percent = (sa.obtained_marks / (sa.total_marks or 1.0)) * 100.0
        sa.save(update_fields=["obtained_marks", "total_marks", "percent"])

        # ---- compose response for this question ----
        selected_opts = list(
            AttemptAnswer.objects
            .filter(stage_attempt=sa, question=q, selected_option__isnull=False)
            .values_list("selected_option_id", flat=True)
        )

        if updated_rows:
            any_row = updated_rows[0]
            payload = {
                "stage_attempt_id": str(sa.id),
                "question_id": str(q.id),
                "selected_option": str(selected_opts[0]) if len(selected_opts) == 1 else None,
                "selected_options": [str(x) for x in selected_opts],
                "answer_text": getattr(any_row, "answer_text", "") or "",
                "answer_number": getattr(any_row, "answer_number", None),
                "answer_bool": getattr(any_row, "answer_bool", None),
                "bookmark": bool(getattr(any_row, "bookmark", False)),
                "final": bool(getattr(any_row, "final", False)),
                "no_ans": bool(getattr(any_row, "no_ans", False)),
                "question_is_correct": bool(getattr(any_row, "is_correct", False)),
                "question_awarded_marks": float(
                    sum(AttemptAnswer.objects
                        .filter(stage_attempt=sa, question=q)
                        .values_list("awarded_marks", flat=True)) or 0.0
                ),
                "stage_totals": {
                    "obtained": sa.obtained_marks,
                    "total": sa.total_marks,
                    "percent": sa.percent,
                },
            }
        else:
            payload = {
                "stage_attempt_id": str(sa.id),
                "question_id": str(q.id),
                "selected_option": None,
                "selected_options": [],
                "answer_text": "",
                "answer_number": None,
                "answer_bool": None,
                "bookmark": bool(bookmark) if bookmark is not None else False,
                "final": bool(final) if final is not None else False,
                "no_ans": no_ans_flag,
                "question_is_correct": False,
                "question_awarded_marks": 0.0,
                "stage_totals": {
                    "obtained": sa.obtained_marks,
                    "total": sa.total_marks,
                    "percent": sa.percent,
                },
            }

        return Response(payload, status=status.HTTP_200_OK)


class AntiCheatSummaryView(APIView):
    """
    GET /api/anticheat/summary/?attempt_id=<uuid>
        or /api/anticheat/summary/?stage_attempt_id=<uuid>

    Returns per-code counts and current attempt status.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.query_params.get("attempt_id"):
            attempt = get_object_or_404(QuizAttempt, pk=request.query_params["attempt_id"], user=request.user)
        elif request.query_params.get("stage_attempt_id"):
            sa = get_object_or_404(QuizStageAttempt, pk=request.query_params["stage_attempt_id"], attempt__user=request.user)
            attempt = sa.attempt
        else:
            raise ValidationError("Provide attempt_id or stage_attempt_id.")

        qs = (AntiCheatEventLog.objects
              .filter(attempt=attempt)
              .values("code")
              .annotate(count=Count("id"))
              .order_by("code"))

        counts = {r["code"]: r["count"] for r in qs}
        return Response({
            "attempt_id": str(attempt.id),
            "status": attempt.status,
            "disqualified_reason": attempt.disqualified_reason,
            "counts": counts
        }, status=200)

class StartActiveQuizView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request):
        # --- tiny helper just for console diagnostics ---
        def _p(reason, **extra):
            try_user = request.user if hasattr(request, "user") else None
            u_id = getattr(try_user, "id", None)
            u_name = getattr(try_user, "username", None)
            s_id = str(extra.get("stage_id")) if "stage_id" in extra else None
            a_id = str(extra.get("attempt_id")) if "attempt_id" in extra else None
            sa_id = str(extra.get("stage_attempt_id")) if "stage_attempt_id" in extra else None
            print(
                "[QUIZ START FAIL] reason={reason} user_id={uid} username={uname} "
                "quiz_id={qid} stage_id={sid} attempt_id={aid} stage_attempt_id={said} extra={extra}".format(
                    reason=reason,
                    uid=str(u_id),
                    uname=str(u_name),
                    qid=str(extra.get("quiz_id")),
                    sid=s_id,
                    aid=a_id,
                    said=sa_id,
                    extra={k: v for k, v in extra.items() if k not in ("quiz_id","stage_id","attempt_id","stage_attempt_id")}
                )
            )

        # ---- resolve active quiz ----
        active = list(Quiz.objects.filter(is_active=True))
        if not active:
            _p("NO_ACTIVE_QUIZ")
            raise ValidationError("No active quiz.")
        if len(active) > 1:
            _p("MULTIPLE_ACTIVE_QUIZZES", active_ids=[str(q.id) for q in active])
            raise ValidationError("Multiple active quizzes found; only one quiz may be active at a time.")
        quiz = active[0]

        # ---- resolve current stage ----
        stage = (
            quiz.stages.filter(is_current=True).order_by("order").first()
            or quiz.stages.order_by("order").first()
        )
        if not stage:
            _p("NO_STAGE_CONFIGURED", quiz_id=str(quiz.id))
            raise ValidationError("No stage configured for the active quiz.")
        if not stage.is_in_window():
            _p("STAGE_WINDOW_CLOSED", quiz_id=str(quiz.id), stage_id=str(stage.id))
            raise ValidationError("The current stage is not open right now.")

        # ---- tutorial prerequisite ----
        if quiz.prerequisite_tutorial_id:
            TutorialProgress = apps.get_model("learning", "TutorialProgress")
            ok = TutorialProgress.objects.filter(
                user=request.user,
                tutorial_id=quiz.prerequisite_tutorial_id,
                is_completed=True,
            ).exists()
            if not ok:
                _p("TUTORIAL_INCOMPLETE",
                   quiz_id=str(quiz.id),
                   stage_id=str(stage.id),
                   tutorial_id=str(quiz.prerequisite_tutorial_id))
                raise ValidationError("Please complete the required tutorial before starting the quiz.")

        # ---- admission gate (if required) ----
        if stage.requires_admission and not StageAdmission.objects.filter(stage=stage, user=request.user).exists():
            _p("NOT_ADMITTED", quiz_id=str(quiz.id), stage_id=str(stage.id))
            raise PermissionDenied("You are not admitted to the current stage.")

        # ---- single-attempt enforcement + create/lock ----
        with transaction.atomic():
            existing = _assert_single_attempt(quiz, request.user)
            if existing:
                attempt = QuizAttempt.objects.select_for_update().get(pk=existing.pk)
                if attempt.status != AttemptStatus.STARTED:
                    last_sa = (
                        QuizStageAttempt.objects
                        .filter(attempt=attempt, stage=stage)
                        .order_by("-created_at")
                        .first()
                    )
                    _p("ATTEMPT_ALREADY_COMPLETED_OR_UNAVAILABLE",
                       quiz_id=str(quiz.id),
                       stage_id=str(stage.id),
                       attempt_id=str(attempt.id),
                       attempt_status=attempt.status,
                       stage_attempt_id=str(last_sa.id) if last_sa else None)
                    return Response({
                        "detail": "Attempt already completed or unavailable.",
                        "attempt_id": str(attempt.id),
                        "attempt_status": attempt.status,
                        "stage_id": str(stage.id),
                        "stage_attempt_id": str(last_sa.id) if last_sa else None,
                        "resume": False
                    }, status=status.HTTP_409_CONFLICT)
            else:
                attempt = QuizAttempt.objects.create(
                    quiz=quiz,
                    user=request.user,
                    start_ip=_client_ip(request),
                    user_agent=request.data.get("user_agent") or request.META.get("HTTP_USER_AGENT", ""),
                    device_fingerprint=request.data.get("device_fingerprint", ""),
                )
                # initialize total marks from manual mappings (if any)
                total = 0.0
                for st in quiz.stages.all():
                    for sq in StageQuestion.objects.filter(stage=st):
                        total += float(sq.effective_marks())
                attempt.total_marks = total
                attempt.save(update_fields=["total_marks", "start_ip", "user_agent", "device_fingerprint"])

        # ---- anticheat stage-open tracking / resume handling ----
        existing_open = AntiCheatEventLog.objects.filter(
            attempt=attempt, code="STAGE_OPEN", details__stage_id=str(stage.id)
        ).exists()
        existing_sa = QuizStageAttempt.objects.filter(
            attempt=attempt, stage=stage, submitted_at__isnull=True
        ).first()
        resuming = bool(existing_open and existing_sa)

        # If the stage was opened before but there's no active SA, block second starts (unless allowed)
        if existing_open and not existing_sa and not ALLOW_SECOND_START_DEV:
            _p("SECOND_START_BLOCKED",
               quiz_id=str(quiz.id),
               stage_id=str(stage.id),
               attempt_id=str(attempt.id),
               allow_second_start_dev=bool(ALLOW_SECOND_START_DEV))
            return Response({
                "detail": "This stage has already been started. Second attempt is not allowed.",
                "attempt_id": str(attempt.id),
                "stage_id": str(stage.id),
                "stage_attempt_id": None,
                "resume": False
            }, status=status.HTTP_409_CONFLICT)

        # Log STAGE_OPEN exactly once per (attempt, stage)
        if not existing_open and not ANTICHEAT_DISABLED:
            AntiCheatEventLog.objects.create(
                attempt=attempt, code="STAGE_OPEN", details={"stage_id": str(stage.id)}
            )

        # ---- get/lock stage attempt; build items once if missing ----
        with transaction.atomic():
            if resuming:
                sa = QuizStageAttempt.objects.select_for_update().get(pk=existing_sa.pk)
            else:
                sa, _ = QuizStageAttempt.objects.get_or_create(attempt=attempt, stage=stage)
                sa = QuizStageAttempt.objects.select_for_update().get(pk=sa.pk)

            if sa.submitted_at:
                _p("STAGE_ALREADY_SUBMITTED",
                   quiz_id=str(quiz.id),
                   stage_id=str(stage.id),
                   attempt_id=str(attempt.id),
                   stage_attempt_id=str(sa.id))
                return Response({
                    "detail": "Stage already submitted.",
                    "attempt_id": str(attempt.id),
                    "attempt_status": attempt.status,
                    "stage_id": str(stage.id),
                    "stage_attempt_id": str(sa.id),
                    "resume": False
                }, status=status.HTTP_409_CONFLICT)

            if not sa.items.exists():
                mapped = (
                    StageQuestion.objects.filter(stage=stage)
                    .select_related("question").order_by("order")
                )
                if mapped.exists():
                    bulk, order_no = [], 1
                    for sq in mapped:
                        q = sq.question
                        bulk.append(StageAttemptItem(
                            stage_attempt=sa, question=q, order=order_no,
                            marks=float(sq.effective_marks()),
                            negative_marks=float(sq.effective_negative()),
                            time_limit_seconds=int(sq.effective_time()),
                        ))
                        order_no += 1
                    StageAttemptItem.objects.bulk_create(bulk)
                else:
                    quotas = _stage_quota_from_quiz(quiz, stage)
                    pool = _bank_for_stage(stage)
                    if not pool.exists():
                        pool = Question.objects.filter(is_active=True)

                    chosen_ids = []
                    for dkey, dname in [("easy","easy"),("medium","medium"),("hard","hard")]:
                        need = quotas[dkey]
                        if need <= 0:
                            continue
                        diff_pool = list(pool.filter(difficulty=getattr(Difficulty, dname.upper()))
                                         .values_list("id", flat=True))
                        if not diff_pool:
                            continue
                        take = min(need, len(diff_pool))
                        chosen_ids += _pick_consistent(diff_pool, take, request.user.id, stage.id, salt=str(attempt.id))

                    stage_total = stage.question_count or quiz.question_count
                    if len(chosen_ids) < stage_total:
                        remaining = list(pool.exclude(id__in=chosen_ids).values_list("id", flat=True))
                        extra = min(stage_total - len(chosen_ids), len(remaining))
                        if extra > 0:
                            chosen_ids += _pick_consistent(
                                remaining, extra, request.user.id, stage.id, salt=str(attempt.id)+":fill"
                            )

                    ordered_ids = _pick_consistent(
                        chosen_ids, len(chosen_ids), request.user.id, stage.id, salt=str(attempt.id)+":order"
                    )

                    qs_map = Question.objects.in_bulk(ordered_ids)
                    bulk, order_no = [], 1
                    for qid in ordered_ids:
                        q = qs_map[qid]
                        bulk.append(StageAttemptItem(
                            stage_attempt=sa, question=q, order=order_no,
                            marks=float(q.marks), negative_marks=float(q.negative_marks),
                            time_limit_seconds=int(q.time_limit_seconds),
                        ))
                        order_no += 1
                    StageAttemptItem.objects.bulk_create(bulk)

                # keep attempt.total_marks in sync
                agg_total = sa.items.aggregate(s=Sum("marks"))["s"] or 0
                if float(agg_total) > float(attempt.total_marks or 0):
                    attempt.total_marks = float(agg_total)
                    attempt.save(update_fields=["total_marks"])

        # ---- build FULL payload (no pagination) ----
        items_qs = list(sa.items.select_related("question").order_by("order", "id"))

        # question shuffle (stage > quiz)
        shuf_q = stage.shuffle_questions if stage.shuffle_questions is not None else quiz.shuffle_questions
        rotate = request.data.get("rotate") or "day"
        if shuf_q:
            hseed = _seed(request, f"stage:{stage.id}:attempt:{sa.id}", rotate=rotate)
            items_qs = sorted(
                items_qs,
                key=lambda it: hashlib.sha256(f"{hseed}:{it.question_id}:{it.order}".encode()).hexdigest()
            )

        # options shuffle
        shuf_o = stage.shuffle_options if stage.shuffle_options is not None else quiz.shuffle_options
        opt_seed = _seed(request, f"opts:{stage.id}:{sa.id}", rotate=rotate)

        def _public_question(q):
            return {
                "id": str(q.id),
                "text": q.text,
                "explanation": q.explanation,
                "question_type": q.question_type,
                "time_limit_seconds": q.time_limit_seconds,
                "tags": q.tags,
            }

        def _public_options(q):
            opts = list(q.options.all().values("id", "text"))
            if shuf_o and opts:
                opts.sort(key=lambda o: hashlib.sha256(f"{opt_seed}:{q.id}:{o['id']}".encode()).hexdigest())
            return [{"id": str(o["id"]), "text": o["text"]} for o in opts]

        payload_items = [{
            "order": it.order,
            "marks": float(it.marks),
            "negative_marks": float(it.negative_marks),
            "time_limit_seconds": int(it.time_limit_seconds),
            "question": _public_question(it.question),
            "options": _public_options(it.question),
        } for it in items_qs]

        # ---- FINAL SAFETY: DQ?
        if attempt.status == AttemptStatus.DISQUALIFIED:
            _p("ATTEMPT_DISQUALIFIED",
               quiz_id=str(quiz.id),
               stage_id=str(stage.id),
               attempt_id=str(attempt.id),
               disqualified_reason=attempt.disqualified_reason)
            raise PermissionDenied(attempt.disqualified_reason or "Attempt disqualified.")

        return Response({
            "attempt_id": str(attempt.id),
            "stage_id": str(stage.id),
            "stage_attempt_id": str(sa.id),
            "quiz": {"id": str(quiz.id), "title": quiz.title},
            "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order},
            "total_items": len(payload_items),
            "configured_question_count": int(stage.question_count or quiz.question_count or 0),
            "items": payload_items,
            "resume": resuming  # ← full payload even on resume
        }, status=status.HTTP_200_OK)



class StartStageAndGetQuestionsView(APIView):
    """
    POST /api/quizzes/<uuid:quiz_id>/start/
    Body (optional):
      {
        "page": 1,
        "page_size": 5,
        "device_fingerprint": "...",
        "user_agent": "...",
        "rotate": "day",         # "day" | "hour" | "week" | "none"
        "return_all": false      # if true -> ignore pagination and return all questions
      }
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, quiz_id):
        # --- resolve quiz + current stage ---
        quiz = get_object_or_404(Quiz, pk=quiz_id)
        if not quiz.is_active:
            raise ValidationError("This quiz is not active.")

        stage = (quiz.stages.filter(is_current=True).order_by("order").first()
                 or quiz.stages.order_by("order").first())
        if not stage:
            raise ValidationError("No stage configured for this quiz.")

        # Stage/quiz window
        if not stage.is_in_window():
            raise ValidationError("The quiz stage is not currently open.")

        # Tutorial prerequisite
        if quiz.prerequisite_tutorial_id:
            TutorialProgress = apps.get_model("learning", "TutorialProgress")
            ok = TutorialProgress.objects.filter(
                user=request.user,
                tutorial_id=quiz.prerequisite_tutorial_id,
                is_completed=True,
            ).exists()
            if not ok:
                raise ValidationError("Please complete the required tutorial before starting the quiz.")

        # Admission gate
        if stage.requires_admission and not StageAdmission.objects.filter(stage=stage, user=request.user).exists():
            raise PermissionDenied("You are not admitted to the current stage.")

        # --- attempt objects (single attempt per user/quiz) ---
        try:
            with transaction.atomic():
                existing = _assert_single_attempt(quiz, request.user)  # raises Conflict (409) if >1
                if existing:
                    attempt = QuizAttempt.objects.select_for_update().get(pk=existing.pk)
                    if attempt.status != AttemptStatus.STARTED:
                        raise ValidationError("Attempt already completed or unavailable.")
                else:
                    attempt = QuizAttempt.objects.create(
                        quiz=quiz,
                        user=request.user,
                        start_ip=_client_ip(request),
                        user_agent=request.data.get("user_agent") or request.META.get("HTTP_USER_AGENT", ""),
                        device_fingerprint=request.data.get("device_fingerprint", ""),
                    )
                    # initialize total marks from manual mappings (if any)
                    total = 0.0
                    for st in quiz.stages.all():
                        for sq in StageQuestion.objects.filter(stage=st):
                            total += float(sq.effective_marks())
                    attempt.total_marks = total
                    attempt.save(update_fields=["total_marks", "start_ip", "user_agent", "device_fingerprint"])
        except Conflict as e:
            dup_ids = list(
                QuizAttempt.objects
                .filter(quiz=quiz, user=request.user)
                .order_by("created_at")
                .values_list("id", flat=True)
            )
            return Response(
                {"detail": str(e.detail), "error": "multiple_attempts", "attempt_ids": [str(x) for x in dup_ids]},
                status=409
            )

        # --- optional anticheat "STAGE_OPEN" logging (once per stage) ---
        existing_open = AntiCheatEventLog.objects.filter(
            attempt=attempt, code="STAGE_OPEN", details__stage_id=str(stage.id)
        ).exists()
        if existing_open:
            existing_sa = QuizStageAttempt.objects.filter(
                attempt=attempt, stage=stage, submitted_at__isnull=True
            ).first()
            if not existing_sa and not ALLOW_SECOND_START_DEV:
                raise ValidationError("This stage has already been started. Second attempt is not allowed.")
        if not existing_open and not ANTICHEAT_DISABLED:
            AntiCheatEventLog.objects.create(
                attempt=attempt,
                code="STAGE_OPEN",
                details={"stage_id": str(stage.id)},
            )

        # --- stage attempt + one-time paper build ---
        with transaction.atomic():
            sa, _ = QuizStageAttempt.objects.get_or_create(attempt=attempt, stage=stage)
            sa = QuizStageAttempt.objects.select_for_update().get(pk=sa.pk)
            if sa.submitted_at:
                raise ValidationError("This stage has already been submitted.")

            if not sa.items.exists():
                mapped = (
                    StageQuestion.objects.filter(stage=stage)
                    .select_related("question")
                    .order_by("order")
                )
                if mapped.exists():
                    bulk, order_no = [], 1
                    for sq in mapped:
                        q = sq.question
                        bulk.append(StageAttemptItem(
                            stage_attempt=sa,
                            question=q,
                            order=order_no,
                            marks=float(sq.effective_marks()),
                            negative_marks=float(sq.effective_negative()),
                            time_limit_seconds=int(sq.effective_time()),
                        ))
                        order_no += 1
                    StageAttemptItem.objects.bulk_create(bulk)
                else:
                    # random rule path with difficulty quotas
                    quotas = _stage_quota_from_quiz(quiz, stage)
                    pool = _bank_for_stage(stage)
                    if not pool.exists():
                        pool = Question.objects.filter(is_active=True)

                    chosen_ids = []
                    for diff_key, diff_val in [("easy","easy"),("medium","medium"),("hard","hard")]:
                        need = quotas[diff_key]
                        if need <= 0:
                            continue
                        diff_pool = list(
                            pool.filter(difficulty=getattr(Difficulty, diff_val.upper()))
                                .values_list("id", flat=True)
                        )
                        if not diff_pool:
                            continue
                        take = min(need, len(diff_pool))
                        chosen_ids += _pick_consistent(
                            diff_pool, take, request.user.id, stage.id, salt=str(attempt.id)
                        )

                    stage_total = stage.question_count or quiz.question_count
                    if len(chosen_ids) < stage_total:
                        remaining = list(pool.exclude(id__in=chosen_ids).values_list("id", flat=True))
                        extra = min(stage_total - len(chosen_ids), len(remaining))
                        if extra > 0:
                            chosen_ids += _pick_consistent(
                                remaining, extra, request.user.id, stage.id, salt=str(attempt.id)+":fill"
                            )

                    ordered_ids = _pick_consistent(
                        chosen_ids, len(chosen_ids), request.user.id, stage.id, salt=str(attempt.id)+":order"
                    )

                    qs_map = Question.objects.in_bulk(ordered_ids)
                    bulk, order_no = [], 1
                    for qid in ordered_ids:
                        q = qs_map[qid]
                        bulk.append(StageAttemptItem(
                            stage_attempt=sa,
                            question=q,
                            order=order_no,
                            marks=float(q.marks),
                            negative_marks=float(q.negative_marks),
                            time_limit_seconds=int(q.time_limit_seconds),
                        ))
                        order_no += 1
                    StageAttemptItem.objects.bulk_create(bulk)

                # keep attempt.total_marks in sync if this stage added more
                agg_total = sa.items.aggregate(s=Sum("marks"))["s"] or 0
                if float(agg_total) > float(attempt.total_marks or 0):
                    attempt.total_marks = float(agg_total)
                    attempt.save(update_fields=["total_marks"])

        # --- fetch + deterministic shuffles (per user) ---
        items_qs = list(sa.items.select_related("question").order_by("order", "id"))

        shuf_q = stage.shuffle_questions if stage.shuffle_questions is not None else quiz.shuffle_questions
        rotate = request.data.get("rotate") or "day"
        if shuf_q:
            qseed = _seed(request, f"stage:{stage.id}:attempt:{sa.id}", rotate=rotate)
            items_qs.sort(key=lambda it: hashlib.sha256(
                f"{qseed}:{it.question_id}:{it.order}".encode("utf-8")
            ).hexdigest())

        shuf_o = stage.shuffle_options if stage.shuffle_options is not None else quiz.shuffle_options
        opt_seed = _seed(request, f"opts:{stage.id}:{sa.id}", rotate=rotate)

        def _public_question(q):
            return {
                "id": str(q.id),
                "text": q.text,
                "explanation": q.explanation,
                "question_type": q.question_type,
                "time_limit_seconds": q.time_limit_seconds,
                "tags": q.tags,
            }

        def _public_options(q):
            opts = list(q.options.all().values("id", "text"))  # never expose is_correct
            if shuf_o and opts:
                opts.sort(key=lambda o: hashlib.sha256(
                    f"{opt_seed}:{q.id}:{o['id']}".encode("utf-8")
                ).hexdigest())
            return [{"id": str(o["id"]), "text": o["text"]} for o in opts]

        # --- pagination (or return all) ---
        return_all = bool(request.data.get("return_all", False))
        if return_all:
            paged = items_qs
            page = 1
            page_size = len(items_qs)
            total_items = len(items_qs)
            total_pages = 1
            is_last = True
        else:
            page = max(1, int(request.data.get("page", 1)))
            page_size = min(50, max(1, int(request.data.get("page_size", 5))))
            total_items = len(items_qs)
            total_pages = max(1, (total_items + page_size - 1) // page_size)
            start = (page - 1) * page_size
            end = start + page_size
            paged = items_qs[start:end]
            is_last = page >= total_pages

        payload_items = [{
            "order": it.order,
            "marks": float(it.marks),
            "negative_marks": float(it.negative_marks),
            "time_limit_seconds": int(it.time_limit_seconds),
            "question": _public_question(it.question),
            "options": _public_options(it.question),
        } for it in paged]

        # Final safety: disqualified?
        if attempt.status == AttemptStatus.DISQUALIFIED:
            raise PermissionDenied(attempt.disqualified_reason or "Attempt disqualified.")

        return Response({
            "attempt_id": str(attempt.id),
            "stage_attempt_id": str(sa.id),
            "quiz": QuizSerializer(quiz).data,
            "stage": QuizStageSerializer(stage).data,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "is_last_page": is_last,
            "configured_question_count": int(stage.question_count or quiz.question_count or 0),
            "items": payload_items,
        }, status=200)

class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all().prefetch_related("options")
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = QuestionSerializer
    pagination_class = SmallPage

    def get_serializer_class(self):
        if self.action in ["create", "bulk", "import_excel"]:
            return QuestionCreateSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        if not IsAdmin().has_permission(request, self):
            raise PermissionDenied("Only admin can create questions.")
        ser = QuestionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        q = ser.save()
        return Response(QuestionSerializer(q).data, status=201)

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request):
        if not IsAdmin().has_permission(request, self):
            raise PermissionDenied("Only admin can bulk-create questions.")
        if not isinstance(request.data, list):
            return Response({"detail": "Expected list payload"}, status=400)
        ser = QuestionBulkCreateItemSerializer(data=request.data, many=True)
        ser.is_valid(raise_exception=True)
        created = []
        with transaction.atomic():
            for item in ser.validated_data:
                q = QuestionCreateSerializer().create(item)
                created.append(q.id)
        qs = Question.objects.filter(id__in=created).prefetch_related("options")
        return Response({"created": len(created), "questions": QuestionSerializer(qs, many=True).data}, status=201)

    @action(detail=False, methods=["post"], url_path="import-excel")
    def import_excel(self, request):
        if not IsAdmin().has_permission(request, self):
            raise PermissionDenied("Only admin can import questions.")
        upload = ExcelUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        f = upload.validated_data["file"]
        try:
            xl = pd.ExcelFile(f)
        except Exception as e:
            return Response({"detail": f"Invalid Excel: {e}"}, status=400)

        created_ids = []
        with transaction.atomic():
            if "questions" in xl.sheet_names and "options" not in xl.sheet_names:
                df = xl.parse("questions").fillna("")
                for _, r in df.iterrows():
                    payload = {
                        "text": str(r.get("text", "")).strip(),
                        "explanation": str(r.get("explanation", "")),
                        "question_type": str(r.get("question_type", "single")).lower(),
                        "subspecialty": str(r.get("subspecialty", "")),
                        "difficulty": str(r.get("difficulty", "medium")).lower(),
                        "region_hint": str(r.get("region_hint", "")).upper() or "",
                        "marks": float(r.get("marks", 1) or 1),
                        "negative_marks": float(r.get("negative_marks", 0) or 0),
                        "time_limit_seconds": int(r.get("time_limit_seconds", 120) or 120),
                        "is_active": bool(r.get("is_active", True)),
                        "tags": json.loads(r.get("tags_json", "{}") or "{}"),
                        "options": json.loads(r.get("options_json", "[]") or "[]"),
                    }
                    q = QuestionCreateSerializer().create(payload)
                    created_ids.append(q.id)
            else:
                qdf = xl.parse("questions").fillna("")
                odf = xl.parse("options").fillna("")
                tmp_map = {}
                for _, r in qdf.iterrows():
                    payload = {
                        "text": str(r.get("text", "")).strip(),
                        "explanation": str(r.get("explanation", "")),
                        "question_type": str(r.get("question_type", "single")).lower(),
                        "subspecialty": str(r.get("subspecialty", "")),
                        "difficulty": str(r.get("difficulty", "medium")).lower(),
                        "region_hint": str(r.get("region_hint", "")).upper() or "",
                        "marks": float(r.get("marks", 1) or 1),
                        "negative_marks": float(r.get("negative_marks", 0) or 0),
                        "time_limit_seconds": int(r.get("time_limit_seconds", 120) or 120),
                        "is_active": bool(r.get("is_active", True)),
                        "tags": json.loads(r.get("tags_json", "{}") or "{}"),
                        "options": [],
                    }
                    q = Question.objects.create(**{k: v for k, v in payload.items() if k != "options"})
                    created_ids.append(q.id)
                    key = int(r.get("id", 0)) if r.get("id", 0) else str(r.get("text", "")).strip()
                    tmp_map[key] = q.id
                bulk_opts = []
                for _, r in odf.iterrows():
                    qref = r.get("question_id") or str(r.get("question_text", "")).strip()
                    qid = tmp_map.get(qref)
                    if not qid:
                        continue
                    bulk_opts.append(
                        QuestionOption(
                            question_id=qid,
                            text=str(r.get("text", "")).strip(),
                            is_correct=bool(r.get("is_correct", False)),
                            order=int(r.get("order", 0) or 0),
                        )
                    )
                if bulk_opts:
                    QuestionOption.objects.bulk_create(bulk_opts)

        qs = Question.objects.filter(id__in=created_ids).prefetch_related("options")
        return Response({"created": len(created_ids), "questions": QuestionSerializer(qs, many=True).data}, status=201)

class QuizViewSet(viewsets.ModelViewSet):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = SmallPage

    @action(detail=False, methods=["post"], url_path="import-excel", permission_classes=[IsAdmin])
    def import_excel(self, request):
        upload = ExcelUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        f = upload.validated_data["file"]
        try:
            df = pd.read_excel(f, sheet_name="quizzes").fillna("")
        except Exception as e:
            return Response({"detail": f"Invalid Excel: {e}"}, status=400)

        created = 0
        with transaction.atomic():
            for _, r in df.iterrows():
                data = {
                    "title": str(r.get("title", "")).strip(),
                    "slug": str(r.get("slug", "")).strip(),
                    "description": str(r.get("description", "")),
                    "subspecialty": str(r.get("subspecialty", "")),
                    "start_at": pd.to_datetime(r.get("start_at")).to_pydatetime(),
                    "end_at": pd.to_datetime(r.get("end_at")).to_pydatetime(),
                    "duration_seconds": int(r.get("duration_seconds", 1800) or 1800),
                    "pass_threshold_percent": int(r.get("pass_threshold_percent", 90) or 90),
                    "question_count": int(r.get("question_count", 25) or 25),
                    "shuffle_questions": bool(r.get("shuffle_questions", True)),
                    "shuffle_options": bool(r.get("shuffle_options", True)),
                    "require_fullscreen": bool(r.get("require_fullscreen", True)),
                    "lock_on_tab_switch": bool(r.get("lock_on_tab_switch", True)),
                }
                Quiz.objects.update_or_create(slug=data["slug"], defaults=data)
                created += 1
        return Response({"created_or_updated": created}, status=201)

    @action(detail=True, methods=["get"], url_path="questions", permission_classes=[IsAdminOrReadOnly])
    def questions(self, request, pk=None):
        quiz = self.get_object()
        stages = quiz.stages.all().order_by("order")
        out = []
        for st in stages:
            rows = (
                StageQuestion.objects.filter(stage=st)
                .select_related("question")
                .order_by("order")
            )
            for x in rows:
                out.append(
                    {
                        "stage_order": st.order,
                        "stage": QuizStageSerializer(st).data,
                        "stage_question": StageQuestionSerializer(x).data,
                        "question": QuestionSerializer(x.question).data,
                        "options": QuestionOptionSerializer(
                            x.question.options.all().order_by("order", "id"), many=True
                        ).data,
                    }
                )
        return Response(out)


    @action(detail=False, methods=["get"], url_path="open", permission_classes=[permissions.IsAuthenticated])
    def open(self, request):
        now = timezone.now()
        qs = Quiz.objects.filter(start_at__lte=now, end_at__gte=now).order_by("start_at")
        data = []
        TutorialProgress = apps.get_model("learning", "TutorialProgress")
        for q in qs:
            tut_ok = True
            tut_id = getattr(q, "prerequisite_tutorial_id", None)
            if tut_id:
                tut_ok = TutorialProgress.objects.filter(
                    user=request.user, tutorial_id=tut_id, is_completed=True
                ).exists()
            data.append({
                "quiz": QuizSerializer(q).data,
                "tutorial_required": bool(tut_id),
                "tutorial_completed": tut_ok,
                "can_start": tut_ok,  # and window is open
            })
        return Response(data)


    @action(detail=True, methods=["get"], url_path="stages", permission_classes=[permissions.AllowAny])
    def list_stages(self, request, pk=None):
        """
        List all stages for this quiz (ordered), plus the current stage id.
        GET /api/quizzes/<quiz_id>/stages/
        """
        quiz = self.get_object()
        stages_qs = quiz.stages.all().order_by("order")
        current = stages_qs.filter(is_current=True).first()
        return Response({
            "quiz": QuizSerializer(quiz).data,
            "current_stage_id": str(current.id) if current else None,
            "items": QuizStageSerializer(stages_qs, many=True).data,
        }, status=200)

    @action(detail=True, methods=["get"], url_path="current-stage", permission_classes=[permissions.AllowAny])
    def current_stage(self, request, pk=None):
        """
        Get the current stage for this quiz (falls back to first stage if none flagged).
        GET /api/quizzes/<quiz_id>/current-stage/
        """
        quiz = self.get_object()
        st = quiz.stages.filter(is_current=True).order_by("order").first() \
             or quiz.stages.order_by("order").first()
        if not st:
            return Response({"detail": "No stages configured for this quiz."}, status=404)
        return Response(QuizStageSerializer(st).data, status=200)

    @action(detail=True, methods=["post"], url_path="set-current-stage", permission_classes=[IsAdmin])
    def set_current_stage(self, request, pk=None):
        """
        Set a stage (by id) as current for this quiz. Admin only.
        POST /api/quizzes/<quiz_id>/set-current-stage/
        Body: { "stage_id": "<uuid>" }
        """
        quiz = self.get_object()
        stage_id = request.data.get("stage_id")
        if not stage_id:
            return Response({"detail": "stage_id is required."}, status=400)
        st = get_object_or_404(QuizStage, pk=stage_id, quiz=quiz)
        QuizStage.objects.filter(quiz=quiz, is_current=True).update(is_current=False)
        st.is_current = True
        st.save(update_fields=["is_current"])
        return Response({"ok": True, "current_stage_id": str(st.id)}, status=200)

    @action(detail=True, methods=["post"], url_path="publish-results", permission_classes=[IsAdmin])
    def publish_results(self, request, pk=None):
        quiz = self.get_object()
        quiz.results_visible_after_close = True
        quiz.results_published_at = timezone.now()
        quiz.save(update_fields=["results_visible_after_close", "results_published_at"])
        return Response({"ok": True, "published_at": quiz.results_published_at})

    @action(detail=True, methods=["get"], url_path="my-status", permission_classes=[permissions.IsAuthenticated])
    def my_status(self, request, pk=None):
        quiz = self.get_object()
        now = timezone.now()
        in_window = quiz.start_at <= now <= quiz.end_at
        tut_id = getattr(quiz, "prerequisite_tutorial_id", None)
        tutorial_ok = True
        if tut_id:
            TutorialProgress = apps.get_model("learning", "TutorialProgress")
            tutorial_ok = TutorialProgress.objects.filter(
                user=request.user, tutorial_id=tut_id, is_completed=True
            ).exists()
        return Response({
            "in_window": in_window,
            "tutorial_required": bool(tut_id),
            "tutorial_completed": tutorial_ok,
            "can_start": in_window and tutorial_ok,
            "window": {"start_at": quiz.start_at, "end_at": quiz.end_at},
        })

    @action(
        detail=False,
        methods=["get"],
        url_path="with-stages",
        permission_classes=[permissions.AllowAny],
    )
    def with_stages(self, request):
        """
        GET /api/quizzes/with-stages/
        Returns a list of quizzes with their stages ordered by stage.order.
        If the requester is an authenticated STUDENT, each stage also carries
        the student's status (attempted/submitted, marks, time, etc.).
        """
        # Is the requester a student?
        is_student = (
            request.user.is_authenticated
            and getattr(request.user, "role", "").upper() == "STUDENT"
        )

        # Rely on QuizStage.Meta(ordering=("quiz","order","created_at"))
        # and prefetch the broad relations (no filtered Prefetch).
        qs = (
            Quiz.objects
            .all()
            .order_by("start_at", "id")
            .prefetch_related(
                "stages",
                "attempts",                    # all attempts for this quiz
                "stages__attempts",            # all stage attempts
                "stages__attempts__attempt",   # so we can read sa.attempt.user_id without extra queries
            )
        )

        items = []
        for q in qs:
            quiz_data = QuizSerializer(q).data

            # Student’s quiz-level attempt (pick only this user’s)
            my_quiz_attempt_data = None
            if is_student:
                ats_for_me = [a for a in q.attempts.all() if a.user_id == request.user.id]  # uses prefetch cache
                my_attempt = ats_for_me[0] if ats_for_me else None

                if my_attempt:
                    my_quiz_attempt_data = {
                        "attempt_id": str(my_attempt.id),
                        "status": my_attempt.status,
                        "submitted": bool(my_attempt.submitted_at),
                        "submitted_at": my_attempt.submitted_at,
                        "percent": float(my_attempt.percent),
                        "obtained_marks": float(my_attempt.obtained_marks),
                        "total_marks": float(my_attempt.total_marks),
                        "time_taken_seconds": int(my_attempt.time_taken_seconds or 0),
                    }
                else:
                    my_quiz_attempt_data = {
                        "attempt_id": None,
                        "status": None,
                        "submitted": False,
                        "submitted_at": None,
                        "percent": None,
                        "obtained_marks": None,
                        "total_marks": None,
                        "time_taken_seconds": 0,
                    }

            # Build stages list (already ordered by Meta; sort defensively just in case)
            stages_qs = list(q.stages.all())
            stages_qs.sort(key=lambda s: (getattr(s, "order", 0), str(s.id)))

            stages_data = []
            for st in stages_qs:
                base = QuizStageSerializer(st).data

                if is_student:
                    # stage attempts are prefetched; filter to this user via the linked attempt
                    sa_for_me = [
                        sa for sa in st.attempts.all()  # uses prefetch cache
                        if getattr(sa, "attempt", None) and sa.attempt.user_id == request.user.id
                    ]
                    sa = sa_for_me[0] if sa_for_me else None

                    base.update({
                        "my_attempted": bool(sa),
                        "my_stage_attempt_id": str(sa.id) if sa else None,
                        "my_submitted": bool(sa and sa.submitted_at),
                        "my_submitted_at": sa.submitted_at if sa else None,
                        "my_percent": float(sa.percent) if sa else None,
                        "my_obtained_marks": float(sa.obtained_marks) if sa else None,
                        "my_total_marks": float(sa.total_marks) if sa else None,
                        "my_time_taken_seconds": int(sa.time_taken_seconds or 0) if sa else 0,
                    })

                stages_data.append(base)

            items.append({
                "quiz": quiz_data,
                "my_quiz_attempt": my_quiz_attempt_data if is_student else None,
                "stages": stages_data,
            })

        return Response({"items": items}, status=200)

class QuizStageViewSet(viewsets.ModelViewSet):
    serializer_class = QuizStageSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = SmallPage

    def get_queryset(self):
        qs = QuizStage.objects.select_related("quiz").all()
        quiz_id = self.request.query_params.get("quiz")
        if quiz_id:
            qs = qs.filter(quiz_id=quiz_id)
        is_current = self.request.query_params.get("is_current")
        if is_current is not None:
            val = str(is_current).lower() in ["1", "true", "yes"]
            qs = qs.filter(is_current=val)
        return qs

    @action(detail=True, methods=["get"], url_path="questions", permission_classes=[IsAdminOrReadOnly])
    def questions(self, request, pk=None):
        stage = self.get_object()
        rows = (
            StageQuestion.objects.filter(stage=stage)
            .select_related("question")
            .order_by("order")
        )
        payload = [
            {
                "stage_question": StageQuestionSerializer(x).data,
                "question": QuestionSerializer(x.question).data,
                "options": QuestionOptionSerializer(
                    x.question.options.all().order_by("order", "id"), many=True
                ).data,
            }
            for x in rows
        ]
        return Response({"stage": QuizStageSerializer(stage).data, "items": payload})

    @action(detail=False, methods=["post"], url_path="import-excel", permission_classes=[IsAdmin])
    def import_excel(self, request):
        upload = ExcelUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        f = upload.validated_data["file"]
        try:
            df = pd.read_excel(f, sheet_name="stages").fillna("")
        except Exception as e:
            return Response({"detail": f"Invalid Excel: {e}"}, status=400)

        created = 0
        with transaction.atomic():
            for _, r in df.iterrows():
                quiz = get_object_or_404(Quiz, slug=str(r.get("quiz_slug", "")).strip())
                data = {
                    "quiz": quiz,
                    "title": str(r.get("title", "")).strip(),
                    "description": str(r.get("description", "")),
                    "order": int(r.get("order", 1) or 1),
                    "duration_seconds": int(r.get("duration_seconds", 0) or 0) or None,
                    "question_count": int(r.get("question_count", 0) or 0) or None,
                    "shuffle_questions": None
                    if r.get("shuffle_questions", "") == ""
                    else bool(r.get("shuffle_questions")),
                    "shuffle_options": None
                    if r.get("shuffle_options", "") == ""
                    else bool(r.get("shuffle_options")),
                }
                QuizStage.objects.update_or_create(
                    quiz=quiz, order=data["order"], defaults=data
                )
                created += 1
        return Response({"created_or_updated": created}, status=201)

    @action(detail=True, methods=["post"], url_path="set-current", permission_classes=[IsAdmin])
    def set_current(self, request, pk=None):
        st = self.get_object()
        QuizStage.objects.filter(quiz=st.quiz, is_current=True).update(is_current=False)
        st.is_current = True
        st.save(update_fields=["is_current"])
        return Response({"ok": True, "current_stage_id": str(st.id)})

    @action(detail=True, methods=["post"], url_path="admit", permission_classes=[IsAdmin])
    def admit(self, request, pk=None):
        """
        Admit users into THIS stage based on prior results.
        Body examples:
          {"mode":"TOP_N", "from_stage_order":1, "n":50}
          {"mode":"PERCENT_GTE", "from_stage_order":1, "threshold": 70}
          {"mode":"ZONE_TOP_N", "from_stage_order":1, "per_zone":{"NORTH":10,"SOUTH":10}}
          {"mode":"MANUAL", "user_ids":[1,2,3]}
        """
        stage = self.get_object()
        mode = (request.data.get("mode") or "").upper()
        from_order = request.data.get("from_stage_order")
        user_ids = set()

        if mode == "MANUAL":
            user_ids = set(map(int, request.data.get("user_ids") or []))
        else:
            if not from_order:
                return Response({"detail": "from_stage_order is required"}, status=400)
            prev = get_object_or_404(QuizStage, quiz=stage.quiz, order=int(from_order))
            base_qs = LeaderboardEntry.objects.filter(
                quiz=stage.quiz, quiz_stage=prev
            ).order_by("-percent", "time_taken_seconds", "id")

            if mode == "TOP_N":
                n = int(request.data.get("n", 0) or 0)
                user_ids = set(base_qs.values_list("user_id", flat=True)[:n])
            elif mode == "PERCENT_GTE":
                thr = float(request.data.get("threshold", 0))
                user_ids = set(base_qs.filter(percent__gte=thr).values_list("user_id", flat=True))
            elif mode == "ZONE_TOP_N":
                per_zone = request.data.get("per_zone") or {}
                for z, n in per_zone.items():
                    zqs = base_qs.filter(zone=z)[:int(n)]
                    user_ids.update(zqs.values_list("user_id", flat=True))
            elif mode == "STATE_TOP_N":
                per_state = request.data.get("per_state") or {}
                for s, n in per_state.items():
                    sqs = base_qs.filter(user__state=s)[:int(n)]
                    user_ids.update(sqs.values_list("user_id", flat=True))
            else:
                return Response({"detail": "Invalid mode"}, status=400)

        created = 0
        with transaction.atomic():
            for uid in user_ids:
                StageAdmission.objects.update_or_create(
                    stage=stage,
                    user_id=uid,
                    defaults=dict(rule_code=mode, meta=request.data, granted_by=request.user),
                )
                created += 1

        if request.data.get("set_current", True):
            QuizStage.objects.filter(quiz=stage.quiz, is_current=True).update(is_current=False)
            stage.is_current = True
            stage.requires_admission = True
            stage.save(update_fields=["is_current", "requires_admission"])

        return Response({"admitted": created, "stage_id": str(stage.id)}, status=200)

class StageQuestionViewSet(viewsets.ModelViewSet):
    queryset = StageQuestion.objects.select_related("stage", "question", "stage__quiz").all()
    serializer_class = StageQuestionSerializer
    permission_classes = [AdminCanWrite_TeacherCanManageStageQuestion]
    allow_teacher_write = True
    pagination_class = SmallPage

    @action(detail=False, methods=["post"], url_path="bulk-add")
    def bulk_add(self, request):
        if not (IsAdmin().has_permission(request, self) or IsTeacher().has_permission(request, self)):
            raise PermissionDenied("Only admin/teacher can modify stage questions.")
        ser = StageQuestionBulkAddSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        stage = ser.validated_data["stage"]
        items = ser.validated_data["items"]

        created = 0
        with transaction.atomic():
            for it in items:
                q = get_object_or_404(Question, pk=it.get("question"))
                StageQuestion.objects.update_or_create(
                    stage=stage,
                    question=q,
                    defaults={
                        "order": int(it.get("order", 1) or 1),
                        "marks": it.get("marks"),
                        "negative_marks": it.get("negative_marks"),
                        "time_limit_seconds": it.get("time_limit_seconds"),
                    },
                )
                created += 1
        qs = StageQuestion.objects.filter(stage=stage).order_by("order")
        return Response(
            {"upserted": created, "stage_questions": StageQuestionSerializer(qs, many=True).data},
            status=201,
        )

    @action(detail=False, methods=["post"], url_path="import-excel", permission_classes=[IsAdmin])
    def import_excel(self, request):
        upload = ExcelUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        f = upload.validated_data["file"]
        try:
            df = pd.read_excel(f, sheet_name="stage_questions").fillna("")
        except Exception as e:
            return Response({"detail": f"Invalid Excel: {e}"}, status=400)

        upserted = 0
        with transaction.atomic():
            for _, r in df.iterrows():
                quiz = get_object_or_404(Quiz, slug=str(r.get("quiz_slug", "")).strip())
                stage = get_object_or_404(QuizStage, quiz=quiz, order=int(r.get("stage_order", 1) or 1))

                qid = r.get("question_id")
                qtext = str(r.get("question_text", "")).strip()
                if qid:
                    q = get_object_or_404(Question, pk=int(qid))
                else:
                    q = Question.objects.filter(text=qtext).first()
                    if not q:
                        continue

                StageQuestion.objects.update_or_create(
                    stage=stage,
                    question=q,
                    defaults={
                        "order": int(r.get("order", 1) or 1),
                        "marks": float(r.get("marks")) if r.get("marks", "") != "" else None,
                        "negative_marks": float(r.get("negative_marks"))
                        if r.get("negative_marks", "") != ""
                        else None,
                        "time_limit_seconds": int(r.get("time_limit_seconds"))
                        if r.get("time_limit_seconds", "") != ""
                        else None,
                    },
                )
                upserted += 1
        return Response({"upserted": upserted}, status=201)

class StageRandomRuleViewSet(viewsets.ModelViewSet):
    queryset = StageRandomRule.objects.select_related("stage", "stage__quiz").all()
    serializer_class = StageRandomRuleSerializer
    permission_classes = [IsAdmin]

class PaperView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, pk=quiz_id)
        stages = list(quiz.stages.all().order_by("order"))
        rotate = request.query_params.get("rotate", "day")
        seed = request.query_params.get("seed") or _seed(request, f"quiz:{quiz.id}", rotate)
        out = {"quiz": QuizSerializer(quiz).data, "seed": seed, "stages": []}
        for st in stages:
            st_shuffle_q = st.shuffle_questions if st.shuffle_questions is not None else quiz.shuffle_questions
            st_shuffle_o = st.shuffle_options if st.shuffle_options is not None else quiz.shuffle_options
            stage_qs = StageQuestion.objects.filter(stage=st).select_related("question").order_by("order")
            sq_items = list(stage_qs)
            if st_shuffle_q:
                sq_items.sort(key=lambda sq:
                              hashlib.sha256(f"{seed}:{st.id}:{sq.order}:{sq.question_id}".encode()).hexdigest())
            stage_payload = []
            for sq in sq_items:
                q = sq.question
                opts = list(q.options.all())
                if st_shuffle_o and opts:
                    opts.sort(key=lambda o: hashlib.sha256(f"{seed}:{q.id}:{o.id}".encode()).hexdigest())
                stage_payload.append({
                    "stage_question": StageQuestionSerializer(sq).data,
                    "question": QuestionSerializer(q).data,
                    "options": QuestionOptionSerializer(opts, many=True).data,
                })
            out["stages"].append({"stage": QuizStageSerializer(st).data, "items": stage_payload})
        return Response(out)

class AttemptStartView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    def post(self, request):
        quiz = get_object_or_404(Quiz, pk=request.data.get("quiz_id"))
        now = timezone.now()
        if not (quiz.start_at <= now <= quiz.end_at):
            raise ValidationError("Quiz window is closed or not started.")

        if quiz.prerequisite_tutorial_id:
            TutorialProgress = apps.get_model("learning", "TutorialProgress")
            ok = TutorialProgress.objects.filter(
                user=request.user, tutorial_id=quiz.prerequisite_tutorial_id, is_completed=True
            ).exists()
            if not ok:
                raise ValidationError("Please complete the required tutorial before starting the quiz.")

        with transaction.atomic():
            existing = _assert_single_attempt(quiz, request.user)
            if existing:
                raise ValidationError("You have already attempted this quiz.")
            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                user=request.user,
                start_ip=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                device_fingerprint=request.headers.get("X-Device-Fingerprint", ""),
            )
            total = 0.0
            for st in quiz.stages.all():
                for sq in StageQuestion.objects.filter(stage=st):
                    total += float(sq.effective_marks())
            attempt.total_marks = total
            attempt.save(update_fields=["total_marks", "start_ip", "user_agent", "device_fingerprint"])

        return Response({"attempt_id": str(attempt.id), "status": attempt.status}, status=200)

class StageAttemptStartView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    def post(self, request):
        attempt = get_object_or_404(QuizAttempt, pk=request.data.get("attempt_id"), user=request.user)
        stage = get_object_or_404(QuizStage, pk=request.data.get("stage_id"), quiz=attempt.quiz)
        if getattr(stage, "requires_admission", False):
            if not StageAdmission.objects.filter(stage=stage, user=request.user).exists():
                raise PermissionDenied("You are not admitted to this stage.")

        with transaction.atomic():
            sa, _ = QuizStageAttempt.objects.get_or_create(attempt=attempt, stage=stage)
            sa = QuizStageAttempt.objects.select_for_update().get(pk=sa.pk)
            if sa.submitted_at:
                raise ValidationError("This stage has already been submitted.")
            if sa.items.exists():
                return Response({"stage_attempt_id": str(sa.id)}, status=200)

            mapped = StageQuestion.objects.filter(stage=stage).select_related("question").order_by("order")
            if mapped.exists():
                bulk, order_no = [], 1
                for sq in mapped:
                    q = sq.question
                    bulk.append(StageAttemptItem(
                        stage_attempt=sa,
                        question=q,
                        order=order_no,
                        marks=float(sq.effective_marks()),
                        negative_marks=float(sq.effective_negative()),
                        time_limit_seconds=int(sq.effective_time()),
                    ))
                    order_no += 1
                StageAttemptItem.objects.bulk_create(bulk)
                return Response({"stage_attempt_id": str(sa.id)}, status=200)

            quotas = _stage_quota_from_quiz(attempt.quiz, stage)
            pool = _bank_for_stage(stage)
            chosen_ids = []
            for diff_key, diff_val in [("easy","easy"), ("medium","medium"), ("hard","hard")]:
                need = quotas[diff_key]
                if need <= 0:
                    continue
                diff_pool = list(pool.filter(difficulty=getattr(Difficulty, diff_val.upper()))
                                 .values_list("id", flat=True))
                if not diff_pool:
                    continue
                take = min(need, len(diff_pool))
                chosen_ids += _pick_consistent(diff_pool, take, request.user.id, stage.id, salt=str(attempt.id))

            stage_total = stage.question_count or attempt.quiz.question_count
            if len(chosen_ids) < stage_total:
                remaining = list(pool.exclude(id__in=chosen_ids).values_list("id", flat=True))
                extra = min(stage_total - len(chosen_ids), len(remaining))
                if extra > 0:
                    chosen_ids += _pick_consistent(remaining, extra, request.user.id, stage.id, salt=str(attempt.id)+":fill")

            ordered_ids = _pick_consistent(chosen_ids, len(chosen_ids), request.user.id, stage.id, salt=str(attempt.id)+":order")
            qs_map = Question.objects.in_bulk(ordered_ids)
            bulk, order_no = [], 1
            for qid in ordered_ids:
                q = qs_map[qid]
                bulk.append(StageAttemptItem(
                    stage_attempt=sa,
                    question=q,
                    order=order_no,
                    marks=float(q.marks),
                    negative_marks=float(q.negative_marks),
                    time_limit_seconds=int(q.time_limit_seconds),
                ))
                order_no += 1
            StageAttemptItem.objects.bulk_create(bulk)
        return Response({"stage_attempt_id": str(sa.id)}, status=200)

class StageAttemptPaperView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    def get(self, request, stage_attempt_id):
        sa = get_object_or_404(QuizStageAttempt, pk=stage_attempt_id, attempt__user=request.user)
        items = sa.items.select_related("question").order_by("order", "id")
        out = {"stage_attempt_id": str(sa.id), "stage": QuizStageSerializer(sa.stage).data, "items": []}
        for it in items:
            q = it.question
            opts = list(q.options.all())
            opts.sort(key=lambda o: _hash_int(f"{request.user.id}:{sa.stage.id}:{q.id}:{o.id}"))
            out["items"].append({
                "order": it.order,
                "marks": float(it.marks),
                "negative_marks": float(it.negative_marks),
                "time_limit_seconds": it.time_limit_seconds,
                "question": QuestionSerializer(q).data,
                "options": QuestionOptionSerializer(opts, many=True).data,
            })
        return Response(out)
    
class AttemptPaperView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    def get(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, pk=attempt_id, user=request.user)
        data = {"attempt_id": str(attempt.id), "quiz": QuizSerializer(attempt.quiz).data, "stages": []}
        for sa in attempt.stage_attempts.select_related("stage").all().order_by("stage__order"):
            sub = StageAttemptPaperView().get(request, sa.id).data
            data["stages"].append(sub)
        return Response(data)

class AnswerSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request):
        sa = get_object_or_404(
            QuizStageAttempt,
            pk=request.data.get("stage_attempt_id"),
            attempt__user=request.user,
        )
        attempt = sa.attempt
        if attempt.status != AttemptStatus.STARTED:
            raise ValidationError("Attempt is not active.")

        q = get_object_or_404(Question, pk=request.data.get("question_id"))
        sai = StageAttemptItem.objects.filter(stage_attempt=sa, question=q).first()
        if not sai:
            raise ValidationError("Question is not part of this stage attempt.")

        selected = None
        if request.data.get("selected_option"):
            selected = get_object_or_404(
                QuestionOption, pk=request.data["selected_option"], question=q
            )

        ans = AttemptAnswer(
            stage_attempt=sa,
            question=q,
            selected_option=selected,
            answer_text=request.data.get("answer_text", ""),
            answer_number=request.data.get("answer_number"),
            answer_bool=request.data.get("answer_bool"),
            time_spent_seconds=int(request.data.get("time_spent_seconds", 0) or 0),
        )

        marks = float(sai.marks)
        neg = float(sai.negative_marks) if sa.stage.is_negative_makring else 0.0  # ← gate
        correct = False
        awarded = 0.0

        if selected is not None:
            correct = bool(selected.is_correct)
            awarded = marks if correct else (-neg)

        elif q.question_type == QuestionType.TRUE_FALSE and request.data.get("answer_bool") is not None:
            awarded = 0.0

        ans.is_correct = correct
        ans.awarded_marks = awarded
        ans.save()

        # recompute stage totals
        agg = AttemptAnswer.objects.filter(stage_attempt=sa).aggregate(s=Sum("awarded_marks"))
        sa.obtained_marks = float(agg["s"] or 0.0)
        tot = sa.items.aggregate(s=Sum("marks"))["s"] or 0
        sa.total_marks = float(tot)
        sa.percent = (sa.obtained_marks / (sa.total_marks or 1.0)) * 100.0
        sa.save(update_fields=["obtained_marks", "total_marks", "percent"])

        # <- return the IDs you need
        return Response({
            "answer_id": str(ans.id),
            "stage_attempt_id": str(sa.id),
            "stage_id": str(sa.stage_id),
            "question_id": str(q.id),
            "selected_option": str(ans.selected_option_id) if ans.selected_option_id else None,
            "answer_text": ans.answer_text,
            "answer_number": ans.answer_number,
            "answer_bool": ans.answer_bool,
            "is_correct": bool(ans.is_correct),
            "awarded_marks": float(ans.awarded_marks),
            "time_spent_seconds": int(ans.time_spent_seconds or 0),
            "stage_totals": {
                "obtained": sa.obtained_marks,
                "total": sa.total_marks,
                "percent": sa.percent,
            },
        }, status=201)

class StageSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request):
        sa = get_object_or_404(
            QuizStageAttempt,
            pk=request.data.get("stage_attempt_id"),
            attempt__user=request.user,
        )

        # Optional: recompute aggregates at submit time (safe & helpful)
        agg = AttemptAnswer.objects.filter(stage_attempt=sa).aggregate(s=Sum("awarded_marks"))
        sa.obtained_marks = float(agg["s"] or 0.0)
        tot = sa.items.aggregate(s=Sum("marks"))["s"] or 0
        sa.total_marks = float(tot)
        sa.percent = (sa.obtained_marks / (sa.total_marks or 1.0)) * 100.0

        already_submitted = bool(sa.submitted_at)
        if not already_submitted:
            sa.mark_submitted()
        sa.save(update_fields=["submitted_at", "time_taken_seconds", "obtained_marks", "total_marks", "percent"])

        # Upsert stage leaderboard row
        LeaderboardEntry.objects.update_or_create(
            quiz=sa.attempt.quiz,
            quiz_stage=sa.stage,
            user=sa.attempt.user,
            defaults=dict(
                zone=getattr(sa.attempt.user, "zone", ""),
                subspecialty=sa.attempt.quiz.subspecialty or "",
                percent=sa.percent,
                obtained_marks=sa.obtained_marks,
                total_marks=sa.total_marks,
                time_taken_seconds=sa.time_taken_seconds,
            ),
        )

        # Always include IDs (even if not sent in request)
        return Response({
            "submitted": True,
            "already_submitted": already_submitted,
            "stage_attempt_id": str(sa.id),
            "stage_id": str(sa.stage_id),           # ← here you go
            "attempt_id": str(sa.attempt_id),
            "quiz_id": str(sa.attempt.quiz_id),
            "stage_percent": float(sa.percent),
            "obtained_marks": float(sa.obtained_marks),
            "total_marks": float(sa.total_marks),
            "time_taken_seconds": sa.time_taken_seconds,
        }, status=200)

class AttemptSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    def post(self, request):
        attempt = get_object_or_404(QuizAttempt, pk=request.data.get("attempt_id"), user=request.user)
        if attempt.status != AttemptStatus.STARTED:
            raise ValidationError("Attempt is not active.")
        staggs = attempt.stage_attempts.aggregate(total=Sum("total_marks"), obtained=Sum("obtained_marks"))
        attempt.total_marks = float(staggs["total"] or attempt.total_marks)
        attempt.obtained_marks = float(staggs["obtained"] or 0)
        attempt.percent = (attempt.obtained_marks / (attempt.total_marks or 1.0)) * 100.0
        attempt.mark_submitted()
        attempt.compute_pass()
        attempt.save(update_fields=[
            "submitted_at", "time_taken_seconds", "status",
            "total_marks", "obtained_marks", "percent", "is_passed",
        ])

        zone_val = getattr(getattr(request.user, "participant", None), "zone", "") or getattr(request.user, "zone", "")
        LeaderboardEntry.objects.update_or_create(
            quiz=attempt.quiz,
            quiz_stage=None,
            user=request.user,
            defaults=dict(
                zone=zone_val,
                subspecialty=attempt.quiz.subspecialty or "",
                percent=attempt.percent,
                obtained_marks=attempt.obtained_marks,
                total_marks=attempt.total_marks,
                time_taken_seconds=attempt.time_taken_seconds,
            ),
        )
        return Response({"submitted": True, "is_passed": attempt.is_passed, "percent": attempt.percent}, status=200)

class LeaderboardZoneTopsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, quiz_id):
        try:
            limit = int(request.query_params.get("limit", 5))
            limit = max(1, min(50, limit))
        except Exception:
            limit = 5

        by = (request.query_params.get("by") or "zone").lower()  # "zone" | "state"
        group_field = F("zone") if by == "zone" else F("user__state")
        group_label = "zone" if by == "zone" else "state"

        cheat_count_subq = (
            AntiCheatEventLog.objects
            .filter(attempt__quiz_id=OuterRef("quiz_id"), attempt__user_id=OuterRef("user_id"))
            .values("attempt__user_id").annotate(c=Count("id")).values("c")[:1]
        )

        qs = (LeaderboardEntry.objects
              .filter(quiz_id=quiz_id)
              .annotate(cheat_count=Coalesce(Subquery(cheat_count_subq), 0))
              .annotate(group_rank=Window(
                  expression=Rank(),
                  partition_by=[group_field],
                  order_by=[
                      F("percent").desc(),
                      F("time_taken_seconds").asc(),
                      F("cheat_count").asc(),
                      F("user_id").asc(),
                  ],
              ))
              .filter(group_rank__lte=limit)
              .select_related("user")
              .order_by(group_field.asc(), "group_rank"))

        data = [{
            group_label: (row.zone if by == "zone" else getattr(row.user, "state", None)),
            "rank": int(row.group_rank),
            "user_id": row.user_id,
            "username": row.user.username,
            "zone": row.zone,
            "state": getattr(row.user, "state", None),
            "percent": float(row.percent),
            "obtained": float(row.obtained_marks),
            "total": float(row.total_marks),
            "time_taken_seconds": row.time_taken_seconds,
            "cheat_events": int(row.cheat_count or 0),
        } for row in qs]

        return Response({"by": by.upper(), "limit_per_group": limit, "results": data}, status=status.HTTP_200_OK)


class LeaderboardTopView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, quiz_id):
        # ---- params ---------------------------------------------------------
        group_by = (request.query_params.get("group_by") or "zone").strip().lower()  # zone|state|overall
        try:
            limit = int(request.query_params.get("limit", 5))
            limit = max(1, min(50, limit))
        except Exception:
            limit = 5

        def _csv(qp_key):
            raw = request.query_params.get(qp_key) or ""
            if not raw:
                return []
            return [x.strip().upper() for x in raw.split(",") if x.strip()]

        zones_filter  = _csv("zones")   # e.g. ?zones=NORTH,WEST
        states_filter = _csv("states")  # e.g. ?states=MAHARASHTRA,DELHI

        # ---- base queryset --------------------------------------------------
        base = (LeaderboardEntry.objects
                .filter(quiz_id=quiz_id)
                .select_related("user"))

        if zones_filter:
            base = base.filter(zone__in=zones_filter)
        if states_filter:
            base = base.filter(user__state__in=states_filter)

        # anti-cheat *count* (kept as before; no disqualification messaging)
        cheat_count_subq = (
            AntiCheatEventLog.objects
            .filter(attempt__quiz_id=OuterRef("quiz_id"), attempt__user_id=OuterRef("user_id"))
            .values("attempt__user_id").annotate(c=Count("id")).values("c")[:1]
        )

        order_cols = [
            F("percent").desc(),
            F("time_taken_seconds").asc(),
            F("cheat_count").asc(),
            F("user_id").asc(),
        ]

        # ---- group by STATE (top-N per state) ------------------------------
        if group_by == "state":
            qs = (base
                  .annotate(cheat_count=Coalesce(Subquery(cheat_count_subq), 0))
                  .annotate(state=F("user__state"))
                  .annotate(state_rank=Window(
                      expression=Rank(),
                      partition_by=[F("state")],
                      order_by=order_cols,
                  ))
                  .filter(state_rank__lte=limit)
                  .order_by("state", "state_rank"))

            data = [{
                "state": row.state or "",
                "zone": row.zone or "",
                "rank": int(row.state_rank),
                "user_id": row.user_id,
                "username": row.user.username,
                "percent": float(row.percent),
                "obtained": float(row.obtained_marks),
                "total": float(row.total_marks),
                "time_taken_seconds": row.time_taken_seconds,
                "cheat_events": int(row.cheat_count or 0),
            } for row in qs]

            return Response({
                "group_by": "state",
                "limit_per_state": limit,
                "filters": {"states": states_filter or "ALL", "zones": zones_filter or "ALL"},
                "results": data,
            }, status=status.HTTP_200_OK)

        # ---- OVERALL (single top-N across everyone) ------------------------
        if group_by == "overall":
            qs = (base
                  .annotate(cheat_count=Coalesce(Subquery(cheat_count_subq), 0))
                  .annotate(state=F("user__state"))
                  .order_by(*order_cols)[:limit])

            data = [{
                "rank": idx + 1,
                "user_id": row.user_id,
                "username": row.user.username,
                "zone": row.zone or "",
                "state": row.state or "",
                "percent": float(row.percent),
                "obtained": float(row.obtained_marks),
                "total": float(row.total_marks),
                "time_taken_seconds": row.time_taken_seconds,
                "cheat_events": int(row.cheat_count or 0),
            } for idx, row in enumerate(qs)]

            return Response({
                "group_by": "overall",
                "limit": limit,
                "filters": {"states": states_filter or "ALL", "zones": zones_filter or "ALL"},
                "results": data,
            }, status=status.HTTP_200_OK)

        # ---- default: ZONE (top-N per zone) --------------------------------
        qs = (base
              .annotate(cheat_count=Coalesce(Subquery(cheat_count_subq), 0))
              .annotate(zone_rank=Window(
                  expression=Rank(),
                  partition_by=[F("zone")],
                  order_by=order_cols,
              ))
              .annotate(state=F("user__state"))
              .filter(zone_rank__lte=limit)
              .order_by("zone", "zone_rank"))

        data = [{
            "zone": row.zone or "",
            "state": row.state or "",
            "rank": int(row.zone_rank),
            "user_id": row.user_id,
            "username": row.user.username,
            "percent": float(row.percent),
            "obtained": float(row.obtained_marks),
            "total": float(row.total_marks),
            "time_taken_seconds": row.time_taken_seconds,
            "cheat_events": int(row.cheat_count or 0),
        } for row in qs]

        return Response({
            "group_by": "zone",
            "limit_per_zone": limit,
            "filters": {"states": states_filter or "ALL", "zones": zones_filter or "ALL"},
            "results": data,
        }, status=status.HTTP_200_OK)



class StartQuizAndFetchView(APIView):
    """
    One-click 'Start Quiz' + fetch paginated questions for the CURRENT stage.
    Flow:
      - find current stage (fallback first)
      - check quiz window, tutorial (if any)
      - check stage window (stage.start_at/end_at or falls back to quiz window)
      - if stage.requires_admission, enforce StageAdmission
      - create/get QuizAttempt + QuizStageAttempt
      - build unique paper (manual mapping or random quotas)
      - return paginated items (no `is_correct`), shuffled as configured
      - when last page reached, `is_last_page=true`; if page > last, return `done=true`
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request):
        quiz_id = request.data.get("quiz_id")
        if not quiz_id:
            raise ValidationError("quiz_id is required.")

        # pagination
        page = max(1, int(request.data.get("page", 1) or 1))
        page_size = max(1, min(50, int(request.data.get("page_size", 1) or 1)))
        rotate = request.data.get("rotate", "day")

        quiz = get_object_or_404(Quiz, pk=quiz_id)
        now = timezone.now()

        # ---- quiz window
        if not (quiz.start_at <= now <= quiz.end_at):
            raise ValidationError("Quiz window is closed or not started.")

        # ---- tutorial gate (if set)
        if quiz.prerequisite_tutorial_id:
            TutorialProgress = apps.get_model("learning", "TutorialProgress")
            ok = TutorialProgress.objects.filter(
                user=request.user,
                tutorial_id=quiz.prerequisite_tutorial_id,
                is_completed=True
            ).exists()
            if not ok:
                raise ValidationError("Please complete the required tutorial before starting the quiz.")

        # ---- get current stage (fallback first stage)
        stage = quiz.stages.filter(is_current=True).order_by("order").first() or \
                quiz.stages.order_by("order").first()
        if not stage:
            raise ValidationError("No stages configured for this quiz.")

        # ---- stage-level window (fallback to quiz window)
        st_start = stage.start_at or quiz.start_at
        st_end   = stage.end_at   or quiz.end_at
        if not (st_start <= now <= st_end):
            raise ValidationError("Stage window is closed or not started.")

        if stage.requires_admission:
            if not StageAdmission.objects.filter(stage=stage, user=request.user).exists():
                raise PermissionDenied("You are not admitted to this stage.")

        attempt, created_attempt = QuizAttempt.objects.get_or_create(quiz=quiz, user=request.user)
        if not created_attempt and attempt.status != AttemptStatus.STARTED:
            raise ValidationError("Attempt already completed or unavailable.")

        sa, _ = QuizStageAttempt.objects.get_or_create(attempt=attempt, stage=stage)
        if sa.submitted_at:
            return Response({
                "attempt_id": str(attempt.id),
                "stage_attempt_id": str(sa.id),
                "submitted": True,
                "detail": "This stage has already been submitted."
            })

        # ---- build items once (manual mapping OR random rule with quotas)
        if not sa.items.exists():
            st_shuffle_q = stage.shuffle_questions if stage.shuffle_questions is not None else quiz.shuffle_questions

            mapped = list(
                StageQuestion.objects.filter(stage=stage).select_related("question").order_by("order")
            )
            if mapped:
                if st_shuffle_q:
                    seed = _seed(request, f"stage:{stage.id}", rotate)
                    mapped.sort(
                        key=lambda sq: hashlib.sha256(
                            f"{seed}:{sa.id}:{sq.order}:{sq.question_id}".encode("utf-8")
                        ).hexdigest()
                    )
                bulk, order_no = [], 1
                for sq in mapped:
                    q = sq.question
                    bulk.append(StageAttemptItem(
                        stage_attempt=sa,
                        question=q,
                        order=order_no,
                        marks=float(sq.effective_marks()),
                        negative_marks=float(sq.effective_negative()),
                        time_limit_seconds=int(sq.effective_time()),
                    ))
                    order_no += 1
                StageAttemptItem.objects.bulk_create(bulk)
            else:
                quotas = _stage_quota_from_quiz(quiz, stage)
                pool = _bank_for_stage(stage)

                chosen_ids = []
                for dk, dv in [("easy","easy"), ("medium","medium"), ("hard","hard")]:
                    need = quotas[dk]
                    if need <= 0:
                        continue
                    diff_pool = list(
                        pool.filter(difficulty=getattr(Difficulty, dv.upper()))
                            .values_list("id", flat=True)
                    )
                    if not diff_pool:
                        continue
                    take = min(need, len(diff_pool))
                    chosen_ids += _pick_consistent(
                        diff_pool, take, request.user.id, stage.id, salt=str(attempt.id)
                    )

                stage_total = stage.question_count or quiz.question_count
                if len(chosen_ids) < stage_total:
                    remaining = list(pool.exclude(id__in=chosen_ids).values_list("id", flat=True))
                    extra = min(stage_total - len(chosen_ids), len(remaining))
                    if extra > 0:
                        chosen_ids += _pick_consistent(
                            remaining, extra, request.user.id, stage.id, salt=str(attempt.id)+":fill"
                        )

                ordered_ids = _pick_consistent(
                    chosen_ids, len(chosen_ids), request.user.id, stage.id, salt=str(attempt.id)+":order"
                )

                qs_map = Question.objects.in_bulk(ordered_ids)
                bulk, order_no = [], 1
                for qid in ordered_ids:
                    q = qs_map[qid]
                    bulk.append(StageAttemptItem(
                        stage_attempt=sa,
                        question=q,
                        order=order_no,
                        marks=float(q.marks),
                        negative_marks=float(q.negative_marks),
                        time_limit_seconds=int(q.time_limit_seconds),
                    ))
                    order_no += 1
                StageAttemptItem.objects.bulk_create(bulk)

            # initialize total marks & attempt metadata (first time)
            if created_attempt or float(attempt.total_marks or 0) == 0:
                total_marks_all = 0.0
                for st in quiz.stages.all():
                    st_items = StageAttemptItem.objects.filter(
                        stage_attempt__attempt=attempt, stage_attempt__stage=st
                    )
                    if st_items.exists():
                        total_marks_all += float(st_items.aggregate(s=Sum("marks"))["s"] or 0)
                attempt.total_marks = total_marks_all
                attempt.start_ip = _client_ip(request)
                attempt.user_agent = request.META.get("HTTP_USER_AGENT", "")
                attempt.device_fingerprint = request.headers.get("X-Device-Fingerprint", "")
                attempt.save(update_fields=["total_marks", "start_ip", "user_agent", "device_fingerprint"])

        # ---- serve paginated questions (redact is_correct)
        st_shuffle_o = stage.shuffle_options if stage.shuffle_options is not None else quiz.shuffle_options
        seed_opts = _seed(request, f"opts:{stage.id}", rotate)

        total = sa.items.count()
        total_pages = max(1, ceil(total / page_size))
        if page > total_pages:
            return Response({
                "attempt_id": str(attempt.id),
                "stage_attempt_id": str(sa.id),
                "pagination": {
                    "page": page, "page_size": page_size,
                    "total_items": total, "total_pages": total_pages,
                    "is_last_page": True
                },
                "done": True,
                "message": "Last question already served. Submit/close this stage now."
            })

        offset = (page - 1) * page_size
        items = list(
            sa.items.select_related("question")
            .order_by("order","id")[offset: offset+page_size]
        )

        def _safe_option_list(q):
            opts = list(q.options.all())
            if st_shuffle_o:
                opts.sort(key=lambda o: hashlib.sha256(
                    f"{seed_opts}:{request.user.id}:{stage.id}:{q.id}:{o.id}".encode("utf-8")
                ).hexdigest())
            else:
                opts.sort(key=lambda o: (o.order, o.id))
            return [{"id": str(o.id), "text": o.text, "order": o.order} for o in opts]

        payload = []
        for it in items:
            q = it.question
            payload.append({
                "order": it.order,
                "marks": float(it.marks),
                "negative_marks": float(it.negative_marks),
                "time_limit_seconds": it.time_limit_seconds,
                "question": {
                    "id": str(q.id),
                    "text": q.text,
                    "explanation": q.explanation,         # keep/remove as you prefer
                    "question_type": q.question_type,
                    "time_limit_seconds": q.time_limit_seconds,
                },
                "options": _safe_option_list(q),          # NO is_correct anywhere
            })

        return Response({
            "attempt_id": str(attempt.id),
            "stage": QuizStageSerializer(stage).data,
            "stage_attempt_id": str(sa.id),
            "pagination": {
                "page": page, "page_size": page_size,
                "total_items": total, "total_pages": total_pages,
                "is_last_page": page >= total_pages
            },
            "items": payload,
            "hint": "If is_last_page is true and user submits, call /api/stage/submit/ (then /api/attempts/submit/ when all stages done)."
        })

class MyStageAnswersView(APIView):
    """
    GET /api/stages/<uuid:stage_id>/my-answers/

    Returns all questions in the stage attempt (for the requesting user) with:
      - question, options (with is_correct), correct_option_ids
      - given_option_ids / given_text / given_number / given_bool
      - per-question time_spent_seconds (sum across rows)
      - awarded_marks, is_correct
      - stage totals (time + marks)
    If attempt/stage attempt not found, returns a 200 with attempt_given/stage_attempt_given flags.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request, stage_id):
        from collections import defaultdict

        # stage must exist
        stage = get_object_or_404(QuizStage, pk=stage_id)

        # the user must have an attempt for this quiz
        attempt = QuizAttempt.objects.filter(quiz=stage.quiz, user=request.user).first()
        if not attempt:
            # Attempt not given
            return Response({
                "attempt_given": False,
                "stage_attempt_given": False,
                "attempt_id": None,
                "stage_attempt_id": None,
                "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order},
                "totals": {
                    "questions": 0,
                    "awarded_marks": 0.0,
                    "stage_obtained_marks": 0.0,
                    "stage_total_marks": 0.0,
                    "stage_percent": 0.0,
                    "time_spent_seconds_sum": 0,
                    "time_taken_seconds_stage": 0,
                    "submitted_at": None,
                },
                "items": [],
                "detail": "Attempt not given.",
            }, status=200)

        sa = QuizStageAttempt.objects.filter(attempt=attempt, stage=stage).first()
        if not sa:
            return Response({
                "attempt_given": True,
                "stage_attempt_given": False,
                "attempt_id": str(attempt.id),
                "stage_attempt_id": None,
                "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order},
                "totals": {
                    "questions": 0,
                    "awarded_marks": 0.0,
                    "stage_obtained_marks": 0.0,
                    "stage_total_marks": 0.0,
                    "stage_percent": 0.0,
                    "time_spent_seconds_sum": 0,
                    "time_taken_seconds_stage": 0,
                    "submitted_at": None,
                },
                "items": [],
                "detail": "Stage attempt not started.",
            }, status=200)

        # (optional gate) only allow review after submit/results:
        if not sa.submitted_at and not stage.quiz.results_visible_after_close:
            return Response({
                "attempt_given": True,
                "stage_attempt_given": True,
                "attempt_id": str(attempt.id),
                "stage_attempt_id": str(sa.id),
                "locked": True,
                "detail": "Answers review is not available until submission or results are published."
            }, status=200)

        # fetch stage items with their questions & options
        items = (
            StageAttemptItem.objects
            .filter(stage_attempt=sa)
            .select_related("question")
            .prefetch_related("question__options")
            .order_by("order", "id")
        )

        # fetch all answers for this stage attempt (group them by question)
        answers = (
            AttemptAnswer.objects
            .filter(stage_attempt=sa)
            .select_related("selected_option", "question")
            .order_by("id")
        )
        by_qid = defaultdict(list)
        for a in answers:
            by_qid[str(a.question_id)].append(a)

        payload_items = []
        total_awarded = 0.0
        total_time_spent = 0

        for it in items:
            q = it.question
            qid = str(q.id)

            # options including correctness (post-exam review)
            opts_qs = list(q.options.all().order_by("order", "id").values("id", "text", "is_correct"))
            options = [{"id": str(o["id"]), "text": o["text"], "is_correct": bool(o["is_correct"])} for o in opts_qs]
            correct_ids = [str(o["id"]) for o in opts_qs if o["is_correct"]]

            # user rows for this question
            rows = by_qid.get(qid, [])

            given_option_ids = [str(r.selected_option_id) for r in rows if r.selected_option_id]
            given_text   = (rows[0].answer_text   if rows and rows[0].answer_text   else "")
            given_number = (rows[0].answer_number if rows and rows[0].answer_number is not None else None)
            given_bool   = (rows[0].answer_bool   if rows and rows[0].answer_bool   is not None else None)

            q_awarded    = float(sum([r.awarded_marks for r in rows]) or 0.0)
            q_is_correct = bool(rows[0].is_correct) if rows else False
            q_time_spent = int(sum([int(r.time_spent_seconds or 0) for r in rows]) or 0)

            total_awarded += q_awarded
            total_time_spent += q_time_spent

            payload_items.append({
                "order": it.order,
                "marks": float(it.marks),
                "negative_marks": float(it.negative_marks),
                "time_limit_seconds": int(it.time_limit_seconds),
                "question": {
                    "id": qid,
                    "text": q.text,
                    "question_type": q.question_type,
                },
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
            "attempt_given": True,
            "stage_attempt_given": True,
            "attempt_id": str(attempt.id),
            "stage_attempt_id": str(sa.id),
            "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order},
            "totals": {
                "questions": len(payload_items),
                "awarded_marks": float(total_awarded),
                "stage_obtained_marks": float(sa.obtained_marks),
                "stage_total_marks": float(sa.total_marks),
                "stage_percent": float(sa.percent),
                "time_spent_seconds_sum": int(total_time_spent),
                "time_taken_seconds_stage": int(sa.time_taken_seconds or 0),
                "submitted_at": sa.submitted_at,
            },
            "items": payload_items,
        }, status=200)

def _stage_qcount(stage: QuizStage, quiz: Quiz) -> int:
    """
    Prefer explicit stage.question_count → else quiz.question_count → else mapped questions count.
    Used only for 'avg_seconds_per_question' display metric.
    """
    return (stage.question_count or quiz.question_count or stage.stage_questions.count() or 1)

class StageLeaderboardView(APIView):
    """
    GET
      /api/leaderboard/stage/
      /api/leaderboard/stage/<uuid:stage_id>/

    Query:
      - quiz_id=<uuid>           (optional)
      - stage_id=<uuid>          (optional)
      - limit=<int>              (default: 100 if requires_admission, else 5)
      - by=zone|state|overall    (default: zone)
      - zones=Z1,Z2              (optional filter)
      - states=S1,S2             (optional filter)
    """
    permission_classes = [permissions.AllowAny]

    def _resolve_stage(self, request, stage_id):
        qid = request.query_params.get("quiz_id")
        sid = stage_id or request.query_params.get("stage_id")

        if sid:
            stage = get_object_or_404(QuizStage, pk=sid)
            return stage.quiz, stage

        if qid:
            quiz = get_object_or_404(Quiz, pk=qid)
            stage = (
                quiz.stages.filter(is_current=True).order_by("order").first()
                or quiz.stages.order_by("order").first()
            )
            if not stage:
                raise ValidationError("No stages configured for the selected quiz.")
            return quiz, stage

        active = list(Quiz.objects.filter(is_active=True))
        if not active:
            raise ValidationError("No active quiz.")
        if len(active) > 1:
            raise ValidationError("Multiple active quizzes found; only one quiz may be active at a time.")

        quiz = active[0]
        stage = (
            quiz.stages.filter(is_current=True).order_by("order").first()
            or quiz.stages.order_by("order").first()
        )
        if not stage:
            raise ValidationError("No stages configured for the active quiz.")
        return quiz, stage

    def get(self, request, stage_id=None):
        quiz, stage = self._resolve_stage(request, stage_id)
        qcount = _stage_qcount(stage, quiz)

        now = timezone.now()
        provisional = (stage.end_at is None) or (now < stage.end_at)
        finalized = bool(stage.end_at and now >= stage.end_at)

        default_limit = 100 if stage.requires_admission else 5
        try:
            limit = int(request.query_params.get("limit", default_limit))
            limit = max(1, min(1000, limit))
        except Exception:
            limit = default_limit

        by = (request.query_params.get("by") or "zone").strip().lower()  # zone|state|overall

        # filters
        def _csv(key):
            raw = (request.query_params.get(key) or "").strip()
            return [x.strip().upper() for x in raw.split(",") if x.strip()] if raw else []

        zones_filter  = _csv("zones")    # ?zones=NORTH,WEST
        states_filter = _csv("states")   # ?states=MAHARASHTRA,DELHI

        cheat_count_subq = (
            AntiCheatEventLog.objects
            .filter(
                attempt__quiz_id=OuterRef("quiz_id"),
                attempt__user_id=OuterRef("user_id"),
            )
            .values("attempt__user_id")
            .annotate(c=Count("id"))
            .values("c")[:1]
        )

        base = (
            LeaderboardEntry.objects
            .filter(quiz_id=quiz.id, quiz_stage_id=stage.id)
            .select_related("user")
        )
        if zones_filter:
            base = base.filter(zone__in=zones_filter)
        if states_filter:
            base = base.filter(user__state__in=states_filter)

        order_cols = [
            F("percent").desc(),
            F("time_taken_seconds").asc(),
            F("cheat_count").asc(),
            F("user_id").asc(),
        ]

        header = {
            "quiz": {"id": str(quiz.id), "title": quiz.title},
            "stage": {
                "id": str(stage.id),
                "title": stage.title,
                "order": stage.order,
                "start_at": stage.start_at,
                "end_at": stage.end_at,
            },
            "computed_at": now,
            "provisional": provisional,
            "finalized": finalized,
            "note": (
                ("Provisional leaderboard — will be finalized after the stage closes at "
                 f"{stage.end_at}.")
                if provisional and stage.end_at
                else ("Provisional leaderboard — live and may change until the stage is closed."
                      if provisional else "Final results.")
            ),
            "group_by": by.upper(),
            "filters": {"zones": zones_filter or "ALL", "states": states_filter or "ALL"},
            "rank_order": [
                "percent DESC",
                "time_taken_seconds ASC",
                "cheat_events ASC",
                "user_id ASC",
            ],
        }

        # OVERALL list (either explicitly requested or when gate is on)
        if stage.requires_admission or by == "overall":
            qs = (
                base
                .annotate(cheat_count=Coalesce(Subquery(cheat_count_subq), 0))
                .annotate(state=F("user__state"))
                .order_by(*order_cols)[:limit]
            )
            results = [{
                "rank": idx + 1,
                "user_id": row.user_id,
                "username": row.user.username,
                "zone": row.zone or "",
                "state": row.state or "",
                "percent": float(row.percent),
                "obtained": float(row.obtained_marks),
                "total": float(row.total_marks),
                "time_taken_seconds": row.time_taken_seconds,
                "avg_seconds_per_question": round((row.time_taken_seconds or 0) / float(qcount), 2),
                "cheat_events": int(row.cheat_count or 0),
            } for idx, row in enumerate(qs)]

            return Response({
                **header,
                "requires_admission": bool(stage.requires_admission),
                "mode": "overall",
                "limit": limit,
                "results": results,
            }, status=status.HTTP_200_OK)

        # group tops (zone or state)
        group_field = F("zone") if by == "zone" else F("user__state")
        group_label = "zone" if by == "zone" else "state"

        qs = (
            base
            .annotate(cheat_count=Coalesce(Subquery(cheat_count_subq), 0))
            .annotate(group_rank=Window(
                expression=Rank(),
                partition_by=[group_field],
                order_by=order_cols,
            ))
            .filter(group_rank__lte=limit)
            .annotate(state=F("user__state"))
            .order_by(group_field.asc(), "group_rank")
        )

        results = [{
            group_label: (row.zone if by == "zone" else (row.state or "")),
            "rank": int(row.group_rank),
            "user_id": row.user_id,
            "username": row.user.username,
            "zone": row.zone or "",
            "state": row.state or "",
            "percent": float(row.percent),
            "obtained": float(row.obtained_marks),
            "total": float(row.total_marks),
            "time_taken_seconds": row.time_taken_seconds,
            "avg_seconds_per_question": round((row.time_taken_seconds or 0) / float(qcount), 2),
            "cheat_events": int(row.cheat_count or 0),
        } for row in qs]

        return Response({
            **header,
            "requires_admission": False,
            "mode": ("zone_tops" if by == "zone" else "state_tops"),
            "limit_per_group": limit,
            "results": results,
        }, status=status.HTTP_200_OK)



# exams/views.py
from decimal import Decimal
from django.db import transaction
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from exams.models import Question, QuestionOption
from exams.serializers import QuestionBulkInSerializer
from common.enums import QuestionType, Difficulty  # adjust if needed

from accounts.permissions import IsAdminOrTeacher  # or your own admin-only guard

class BulkQuestionCreateAPIView(APIView):
    """
    POST /api/questions/bulk/
    Body: [ {question payload with options}, ... ]  (array)

    Creates questions + their options in bulk (fast), with validation:
      - SINGLE_CHOICE => exactly one correct option
      - MULTI_CHOICE  => at least one correct option
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrTeacher]

    def post(self, request):
        if not isinstance(request.data, list):
            return Response({"detail": "Expected a JSON array of questions."}, status=400)
        if len(request.data) == 0:
            return Response({"detail": "Array is empty."}, status=400)
        if len(request.data) > 1000:
            return Response({"detail": "Too many items. Max 1000 per request."}, status=413)

        ser = QuestionBulkInSerializer(data=request.data, many=True)
        ser.is_valid(raise_exception=True)
        items = ser.validated_data

        questions = []
        for item in items:
            questions.append(Question(
                text=item["text"].strip(),
                explanation=item.get("explanation", "") or "",
                question_type=item.get("question_type", QuestionType.SINGLE_CHOICE),
                time_limit_seconds=item.get("time_limit_seconds", 120),
                subspecialty=item.get("subspecialty", "") or "",
                difficulty=item.get("difficulty", Difficulty.MEDIUM),
                region_hint=item.get("region_hint", "") or "",
                marks=item.get("marks", Decimal("1.00")),
                negative_marks=item.get("negative_marks", Decimal("0.00")),
                is_active=item.get("is_active", True),
                tags=item.get("tags", {}) or {},
            ))

        with transaction.atomic():
            Question.objects.bulk_create(questions)

            options_to_create = []
            # zip relies on preserved order: created `questions` aligns with `items`
            for q_obj, item in zip(questions, items):
                opts = item.get("options", [])
                for idx, o in enumerate(opts):
                    options_to_create.append(QuestionOption(
                        question=q_obj,
                        text=o["text"].strip(),
                        is_correct=bool(o.get("is_correct", False)),
                        order=o.get("order", idx),
                    ))

            if options_to_create:
                QuestionOption.objects.bulk_create(options_to_create)

        return Response(
            {
                "created_questions": len(questions),
                "created_options": len(options_to_create),
                "question_ids": [q.id for q in questions],
            },
            status=status.HTTP_201_CREATED,
        )



# --- add (or keep) these imports at the top of the file ---
from django.db import transaction
from django.db.models import F, Window, Q, Count
from django.db.models.functions import Rank
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from accounts.models import User
from exams.models import Quiz, QuizStage, LeaderboardEntry, StageAdmission
# -----------------------------------------------------------


class StageAdmissionSelectTopsView(APIView):
    """
    POST /api/stages/<uuid:stage_id>/admissions/select-tops/

    Body:
    {
      "count": 5,                        // >0; required if selecting from leaderboard
      "by": "zone" | "state",            // default "zone"
      "per_zone": true,                  // when by=zone (group top-N per zone)
      "per_state": true,                 // when by=state (group top-N per state)
      "zones": ["NORTH","WEST"],         // optional filter if by=zone
      "states": ["MAHARASHTRA","UP"],    // optional filter if by=state
      "source_stage_id": "<uuid>",       // optional; else uses previous stage

      "extra_user_ids": ["...","..."],   // manual additions (legacy)
      "user_ids": ["...","..."]          // explicit manual list (can be used alone)
    }
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser | IsAdminOrTeacher]

    def post(self, request, stage_id):
        target_stage: QuizStage = get_object_or_404(QuizStage, pk=stage_id)
        quiz: Quiz = target_stage.quiz

        count = request.data.get("count")
        by = (request.data.get("by") or "zone").lower()  # "zone" | "state"
        if by not in ("zone", "state"):
            raise ValidationError("'by' must be 'zone' or 'state'.")

        group_field_name = "zone" if by == "zone" else "user__state"

        per_group = bool(request.data.get("per_zone" if by == "zone" else "per_state", False))
        groups = request.data.get("zones") if by == "zone" else request.data.get("states")
        src_stage_id = request.data.get("source_stage_id")

        extra_user_ids = request.data.get("extra_user_ids") or []
        manual_user_ids = request.data.get("user_ids") or []

        if groups is not None and not isinstance(groups, (list, tuple)):
            raise ValidationError(f"'{ 'zones' if by=='zone' else 'states' }' must be an array when provided.")
        if not isinstance(extra_user_ids, (list, tuple)):
            raise ValidationError("'extra_user_ids' must be an array when provided.")
        if not isinstance(manual_user_ids, (list, tuple)):
            raise ValidationError("'user_ids' must be an array when provided.")

        using_leaderboard = count is not None
        if not using_leaderboard and not extra_user_ids and not manual_user_ids:
            raise ValidationError("Provide 'count' for leaderboard selection or 'user_ids' / 'extra_user_ids'.")

        source_stage = None
        if using_leaderboard:
            try:
                count = int(count)
            except Exception:
                raise ValidationError("Provide 'count' as a positive integer.")
            if count <= 0:
                raise ValidationError("'count' must be > 0.")

            if src_stage_id:
                source_stage = get_object_or_404(QuizStage, pk=src_stage_id)
                if source_stage.quiz_id != quiz.id:
                    raise ValidationError("source_stage_id must belong to the same quiz as the target stage.")
            else:
                source_stage = (
                    quiz.stages.filter(order__lt=target_stage.order)
                    .order_by("-order")
                    .first()
                )
                if not source_stage:
                    raise ValidationError("No previous stage exists; specify 'source_stage_id' or use 'user_ids' only.")

        # ----- Build selection from leaderboard (optional) -----
        from_tops = []
        if using_leaderboard:
            base = LeaderboardEntry.objects.filter(
                quiz_id=quiz.id,
                quiz_stage_id=source_stage.id,
            )
            if groups:
                if by == "zone":
                    base = base.filter(zone__in=groups)
                else:
                    base = base.filter(user__state__in=groups)

            order_cols = [F("percent").desc(), F("time_taken_seconds").asc(), F("user_id").asc()]

            if per_group:
                ranked = (
                    base.annotate(group_rank=Window(
                        expression=Rank(),
                        partition_by=[F(group_field_name)],
                        order_by=order_cols,
                    ))
                    .filter(group_rank__lte=count)
                    .values_list("user_id", flat=True)
                )
                # keep native UUID/int type
                from_tops = list(ranked)
            else:
                ranked = base.order_by(*order_cols).values_list("user_id", flat=True)[:count]
                from_tops = list(ranked)  # native type

        # ----- Validate & combine manual lists (keep native ID type) -----
        def _valid_ids(ids):
            """
            Returns (valid_ids_native, invalid_ids_as_str).
            If `ids` are strings, Django will coerce them when filtering; we then
            return the found IDs in their native type so later comparisons are correct.
            """
            if not ids:
                return [], []
            found_native = list(User.objects.filter(id__in=ids).values_list("id", flat=True))
            found_str = {str(u) for u in found_native}
            invalid = [str(x) for x in ids if str(x) not in found_str]
            return found_native, invalid

        extra_valid, extra_invalid = _valid_ids(extra_user_ids)
        manual_valid, manual_invalid = _valid_ids(manual_user_ids)

        # Combined (dedup) — all in native type now
        combined = list(from_tops) + list(extra_valid) + list(manual_valid)
        final_user_ids = list(dict.fromkeys(combined))  # preserves order & dedups

        if not final_user_ids and (extra_invalid or manual_invalid):
            return Response({
                "target_stage_id": str(target_stage.id),
                "source_stage_id": str(source_stage.id) if source_stage else None,
                "by": by.upper(),
                "mode": ("per_group" if per_group else "overall") if using_leaderboard else None,
                "count": count if using_leaderboard else None,
                "groups": groups or "ALL",
                "created": 0,
                "created_user_ids": [],
                "already_present_user_ids": [],
                "invalid_user_ids": extra_invalid + manual_invalid,
                "requires_admission": bool(target_stage.requires_admission),
                "note": "No valid users to admit.",
            }, status=status.HTTP_200_OK)

        # Find already present (native types) and compute to_create (native)
        existing = set(
            StageAdmission.objects.filter(stage=target_stage, user_id__in=final_user_ids)
            .values_list("user_id", flat=True)
        )
        to_create = [uid for uid in final_user_ids if uid not in existing]

        # Prepare bulk rows
        bulk_rows = []
        from_tops_set = set(from_tops)
        manual_union = set(extra_valid) | set(manual_valid)

        for uid in to_create:
            if using_leaderboard and uid in from_tops_set:
                rc = ("ZONE_TOP_N" if by == "zone" else "STATE_TOP_N") if per_group else "TOP_N"
                meta = {
                    "source_stage_id": str(source_stage.id) if source_stage else None,
                    "count": count,
                    "by": by.upper(),
                    "groups": groups or "ALL",
                }
            else:
                rc = "MANUAL"
                meta = {"manual": True}
            bulk_rows.append(
                StageAdmission(stage=target_stage, user_id=uid, rule_code=rc, meta=meta)
            )

        # Write with conflict ignore (unique(stage,user) will skip dupes on races)
        with transaction.atomic():
            if bulk_rows:
                StageAdmission.objects.bulk_create(bulk_rows, ignore_conflicts=True)
            if not target_stage.requires_admission:
                target_stage.requires_admission = True
                target_stage.save(update_fields=["requires_admission"])

        created_from_tops   = [uid for uid in to_create if uid in from_tops_set]
        created_from_manual = [uid for uid in to_create if uid in manual_union]

        # Stringify IDs for the API response
        return Response({
            "target_stage_id": str(target_stage.id),
            "source_stage_id": str(source_stage.id) if source_stage else None,
            "by": by.upper(),
            "mode": ("per_group" if per_group else "overall") if using_leaderboard else None,
            "count": count if using_leaderboard else None,
            "groups": groups or "ALL",
            "selected_user_ids": [str(x) for x in final_user_ids],

            "created": len(to_create),
            "created_user_ids": [str(x) for x in to_create],
            "created_from_tops": [str(x) for x in created_from_tops],
            "created_from_manual": [str(x) for x in created_from_manual],

            "already_present_user_ids": [str(x) for x in existing],
            "invalid_user_ids": extra_invalid + manual_invalid,

            "requires_admission": True,
        }, status=status.HTTP_200_OK)



class StageAdmissionListView(APIView):
    """
    GET /api/stages/<uuid:stage_id>/admissions/

    Query params:
      - page=<int>           default 1
      - page_size=<int>      default 25 (max 500)
      - zone=<Z1>&zone=<Z2>  optional, filter by user.zone (repeatable)
        OR zone=Z1,Z2        (comma list also works)
      - q=<text>             optional search in username/first_name/last_name/email

    Behavior:
      - If stage.requires_admission == False -> open_for_all=true, items=[] (no whitelist).
      - Else -> returns paginated whitelist with zone breakdown.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrTeacher]

    def get(self, request, stage_id):
        stage = get_object_or_404(QuizStage, pk=stage_id)

        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except Exception:
            page = 1
        try:
            page_size = int(request.query_params.get("page_size", 25))
            page_size = max(1, min(500, page_size))
        except Exception:
            page_size = 25

        by = (request.query_params.get("by") or "zone").lower()  # "zone" | "state"

        # zone filters
        zones = request.query_params.getlist("zone")
        if len(zones) == 1 and "," in zones[0]:
            zones = [z.strip() for z in zones[0].split(",") if z.strip()]
        # state filters  ← NEW
        states = request.query_params.getlist("state")
        if len(states) == 1 and "," in states[0]:
            states = [s.strip() for s in states[0].split(",") if s.strip()]

        q = (request.query_params.get("q") or "").strip()

        if not stage.requires_admission:
            return Response({
                "stage": {
                    "id": str(stage.id),
                    "title": stage.title,
                    "order": stage.order,
                    "requires_admission": False,
                },
                "open_for_all": True,
                "filters": {"by": by.upper(), "zones": zones or "ALL", "states": states or "ALL", "q": q},
                "counts": {"total": 0, "group_breakdown": []},
                "pagination": {
                    "page": 1, "page_size": 0,
                    "total_items": 0, "total_pages": 1, "is_last_page": True,
                },
                "items": [],
                "note": "Stage is open to all users; no admission list required.",
            }, status=status.HTTP_200_OK)

        qs = (
            StageAdmission.objects
            .filter(stage=stage)
            .select_related("user")
            .order_by("-admitted_at", "user_id")
        )

        if zones:
            qs = qs.filter(user__zone__in=zones)
        if states:
            qs = qs.filter(user__state__in=states)

        if q:
            qs = qs.filter(
                Q(user__username__icontains=q) |
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q) |
                Q(user__email__icontains=q)
            )

        total = qs.count()

        # breakdown by selected dimension
        if by == "state":
            group_counts = (
                qs.values("user__state").annotate(n=Count("id")).order_by("user__state")
            )
            group_breakdown = [{"state": (row["user__state"] or ""), "count": row["n"]} for row in group_counts]
        else:
            group_counts = (
                qs.values("user__zone").annotate(n=Count("id")).order_by("user__zone")
            )
            group_breakdown = [{"zone": (row["user__zone"] or ""), "count": row["n"]} for row in group_counts]

        total_pages = max(1, (total + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages
        start = (page - 1) * page_size
        end = start + page_size
        page_qs = list(qs[start:end])

        def _full_name(u):
            if hasattr(u, "get_full_name"):
                name = (u.get_full_name() or "").strip()
                if name:
                    return name
            fn = getattr(u, "first_name", "") or ""
            ln = getattr(u, "last_name", "") or ""
            return (fn + " " + ln).strip() or None

        items = [{
            "user_id": str(row.user_id),
            "username": row.user.username,
            "full_name": _full_name(row.user),
            "email": getattr(row.user, "email", None),
            "zone": getattr(row.user, "zone", ""),
            "state": getattr(row.user, "state", None),  # ← NEW
            "admitted_at": row.admitted_at,
            "rule_code": row.rule_code,
            "meta": row.meta,
        } for row in page_qs]

        return Response({
            "stage": {
                "id": str(stage.id),
                "title": stage.title,
                "order": stage.order,
                "requires_admission": True,
            },
            "open_for_all": False,
            "filters": {"by": by.upper(), "zones": zones or "ALL", "states": states or "ALL", "q": q},
            "counts": {
                "total": total,
                "group_breakdown": group_breakdown,
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": total_pages,
                "is_last_page": page >= total_pages,
            },
            "items": items,
        }, status=status.HTTP_200_OK)




# === Unified start: active quiz → current stage → (rounds or stage questions) ===
from rest_framework.permissions import IsAuthenticated
from .models import (
    Quiz, QuizStage, StageAdmission, Question, QuestionOption,
    StageQuestion, StageRandomRule, QuizAttempt, QuizStageAttempt,
    StageMode, Team, TeamMember,
    Round, RoundQuestion, RoundOption, RoundAttempt, RoundKind,
)
from django.db import transaction

class StartOpenQuizUnifiedView(APIView):
    """
    POST /api/start/open/
    Body (optional):
      {
        "team_id": "<uuid>",   # only for TEAM stages; if omitted, we'll pick user's active team in this quiz
        "rotate": "day"        # keep for deterministic seeds when we fall back to random (defaults to "day")
      }

    Response (examples):
      - Stage with Rounds:
        { quiz:{...}, stage:{...}, actor:{mode:"TEAM", team_id:"..."}, round:{id,...,kind:"VIDEO"},
          items:[ {order, marks, time_limit_seconds, media:{image|audio|video...}, question:{...}, options:[...]} ],
          same_order:true, randomized:false, source:"round_questions"
        }
      - Stage without Rounds (your old flow):
        { quiz:{...}, stage:{...}, actor:{mode:"INDIVIDUAL", user_id:"..."}, items:[...], source:"stage_questions" }
    """
    permission_classes = [IsAuthenticated, IsStudent]

    # ---------- tiny helpers ----------
    def _active_quiz_or_error(self):
        active = list(Quiz.objects.filter(is_active=True))
        if not active:
            raise ValidationError("No active quiz.")
        if len(active) > 1:
            raise ValidationError("Multiple active quizzes found; only one may be active.")
        return active[0]

    def _resolve_actor_or_error(self, request, quiz: Quiz, stage: QuizStage):
        """
        Return ("INDIVIDUAL", {"user_id":...}) or ("TEAM", {"team_id":..., "name":...})
        Validates admission + team membership if needed.
        """
        # admission gate (common)
        if stage.requires_admission:
            if not StageAdmission.objects.filter(stage=stage, user=request.user).exists():
                raise PermissionDenied("You are not admitted to this stage.")

        if stage.mode == StageMode.INDIVIDUAL:
            return "INDIVIDUAL", {"user_id": str(request.user.id)}

        # TEAM mode
        team_id = request.data.get("team_id")
        tm_qs = TeamMember.objects.select_related("team").filter(
            user=request.user, team__quiz=quiz, team__is_active=True
        )
        if team_id:
            tm = tm_qs.filter(team_id=team_id).first()
            if not tm:
                raise PermissionDenied("You are not a member of this active team for this quiz.")
        else:
            tm = tm_qs.order_by("created_at").first()
            if not tm:
                raise PermissionDenied("Active team membership required for this stage.")
        return "TEAM", {"team_id": str(tm.team_id), "name": tm.team.name}

    def _public_base_options(self, q: Question, *, no_shuffle=True):
        opts = list(q.options.all().order_by("order", "id"))
        # DO NOT expose correctness here
        return [{"base_option_id": str(o.id), "round_option_id": None, "text": o.text,
                 "image": None, "audio": None, "video": None, "order": o.order} for o in opts]

    def _public_round_options(self, rq: RoundQuestion):
        ros = list(rq.options.all().order_by("order", "id"))
        if ros:
            out = []
            for ro in ros:
                text = ro.effective_text()
                out.append({
                    "round_option_id": str(ro.id),
                    "base_option_id": str(ro.base_option_id) if ro.base_option_id else None,
                    "text": text,
                    "image": (ro.image.url if ro.image else None),
                    "audio": (ro.audio.url if ro.audio else None),
                    "video": (ro.video.url if ro.video else None),
                    "order": ro.order,
                })
            return out
        # no overrides → fall back to base options
        return self._public_base_options(rq.question)

    def _rq_media(self, rq: RoundQuestion):
        return {
            "image": rq.prompt_image.url if rq.prompt_image else None,
            "audio": rq.prompt_audio.url if rq.prompt_audio else None,
            "video": rq.prompt_video.url if rq.prompt_video else None,
            "caption": rq.caption or "",
            "autoplay": bool(rq.autoplay_media),
            "start_ms": int(rq.media_start_ms or 0),
            "duration_ms": int(rq.media_duration_ms) if rq.media_duration_ms is not None else None,
        }

    def _round_items_from_mapping(self, rnd: Round):
        rows = (RoundQuestion.objects
                .filter(round=rnd)
                .select_related("question")
                .order_by("order", "created_at"))
        items = []
        for rq in rows:
            q = rq.question
            items.append({
                "order": rq.order,
                "marks": float(rq.effective_marks()),
                "negative_marks": float(rq.effective_negative()),
                "time_limit_seconds": int(rq.effective_time() or q.time_limit_seconds),
                "media": self._rq_media(rq),
                "question": {
                    "id": str(q.id),
                    "text": q.text,
                    "question_type": q.question_type,
                    "time_limit_seconds": q.time_limit_seconds,
                },
                "options": self._public_round_options(rq),
            })
        return items

    def _round_items_random_deterministic(self, request, quiz: Quiz, stage: QuizStage, rnd: Round):
        """
        If a round has no RoundQuestion mapping, build a deterministic random set:
        - same for everyone in TEAM mode
        - stable across requests (seeded by round.id)
        """
        pool = _bank_for_stage(stage)
        if not pool.exists():
            pool = Question.objects.filter(is_active=True)

        count = int(rnd.question_count or stage.question_count or quiz.question_count or 1)
        all_ids = list(pool.values_list("id", flat=True))
        if not all_ids:
            return []

        # seed that does NOT depend on user → same order for all
        ranked = sorted(all_ids,
                        key=lambda qid: _hash_int(f"round:{rnd.id}:quiz:{quiz.id}:stage:{stage.id}:qid:{qid}"))
        chosen = ranked[:count]
        qmap = Question.objects.in_bulk(chosen)

        items = []
        order_no = 1
        for qid in chosen:
            q = qmap[qid]
            items.append({
                "order": order_no,
                "marks": float(q.marks),
                "negative_marks": float(q.negative_marks if stage.is_negative_makring else 0.0),
                "time_limit_seconds": int(q.time_limit_seconds),
                "media": {"image": None, "audio": None, "video": None,
                          "caption": "", "autoplay": True, "start_ms": 0, "duration_ms": None},
                "question": {
                    "id": str(q.id),
                    "text": q.text,
                    "question_type": q.question_type,
                    "time_limit_seconds": q.time_limit_seconds,
                },
                "options": self._public_base_options(q),  # no shuffle, preserve order
            })
            order_no += 1
        return items

    def _stage_items_fallback_oldflow(self, request, quiz: Quiz, stage: QuizStage, sa: QuizStageAttempt):
        """
        Reuse your existing StageAttemptItem build + serve (no need to repeat all code).
        Returns the same structure your old StartActiveQuizView returns (full items).
        """
        # reuse the exact builder from StartActiveQuizView
        # If items already built for this SA, just serialize them (no shuffle requested here).
        if not sa.items.exists():
            # Build from StageQuestion mapping or random quotas (same as your code)
            mapped = (StageQuestion.objects.filter(stage=stage)
                      .select_related("question").order_by("order"))
            if mapped.exists():
                bulk, order_no = [], 1
                for sq in mapped:
                    q = sq.question
                    bulk.append(StageAttemptItem(
                        stage_attempt=sa, question=q, order=order_no,
                        marks=float(sq.effective_marks()),
                        negative_marks=float(sq.effective_negative()),
                        time_limit_seconds=int(sq.effective_time()),
                    ))
                    order_no += 1
                StageAttemptItem.objects.bulk_create(bulk)
            else:
                quotas = _stage_quota_from_quiz(quiz, stage)
                pool = _bank_for_stage(stage)
                if not pool.exists():
                    pool = Question.objects.filter(is_active=True)

                chosen_ids = []
                for dkey in ("easy", "medium", "hard"):
                    need = quotas[dkey]
                    if need <= 0:
                        continue
                    diff_pool = list(pool.filter(difficulty=getattr(Difficulty, dkey.upper()))
                                     .values_list("id", flat=True))
                    if not diff_pool:
                        continue
                    take = min(need, len(diff_pool))
                    chosen_ids += _pick_consistent(diff_pool, take, request.user.id, stage.id, salt=str(sa.attempt_id))

                stage_total = stage.question_count or quiz.question_count
                if len(chosen_ids) < stage_total:
                    remaining = list(pool.exclude(id__in=chosen_ids).values_list("id", flat=True))
                    extra = min(stage_total - len(chosen_ids), len(remaining))
                    if extra > 0:
                        chosen_ids += _pick_consistent(
                            remaining, extra, request.user.id, stage.id, salt=str(sa.attempt_id)+":fill"
                        )

                ordered_ids = _pick_consistent(
                    chosen_ids, len(chosen_ids), request.user.id, stage.id, salt=str(sa.attempt_id)+":order"
                )
                qmap = Question.objects.in_bulk(ordered_ids)
                bulk, order_no = [], 1
                for qid in ordered_ids:
                    q = qmap[qid]
                    bulk.append(StageAttemptItem(
                        stage_attempt=sa, question=q, order=order_no,
                        marks=float(q.marks), negative_marks=float(q.negative_marks),
                        time_limit_seconds=int(q.time_limit_seconds),
                    ))
                    order_no += 1
                StageAttemptItem.objects.bulk_create(bulk)

        # serialize (no option shuffle; preserve saved order)
        items_qs = list(sa.items.select_related("question").order_by("order", "id"))
        payload_items = []
        for it in items_qs:
            q = it.question
            opts = list(q.options.all().order_by("order", "id").values("id", "text", "order"))
            payload_items.append({
                "order": it.order,
                "marks": float(it.marks),
                "negative_marks": float(it.negative_marks),
                "time_limit_seconds": int(it.time_limit_seconds),
                "media": {"image": None, "audio": None, "video": None,
                          "caption": "", "autoplay": True, "start_ms": 0, "duration_ms": None},
                "question": {"id": str(q.id), "text": q.text, "question_type": q.question_type,
                             "time_limit_seconds": q.time_limit_seconds},
                "options": [{"base_option_id": str(o["id"]), "round_option_id": None,
                             "text": o["text"], "image": None, "audio": None, "video": None,
                             "order": o["order"]} for o in opts],
            })
        return payload_items

    # ---------- main POST ----------
    def post(self, request):
        quiz = self._active_quiz_or_error()

        # current stage (fallback to first)
        stage = (quiz.stages.filter(is_current=True).order_by("order").first()
                 or quiz.stages.order_by("order").first())
        if not stage:
            raise ValidationError("No stage configured for the active quiz.")
        if not stage.is_in_window():
            raise ValidationError("The current stage is not open right now.")

        # actor validation
        mode, actor = self._resolve_actor_or_error(request, quiz, stage)

        # if stage has rounds → serve round flow
        if stage.rounds.exists():
            rounds = list(stage.rounds.all().order_by("order", "created_at"))
            current_round = rounds[0]  # simple: serve the first one; you can extend to 'first not yet submitted'

            # Ensure a RoundAttempt exists for the actor (team/user)
            with transaction.atomic():
                if mode == "TEAM":
                    ra, _ = RoundAttempt.objects.get_or_create(round=current_round, team_id=actor["team_id"], user=None)
                else:
                    ra, _ = RoundAttempt.objects.get_or_create(round=current_round, user=request.user, team=None)

            # Build items
            if RoundQuestion.objects.filter(round=current_round).exists():
                items = self._round_items_from_mapping(current_round)
                source = "round_questions"
                randomized = False
            else:
                items = self._round_items_random_deterministic(request, quiz, stage, current_round)
                source = "random_bank"
                randomized = True

            return Response({
                "quiz": {"id": str(quiz.id), "title": quiz.title},
                "stage": {
                    "id": str(stage.id), "title": stage.title, "order": stage.order,
                    "mode": stage.mode, "requires_admission": bool(stage.requires_admission),
                },
                "actor": {"mode": mode, **actor},
                "round": {
                    "id": str(current_round.id), "title": current_round.title,
                    "order": current_round.order, "kind": current_round.kind,
                },
                "same_order": True,
                "randomized": randomized,
                "source": source,
                "items": items,
            }, status=200)

        # else → legacy stage-question flow (INDIVIDUAL stage paper, or TEAM stage without rounds)
        # Create/get quiz + stage attempt (so totals etc. stay consistent with your existing code)
        with transaction.atomic():
            attempt, _ = QuizAttempt.objects.get_or_create(quiz=quiz, user=request.user)
            sa, _ = QuizStageAttempt.objects.get_or_create(attempt=attempt, stage=stage)
            if sa.submitted_at:
                return Response({
                    "detail": "Stage already submitted.",
                    "attempt_id": str(attempt.id),
                    "stage_attempt_id": str(sa.id),
                    "submitted": True
                }, status=409)

        items = self._stage_items_fallback_oldflow(request, quiz, stage, sa)
        return Response({
            "quiz": {"id": str(quiz.id), "title": quiz.title},
            "stage": {
                "id": str(stage.id), "title": stage.title, "order": stage.order,
                "mode": stage.mode, "requires_admission": bool(stage.requires_admission),
            },
            "actor": {"mode": mode, **actor},
            "source": "stage_questions",
            "same_order": True,
            "randomized": False,
            "items": items,
            "stage_attempt_id": str(sa.id),
            "attempt_id": str(sa.attempt_id),
        }, status=200)



