# scripts/seed_reset_clean.py
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from common.enums import Zone, Difficulty, QuestionType
from exams.models import (
    Question, QuestionOption,
    Quiz, QuizStage, StageRandomRule,
    StageQuestion, StageAdmission,
    QuizAttempt, QuizStageAttempt, AttemptAnswer,
    StageAttemptItem, LeaderboardEntry, AccessToken,
)
from learning.models import Tutorial, TutorialProgress

print("=== RESET START (exams-only) ===")

# 0) Safety: ensure new fields exist (is_active on Quiz, start/end on QuizStage)
#   -> run your migrations before using this script:
#   python manage.py makemigrations && python manage.py migrate

# 1) Clear exam data (keep users)
AttemptAnswer.objects.all().delete()
StageAttemptItem.objects.all().delete()
QuizStageAttempt.objects.all().delete()
QuizAttempt.objects.all().delete()
LeaderboardEntry.objects.all().delete()
StageAdmission.objects.all().delete()
StageQuestion.objects.all().delete()
StageRandomRule.objects.all().delete()
QuizStage.objects.all().delete()
AccessToken.objects.all().delete()
# keep question bank if you want; set to True to wipe
WIPE_BANK = False
if WIPE_BANK:
    QuestionOption.objects.all().delete()
    Question.objects.all().delete()

print("Cleared exams data.")

# 2) Tutorial (prereq)
tutorial, _ = Tutorial.objects.update_or_create(
    slug="safety-briefing",
    defaults={
        "title": "Safety & Fair Play Briefing",
        "description": "Watch this before starting any quiz.",
        "video_url": "https://example.com/video.mp4",
        "min_watch_seconds": 30,
        "require_submit_click": True,
    }
)
print("Tutorial ready:", tutorial.slug)

# 3) Make sure at least a small global bank exists
def ensure_q(text, diff):
    q, created = Question.objects.get_or_create(
        text=text,
        defaults={
            "explanation": "Because reasons.",
            "question_type": QuestionType.SINGLE_CHOICE,
            "subspecialty": "general",
            "difficulty": diff,
            "region_hint": "",
            "marks": 1,
            "negative_marks": 0.25,
            "time_limit_seconds": 60,
            "is_active": True,
        },
    )
    if q.options.count() == 0:
        QuestionOption.objects.bulk_create([
            QuestionOption(question=q, text="Opt A (correct)", is_correct=True, order=1),
            QuestionOption(question=q, text="Opt B", is_correct=False, order=2),
            QuestionOption(question=q, text="Opt C", is_correct=False, order=3),
            QuestionOption(question=q, text="Opt D", is_correct=False, order=4),
        ])
    return q

if Question.objects.count() < 12:
    for i in range(1,6):  ensure_q(f"Easy Q{i}",   Difficulty.EASY)
    for i in range(1,4):  ensure_q(f"Medium Q{i}", Difficulty.MEDIUM)
    for i in range(1,3):  ensure_q(f"Hard Q{i}",   Difficulty.HARD)

print("Question bank size:", Question.objects.count())

# 4) Create two quizzes (idempotent), one marked active
now = timezone.now()
win_start = now - timedelta(days=1)
win_end   = now + timedelta(days=14)

def upsert_quiz(slug, title, easy, med, hard, qcount, active=False, prereq=tutorial):
    quiz, _ = Quiz.objects.update_or_create(
        slug=slug,
        defaults={
            "title": title,
            "description": "Seeded quiz",
            "subspecialty": "general",
            "easy_count": easy, "medium_count": med, "hard_count": hard,
            "start_at": win_start, "end_at": win_end,
            "duration_seconds": 1800,
            "pass_threshold_percent": 60,
            "max_attempts_per_user": 1,
            "question_count": qcount,
            "shuffle_questions": True, "shuffle_options": True,
            "require_fullscreen": True, "lock_on_tab_switch": True,
            "prerequisite_tutorial": prereq,
            "is_active": active,
        }
    )
    # stages (set stage 1 current)
    s1, _ = QuizStage.objects.update_or_create(
        quiz=quiz, order=1,
        defaults={
            "title": "Stage 1", "description": "Round 1",
            "is_current": True,
            "start_at": win_start, "end_at": win_end,
            "question_count": None, "duration_seconds": None,
            "shuffle_questions": None, "shuffle_options": None,
            "requires_admission": False,
        }
    )
    s2, _ = QuizStage.objects.update_or_create(
        quiz=quiz, order=2,
        defaults={
            "title": "Stage 2", "description": "Round 2",
            "is_current": False,
            "start_at": win_start + timedelta(days=7),
            "end_at":   win_end   + timedelta(days=7),
            "question_count": None, "duration_seconds": None,
            "shuffle_questions": None, "shuffle_options": None,
            "requires_admission": True,  # gated for demos
        }
    )
    # ensure only s1 is current
    QuizStage.objects.filter(quiz=quiz).exclude(pk=s1.pk).update(is_current=False)

    # random rules per stage (filters optional; quotas come from quiz)
    StageRandomRule.objects.update_or_create(
        stage=s1, defaults={"count": qcount, "tags_any": [], "difficulties": [], "subspecialties": [], "region_hints": []}
    )
    StageRandomRule.objects.update_or_create(
        stage=s2, defaults={"count": qcount, "tags_any": [], "difficulties": [], "subspecialties": [], "region_hints": []}
    )
    return quiz, s1, s2

# make quiz-alpha active, quiz-beta inactive
quiz_alpha, s1a, s2a = upsert_quiz("quiz-alpha", "Quiz Alpha", 3, 2, 1, 6, active=True)
quiz_beta,  s1b, s2b = upsert_quiz("quiz-beta",  "Quiz Beta",  4, 3, 1, 8, active=False)

# only one active at a time
Quiz.objects.exclude(pk=quiz_alpha.pk).update(is_active=False)

print("Active quiz:", quiz_alpha.slug)
print("Stages:", list(QuizStage.objects.filter(quiz=quiz_alpha).values("order","is_current","start_at","end_at")))
print("Other quiz:", quiz_beta.slug)
print("=== RESET DONE ===")

# Optional: mark tutorial completed for all students having TutorialProgress rows
for tp in TutorialProgress.objects.filter(tutorial=tutorial):
    tp.watched_seconds = max(tp.watched_seconds, tutorial.min_watch_seconds)
    tp.submit()
    tp.save()

print("=== RESET DONE ===")
