# views_play_v2.py
from django.db import transaction
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import (Quiz, QuizStage, StageMode, StageAdmission, TeamMember, Team,
                     Round, RoundQuestion, RoundOption, QuestionOption, RoundAttempt,
                     RoundAttemptStatus)
from .serializers_play import PublicRoundSerializer
from .utils_rounds import deterministic_shuffle

class StartStageV2View(APIView):
    """
    POST /api/v2/start/
    Body (optional):
      { "team_id": "<uuid>" }  # required only for TEAM stage if user belongs to multiple active teams
    """
    permission_classes = [IsAuthenticated]

    # --- admissions + actor ---
    def _resolve_actor_and_check_admission(self, request, quiz: Quiz, stage: QuizStage):
        if stage.mode == StageMode.INDIVIDUAL:
            # admission: by user (or open)
            if stage.requires_admission:
                ok = StageAdmission.objects.filter(stage=stage, user=request.user).exists()
                if not ok:
                    raise PermissionDenied("You are not admitted to this stage.")
            return "INDIVIDUAL", {"user_id": str(request.user.id)}, None

        # TEAM mode
        # pick team
        team_id = request.data.get("team_id")
        tm_qs = TeamMember.objects.select_related("team").filter(
            user=request.user, team__quiz=quiz, team__is_active=True
        )
        if team_id:
            tm = tm_qs.filter(team_id=team_id).first()
            if not tm:
                raise PermissionDenied("You are not a member of this active team.")
        else:
            tm = tm_qs.order_by("created_at").first()
            if not tm:
                raise PermissionDenied("Active team membership required.")

        # admission: either explicit TEAM admission, or USER admission also permits the team (fallback)
        if stage.requires_admission:
            ok = StageAdmission.objects.filter(Q(stage=stage, team=tm.team) | Q(stage=stage, user=request.user)).exists()
            if not ok:
                raise PermissionDenied("This team is not admitted to this stage.")

        return "TEAM", {"team_id": str(tm.team_id), "team_name": tm.team.name}, tm.team

    # --- options builder (no correctness) ---
    def _options_for(self, rq: RoundQuestion):
        ros = list(rq.options.all().order_by("order", "id"))
        if ros:
            out = []
            for ro in ros:
                out.append({
                    "round_option_id": str(ro.id),
                    "base_option_id": str(ro.base_option_id) if ro.base_option_id else None,
                    "text": ro.effective_text(),
                    "image": (ro.image.url if ro.image else None),
                    "audio": (ro.audio.url if ro.audio else None),
                    "video": (ro.video.url if ro.video else None),
                    "order": ro.order,
                })
            return out
        # fallback to base options
        bos = list(QuestionOption.objects.filter(question=rq.question).order_by("order","id"))
        return [{
            "round_option_id": None, "base_option_id": str(b.id),
            "text": b.text, "image": None, "audio": None, "video": None, "order": b.order
        } for b in bos]

    def _media_for(self, rq: RoundQuestion):
        return {
            "image": rq.prompt_image.url if rq.prompt_image else None,
            "audio": rq.prompt_audio.url if rq.prompt_audio else None,
            "video": rq.prompt_video.url if rq.prompt_video else None,
            "caption": rq.caption or "",
            "autoplay": bool(rq.autoplay_media),
            "start_ms": int(rq.media_start_ms or 0),
            "duration_ms": int(rq.media_duration_ms) if rq.media_duration_ms is not None else None,
        }

    def _items_for_round(self, round_obj: Round):
        # assigned questions only; if fixed_order=False → deterministic shuffle for everyone
        rqs = list(RoundQuestion.objects.filter(round=round_obj)
                   .select_related("question").order_by("order","created_at","id"))
        if not rqs:
            return []

        if not round_obj.fixed_order:
            ids = [rq.id for rq in rqs]
            ids = deterministic_shuffle(ids, f"round:{round_obj.id}")
            id_to_rq = {rq.id: rq for rq in rqs}
            rqs = [id_to_rq[i] for i in ids]

        items, ordno = [], 1
        for rq in rqs:
            q = rq.question
            items.append({
                "order": ordno,
                "marks": float(rq.effective_marks()),
                "negative_marks": float(rq.effective_negative()),
                "time_limit_seconds": int(rq.effective_time()),
                "media": self._media_for(rq),
                "question": {
                    "id": str(q.id),
                    "text": q.text,
                    "question_type": q.question_type,
                    "time_limit_seconds": q.time_limit_seconds,
                },
                "options": self._options_for(rq) if round_obj.is_option else [],
            })
            ordno += 1
        return items

    def _next_round_to_play(self, stage: QuizStage, actor_mode: str, team: Team|None, user):
        rounds = list(stage.rounds.filter(is_active=True).order_by("order","created_at"))
        if not rounds:
            raise ValidationError("No rounds configured for this stage.")

        # find first not-submitted round attempt (actor-specific)
        for rnd in rounds:
            q = Q(round=rnd)
            if actor_mode == "TEAM":
                q &= Q(team=team)
            else:
                q &= Q(user=user)
            ra = RoundAttempt.objects.filter(q).first()
            if not ra or ra.status != RoundAttemptStatus.SUBMITTED:
                return rnd
        return None  # all done

    def post(self, request):
        # 1) active quiz + current stage
        quiz = Quiz.objects.filter(is_active=True).first()
        if not quiz:
            raise ValidationError("No active quiz.")
        stage = quiz.current_stage
        if not stage:
            raise ValidationError("No stage configured.")
        if not stage.is_in_window():
            raise ValidationError("Stage is not open now.")

        # 2) admission + actor
        mode, actor, team = self._resolve_actor_and_check_admission(request, quiz, stage)

        single_result = bool(getattr(stage, "SIngle_result", False))

        # 3) choose round
        if single_result:
            current = self._next_round_to_play(stage, mode, team, request.user)
            if not current:
                return Response({
                    "done": True,
                    "message": "All rounds submitted for this stage.",
                    "stage_id": str(stage.id),
                }, status=200)
            with transaction.atomic():
                # idempotent get/create
                ra_kwargs = dict(round=current)
                if mode == "TEAM":
                    ra_kwargs["team"] = team
                else:
                    ra_kwargs["user"] = request.user
                RoundAttempt.objects.get_or_create(**ra_kwargs)

            payload = {
                "quiz":  {"id": str(quiz.id), "title": quiz.title},
                "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order,
                          "mode": stage.mode, "requires_admission": bool(stage.requires_admission)},
                "actor": {"mode": mode, **actor},
                "single_result": True,
                "round": {
                    "id": str(current.id), "title": current.title, "order": current.order, "kind": current.kind
                },
                "items": self._items_for_round(current),
            }
            return Response(payload, status=200)

        # combined result after all rounds → serve first active (or next unattempted), but flag combined_result
        rounds = list(stage.rounds.filter(is_active=True).order_by("order","created_at"))
        if not rounds:
            raise ValidationError("No rounds configured for this stage.")
        current = self._next_round_to_play(stage, mode, team, request.user) or rounds[-1]
        with transaction.atomic():
            ra_kwargs = dict(round=current)
            if mode == "TEAM":
                ra_kwargs["team"] = team
            else:
                ra_kwargs["user"] = request.user
            RoundAttempt.objects.get_or_create(**ra_kwargs)

        return Response({
            "quiz":  {"id": str(quiz.id), "title": quiz.title},
            "stage": {"id": str(stage.id), "title": stage.title, "order": stage.order,
                      "mode": stage.mode, "requires_admission": bool(stage.requires_admission)},
            "actor": {"mode": mode, **actor},
            "single_result": False,                 # combined at the end
            "round": {"id": str(current.id), "title": current.title, "order": current.order, "kind": current.kind},
            "items": self._items_for_round(current),
        }, status=200)


# views_play_v2.py (cont.)
from rest_framework import status
from .tasks import score_round_attempt_task, score_stage_if_complete_task

class SubmitRoundV2View(APIView):
    """
    POST /api/v2/rounds/{round_id}/submit/
    Body: {
      "answers": [
        { "round_question_id":"...", "round_option_id":"..." }           # option round
        { "round_question_id":"...", "base_option_id":"..." }            # base option fallback
        { "round_question_id":"...", "answer_text":"..." }               # free-form
        { "round_question_id":"...", "answer_bool": true }               # free-form
        { "round_question_id":"...", "answer_number": 3.14 }             # free-form
      ]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, round_id):
        rnd = Round.objects.filter(id=round_id).select_related("stage","stage__quiz").first()
        if not rnd:
            raise ValidationError("Invalid round.")
        stage, quiz = rnd.stage, rnd.stage.quiz

        # actor
        mode, actor, team = StartStageV2View()._resolve_actor_and_check_admission(request, quiz, stage)

        # fetch/create attempt
        ra_q = Q(round=rnd)
        if mode == "TEAM":
            ra_q &= Q(team=team)
        else:
            ra_q &= Q(user=request.user)
        ra = RoundAttempt.objects.filter(ra_q).first()
        if not ra:
            raise ValidationError("Round not started.")
        if ra.status == RoundAttemptStatus.SUBMITTED:
            return Response({"detail":"Already submitted."}, status=status.HTTP_200_OK)

        # write answers (idempotent per round_question)
        incoming = request.data.get("answers") or []
        rq_map = {str(rq.id): rq for rq in rnd.round_questions.all()}
        from .models import RoundAnswer, RoundAnswerStatus

        bulk_new, to_update = [], []
        for row in incoming:
            rqid = str(row.get("round_question_id") or "")
            rq = rq_map.get(rqid)
            if not rq:
                continue
            ans = RoundAnswer.objects.filter(round_attempt=ra, round_question=rq).first()
            payload = dict(
                selected_round_option_id=row.get("round_option_id"),
                selected_base_option_id=row.get("base_option_id"),
                answer_text=row.get("answer_text") or "",
                answer_bool=row.get("answer_bool", None),
                answer_number=row.get("answer_number", None),
                status=RoundAnswerStatus.PENDING,
                final=True,
            )
            if ans:
                for k,v in payload.items(): setattr(ans, k, v)
                to_update.append(ans)
            else:
                bulk_new.append(RoundAnswer(round_attempt=ra, round_question=rq, **payload))

        if bulk_new:
            RoundAnswer.objects.bulk_create(bulk_new)
        for x in to_update:
            x.save(update_fields=[
                "selected_round_option","selected_base_option","answer_text","answer_bool","answer_number",
                "status","final","updated_at"
            ])

        # mark submit + async score
        ra.mark_submitted()
        ra.save(update_fields=["submitted_at","status","time_taken_seconds","updated_at"])
        score_round_attempt_task.delay(str(ra.id))

        # if combined result → maybe trigger stage score when all rounds done for this actor
        if not getattr(stage, "SIngle_result", False):
            score_stage_if_complete_task.delay(str(stage.id), "TEAM" if mode=="TEAM" else "INDIVIDUAL",
                                               str(team.id) if team else str(request.user.id))

        return Response({"detail": "Submitted.", "round_attempt_id": str(ra.id)}, status=200)
