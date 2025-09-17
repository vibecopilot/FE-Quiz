# exams/tasks.py
from __future__ import annotations
from celery import shared_task
from django.db import transaction, IntegrityError
from django.utils import timezone

from .models import Quiz

def _stage_is_in_window(stage, now):
    """If a stage defines its own window, use it; otherwise fall back to quiz window."""
    if stage.start_at and stage.end_at:
        return stage.start_at <= now <= stage.end_at
    quiz = stage.quiz
    return quiz.start_at <= now <= quiz.end_at

def _pick_current_stage_for_quiz(quiz: Quiz, now):
    """
    Choose the 'current' stage for a quiz at 'now'.
    Priority:
      1) a stage flagged is_current=True and still in window
      2) a stage whose window includes now (earliest by order)
      3) fallback: first by order
    """
    stage = quiz.stages.filter(is_current=True).order_by("order").first()
    if stage and _stage_is_in_window(stage, now):
        return stage

    in_window = [s for s in quiz.stages.order_by("order") if _stage_is_in_window(s, now)]
    if in_window:
        return in_window[0]

    return quiz.stages.order_by("order").first()

def _switch_to_due_quiz(now) -> bool:
    """
    If ANY quiz window includes now, activate exactly one such quiz and set its chosen stage current.
    Returns True if a switch/activation happened, False otherwise.
    """
    candidate = (
        Quiz.objects
        .filter(start_at__lte=now, end_at__gte=now)  # window includes now
        .order_by("start_at", "id")
        .first()
    )
    if not candidate or not candidate.stages.exists():
        return False

    chosen = _pick_current_stage_for_quiz(candidate, now)
    if not chosen or not _stage_is_in_window(chosen, now):
        # if chosen isn't actually “live”, don't switch
        return False

    try:
        with transaction.atomic():
            # make this quiz the sole active one; set only the chosen stage current
            Quiz.objects.update(is_active=False)
            candidate.is_active = True
            candidate.save(update_fields=["is_active"])
            candidate.stages.update(is_current=False)
            chosen.is_current = True
            chosen.save(update_fields=["is_current"])
        return True
    except IntegrityError:
        return False

def _advance_active_quiz_if_needed(now):
    """
    Stage rollover policy (non-destructive):
    - Do NOT clear is_current on the last/ended stage just because it ended.
    - Only switch to the next stage when the next stage’s start time has arrived (now >= next.start_at).
    - If the active quiz is outside its window and some other quiz window includes now, switch to that quiz.
      Otherwise keep the current quiz active (non-destructive).
    """
    active = Quiz.objects.filter(is_active=True).first()
    if not active:
        return

    # If the active quiz window is over, try to switch to a quiz that is due now.
    if active.end_at and now > active.end_at:
        # Attempt non-destructive handoff to another due quiz
        switched = _switch_to_due_quiz(now)
        # If nothing is due yet, we keep the old quiz active (do nothing)
        return

    # Manage stages within the active quiz
    cur = active.stages.filter(is_current=True).order_by("order").first()
    if not cur:
        # Repair pointer: set a reasonable current stage
        new_cur = _pick_current_stage_for_quiz(active, now)
        if new_cur:
            with transaction.atomic():
                active.stages.update(is_current=False)
                new_cur.is_current = True
                new_cur.save(update_fields=["is_current"])
        return

    # If current stage is within its window → nothing to do
    if _stage_is_in_window(cur, now):
        return

    # Current stage is past its window; ONLY switch if the next stage has started
    nxt = active.stages.filter(order__gt=cur.order).order_by("order").first()
    if nxt and nxt.start_at and now >= nxt.start_at:
        with transaction.atomic():
            active.stages.update(is_current=False)
            nxt.is_current = True
            nxt.save(update_fields=["is_current"])
    # else: leave `cur.is_current=True` (non-destructive) until next stage actually starts

def _activate_due_quiz_if_needed(now):
    """
    Activation policy:
    - If there is already an active quiz within its window → nothing to do.
    - If there is an active quiz but it's outside its window → try to switch to a due quiz (non-destructive otherwise).
    - If there is NO active quiz → try to activate a due quiz.
    """
    active = Quiz.objects.filter(is_active=True).first()
    if active:
        if active.end_at and now > active.end_at:
            _switch_to_due_quiz(now)  # best-effort handoff
        return

    # No active quiz → try to activate a due one
    _switch_to_due_quiz(now)

@shared_task(bind=True, ignore_result=True)
def rollover_quizzes_and_stages(self):
    """
    Periodic task (safe to run every minute):
      1) Progress the active quiz’s stage ONLY when the next stage has actually started.
      2) Switch quizzes ONLY when another quiz window includes now; otherwise keep current active.
    """
    now = timezone.now()
    _advance_active_quiz_if_needed(now)
    _activate_due_quiz_if_needed(now)



# tasks.py
from celery import shared_task
from django.db.models import Sum, F
from .models import RoundAttempt, RoundAnswer, RoundAnswerStatus, QuizStage, Round, StageMode

@shared_task
def score_round_attempt_task(round_attempt_id: str):
    ra = RoundAttempt.objects.select_related("round").filter(id=round_attempt_id).first()
    if not ra: return
    # compute awarded marks per answer
    answers = list(RoundAnswer.objects.filter(round_attempt=ra).select_related("round_question","selected_round_option","selected_base_option"))
    total = 0
    for ans in answers:
        ans.compute_correctness_and_marks()
        ans.save(update_fields=["status","awarded_marks","updated_at"])
        total += float(ans.awarded_marks or 0)
    ra.obtained_marks = total
    # total marks = sum of question marks in that round
    full = Round.objects.filter(id=ra.round_id).values_list("round_questions__marks", flat=True)
    # fallback to question.marks when rq.marks is null
    rq_rows = ra.round.round_questions.select_related("question")
    ra.total_marks = sum(float(rq.marks if rq.marks is not None else rq.question.marks) for rq in rq_rows)
    ra.percent = (100.0 * float(ra.obtained_marks) / float(ra.total_marks or 1)) if ra.total_marks else 0
    ra.save(update_fields=["obtained_marks","total_marks","percent","updated_at"])

@shared_task
def score_stage_if_complete_task(stage_id: str, mode: str, actor_id: str):
    """
    If all active rounds for this actor are submitted, you can compute & persist a stage-level line,
    push leaderboard, etc. (skeleton left minimal intentionally)
    """
    stage = QuizStage.objects.filter(id=stage_id).first()
    if not stage: return
    rounds = list(stage.rounds.filter(is_active=True).values_list("id", flat=True))
    if not rounds: return
    if mode == "TEAM":
        submitted = RoundAttempt.objects.filter(round_id__in=rounds, team_id=actor_id, status="SUBMITTED").count()
    else:
        submitted = RoundAttempt.objects.filter(round_id__in=rounds, user_id=actor_id, status="SUBMITTED").count()
    if submitted == len(rounds):
        # TODO: aggregate to a StageAttempt/Leaderboard row if you keep one for TEAM flow.
        pass


