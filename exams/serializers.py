# exams/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from common.enums import Zone, Difficulty, QuestionType
from .models import (
    Quiz, QuizStage, Question, QuestionOption, StageQuestion, StageRandomRule,
    QuizAttempt, QuizStageAttempt, AttemptAnswer, LeaderboardEntry,
    AccessToken, AntiCheatEventLog, QuestionExposureLog,
)

User = get_user_model()


# exams/serializers.py
from decimal import Decimal
from rest_framework import serializers
from exams.models import Question, QuestionOption
from common.enums import Zone
from common.enums import QuestionType, Difficulty  # adjust import to your project

class QuestionOptionInSerializer(serializers.Serializer):
    text = serializers.CharField()
    is_correct = serializers.BooleanField(default=False)
    order = serializers.IntegerField(required=False, min_value=0)

class QuestionBulkInSerializer(serializers.Serializer):
    text = serializers.CharField()
    explanation = serializers.CharField(required=False, allow_blank=True)
    question_type = serializers.ChoiceField(
        choices=QuestionType.choices, required=False, default=QuestionType.SINGLE_CHOICE
    )
    time_limit_seconds = serializers.IntegerField(required=False, min_value=10, max_value=3600, default=120)
    subspecialty = serializers.CharField(required=False, allow_blank=True)
    difficulty = serializers.ChoiceField(choices=Difficulty.choices, required=False, default=Difficulty.MEDIUM)
    region_hint = serializers.ChoiceField(choices=Zone.choices, required=False, allow_blank=True)
    marks = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, default=Decimal("1.00"))
    negative_marks = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, default=Decimal("0.00"))
    is_active = serializers.BooleanField(required=False, default=True)
    tags = serializers.JSONField(required=False, default=dict)

    # required for choice questions
    options = QuestionOptionInSerializer(many=True)

    def validate(self, attrs):
        qtype = attrs.get("question_type", QuestionType.SINGLE_CHOICE)
        options = attrs.get("options") or []

        # Basic options validation
        if qtype in (QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE):
            if len(options) < 2:
                raise serializers.ValidationError("At least 2 options are required for choice questions.")
            correct_count = sum(1 for o in options if o.get("is_correct"))
            if qtype == QuestionType.SINGLE_CHOICE and correct_count != 1:
                raise serializers.ValidationError("SINGLE_CHOICE must have exactly one correct option.")
            if qtype == QuestionType.MULTI_CHOICE and correct_count < 1:
                raise serializers.ValidationError("MULTI_CHOICE must have at least one correct option.")
            if any(not (o.get("text") or "").strip() for o in options):
                raise serializers.ValidationError("Option text cannot be blank.")
        else:
            # If you add non-choice types later, relax this as needed.
            pass

        return attrs


# ---------- Question Bank ----------
class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "text", "is_correct", "order"]

class QuestionOptionCreateIn(serializers.Serializer):
    text = serializers.CharField()
    is_correct = serializers.BooleanField(default=False)
    order = serializers.IntegerField(required=False, allow_null=True)

    def validate_text(self, v):
        v = (v or "").strip()
        if not v:
            raise serializers.ValidationError("Option text cannot be empty.")
        return v

class QuestionCreateSerializer(serializers.ModelSerializer):
    options = QuestionOptionCreateIn(many=True, required=False)

    class Meta:
        model = Question
        fields = [
            "id", "text", "explanation", "question_type", "subspecialty",
            "difficulty", "region_hint", "marks", "negative_marks",
            "time_limit_seconds", "is_active", "tags", "options",
        ]

    def validate(self, data):
        qt = data.get("question_type")
        options = data.get("options") or []
        if qt in (QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE):
            if not options:
                raise serializers.ValidationError("Options are required for choice questions.")
            if qt == QuestionType.SINGLE_CHOICE:
                correct = [o for o in options if o.get("is_correct")]
                if len(correct) != 1:
                    raise serializers.ValidationError("Single choice must have exactly one correct option.")
            else:
                if not any(o.get("is_correct") for o in options):
                    raise serializers.ValidationError("Multi choice must have at least one correct option.")
        else:
            if options:
                raise serializers.ValidationError("Options are only allowed for choice questions.")
        return data

    def create(self, validated):
        options = validated.pop("options", [])
        q = Question.objects.create(**validated)
        if options:
            bulk = []
            next_order = 1
            for opt in options:
                order_val = opt.get("order") if opt.get("order") is not None else next_order
                bulk.append(QuestionOption(
                    question=q, text=(opt["text"] or "").strip(),
                    is_correct=opt.get("is_correct", False), order=order_val
                ))
                next_order = max(order_val + 1, next_order + 1)
            QuestionOption.objects.bulk_create(bulk)
        return q

class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id", "text", "explanation", "question_type", "subspecialty",
            "difficulty", "region_hint", "marks", "negative_marks",
            "time_limit_seconds", "is_active", "tags", "options",
        ]


class QuestionBulkCreateItemSerializer(QuestionCreateSerializer):
    """Same fields as QuestionCreateSerializer (used for list payload)."""
    pass


# ---------- Quiz & Stages ----------
class QuizSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = [
            "id", "title", "slug", "description", "subspecialty",
            "start_at", "end_at", "duration_seconds", "pass_threshold_percent",
            "max_attempts_per_user", "question_count",
            "shuffle_questions", "shuffle_options", "require_fullscreen", "lock_on_tab_switch",
            "results_visible_after_close", "results_published_at",
        ]

class QuizStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizStage
        fields = [
            "id", "quiz", "title", "description", "order",
            "duration_seconds", "question_count", "shuffle_questions", "shuffle_options",
        ]

class StageQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StageQuestion
        fields = [
            "id", "stage", "question", "order",
            "marks", "negative_marks", "time_limit_seconds",
        ]

class StageQuestionBulkAddSerializer(serializers.Serializer):
    stage = serializers.PrimaryKeyRelatedField(queryset=QuizStage.objects.all())
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    # item: {"question": <id>, "order": <int>, "marks": <dec>?, "negative_marks": <dec>?, "time_limit_seconds": <int>?}

class StageRandomRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StageRandomRule
        fields = ["id", "stage", "count", "tags_any", "difficulties", "subspecialties", "region_hints"]


# ---------- Attempts ----------
class QuizStageAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizStageAttempt
        fields = [
            "id", "attempt", "stage", "started_at", "submitted_at",
            "time_taken_seconds", "total_marks", "obtained_marks", "percent",
        ]
        read_only_fields = ["started_at", "submitted_at", "time_taken_seconds", "total_marks", "obtained_marks", "percent"]

class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = [
            "id", "quiz", "user", "status", "started_at", "submitted_at",
            "device_fingerprint", "start_ip", "user_agent",
            "total_marks", "obtained_marks", "percent", "is_passed",
            "time_taken_seconds", "disqualified_reason"
        ]
        read_only_fields = ["user", "started_at", "submitted_at", "percent", "is_passed", "time_taken_seconds"]

# exams/serializers.py  (only the changed serializer)

from rest_framework import serializers
from .models import AttemptAnswer

class AttemptAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttemptAnswer
        fields = (
            "id", "stage_attempt", "question", "selected_option",
            "answer_text", "answer_number", "answer_bool",
            "is_correct", "awarded_marks", "order", "time_spent_seconds",
            "bookmark", "final", "no_ans",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "is_correct", "awarded_marks", "order",
            "created_at", "updated_at",
        )


# ---------- Leaderboard ----------
class LeaderboardEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardEntry
        fields = [
            "id", "quiz", "quiz_stage", "user", "zone", "subspecialty",
            "percent", "obtained_marks", "total_marks",
            "time_taken_seconds", "rank"
        ]


# ---------- File upload (Excel) ----------
class ExcelUploadSerializer(serializers.Serializer):
    file = serializers.FileField()





