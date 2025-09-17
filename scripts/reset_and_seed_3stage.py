# scripts/reset_and_seed_3stage.py
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from common.enums import Difficulty
from exams.models import (
    Question, QuestionOption,
    Quiz, QuizStage, StageRandomRule,
    StageQuestion,
    QuizAttempt, QuizStageAttempt, AttemptAnswer, StageAttemptItem,
    LeaderboardEntry, StageAdmission, AccessToken,
    # keep AntiCheatEventLog, QuestionExposureLog, ParticipationCertificate
)
from learning.models import Tutorial

"""
Reset exam-only data, keep users/tutorials/anti-cheat logs,
and create ONE active quiz with 3 stages:
  S1: now .. +10m  (15 Q)
  S2: +15m .. +25m (20 Q)   (5m break)
  S3: +30m .. +40m (20 Q)   (5m break)
Questions are picked automatically from Question bank at runtime
(NO StageQuestion mappings).
"""

def run():
    print("=== RESET (exams-only) → seed 3-stage quiz ===")
    now = timezone.now()

    # 0) Keep users & tutorials & anti-cheat logs. Wipe ONLY exam runtime/config tables.
    with transaction.atomic():
        # answers & attempts
        AttemptAnswer.objects.all().delete()
        StageAttemptItem.objects.all().delete()
        QuizStageAttempt.objects.all().delete()
        QuizAttempt.objects.all().delete()

        # stage/quiz config (but NOT questions bank)
        LeaderboardEntry.objects.all().delete()
        StageAdmission.objects.all().delete()
        StageQuestion.objects.all().delete()       # ensure no static mapping
        StageRandomRule.objects.all().delete()
        QuizStage.objects.all().delete()
        AccessToken.objects.all().delete()
        # DO NOT delete AntiCheatEventLog, QuestionExposureLog, ParticipationCertificate

        # OPTIONAL: remove all quizzes (so we can make exactly one active)
        Quiz.objects.all().delete()

    print("Cleared exam data (kept users, tutorials, anti-cheat logs).")

    # 1) Ensure we have a decent bank (<= create up to 200 questions if missing)
    TARGET_BANK = 200
    have = Question.objects.filter(is_active=True).count()
    if have < TARGET_BANK:
        print(f"Question bank too small ({have}). Creating up to {TARGET_BANK - have} questions…")
        # 30/40/30 split -> easy/medium/hard
        to_make = TARGET_BANK - have
        dist = {
            Difficulty.EASY:   int(round(to_make * 0.30)),
            Difficulty.MEDIUM: int(round(to_make * 0.40)),
            Difficulty.HARD:   to_make - int(round(to_make * 0.30)) - int(round(to_make * 0.40)),
        }
        created = []
        for diff, n in dist.items():
            for i in range(n):
                q = Question.objects.create(
                    text=f"[AUTO] {diff.title()} Q{have+len(created)+1}",
                    explanation="",
                    question_type="single",  # single choice
                    subspecialty="general",
                    difficulty=diff,
                    region_hint="",
                    marks=1,
                    negative_marks=0.25,
                    time_limit_seconds=60,
                    is_active=True,
                    tags={},
                )
                # 4 options, first is correct
                QuestionOption.objects.bulk_create([
                    QuestionOption(question=q, text="Option A (correct)", is_correct=True,  order=1),
                    QuestionOption(question=q, text="Option B",           is_correct=False, order=2),
                    QuestionOption(question=q, text="Option C",           is_correct=False, order=3),
                    QuestionOption(question=q, text="Option D",           is_correct=False, order=4),
                ])
                created.append(q.id)
        print(f"Created {len(created)} questions.")
    print("Bank size (active):", Question.objects.filter(is_active=True).count())

    # 2) Create ONE quiz, ACTIVE, with three 10-minute stages and 5-minute gaps
    # Use quiz-level difficulty mix (for proportional per-stage quotas).
    # Here we set a 30/40/30 mix out of 200.
    easy, med, hard = 60, 80, 60
    qcount_total = easy + med + hard  # 200

    s1_start = now
    s1_end   = now + timedelta(minutes=10)

    s2_start = now + timedelta(minutes=15)
    s2_end   = now + timedelta(minutes=25)

    s3_start = now + timedelta(minutes=30)
    s3_end   = now + timedelta(minutes=40)

    quiz, _ = Quiz.objects.update_or_create(
        slug="quiz-live-3stage",
        defaults=dict(
            title="Live 3-Stage Quiz",
            description="Seeded quiz with automatic question selection.",
            subspecialty="general",
            easy_count=easy, medium_count=med, hard_count=hard,
            start_at=s1_start,
            end_at=now + timedelta(hours=1),  # covers all three windows
            duration_seconds=60*45,           # overall (not strictly used per stage)
            pass_threshold_percent=60,
            max_attempts_per_user=1,
            question_count=qcount_total,      # used only for quota ratios
            shuffle_questions=True,
            shuffle_options=True,
            require_fullscreen=True,
            lock_on_tab_switch=True,
            prerequisite_tutorial=Tutorial.objects.order_by("id").first(),  # or None
            is_active=True,
        )
    )

    # Stages: 15 / 20 / 20 questions, 10 min each
    s1, _ = QuizStage.objects.update_or_create(
        quiz=quiz, order=1,
        defaults=dict(
            title="Stage 1", description="Round 1",
            start_at=s1_start, end_at=s1_end,
            duration_seconds=10*60,
            question_count=15,
            shuffle_questions=None, shuffle_options=None,
            is_current=True,
            requires_admission=False,
        )
    )
    s2, _ = QuizStage.objects.update_or_create(
        quiz=quiz, order=2,
        defaults=dict(
            title="Stage 2", description="Round 2",
            start_at=s2_start, end_at=s2_end,
            duration_seconds=10*60,
            question_count=20,
            shuffle_questions=None, shuffle_options=None,
            is_current=False,
            requires_admission=False,   # set True if you want gated entry
        )
    )
    s3, _ = QuizStage.objects.update_or_create(
        quiz=quiz, order=3,
        defaults=dict(
            title="Stage 3", description="Round 3",
            start_at=s3_start, end_at=s3_end,
            duration_seconds=10*60,
            question_count=20,
            shuffle_questions=None, shuffle_options=None,
            is_current=False,
            requires_admission=False,
        )
    )

    # Make sure only Stage 1 is current
    QuizStage.objects.filter(quiz=quiz).exclude(pk=s1.pk).update(is_current=False)

    # Optional: empty random rules (so pool = whole active bank). Your views already honor this.
    StageRandomRule.objects.update_or_create(stage=s1, defaults=dict(count=s1.question_count, tags_any=[], difficulties=[], subspecialties=[], region_hints=[]))
    StageRandomRule.objects.update_or_create(stage=s2, defaults=dict(count=s2.question_count, tags_any=[], difficulties=[], subspecialties=[], region_hints=[]))
    StageRandomRule.objects.update_or_create(stage=s3, defaults=dict(count=s3.question_count, tags_any=[], difficulties=[], subspecialties=[], region_hints=[]))

    # Ensure this is the ONLY active quiz
    Quiz.objects.exclude(pk=quiz.pk).update(is_active=False)

    print("Active quiz:", quiz.slug)
    print("Stages:",
          list(QuizStage.objects.filter(quiz=quiz).order_by("order")
               .values("order","title","start_at","end_at","question_count","duration_seconds","is_current")))
    print("=== DONE ===")
