import random
from django.core.exceptions import ValidationError
from exams.models import Question, QuizStage, StageAttemptItem, StageQuestion

def pick_random_questions_for_stage(stage: QuizStage) -> list[int]:
    manual_ids = list(StageQuestion.objects
                      .filter(stage=stage)
                      .order_by("order")
                      .values_list("question_id", flat=True))
    if manual_ids:
        return manual_ids

    rule = getattr(stage, "random_rule", None)
    qs = Question.objects.filter(is_active=True)

    if rule:
        if rule.tags_any:
            qs = qs.filter(tags__overlap=rule.tags_any)
        if rule.difficulties:
            qs = qs.filter(difficulty__in=rule.difficulties)
        if rule.subspecialties:
            qs = qs.filter(subspecialty__in=rule.subspecialties)
        if rule.region_hints:
            qs = qs.filter(region_hint__in=rule.region_hints)

    need = stage.question_count or stage.quiz.question_count
    ids = list(qs.values_list("id", flat=True))
    if len(ids) < need:
        raise ValidationError("Not enough questions match the stage rule.")

    return random.sample(ids, need)
