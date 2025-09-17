# quiz/services/admissions.py
from __future__ import annotations
from typing import Optional
from accounts.models import User
# local imports kept inside the functions if you’re worried about import cycles


def admit_team_to_stage(stage, team, by_user: Optional[User] = None, meta=None):
    """Grant stage access to a TEAM (no duplicates thanks to unique constraint)."""
    from ..models import StageAdmission
    obj, created = StageAdmission.objects.get_or_create(
        stage=stage, team=team,
        defaults={"rule_code": "PROMOTE", "granted_by": by_user, "meta": meta or {}}
    )
    return obj, created

def admit_team_members_to_stage(stage, team, by_user: Optional[User] = None) -> int:
    """Explode a team into individual admissions for next INDIVIDUAL stage."""
    from ..models import StageAdmission, TeamMember
    uids = TeamMember.objects.filter(team=team).values_list("user_id", flat=True)
    rows = [
        StageAdmission(
            stage=stage,
            user_id=u,
            rule_code="TEAM_TOP",
            granted_by=by_user,
            meta={"team_id": str(team.id)},
        )
        for u in uids
    ]
    created = StageAdmission.objects.bulk_create(rows, ignore_conflicts=True)
    return len(created)
