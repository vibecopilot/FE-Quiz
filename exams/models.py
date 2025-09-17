# from __future__ import annotations
# import uuid
# from django.conf import settings
# from django.core.exceptions import ValidationError
# from django.core.validators import MaxValueValidator, MinValueValidator
# from django.db import models
# from django.utils import timezone
# from common.enums import Zone, Difficulty, QuestionType, AttemptStatus, AntiCheatCode
# from accounts.models import User
# from django.db.models import Q

# class StageMode(models.TextChoices):
#     INDIVIDUAL = "INDIVIDUAL", "Individual"
#     TEAM       = "TEAM",       "Team"


# class TimeStampedModel(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     class Meta: abstract = True


# class Quiz(TimeStampedModel):
#     title = models.CharField(max_length=200)
#     slug  = models.SlugField(max_length=220, unique=True)
#     description = models.TextField(blank=True)
#     is_active = models.BooleanField(default=False)
#     subspecialty = models.CharField(max_length=128, blank=True)
#     easy_count   = models.PositiveIntegerField(default=0)
#     medium_count = models.PositiveIntegerField(default=0)
#     hard_count   = models.PositiveIntegerField(default=0)
#     start_at = models.DateTimeField()
#     end_at   = models.DateTimeField()
#     duration_seconds = models.PositiveIntegerField(
#         default=1800, validators=[MinValueValidator(60), MaxValueValidator(4*3600)]
#     )

#     pass_threshold_percent = models.PositiveIntegerField(
#         default=90, validators=[MinValueValidator(1), MaxValueValidator(100)]
#     )
#     max_attempts_per_user = models.PositiveIntegerField(default=1)
#     question_count = models.PositiveIntegerField(default=25, validators=[MinValueValidator(1)])

#     shuffle_questions  = models.BooleanField(default=True)
#     shuffle_options    = models.BooleanField(default=True)
#     require_fullscreen = models.BooleanField(default=True)
#     lock_on_tab_switch = models.BooleanField(default=True)

#     prerequisite_tutorial = models.ForeignKey(
#         "learning.Tutorial",
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="quizzes_requiring",
#     )

#     results_visible_after_close = models.BooleanField(default=False)
#     results_published_at = models.DateTimeField(null=True, blank=True)

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["is_active"], condition=Q(is_active=True),
#                 name="unique_active_quiz"
#             )
#         ]

#     def is_in_window(self):
#         now = timezone.now()
#         if self.start_at and self.end_at:
#             return self.start_at <= now <= self.end_at
#         return self.quiz.start_at <= now <= self.quiz.end_at

#     def clean(self):
#         if self.start_at >= self.end_at:
#             raise ValidationError("start_at must be earlier than end_at")
#         if (self.easy_count + self.medium_count + self.hard_count) != self.question_count:
#             raise ValidationError("easy_count + medium_count + hard_count must equal question_count")

#     @property
#     def is_within_window(self) -> bool:
#         now = timezone.now()
#         return self.start_at <= now <= self.end_at

#     @property
#     def current_stage(self):
#         return self.stages.filter(is_current=True).order_by("order").first() \
#                or self.stages.order_by("order").first()

#     def __str__(self): return self.title


# class QuizStage(TimeStampedModel):
#     quiz  = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="stages")
#     title = models.CharField(max_length=200)
#     description = models.TextField(blank=True)
#     order = models.PositiveIntegerField(default=1)

#     start_at = models.DateTimeField(null=True, blank=True)
#     end_at   = models.DateTimeField(null=True, blank=True)

#     duration_seconds = models.PositiveIntegerField(
#         null=True, blank=True, validators=[MinValueValidator(30), MaxValueValidator(4*3600)]
#     )
#     question_count   = models.PositiveIntegerField(null=True, blank=True)
#     shuffle_questions= models.BooleanField(null=True, blank=True)
#     shuffle_options  = models.BooleanField(null=True, blank=True)
#     is_current = models.BooleanField(default=False)
#     requires_admission = models.BooleanField(default=False)
#     is_negative_makring=models.BooleanField(default=False)
    
#     class Meta:
#         ordering = ("quiz","order","created_at")
#         unique_together = ("quiz","order")
#         indexes = [models.Index(fields=["quiz","order"])]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["quiz"], condition=Q(is_current=True),
#                 name="uniq_current_stage_per_quiz",
#             ),
#         ]

#     def is_in_window(self) -> bool:
#         now = timezone.now()
#         if self.start_at and self.end_at:
#             return self.start_at <= now <= self.end_at
#         return self.quiz.start_at <= now <= self.quiz.end_at


# class Question(TimeStampedModel):
#     text = models.TextField()
#     explanation = models.TextField(blank=True)
#     question_type = models.CharField(max_length=12, choices=QuestionType.choices,
#                                      default=QuestionType.SINGLE_CHOICE)

#     time_limit_seconds = models.PositiveIntegerField(
#         default=120, validators=[MinValueValidator(10), MaxValueValidator(3600)]
#     )

#     subspecialty = models.CharField(max_length=128, blank=True)
#     difficulty   = models.CharField(max_length=16, choices=Difficulty.choices, default=Difficulty.MEDIUM)
#     region_hint  = models.CharField(max_length=16, choices=Zone.choices, blank=True)

#     marks          = models.DecimalField(max_digits=6, decimal_places=2, default=1)
#     negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)

#     is_active = models.BooleanField(default=True)
#     tags = models.JSONField(blank=True, default=dict)

#     class Meta:
#         indexes = [
#             models.Index(fields=["subspecialty"]),
#             models.Index(fields=["difficulty"]),
#             models.Index(fields=["is_active"]),
#         ]

#     def __str__(self): return f"Q{self.pk}: {self.text[:60]}"


# class QuestionOption(TimeStampedModel):
#     question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
#     text = models.TextField()
#     is_correct = models.BooleanField(default=False)
#     order = models.PositiveIntegerField(default=0)

#     class Meta:
#         ordering = ("question","order","created_at")
#         indexes  = [models.Index(fields=["question","order"])]


# class StageQuestion(TimeStampedModel):
#     """
#     Manual mapping from Bank → Stage with explicit order & overrides.
#     """
#     stage    = models.ForeignKey(QuizStage, on_delete=models.CASCADE, related_name="stage_questions")
#     question = models.ForeignKey(Question,  on_delete=models.CASCADE, related_name="in_stages")
#     order = models.PositiveIntegerField(default=1)

#     marks            = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
#     negative_marks   = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
#     time_limit_seconds = models.PositiveIntegerField(null=True, blank=True)

#     class Meta:
#         unique_together = ("stage","question")
#         ordering = ("stage","order","created_at")
#         indexes  = [models.Index(fields=["stage","order"])]

#     def effective_marks(self):    return self.marks if self.marks is not None else self.question.marks
#     def effective_negative(self): return self.negative_marks if self.negative_marks is not None else self.question.negative_marks
#     def effective_time(self):     return self.time_limit_seconds if self.time_limit_seconds is not None else self.question.time_limit_seconds


# class StageRandomRule(TimeStampedModel):
#     """
#     Define random picking from the bank for a stage (used by service code to build the paper).
#     If any StageQuestion rows exist for a stage, you can choose to ignore or combine with randoms.
#     """
#     stage = models.OneToOneField(QuizStage, on_delete=models.CASCADE, related_name="random_rule")
#     count = models.PositiveIntegerField(validators=[MinValueValidator(1)])
#     tags_any     = models.JSONField(default=list, blank=True)     # ["neuro","ped"]
#     difficulties = models.JSONField(default=list, blank=True)     # ["easy","medium"]
#     subspecialties = models.JSONField(default=list, blank=True)   # ["cardio"]
#     region_hints = models.JSONField(default=list, blank=True)     # ["NORTH","WEST"]


# class AccessToken(TimeStampedModel):
#     quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="access_tokens")
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_tokens")
#     token = models.CharField(max_length=64, unique=True)
#     expires_at = models.DateTimeField()
#     used_at    = models.DateTimeField(null=True, blank=True)
#     used_ip    = models.GenericIPAddressField(null=True, blank=True)

#     class Meta:
#         unique_together = ("quiz","user")
#         indexes = [models.Index(fields=["quiz","user"]),
#                    models.Index(fields=["expires_at"])]

#     @property
#     def is_used(self):    return self.used_at is not None
#     @property
#     def is_expired(self): return timezone.now() > self.expires_at


# class QuizAttempt(TimeStampedModel):
#     quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_attempts")

#     status = models.CharField(max_length=16, choices=AttemptStatus.choices, default=AttemptStatus.STARTED)
#     started_at   = models.DateTimeField(auto_now_add=True)
#     submitted_at = models.DateTimeField(null=True, blank=True)

#     device_fingerprint = models.CharField(max_length=256, blank=True)
#     start_ip   = models.GenericIPAddressField(null=True, blank=True)
#     user_agent = models.TextField(blank=True)
#     is_disqualified = models.BooleanField(default=False, db_index=True)
#     total_marks    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     obtained_marks = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     percent        = models.DecimalField(max_digits=5, decimal_places=2, default=0)
#     is_passed      = models.BooleanField(default=False)

#     time_taken_seconds = models.PositiveIntegerField(default=0)
#     disqualified_reason = models.TextField(blank=True)

#     class Meta:
#         unique_together = ("quiz","user")   # ← one attempt per quiz+user (your “single attempt” rule)
#         indexes = [
#             models.Index(fields=["quiz","user","status"]),
#             models.Index(fields=["percent"]),
#             models.Index(fields=["is_passed"]),
#         ]

#     def clean(self):
#         if self.submitted_at and self.submitted_at < self.started_at:
#             raise ValidationError("submitted_at cannot be earlier than started_at")

#     def mark_submitted(self):
#         self.submitted_at = timezone.now()
#         self.time_taken_seconds = int((self.submitted_at - self.started_at).total_seconds())
#         self.status = AttemptStatus.SUBMITTED

#     def compute_pass(self):
#         self.is_passed = self.percent >= self.quiz.pass_threshold_percent


# class QuizStageAttempt(TimeStampedModel):
#     attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="stage_attempts")
#     stage   = models.ForeignKey(QuizStage, on_delete=models.CASCADE, related_name="attempts")

#     started_at   = models.DateTimeField(auto_now_add=True)
#     submitted_at = models.DateTimeField(null=True, blank=True)
#     is_disqualified = models.BooleanField(default=False, db_index=True)
#     time_taken_seconds = models.PositiveIntegerField(default=0)
#     total_marks    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     obtained_marks = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     percent        = models.DecimalField(max_digits=5, decimal_places=2, default=0)


#     class Meta:
#         unique_together = ("attempt","stage")
#         ordering = ("attempt","stage__order","created_at")
#         indexes  = [models.Index(fields=["attempt","stage"])]

#     def mark_submitted(self):
#         self.submitted_at = timezone.now()
#         self.time_taken_seconds = int((self.submitted_at - self.started_at).total_seconds())


# class AttemptAnswer(TimeStampedModel):
#     stage_attempt = models.ForeignKey(QuizStageAttempt, on_delete=models.CASCADE, related_name="answers")
#     question      = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")

#     selected_option = models.ForeignKey(
#         QuestionOption, on_delete=models.CASCADE, null=True, blank=True, related_name="selected_in"
#     )
#     answer_text   = models.TextField(blank=True)
#     answer_number = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
#     answer_bool   = models.BooleanField(null=True, blank=True)

#     is_correct      = models.BooleanField(default=False)
#     awarded_marks   = models.DecimalField(max_digits=6, decimal_places=2, default=0)
#     order           = models.PositiveIntegerField(default=0)
#     time_spent_seconds = models.PositiveIntegerField(default=0)
#     bookmark = models.BooleanField(default=False)
#     final    = models.BooleanField(default=False)
#     no_ans   = models.BooleanField(default=False)  # mark unanswered / timed-out

#     class Meta:
#         indexes = [models.Index(fields=["stage_attempt","question"])]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["stage_attempt","question","selected_option"],
#                 name="uq_stage_attempt_question_option",
#                 deferrable=models.Deferrable.DEFERRED,
#             )
#         ]

#     class Meta:
#         indexes = [models.Index(fields=["stage_attempt","question"])]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["stage_attempt","question","selected_option"],
#                 name="uq_stage_attempt_question_option",
#                 deferrable=models.Deferrable.DEFERRED,
#             )
#         ]


# class QuestionExposureLog(TimeStampedModel):
#     stage_attempt = models.ForeignKey(QuizStageAttempt, on_delete=models.CASCADE, related_name="exposure_logs")
#     question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="exposure_logs")
#     event = models.CharField(max_length=24, default="shown")  # shown|next|prev|hidden
#     occurred_at = models.DateTimeField(auto_now_add=True)
#     class Meta:
#         indexes = [models.Index(fields=["stage_attempt","question","occurred_at"])]


# class AntiCheatEventLog(TimeStampedModel):
#     attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="anticheat_events")
#     code    = models.CharField(max_length=32, choices=AntiCheatCode.choices)
#     details = models.JSONField(default=dict, blank=True)
#     occurred_at = models.DateTimeField(auto_now_add=True)
#     class Meta:
#         indexes = [models.Index(fields=["attempt","code","occurred_at"])]


# class ParticipationCertificate(TimeStampedModel):
#     attempt = models.OneToOneField(QuizAttempt, on_delete=models.CASCADE, related_name="certificate")
#     serial_number = models.CharField(max_length=32, unique=True)
#     file = models.FileField(upload_to="certificates/")
#     issued_at = models.DateTimeField(auto_now_add=True)


# class LeaderboardEntry(TimeStampedModel):
#     """
#     If quiz_stage is NULL → overall quiz leaderboard.
#     If quiz_stage is set → stage-level leaderboard.
#     """
#     quiz       = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="leaderboard")
#     quiz_stage = models.ForeignKey(QuizStage, on_delete=models.CASCADE, null=True, blank=True, related_name="leaderboard")

#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leaderboard_rows")
#     zone = models.CharField(max_length=16, choices=Zone.choices)
#     state=models.CharField(max_length=40,blank=True)
#     subspecialty = models.CharField(max_length=128, blank=True)

#     percent        = models.DecimalField(max_digits=5, decimal_places=2)
#     obtained_marks = models.DecimalField(max_digits=10, decimal_places=2)
#     total_marks    = models.DecimalField(max_digits=10, decimal_places=2)
#     time_taken_seconds = models.PositiveIntegerField()
#     rank = models.PositiveIntegerField(null=True, blank=True)

#     class Meta:
#         unique_together = ("quiz","quiz_stage","user")
#         indexes = [
#             models.Index(fields=["quiz","quiz_stage","zone","percent","time_taken_seconds"]),
#             models.Index(fields=["quiz","quiz_stage","rank"]),
#         ]


# class StageAttemptItem(TimeStampedModel):
#     stage_attempt = models.ForeignKey(
#         QuizStageAttempt, on_delete=models.CASCADE, related_name="items"
#     )
#     question = models.ForeignKey(
#         Question, on_delete=models.CASCADE, related_name="stage_attempt_items"
#     )
#     order = models.PositiveIntegerField(default=1)

#     marks = models.DecimalField(max_digits=6, decimal_places=2, default=1)
#     negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
#     time_limit_seconds = models.PositiveIntegerField(default=120)

#     class Meta:
#         ordering = ("stage_attempt", "order", "id")
#         indexes = [
#             models.Index(fields=["stage_attempt", "order"]),
#             models.Index(fields=["stage_attempt", "question"]),
#         ]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["stage_attempt", "question"],
#                 name="uq_stageattemptitem_attempt_question",
#                 deferrable=models.Deferrable.DEFERRED,
#             )
#         ]


















from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from common.enums import Zone, Difficulty, QuestionType, AttemptStatus, AntiCheatCode


# ----------------------------
# Common
# ----------------------------

class StageMode(models.TextChoices):
    INDIVIDUAL = "INDIVIDUAL", "Individual"
    TEAM       = "TEAM",       "Team"


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



class Quiz(TimeStampedModel):
    title = models.CharField(max_length=200)
    slug  = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    subspecialty = models.CharField(max_length=128, blank=True)

    easy_count   = models.PositiveIntegerField(default=0)
    medium_count = models.PositiveIntegerField(default=0)
    hard_count   = models.PositiveIntegerField(default=0)

    start_at = models.DateTimeField()
    end_at   = models.DateTimeField()

    duration_seconds = models.PositiveIntegerField(
        default=1800, validators=[MinValueValidator(60), MaxValueValidator(4 * 3600)]
    )

    pass_threshold_percent = models.PositiveIntegerField(
        default=90, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    max_attempts_per_user = models.PositiveIntegerField(default=1)
    question_count = models.PositiveIntegerField(default=25, validators=[MinValueValidator(1)])

    shuffle_questions  = models.BooleanField(default=True)
    shuffle_options    = models.BooleanField(default=True)
    require_fullscreen = models.BooleanField(default=True)
    lock_on_tab_switch = models.BooleanField(default=True)

    prerequisite_tutorial = models.ForeignKey(
        "learning.Tutorial",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quizzes_requiring",
    )

    results_visible_after_close = models.BooleanField(default=False)
    results_published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=Q(is_active=True), name="unique_active_quiz"
            )
        ]

    def is_in_window(self) -> bool:
        now = timezone.now()
        if self.start_at and self.end_at:
            return self.start_at <= now <= self.end_at
        return False

    def clean(self):
        if self.start_at >= self.end_at:
            raise ValidationError("start_at must be earlier than end_at")
        if (self.easy_count + self.medium_count + self.hard_count) != self.question_count:
            raise ValidationError("easy_count + medium_count + hard_count must equal question_count")

    @property
    def is_within_window(self) -> bool:
        now = timezone.now()
        return self.start_at <= now <= self.end_at

    @property
    def current_stage(self):
        return self.stages.filter(is_current=True).order_by("order").first() \
               or self.stages.order_by("order").first()

    def __str__(self):
        return self.title


class QuizStage(TimeStampedModel):
    quiz  = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="stages")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)

    start_at = models.DateTimeField(null=True, blank=True)
    end_at   = models.DateTimeField(null=True, blank=True)

    duration_seconds = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(30), MaxValueValidator(4 * 3600)]
    )
    question_count   = models.PositiveIntegerField(null=True, blank=True)
    shuffle_questions= models.BooleanField(null=True, blank=True)
    shuffle_options  = models.BooleanField(null=True, blank=True)

    is_current = models.BooleanField(default=False)
    requires_admission = models.BooleanField(default=False)
    is_negative_makring = models.BooleanField(default=False)  # (kept spelling to avoid migration churn)

    mode = models.CharField(max_length=12, choices=StageMode.choices, default=StageMode.INDIVIDUAL)
    rounds_required = models.BooleanField(default=False)
    SIngle_result=models.BooleanField(default=False)

    class Meta:
        ordering = ("quiz", "order", "created_at")
        unique_together = ("quiz", "order")
        indexes = [models.Index(fields=["quiz", "order"])]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz"], condition=Q(is_current=True), name="uniq_current_stage_per_quiz"
            ),
        ]

    def is_in_window(self) -> bool:
        now = timezone.now()
        if self.start_at and self.end_at:
            return self.start_at <= now <= self.end_at
        return self.quiz.is_in_window()

    def clean(self):
        # If rounds are required and this stage already exists, enforce at least one round.
        if self.rounds_required and self.pk and not self.rounds.exists():
            raise ValidationError("This stage requires rounds, but no rounds are defined.")

    def __str__(self):
        return f"{self.quiz.title} · {self.title}"


class Question(TimeStampedModel):
    text = models.TextField()
    explanation = models.TextField(blank=True)
    question_type = models.CharField(
        max_length=12, choices=QuestionType.choices, default=QuestionType.SINGLE_CHOICE
    )
    time_limit_seconds = models.PositiveIntegerField(
        default=120, validators=[MinValueValidator(10), MaxValueValidator(3600)]
    )

    subspecialty = models.CharField(max_length=128, blank=True)
    difficulty   = models.CharField(max_length=16, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    region_hint  = models.CharField(max_length=16, choices=Zone.choices, blank=True)

    marks          = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    is_active = models.BooleanField(default=True)
    tags = models.JSONField(blank=True, default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["subspecialty"]),
            models.Index(fields=["difficulty"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"Q{self.pk}: {self.text[:60]}"


class QuestionOption(TimeStampedModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("question", "order", "created_at")
        indexes  = [models.Index(fields=["question", "order"])]



class StageQuestion(TimeStampedModel):
    stage    = models.ForeignKey(QuizStage, on_delete=models.CASCADE, related_name="stage_questions")
    question = models.ForeignKey(Question,  on_delete=models.CASCADE, related_name="in_stages")
    order = models.PositiveIntegerField(default=1)

    marks            = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    negative_marks   = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    time_limit_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("stage", "question")
        ordering = ("stage", "order", "created_at")
        indexes  = [models.Index(fields=["stage", "order"])]

    def effective_marks(self):    return self.marks if self.marks is not None else self.question.marks
    def effective_negative(self): return self.negative_marks if self.negative_marks is not None else self.question.negative_marks
    def effective_time(self):     return self.time_limit_seconds if self.time_limit_seconds is not None else self.question.time_limit_seconds


class StageRandomRule(TimeStampedModel):
    stage = models.OneToOneField(QuizStage, on_delete=models.CASCADE, related_name="random_rule")
    count = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    tags_any     = models.JSONField(default=list, blank=True)
    difficulties = models.JSONField(default=list, blank=True)
    subspecialties = models.JSONField(default=list, blank=True)
    region_hints = models.JSONField(default=list, blank=True)


class AccessToken(TimeStampedModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="access_tokens")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_tokens")
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at    = models.DateTimeField(null=True, blank=True)
    used_ip    = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = ("quiz", "user")
        indexes = [models.Index(fields=["quiz", "user"]),
                   models.Index(fields=["expires_at"])]

    @property
    def is_used(self):    return self.used_at is not None
    @property
    def is_expired(self): return timezone.now() > self.expires_at


class QuizAttempt(TimeStampedModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_attempts")

    status = models.CharField(max_length=16, choices=AttemptStatus.choices, default=AttemptStatus.STARTED)
    started_at   = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    device_fingerprint = models.CharField(max_length=256, blank=True)
    start_ip   = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    is_disqualified = models.BooleanField(default=False, db_index=True)

    total_marks    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    obtained_marks = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    percent        = models.DecimalField(max_digits=5,  decimal_places=2, default=Decimal("0.00"))
    is_passed      = models.BooleanField(default=False)

    time_taken_seconds = models.PositiveIntegerField(default=0)
    disqualified_reason = models.TextField(blank=True)

    class Meta:
        unique_together = ("quiz", "user")   # single attempt per quiz+user
        indexes = [
            models.Index(fields=["quiz", "user", "status"]),
            models.Index(fields=["percent"]),
            models.Index(fields=["is_passed"]),
        ]

    def clean(self):
        if self.submitted_at and self.submitted_at < self.started_at:
            raise ValidationError("submitted_at cannot be earlier than started_at")

    def mark_submitted(self):
        self.submitted_at = timezone.now()
        self.time_taken_seconds = int((self.submitted_at - self.started_at).total_seconds())
        self.status = AttemptStatus.SUBMITTED

    def compute_pass(self):
        self.is_passed = self.percent >= self.quiz.pass_threshold_percent


class QuizStageAttempt(TimeStampedModel):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="stage_attempts")
    stage   = models.ForeignKey(QuizStage, on_delete=models.CASCADE, related_name="attempts")

    started_at   = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    is_disqualified = models.BooleanField(default=False, db_index=True)

    time_taken_seconds = models.PositiveIntegerField(default=0)
    total_marks    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    obtained_marks = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    percent        = models.DecimalField(max_digits=5,  decimal_places=2, default=Decimal("0.00"))

    class Meta:
        unique_together = ("attempt", "stage")
        ordering = ("attempt", "stage__order", "created_at")
        indexes  = [models.Index(fields=["attempt", "stage"])]

    def mark_submitted(self):
        self.submitted_at = timezone.now()
        self.time_taken_seconds = int((self.submitted_at - self.started_at).total_seconds())


class AttemptAnswer(TimeStampedModel):
    stage_attempt = models.ForeignKey(QuizStageAttempt, on_delete=models.CASCADE, related_name="answers")
    question      = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")

    selected_option = models.ForeignKey(
        QuestionOption, on_delete=models.CASCADE, null=True, blank=True, related_name="selected_in"
    )
    answer_text   = models.TextField(blank=True)
    answer_number = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    answer_bool   = models.BooleanField(null=True, blank=True)

    is_correct      = models.BooleanField(default=False)
    awarded_marks   = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    order           = models.PositiveIntegerField(default=0)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    bookmark = models.BooleanField(default=False)
    final    = models.BooleanField(default=False)
    no_ans   = models.BooleanField(default=False)  # mark unanswered / timed-out

    class Meta:
        indexes = [models.Index(fields=["stage_attempt", "question"])]
        constraints = [
            models.UniqueConstraint(
                fields=["stage_attempt", "question", "selected_option"],
                name="uq_stage_attempt_question_option",
                deferrable=models.Deferrable.DEFERRED,
            )
        ]


class QuestionExposureLog(TimeStampedModel):
    stage_attempt = models.ForeignKey(QuizStageAttempt, on_delete=models.CASCADE, related_name="exposure_logs")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="exposure_logs")
    event = models.CharField(max_length=24, default="shown")  # shown|next|prev|hidden
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["stage_attempt", "question", "occurred_at"])]


class AntiCheatEventLog(TimeStampedModel):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="anticheat_events")
    code    = models.CharField(max_length=32, choices=AntiCheatCode.choices)
    details = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["attempt", "code", "occurred_at"])]


class ParticipationCertificate(TimeStampedModel):
    attempt = models.OneToOneField(QuizAttempt, on_delete=models.CASCADE, related_name="certificate")
    serial_number = models.CharField(max_length=32, unique=True)
    file = models.FileField(upload_to="certificates/")
    issued_at = models.DateTimeField(auto_now_add=True)


class LeaderboardEntry(TimeStampedModel):
    """
    If quiz_stage is NULL → overall quiz leaderboard.
    If quiz_stage is set → stage-level leaderboard.
    """
    quiz       = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="leaderboard")
    quiz_stage = models.ForeignKey(QuizStage, on_delete=models.CASCADE, null=True, blank=True, related_name="leaderboard")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leaderboard_rows")
    zone = models.CharField(max_length=16, choices=Zone.choices)
    subspecialty = models.CharField(max_length=128, blank=True)

    percent        = models.DecimalField(max_digits=5,  decimal_places=2)
    obtained_marks = models.DecimalField(max_digits=10, decimal_places=2)
    total_marks    = models.DecimalField(max_digits=10, decimal_places=2)
    time_taken_seconds = models.PositiveIntegerField()
    rank = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("quiz", "quiz_stage", "user")
        indexes = [
            models.Index(fields=["quiz", "quiz_stage", "zone", "percent", "time_taken_seconds"]),
            models.Index(fields=["quiz", "quiz_stage", "rank"]),
        ]


class StageAttemptItem(TimeStampedModel):
    stage_attempt = models.ForeignKey(
        QuizStageAttempt, on_delete=models.CASCADE, related_name="items"
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="stage_attempt_items"
    )
    order = models.PositiveIntegerField(default=1)

    marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    time_limit_seconds = models.PositiveIntegerField(default=120)

    class Meta:
        ordering = ("stage_attempt", "order", "id")
        indexes = [
            models.Index(fields=["stage_attempt", "order"]),
            models.Index(fields=["stage_attempt", "question"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["stage_attempt", "question"],
                name="uq_stageattemptitem_attempt_question",
                deferrable=models.Deferrable.DEFERRED,
            )
        ]


# models.py  (put this after Team model or use "Team" string reference)
class StageAdmission(TimeStampedModel):
    stage = models.ForeignKey(QuizStage, on_delete=models.CASCADE, related_name="admissions")
    user  = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                              related_name="stage_admissions")
    team  = models.ForeignKey("Team", on_delete=models.CASCADE, null=True, blank=True,
                              related_name="stage_admissions")

    rule_code   = models.CharField(max_length=32, blank=True)
    meta        = models.JSONField(default=dict, blank=True)
    granted_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="granted_stage_admissions")
    admitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-admitted_at", "stage_id")
        indexes  = [models.Index(fields=["stage","user"]), models.Index(fields=["stage","team"])]
        constraints = [
            # unique (stage,user) only when user is set
            models.UniqueConstraint(
                fields=["stage","user"],
                condition=Q(user__isnull=False),
                name="uq_stage_admission_stage_user_v2",
            ),
            # unique (stage,team) only when team is set
            models.UniqueConstraint(
                fields=["stage","team"],
                condition=Q(team__isnull=False),
                name="uq_stage_admission_stage_team_v2",
            ),
            # exactly one actor (user XOR team)
            models.CheckConstraint(
                name="ck_stage_admission_exactly_one_actor",
                check=((Q(user__isnull=False) & Q(team__isnull=True)) |
                       (Q(user__isnull=True)  & Q(team__isnull=False))),
            ),
        ]

class Team(TimeStampedModel):
    """
    A team belongs to a Quiz (can participate in TEAM-mode stages).
    """
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="teams_created"
    )

    class Meta:
        unique_together = ("quiz", "name")
        indexes = [models.Index(fields=["quiz", "name"]), models.Index(fields=["quiz", "code"])]

    def __str__(self):
        return f"{self.name} ({self.quiz.title})"


class TeamMember(TimeStampedModel):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="team_memberships")
    is_captain = models.BooleanField(default=False)

    class Meta:
        unique_together = ("team", "user")
        indexes = [models.Index(fields=["team", "user"])]

    def __str__(self):
        return f"{self.user} → {self.team}"


class RoundKind(models.TextChoices):
    NORMAL_QA       = "NORMAL_QA", "Normal Q&A"
    AUDIO           = "AUDIO", "Audio Based"
    VIDEO           = "VIDEO", "Video Based"
    BUZZER          = "BUZZER", "Buzzer"
    RAPID_FIRE      = "RAPID_FIRE", "Rapid Fire"
    FASTEST_FINGER  = "FASTEST_FINGER", "Fastest Finger"


class Round(TimeStampedModel):
    stage = models.ForeignKey(QuizStage, on_delete=models.CASCADE, related_name="rounds")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    fixed_order = models.BooleanField(default=True)  
    is_option   = models.BooleanField(default=False) 
    kind = models.CharField(
        max_length=20, choices=RoundKind.choices, default=RoundKind.NORMAL_QA, db_index=True
    )
    duration_seconds = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(10), MaxValueValidator(3600)]
    )
    question_count = models.PositiveIntegerField(null=True, blank=True)
    is_active=models.BooleanField(default=False)
    class Meta:
        ordering = ("stage", "order", "created_at")
        unique_together = ("stage", "order")
        indexes = [models.Index(fields=["stage", "order"]), models.Index(fields=["kind"])]

    def __str__(self): return f"Round {self.order}: {self.title}"


class RoundQuestion(TimeStampedModel):
    """
    Attach bank questions to a round with per-round media overrides.
    Always render in saved order (no shuffle).
    """
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="round_questions")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="in_rounds")
    order = models.PositiveIntegerField(default=1)

    # Per-round scoring/timing overrides
    marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    negative_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    time_limit_seconds = models.PositiveIntegerField(null=True, blank=True)

    # NEW — prompt media (use any/all as needed)
    prompt_image = models.ImageField(upload_to="quiz/round_prompts/images/", null=True, blank=True)
    prompt_audio = models.FileField(upload_to="quiz/round_prompts/audio/", null=True, blank=True)
    prompt_video = models.FileField(upload_to="quiz/round_prompts/video/", null=True, blank=True)
    caption      = models.CharField(max_length=255, blank=True)  # small on-screen label/caption
    autoplay_media   = models.BooleanField(default=True)
    media_start_ms   = models.PositiveIntegerField(default=0)     # e.g., start video/audio at offset
    media_duration_ms= models.PositiveIntegerField(null=True, blank=True)  # optional clipping window

    class Meta:
        unique_together = ("round", "question")
        ordering = ("round", "order", "created_at")
        indexes  = [models.Index(fields=["round", "order"])]

    def effective_marks(self):    return self.marks if self.marks is not None else self.question.marks
    def effective_negative(self): return self.negative_marks if self.negative_marks is not None else self.question.negative_marks
    def effective_time(self):     return self.time_limit_seconds if self.time_limit_seconds is not None else self.question.time_limit_seconds


class RoundOption(TimeStampedModel):
    """
    Optional per-round option override. If none exist, fall back to Question.options.
    """
    round_question = models.ForeignKey(RoundQuestion, on_delete=models.CASCADE, related_name="options")
    base_option = models.ForeignKey(QuestionOption, on_delete=models.SET_NULL, null=True, blank=True, related_name="round_overrides")

    text = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    # NEW — media for the option itself (image-only questions, AV options, etc.)
    image = models.ImageField(upload_to="quiz/round_options/images/", null=True, blank=True)
    audio = models.FileField(upload_to="quiz/round_options/audio/", null=True, blank=True)
    video = models.FileField(upload_to="quiz/round_options/video/", null=True, blank=True)

    class Meta:
        ordering = ("round_question", "order", "created_at")
        indexes  = [models.Index(fields=["round_question", "order"])]

    def effective_text(self):   return self.text or (self.base_option.text if self.base_option else "")
    def effective_correct(self):
        return self.is_correct if self.is_correct is not None else (self.base_option.is_correct if self.base_option else False)


class RoundAdmission(TimeStampedModel):
    """
    Gatekeeping to start a round (team-based, as requested).
    """
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="admissions")
    team  = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="round_admissions")
    rule_code = models.CharField(max_length=32, blank=True)  # e.g., TOP_N | MANUAL
    meta = models.JSONField(default=dict, blank=True)
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="granted_round_admissions"
    )
    admitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-admitted_at", "round_id", "team_id")
        indexes = [models.Index(fields=["round", "team"])]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "team"],
                name="uq_round_admission_round_team",
                deferrable=models.Deferrable.IMMEDIATE,
            )
        ]


class RoundAttemptStatus(models.TextChoices):
    STARTED   = "STARTED", "Started"
    SUBMITTED = "SUBMITTED", "Submitted"
    # (no DISQUALIFIED — removed as requested)


class RoundAttempt(TimeStampedModel):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="attempts")
    team  = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name="round_attempts")
    user  = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="round_attempts")

    status = models.CharField(max_length=16, choices=RoundAttemptStatus.choices, default=RoundAttemptStatus.STARTED)
    started_at   = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    time_taken_seconds = models.PositiveIntegerField(default=0)
    total_marks    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    obtained_marks = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    percent        = models.DecimalField(max_digits=5,  decimal_places=2, default=Decimal("0.00"))

    class Meta:
        indexes = [
            models.Index(fields=["round", "status"]),
            models.Index(fields=["percent"]),
            models.Index(fields=["round", "team"]),
            models.Index(fields=["round", "user"]),
        ]
        constraints = [
            # ✅ conditional uniques (no deferrable!)
            models.UniqueConstraint(
                fields=["round", "team"],
                name="uq_round_attempt_round_team",
                condition=Q(team__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["round", "user"],
                name="uq_round_attempt_round_user",
                condition=Q(user__isnull=False),
            ),
            # ✅ exactly one of team/user must be set
            models.CheckConstraint(
                name="ck_round_attempt_exactly_one_actor",
                check=(
                    (Q(team__isnull=False) & Q(user__isnull=True)) |
                    (Q(team__isnull=True)  & Q(user__isnull=False))
                ),
            ),
        ]

    def clean(self):
        stage_mode = self.round.stage.mode
        if stage_mode == StageMode.TEAM:
            if not self.team or self.user:
                raise ValidationError("TEAM mode: team is required and user must be empty.")
        else:
            if not self.user or self.team:
                raise ValidationError("INDIVIDUAL mode: user is required and team must be empty.")

    def mark_submitted(self):
        self.submitted_at = timezone.now()
        self.time_taken_seconds = int((self.submitted_at - self.started_at).total_seconds())
        self.status = RoundAttemptStatus.SUBMITTED


class BuzzerAttempt(TimeStampedModel):
    """
    When a team/user buzzes for a particular round question (for buzzer rounds).
    """
    round_attempt = models.ForeignKey(RoundAttempt, on_delete=models.CASCADE, related_name="buzzer_attempts")
    round_question = models.ForeignKey(RoundQuestion, on_delete=models.CASCADE, related_name="buzzer_attempts")
    buzzed_at = models.DateTimeField(auto_now_add=True)
    reaction_ms = models.PositiveIntegerField(default=0)  # gap between show and buzz
    accepted = models.BooleanField(default=True)
    penalty_applied = models.BooleanField(default=False)

    class Meta:
        unique_together = ("round_attempt", "round_question")
        indexes = [models.Index(fields=["round_attempt", "round_question"])]


class RoundAnswerStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CORRECT = "CORRECT", "Correct"
    WRONG   = "WRONG",   "Wrong"
    # (no DISQUALIFIED — removed as requested)


class RoundAnswer(TimeStampedModel):
    """
    Answer for a specific round question.
    Works for both option rounds and buzzer rounds.
    Exactly one of selected_round_option / selected_base_option / free-form should be used.
    """
    round_attempt  = models.ForeignKey(RoundAttempt, on_delete=models.CASCADE, related_name="answers")
    round_question = models.ForeignKey(RoundQuestion, on_delete=models.CASCADE, related_name="answers")

    # If options round, one of these will be used
    selected_round_option = models.ForeignKey(
        RoundOption, on_delete=models.SET_NULL, null=True, blank=True, related_name="chosen_in"
    )
    selected_base_option = models.ForeignKey(
        QuestionOption, on_delete=models.SET_NULL, null=True, blank=True, related_name="chosen_in_round"
    )

    # If free-form (text/number/bool)
    answer_text   = models.TextField(blank=True)
    answer_number = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    answer_bool   = models.BooleanField(null=True, blank=True)
    responded_ms = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=RoundAnswerStatus.choices, default=RoundAnswerStatus.PENDING)
    awarded_marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    time_spent_seconds = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)
    final = models.BooleanField(default=True)  # if you allow multiple revisions, mark the last as final

    class Meta:
        unique_together = ("round_attempt", "round_question")
        indexes = [models.Index(fields=["round_attempt", "round_question"])]

    def compute_correctness_and_marks(self):
        rq = self.round_question
        correct = None

        # If an override RoundOption was used
        if self.selected_round_option_id:
            correct = self.selected_round_option.effective_correct()

        # Else if a base option was used
        elif self.selected_base_option_id:
            correct = self.selected_base_option.is_correct

        # Decide status
        if correct is True:
            self.status = RoundAnswerStatus.CORRECT
            self.awarded_marks = rq.effective_marks()
        elif correct is False:
            self.status = RoundAnswerStatus.WRONG
            self.awarded_marks = -rq.effective_negative()
        else:
            self.status = RoundAnswerStatus.PENDING
            self.awarded_marks = Decimal("0.00")
