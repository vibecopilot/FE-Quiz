# scripts/reset_exam_data.py
from __future__ import annotations
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

def run(*args):
    """
    Wipes ALL exam data (keeps users), then creates:
      • 1 quiz (active now)
      • 3 stages (10m each) with 5m breaks in between
      • 55 demo questions (MCQ) and maps 15/20/20 to the stages
    """

    from exams.models import (
        Quiz, QuizStage, Question, QuestionOption, StageQuestion,
        QuizAttempt, QuizStageAttempt, AttemptAnswer, StageAttemptItem,
        AccessToken, ParticipationCertificate, LeaderboardEntry, StageAdmission,
        AntiCheatEventLog, QuestionExposureLog, StageRandomRule
    )

    print("=== Deleting existing exam data (users untouched) ===")
    with transaction.atomic():
        # Delete deepest children first
        AttemptAnswer.objects.all().delete()
        StageAttemptItem.objects.all().delete()
        QuestionExposureLog.objects.all().delete()
        AntiCheatEventLog.objects.all().delete()
        QuizStageAttempt.objects.all().delete()
        QuizAttempt.objects.all().delete()
        ParticipationCertificate.objects.all().delete()
        LeaderboardEntry.objects.all().delete()
        AccessToken.objects.all().delete()
        StageAdmission.objects.all().delete()
        StageRandomRule.objects.all().delete()
        StageQuestion.objects.all().delete()
        QuestionOption.objects.all().delete()
        Question.objects.all().delete()
        QuizStage.objects.all().delete()
        Quiz.objects.all().delete()

    print("✓ Cleared exam data")

    # ── Seed quiz + stages ───────────────────────────────────────────────────
    now = timezone.now()

    stage1_start = now
    stage1_end   = stage1_start + timedelta(minutes=10)

    stage2_start = stage1_end + timedelta(minutes=5)   # 5 min break
    stage2_end   = stage2_start + timedelta(minutes=10)

    stage3_start = stage2_end + timedelta(minutes=5)   # 5 min break
    stage3_end   = stage3_start + timedelta(minutes=10)

    quiz_start = stage1_start
    quiz_end   = stage3_end

    with transaction.atomic():
        quiz = Quiz.objects.create(
            title="Seeded Quiz (3 stages)",
            slug=f"seeded-{int(now.timestamp())}",
            description="Auto-seeded quiz with 3 stages (10m each, 5m gaps).",
            is_active=True,  # make it active immediately (Celery can also handle this)
            start_at=quiz_start,
            end_at=quiz_end,
            duration_seconds=int((quiz_end - quiz_start).total_seconds()),
            pass_threshold_percent=50,
            question_count=15,   # not used for stages; safe default
            shuffle_questions=True,
            shuffle_options=True,
            require_fullscreen=False,
            lock_on_tab_switch=False,
        )

        s1 = QuizStage.objects.create(
            quiz=quiz,
            title="Stage 1",
            description="Stage 1 (10m)",
            order=1,
            start_at=stage1_start,
            end_at=stage1_end,
            duration_seconds=10 * 60,
            question_count=15,
            shuffle_questions=True,
            shuffle_options=True,
            is_current=True,   # current now
        )
        s2 = QuizStage.objects.create(
            quiz=quiz,
            title="Stage 2",
            description="Stage 2 (10m) after 5m break",
            order=2,
            start_at=stage2_start,
            end_at=stage2_end,
            duration_seconds=10 * 60,
            question_count=20,
            shuffle_questions=True,
            shuffle_options=True,
            is_current=False,
        )
        s3 = QuizStage.objects.create(
            quiz=quiz,
            title="Stage 3",
            description="Stage 3 (10m) after 5m break",
            order=3,
            start_at=stage3_start,
            end_at=stage3_end,
            duration_seconds=10 * 60,
            question_count=20,
            shuffle_questions=True,
            shuffle_options=True,
            is_current=False,
        )

        # Make sure no other quizzes are active (safety, though we just wiped)
        Quiz.objects.exclude(pk=quiz.pk).update(is_active=False)

        # ── Create 55 demo MCQs ──────────────────────────────────────────────
        total_q = 15 + 20 + 20  # 55
        questions = []
        for i in range(1, total_q + 1):
            q = Question.objects.create(
                text=f"Demo Question {i}: 2 + 2 = ?",
                explanation="Because 2 plus 2 equals 4.",
                question_type="SINGLE_CHOICE",
                time_limit_seconds=60,
                subspecialty="General",
                difficulty="MEDIUM",
                region_hint="",   # optional
                marks=1,
                negative_marks=0,
                is_active=True,
                tags={"demo": True, "idx": i},
            )
            # 4 options, first one correct
            QuestionOption.objects.create(question=q, text="4", is_correct=True, order=1)
            QuestionOption.objects.create(question=q, text="3", is_correct=False, order=2)
            QuestionOption.objects.create(question=q, text="5", is_correct=False, order=3)
            QuestionOption.objects.create(question=q, text="22", is_correct=False, order=4)
            questions.append(q)

        # Map to stages: 1..15, 16..35, 36..55
        def map_stage(stage, start_idx, count):
            end_idx = start_idx + count
            order = 1
            for q in questions[start_idx:end_idx]:
                StageQuestion.objects.create(
                    stage=stage,
                    question=q,
                    order=order,
                    marks=1,
                    negative_marks=0,
                    time_limit_seconds=60,
                )
                order += 1

        map_stage(s1, 0, 15)
        map_stage(s2, 15, 20)
        map_stage(s3, 35, 20)

        print("✓ Seeded quiz, stages, questions & mappings")
        print(f"Quiz: {quiz.id}")
        print(f"Stage1: {s1.id} [{s1.start_at} – {s1.end_at}] (15 Qs)")
        print(f"Stage2: {s2.id} [{s2.start_at} – {s2.end_at}] (20 Qs)")
        print(f"Stage3: {s3.id} [{s3.start_at} – {s3.end_at}] (20 Qs)")

    print("All done. (Celery beat/worker will auto-roll stages as time passes.)")
