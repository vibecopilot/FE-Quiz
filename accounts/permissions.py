# accounts/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS

def _role(user):
    return getattr(user, "role", None)

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (_role(request.user) == "ADMIN" or request.user.is_staff))

class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and _role(request.user) == "TEACHER")

class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and _role(request.user) == "STUDENT")

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return IsAdmin().has_permission(request, view)


from rest_framework import permissions

class IsAdminOrTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        role = getattr(request.user, "role", "")
        return bool(request.user and request.user.is_authenticated and role in ("ADMIN", "TEACHER"))


class IsAdminOrTeacher(BasePermission):
    def has_permission(self, request, view):
        return IsAdmin().has_permission(request, view) or IsTeacher().has_permission(request, view)
