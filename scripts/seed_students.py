# scripts/seed_students.py
from django.contrib.auth import get_user_model
from common.enums import Zone

def run(*args):
    User = get_user_model()

    # robust list of zone values (e.g., "NORTH", "SOUTH", ...)
    try:
        zone_values = [c[0] for c in getattr(Zone, "choices", [])] or [z.value for z in Zone]
    except Exception:
        zone_values = ["NORTH", "SOUTH", "EAST", "WEST"]

    created = 0
    touched = 0

    for i in range(10, 61):  # inclusive: 10..60
        username = f"student{i}"
        zone = zone_values[(i - 10) % len(zone_values)]
        defaults = {
            "role": "STUDENT",
            "zone": zone,
            "medical_id": f"MED-{i:05d}",
            "phone": f"900000{i:04d}",        # unique per user
            "email": f"{username}@example.com",
            "is_active": True,
        }
        user, created_now = User.objects.get_or_create(username=username, defaults=defaults)

        # keep it idempotent; fill missing required fields if an existing user lacks them
        changed = False
        if not created_now:
            if not user.zone:
                user.zone = zone; changed = True
            if not user.medical_id:
                user.medical_id = f"MED-{i:05d}"; changed = True
            if not user.phone:
                user.phone = f"900000{i:04d}"; changed = True
            if user.role != "STUDENT":
                user.role = "STUDENT"; changed = True

        user.set_password("123")
        user.save()  # saves password hash and any other changes

        created += 1 if created_now else 0
        touched += 0 if created_now else 1

    print(f"Done. Created: {created}, Updated existing: {touched}")
