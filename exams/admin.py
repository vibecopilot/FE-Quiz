from django.contrib import admin
from .models import (
    Quiz, QuizStage, Question, QuestionOption, StageQuestion, StageRandomRule,
    AccessToken, QuizAttempt, QuizStageAttempt, AttemptAnswer,
    QuestionExposureLog, AntiCheatEventLog, ParticipationCertificate,
    LeaderboardEntry, StageAttemptItem, StageAdmission
)


# ----- Inlines -----
class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 1
    fields = ("text", "is_correct", "order")
    ordering = ("order",)


class StageQuestionInline(admin.TabularInline):
    model = StageQuestion
    extra = 0
    raw_id_fields = ("question",)
    fields = ("question", "order", "marks", "negative_marks", "time_limit_seconds")
    ordering = ("order",)


class StageRandomRuleInline(admin.StackedInline):
    model = StageRandomRule
    extra = 0
    max_num = 1
    can_delete = True


class QuizStageInline(admin.TabularInline):
    model = QuizStage
    extra = 0
    show_change_link = True
    fields = (
        "title", "order", "duration_seconds", "question_count",
        "shuffle_questions", "shuffle_options", "is_current", "requires_admission",
    )
    ordering = ("order",)


class StageAttemptItemInline(admin.TabularInline):
    model = StageAttemptItem
    extra = 0
    raw_id_fields = ("question",)
    fields = ("order", "question", "marks", "negative_marks", "time_limit_seconds")
    ordering = ("order",)


class AttemptAnswerInline(admin.TabularInline):
    model = AttemptAnswer
    extra = 0
    raw_id_fields = ("question", "selected_option")
    fields = ("question", "selected_option", "is_correct", "awarded_marks", "time_spent_seconds")
    readonly_fields = ("is_correct", "awarded_marks")


# ----- ModelAdmins -----
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "short_text", "subspecialty", "difficulty", "region_hint",
                    "marks", "negative_marks", "is_active", "created_at")
    list_filter = ("is_active", "difficulty", "region_hint", "subspecialty")
    search_fields = ("text", "subspecialty")
    inlines = [QuestionOptionInline]
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    def short_text(self, obj):
        return (obj.text or "")[:80]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title", "slug", "subspecialty", "start_at", "end_at",
        "question_count", "shuffle_questions", "shuffle_options",
        "require_fullscreen", "lock_on_tab_switch",
        "prerequisite_tutorial", "results_visible_after_close",
        "is_active",
        
    )
    list_filter = (
        "subspecialty", "shuffle_questions", "shuffle_options",
        "require_fullscreen", "lock_on_tab_switch", "results_visible_after_close",
    )
    search_fields = ("title", "slug", "description")
    date_hierarchy = "start_at"
    inlines = [QuizStageInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(QuizStage)
class QuizStageAdmin(admin.ModelAdmin):
    list_display = ("title", "quiz", "order", "is_current", "requires_admission",
                    "duration_seconds", "question_count", "created_at")
    list_filter = ("quiz", "is_current", "requires_admission")
    search_fields = ("title", "quiz__title")
    ordering = ("quiz", "order")
    inlines = [StageRandomRuleInline, StageQuestionInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(StageQuestion)
class StageQuestionAdmin(admin.ModelAdmin):
    list_display = ("stage", "question", "order", "marks", "negative_marks", "time_limit_seconds")
    list_filter = ("stage__quiz", "stage")
    search_fields = ("question__text",)
    raw_id_fields = ("stage", "question")
    ordering = ("stage", "order")


@admin.register(StageRandomRule)
class StageRandomRuleAdmin(admin.ModelAdmin):
    list_display = ("stage", "count")
    list_filter = ("stage__quiz",)
    search_fields = ("stage__title", "stage__quiz__title")


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    list_display = ("quiz", "user", "token", "expires_at", "used_at", "used_ip", "is_used_flag", "is_expired_flag")
    search_fields = ("token", "quiz__title", "quiz__slug", "user__username", "user__email")
    list_filter = ("expires_at",)
    raw_id_fields = ("quiz", "user")

    def is_used_flag(self, obj): return obj.is_used
    def is_expired_flag(self, obj): return obj.is_expired
    is_used_flag.boolean = True
    is_expired_flag.boolean = True


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz", "user", "status", "percent",
                    "obtained_marks", "total_marks", "time_taken_seconds",
                    "started_at", "submitted_at")
    list_filter = ("status", "quiz")
    search_fields = ("user__username", "user__email", "quiz__title")
    raw_id_fields = ("quiz", "user")
    readonly_fields = ("started_at", "submitted_at", "created_at", "updated_at")


@admin.register(QuizStageAttempt)
class QuizStageAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "stage", "percent", "obtained_marks", "total_marks",
                    "time_taken_seconds", "started_at", "submitted_at")
    list_filter = ("stage__quiz", "stage")
    search_fields = ("attempt__user__username", "stage__title", "stage__quiz__title")
    raw_id_fields = ("attempt", "stage")
    readonly_fields = ("started_at", "submitted_at", "created_at", "updated_at")
    inlines = [StageAttemptItemInline, AttemptAnswerInline]


@admin.register(AttemptAnswer)
class AttemptAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "stage_attempt", "question", "selected_option",
                    "is_correct", "awarded_marks", "time_spent_seconds", "created_at")
    list_filter = ("is_correct",)
    search_fields = ("stage_attempt__attempt__user__username", "question__text")
    raw_id_fields = ("stage_attempt", "question", "selected_option")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StageAttemptItem)
class StageAttemptItemAdmin(admin.ModelAdmin):
    list_display = ("stage_attempt", "order", "question", "marks", "negative_marks", "time_limit_seconds")
    list_filter = ("stage_attempt__stage", "stage_attempt__attempt__quiz")
    search_fields = ("question__text",)
    raw_id_fields = ("stage_attempt", "question")
    ordering = ("stage_attempt", "order")


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("quiz", "quiz_stage", "user", "zone",
                    "percent", "obtained_marks", "total_marks",
                    "time_taken_seconds", "rank", "created_at")
    list_filter = ("quiz", "quiz_stage", "zone")
    search_fields = ("user__username", "quiz__title")
    raw_id_fields = ("quiz", "quiz_stage", "user")
    ordering = ("quiz", "-percent", "time_taken_seconds")


@admin.register(QuestionExposureLog)
class QuestionExposureLogAdmin(admin.ModelAdmin):
    list_display = ("stage_attempt", "question", "event", "occurred_at")
    list_filter = ("event",)
    search_fields = ("question__text", "stage_attempt__attempt__user__username")
    raw_id_fields = ("stage_attempt", "question")
    readonly_fields = ("occurred_at",)


@admin.register(AntiCheatEventLog)
class AntiCheatEventLogAdmin(admin.ModelAdmin):
    list_display = ("attempt", "code", "occurred_at")
    list_filter = ("code",)
    search_fields = ("attempt__user__username", "attempt__quiz__title")
    raw_id_fields = ("attempt",)
    readonly_fields = ("occurred_at",)


@admin.register(ParticipationCertificate)
class ParticipationCertificateAdmin(admin.ModelAdmin):
    list_display = ("attempt", "serial_number", "file", "issued_at")
    search_fields = ("serial_number", "attempt__user__username", "attempt__quiz__title")
    raw_id_fields = ("attempt",)
    readonly_fields = ("issued_at",)


@admin.register(StageAdmission)
class StageAdmissionAdmin(admin.ModelAdmin):
    list_display = ("stage", "user", "rule_code", "admitted_at")
    list_filter = ("stage__quiz", "stage", "rule_code")
    search_fields = ("user__username", "stage__title", "stage__quiz__title")
    raw_id_fields = ("stage", "user")
    readonly_fields = ("admitted_at",)
