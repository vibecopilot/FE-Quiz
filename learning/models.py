# learning/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Course(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_courses")
    title = models.CharField(max_length=200)
    code = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE  = "ACTIVE",  "Active"
        BLOCKED = "BLOCKED", "Blocked"

    user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "course")

    def __str__(self):
        return f"{self.user} -> {self.course} ({self.status})"


class Tutorial(models.Model):
    """
    A short video/tutorial that can be required before a quiz starts.
    If linked from a quiz, the user must 'complete/submit' this tutorial first.
    """
    title = models.CharField(max_length=200)
    slug  = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)

    video_url = models.URLField()
    video = models.FileField(upload_to="tutorials/videos/")

    min_watch_seconds = models.PositiveIntegerField(default=60)  # threshold to allow submit
    require_submit_click = models.BooleanField(default=True)     # user must press 'Submit/Continue'

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "slug")

    def __str__(self):
        return self.title
    
    @property
    def video_url(self) -> str:
        """Convenience property used by the serializer."""
        try:
            return self.video.url
        except Exception:
            return ""



class TutorialProgress(models.Model):
    """
    Per-user progress on a Tutorial.
    'is_completed' goes True once user has watched enough AND (optionally) clicked submit.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tutorial_progress")
    tutorial = models.ForeignKey(Tutorial, on_delete=models.CASCADE, related_name="progress")

    watched_seconds = models.PositiveIntegerField(default=0)
    last_watched_at = models.DateTimeField(null=True, blank=True)

    is_completed  = models.BooleanField(default=False)
    submitted_at  = models.DateTimeField(null=True, blank=True)
    completed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "tutorial")
        indexes = [models.Index(fields=["user", "tutorial"])]

    def can_complete(self) -> bool:
        return self.watched_seconds >= self.tutorial.min_watch_seconds

    def mark_progress(self, seconds: int):
        self.watched_seconds = max(self.watched_seconds, int(seconds or 0))
        self.last_watched_at = timezone.now()

    def submit(self):
        now = timezone.now()
        self.submitted_at = now
        if self.can_complete():
            self.is_completed = True
            self.completed_at = now

    def try_autocomplete(self):
        # For flows that don't need explicit submit
        if not self.tutorial.require_submit_click and self.can_complete():
            self.is_completed = True
            self.completed_at = timezone.now()

