from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, LoginOTP


class LoginOTPInline(admin.TabularInline):
    model = LoginOTP
    extra = 0
    can_delete = False
    readonly_fields = (
        "code", "expires_at", "created_at", "updated_at",
        "sent_count", "last_sent_at", "attempt_count", "is_used",
    )
    fields = readonly_fields


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username", "email", "role", "zone",
        "medical_id", "phone", "is_verified",
        "is_staff", "is_superuser", "is_active", "date_joined",
    )
    list_filter = ("role", "zone", "is_verified", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "medical_id", "phone", "first_name", "last_name")
    ordering = ("-date_joined",)
    inlines = [LoginOTPInline]

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {
            "fields": (
                "role", "medical_id", "phone", "zone",
                "medical_id_proof", "subspecialty", "is_verified", "avatar",
            )
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Profile", {
            "classes": ("wide",),
            "fields": ("role", "medical_id", "phone", "zone", "subspecialty", "is_verified"),
        }),
    )


@admin.register(LoginOTP)
class LoginOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "expires_at", "is_used", "sent_count", "attempt_count", "last_sent_at", "created_at")
    list_filter = ("is_used",)
    search_fields = ("user__username", "user__email", "code")
    readonly_fields = ("created_at", "updated_at")
