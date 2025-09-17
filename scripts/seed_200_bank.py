# seed_demo.py
import random
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from accounts.models import User, LoginOTP, PendingRegistration, RegistrationOTP
from exams.models import (
    Quiz, QuizStage, Question, QuestionOption, StageQuestion, StageRandomRule,
    AccessToken, QuizAttempt, QuizStageAttempt, AttemptAnswer, QuestionExposureLog,
    AntiCheatEventLog, ParticipationCertificate, LeaderboardEntry, StageAttemptItem,
    StageAdmission,
)
from common.enums import Zone, Difficulty, QuestionType

def _choices(enum):
    # Returns list of choice keys, e.g. ["NORTH","SOUTH",...]
    try:
        return [c[0] for c in enum.choices]
    except Exception:
        # fallback if it's a Python Enum
        try:
            return [e.value for e in enum]
        except Exception:
            return []

@transaction.atomic
def run():
    print("Seeding…")

    # ---------- 1) Wipe app data (keep learning tutorials) ----------
    # Delete children → parents to avoid FK headaches
    print("Deleting exam data (but NOT learning tutorials)…")
    StageAdmission.objects.all().delete()
    StageAttemptItem.objects.all().delete()
    LeaderboardEntry.objects.all().delete()
    ParticipationCertificate.objects.all().delete()
    AntiCheatEventLog.objects.all().delete()
    QuestionExposureLog.objects.all().delete()
    AttemptAnswer.objects.all().delete()
    QuizStageAttempt.objects.all().delete()
    QuizAttempt.objects.all().delete()
    AccessToken.objects.all().delete()
    StageRandomRule.objects.all().delete()
    StageQuestion.objects.all().delete()
    QuestionOption.objects.all().delete()
    Question.objects.all().delete()
    Quiz.objects.all().delete()

    print("Deleting auth OTP / pending registrations…")
    LoginOTP.objects.all().delete()
    RegistrationOTP.objects.all().delete()
    PendingRegistration.objects.all().delete()

    print("Deleting users…")
    User.objects.all().delete()

    # ---------- 2) Create users ----------
    zones = _choices(Zone) or ["WEST", "EAST", "NORTH", "SOUTH"]
    def z(i): return zones[i % len(zones)]

    users = []

    # 1 admin
    admin = User.objects.create(
        username="admin",
        email="admin@example.com",
        phone="+910000000001",
        medical_id="M-0001",
        zone=z(0),
        role=User.Roles.ADMIN,
        is_staff=True, is_superuser=True, is_verified=True,
    )
    admin.set_password("123"); admin.save()
    users.append(admin)

    for i in range(2):
        u = User.objects.create(
            username=f"teacher{i+1}",
            email=f"teacher{i+1}@example.com",
            phone=f"+91000000010{i+1}",
            medical_id=f"T-000{i+1}",
            zone=z(i+1),
            role=User.Roles.TEACHER,
            is_verified=True,
        )
        u.set_password("123"); u.save()
        users.append(u)

    # 8 students
    for i in range(8):
        u = User.objects.create(
            username=f"student{i+1}",
            email=f"student{i+1}@example.com",
            phone=f"+91000000020{i+1}",
            medical_id=f"S-000{i+1}",
            zone=z(i+3),
            role=User.Roles.STUDENT,
            is_verified=True,
        )
        u.set_password("123"); u.save()
        users.append(u)

    print(f"Created users: {len(users)}")

    # ---------- 3) Create 200 questions ----------
    print("Creating 200 questions…")
    diffs = [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD]
    q_objs = []
    for i in range(1, 201):
        # distribute difficulty roughly
        if i <= 100:
            diff = Difficulty.EASY
        elif i <= 160:
            diff = Difficulty.MEDIUM
        else:
            diff = Difficulty.HARD

        q = Question.objects.create(
            text=f"Sample question {i}: What is the answer?",
            explanation=f"Explanation for question {i}.",
            question_type=QuestionType.SINGLE_CHOICE,
            time_limit_seconds=90 + (i % 4) * 15,
            subspecialty="General",
            difficulty=diff,
            region_hint=z(i),
            marks=1,
            negative_marks=0,
            is_active=True,
            tags={"topic": "demo", "idx": i},
        )
        # 4 options, one correct
        correct_idx = i % 4
        for k, label in enumerate(["A", "B", "C", "D"], start=1):
            QuestionOption.objects.create(
                question=q,
                text=f"Option {label} for Q{i}",
                is_correct=(k-1 == correct_idx),
                order=k
            )
        q_objs.append(q)
    print("Questions ready.")

    # ---------- 4) Create 1 active quiz with 3 stages ----------
    print("Creating quiz + stages…")
    now = timezone.now()
    quiz = Quiz.objects.create(
        title="Demo Mega Quiz",
        slug=f"demo-quiz-{int(now.timestamp())}",
        description="Autogenerated demo quiz.",
        is_active=True,
        subspecialty="General",
        # make counts consistent with a 30-Q quiz (sum MUST equal question_count)
        easy_count=12, medium_count=10, hard_count=8,
        question_count=30,
        start_at=now,
        end_at=now + timedelta(hours=2),
        duration_seconds=3600,
        pass_threshold_percent=60,
        max_attempts_per_user=1,
        shuffle_questions=True,
        shuffle_options=True,
        require_fullscreen=False,
        lock_on_tab_switch=False,
        results_visible_after_close=False,
    )

    # 3 stages, each with its own question_count
    s1 = QuizStage.objects.create(quiz=quiz, title="Stage 1", order=1, question_count=10, is_current=True)
    s2 = QuizStage.objects.create(quiz=quiz, title="Stage 2", order=2, question_count=10)
    s3 = QuizStage.objects.create(quiz=quiz, title="Stage 3", order=3, question_count=10)

    # Optional random rules (broad — let your paper builder sample from bank)
    StageRandomRule.objects.create(stage=s1, count=10, difficulties=[], subspecialties=[], region_hints=[], tags_any=[])
    StageRandomRule.objects.create(stage=s2, count=10, difficulties=[], subspecialties=[], region_hints=[], tags_any=[])
    StageRandomRule.objects.create(stage=s3, count=10, difficulties=[], subspecialties=[], region_hints=[], tags_any=[])

    print("Done.\nSummary:")
    print(f"  Users: {User.objects.count()} (admin=1, teachers=2, students=8)")
    print(f"  Questions: {Question.objects.count()}")
    print(f"  Quiz: {quiz.title} (active={quiz.is_active}) with stages: {quiz.stages.count()}")

if __name__ == "__main__":
    run()
