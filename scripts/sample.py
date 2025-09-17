from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from common.enums import Zone, Difficulty, QuestionType
from learning.models import Course, Enrollment, Tutorial, TutorialProgress
from exams.models import Question, QuestionOption, Quiz, QuizStage, StageRandomRule
from accounts.models import User
U = User

# ---------------- Users (4 total: 2 students, 1 teacher, 1 admin) ----------------
def ensure_user(username, email, password, role, medical_id, phone, zone, is_staff=False, is_superuser=False):
    user, created = U.objects.get_or_create(username=username, defaults={
        "email": email,
        "role": role,
        "medical_id": medical_id,
        "phone": phone,
        "zone": zone,
        "is_staff": is_staff,
        "is_superuser": is_superuser,
    })
    if created or not user.check_password(password):
        user.set_password(password)
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save()
    return user

admin  = ensure_user("admin",  "admin@example.com",  "Admin@123",  U.Roles.ADMIN,   "ADM001", "9000000001", Zone.NORTH,  is_staff=True, is_superuser=True)
teach  = ensure_user("teacher","teacher@example.com","Teach@123",  U.Roles.TEACHER, "TCH001", "9000000002", Zone.WEST)
stud1  = ensure_user("alice",  "alice@example.com",  "Stud@123",   U.Roles.STUDENT, "STU001", "9000000003", Zone.SOUTH)
stud2  = ensure_user("bob",    "bob@example.com",    "Stud@123",   U.Roles.STUDENT, "STU002", "9000000004", Zone.EAST)

print("Users:", admin.username, teach.username, stud1.username, stud2.username)

# ---------------- Course & Enrollments ----------------
course, _ = Course.objects.get_or_create(
    owner=teach,
    code="demo-course",
    defaults={"title": "Demo Course", "description": "Sample course for seeding."}
)

Enrollment.objects.get_or_create(user=stud1, course=course)
Enrollment.objects.get_or_create(user=stud2, course=course)
print("Course created:", course.title)

# ---------------- Tutorial & mark students completed ----------------
tutorial, _ = Tutorial.objects.get_or_create(
    slug="safety-briefing",
    defaults={
        "title": "Safety & Fair Play Briefing",
        "description": "Watch this before starting any quiz.",
        "video_url": "https://example.com/video.mp4",
        "min_watch_seconds": 30,
        "require_submit_click": True,
    }
)

def complete_tutorial(user):
    tp, _ = TutorialProgress.objects.get_or_create(user=user, tutorial=tutorial)
    tp.watched_seconds = max(tp.watched_seconds, tutorial.min_watch_seconds)
    tp.submit()
    tp.save()

complete_tutorial(stud1)
complete_tutorial(stud2)
print("Tutorial created and completed by both students:", tutorial.title)

# ---------------- Global Question Bank ----------------
def make_q(text, diff=Difficulty.MEDIUM, marks=1, neg=0.25, tag=None):
    q, _ = Question.objects.get_or_create(
        text=text,
        defaults={
            "explanation": "Because reasons.",
            "question_type": QuestionType.SINGLE_CHOICE,
            "subspecialty": "general",
            "difficulty": diff,
            "region_hint": "",  # or Zone.NORTH, etc., if you want
            "marks": marks,
            "negative_marks": neg,
            "time_limit_seconds": 60,
            "is_active": True,
            "tags": {"topic": tag} if tag else {},
        }
    )
    if q.options.count() == 0:
        QuestionOption.objects.bulk_create([
            QuestionOption(question=q, text="Option A (correct)", is_correct=True,  order=1),
            QuestionOption(question=q, text="Option B",           is_correct=False, order=2),
            QuestionOption(question=q, text="Option C",           is_correct=False, order=3),
            QuestionOption(question=q, text="Option D",           is_correct=False, order=4),
        ])
    return q

bank = []
bank += [make_q(f"Easy Q{i}",   diff=Difficulty.EASY,   tag="easy")   for i in range(1,6)]  # 5 easy
bank += [make_q(f"Medium Q{i}", diff=Difficulty.MEDIUM, tag="medium") for i in range(1,4)]  # 3 medium
bank += [make_q(f"Hard Q{i}",   diff=Difficulty.HARD,   tag="hard")   for i in range(1,3)]  # 2 hard
print("Question bank size:", len(bank))

# ---------------- Two Quizzes, each with 2 stages, stage #1 is_current ----------------
now = timezone.now()
win_start = now - timedelta(days=1)
win_end   = now + timedelta(days=7)

def make_quiz(slug, title, easy, med, hard, qcount, prereq_tutorial=None):
    quiz, _ = Quiz.objects.get_or_create(
        slug=slug,
        defaults={
            "title": title,
            "description": "Seeded quiz",
            "subspecialty": "general",
            "easy_count": easy,
            "medium_count": med,
            "hard_count": hard,
            "start_at": win_start,
            "end_at": win_end,
            "duration_seconds": 1800,
            "pass_threshold_percent": 60,
            "max_attempts_per_user": 1,
            "question_count": qcount,
            "shuffle_questions": True,
            "shuffle_options": True,
            "require_fullscreen": True,
            "lock_on_tab_switch": True,
            "prerequisite_tutorial": prereq_tutorial,
        }
    )
    # stages
    s1, _ = QuizStage.objects.get_or_create(quiz=quiz, order=1, defaults={"title": "Stage 1", "description": "Round 1", "is_current": True})
    s2, _ = QuizStage.objects.get_or_create(quiz=quiz, order=2, defaults={"title": "Stage 2", "description": "Round 2", "is_current": False})

    # enforce stage1 as current
    QuizStage.objects.filter(quiz=quiz, is_current=True).exclude(pk=s1.pk).update(is_current=False)
    s1.refresh_from_db()

    # random rules (filters only; quotas come from quiz-level easy/med/hard)
    StageRandomRule.objects.get_or_create(stage=s1, defaults={
        "count": qcount, "tags_any": [], "difficulties": [], "subspecialties": [], "region_hints": []
    })
    StageRandomRule.objects.get_or_create(stage=s2, defaults={
        "count": qcount, "tags_any": [], "difficulties": [], "subspecialties": [], "region_hints": []
    })

    return quiz, s1, s2

quiz1, q1s1, q1s2 = make_quiz(
    slug="quiz-alpha",
    title="Quiz Alpha",
    easy=3, med=2, hard=1, qcount=6,
    prereq_tutorial=tutorial,
)

# quiz2: 8 questions per attempt: 4 easy, 3 medium, 1 hard
quiz2, q2s1, q2s2 = make_quiz(
    slug="quiz-beta",
    title="Quiz Beta",
    easy=4, med=3, hard=1, qcount=8,
    prereq_tutorial=tutorial,
)

print("Quizzes created:", quiz1.title, "and", quiz2.title)
print("Stage current flags:", quiz1.current_stage.title, "|", quiz2.current_stage.title)
print("Done.")
