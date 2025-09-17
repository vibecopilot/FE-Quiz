# exams/permissions.py
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

class AdminCanWrite_TeacherCanManageStageQuestion(BasePermission):
    """
    - Admin: full write
    - Teacher: write only on StageQuestion endpoints (view.attr allow_teacher_write=True)
    - Others: read-only
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if IsAdmin().has_permission(request, view):
            return True
        if getattr(view, "allow_teacher_write", False) and IsTeacher().has_permission(request, view):
            return True
        return False


