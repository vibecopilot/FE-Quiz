from django.contrib import admin
from .models import Course, Enrollment, Tutorial, TutorialProgress


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    raw_id_fields = ("user",)
    fields = ("user", "status", "joined_at")
    readonly_fields = ("joined_at",)


class TutorialProgressInline(admin.TabularInline):
    model = TutorialProgress
    extra = 0
    raw_id_fields = ("user",)
    fields = ("user", "watched_seconds", "is_completed", "submitted_at", "completed_at", "last_watched_at")
    readonly_fields = ("submitted_at", "completed_at", "last_watched_at")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "owner", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "code", "owner__username")
    raw_id_fields = ("owner",)
    readonly_fields = ("created_at",)
    inlines = [EnrollmentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "status", "joined_at")
    list_filter = ("status", "course")
    search_fields = ("user__username", "course__title", "course__code")
    raw_id_fields = ("user", "course")
    readonly_fields = ("joined_at",)


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "min_watch_seconds", "require_submit_click", "created_at")
    search_fields = ("title", "slug")
    readonly_fields = ("created_at", "updated_at")
    inlines = [TutorialProgressInline]


@admin.register(TutorialProgress)
class TutorialProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "tutorial", "watched_seconds", "is_completed", "submitted_at", "completed_at", "last_watched_at")
    list_filter = ("is_completed", "tutorial")
    search_fields = ("user__username", "tutorial__title", "tutorial__slug")
    raw_id_fields = ("user", "tutorial")
    readonly_fields = ("submitted_at", "completed_at", "last_watched_at")
