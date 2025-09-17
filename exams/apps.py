# exams/apps.py
from django.apps import AppConfig

class ExamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "exams"

    def ready(self):
        # Ensures Celery sees exams.tasks (for @shared_task)
        import exams.tasks  # noqa: F401
