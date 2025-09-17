# # learning/views.py
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from accounts.permissions import IsAdmin, IsTeacher, IsStudent, IsAdminOrReadOnly, IsAdminOrTeacher
from .models import Course, Enrollment
from .serializers import CourseSerializer, EnrollmentSerializer, EnrollmentCreateSerializer

User = get_user_model()

class CourseViewSet(viewsets.ModelViewSet):
    """
    Admin/Teacher can create/update courses; others read-only.
    """
    queryset = Course.objects.select_related().all()
    serializer_class = CourseSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        if not (IsAdmin().has_permission(self.request, self) or IsTeacher().has_permission(self.request, self)):
            raise PermissionDenied("Only admin or teacher can create courses.")
        serializer.save(owner=self.request.user)

class EnrollmentViewSet(viewsets.ModelViewSet):
    """
    Students self-enroll; Admin/Teacher can list/manage status.
    """
    queryset = Enrollment.objects.select_related("course").all()
    serializer_class = EnrollmentSerializer

    def get_permissions(self):
        if self.action in ["create", "destroy", "my"]:
            return [permissions.IsAuthenticated(),]
        if self.action in ["set_status"]:
            return [IsAdminOrTeacher()]
        return [permissions.IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        # Admin/Teacher see all; Student sees own
        if IsAdmin().has_permission(request, self) or IsTeacher().has_permission(request, self):
            qs = self.get_queryset()
        else:
            qs = self.get_queryset().filter(user=request.user)
        return Response(EnrollmentSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def my(self, request):
        """
        Current user's enrollments.
        (Aapke enrollments dikhata hai.)
        """
        qs = self.get_queryset().filter(user=request.user)
        return Response(EnrollmentSerializer(qs, many=True).data)

    def create(self, request, *args, **kwargs):
        """
        Student self-enrolls in a course.
        (Student khud course join karta hai.)
        """
        if not IsStudent().has_permission(request, self) and not IsAdmin().has_permission(request, self):
            # Allow admin to enroll users via POST if needed (by auth header user).
            raise PermissionDenied("Only students can self-enroll.")

        ser = EnrollmentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        course = ser.validated_data["course"]
        obj, created = Enrollment.objects.get_or_create(user=request.user, course=course)
        return Response(EnrollmentSerializer(obj).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="set-status")
    def set_status(self, request, pk=None):
        """
        Admin/Teacher can set status = ACTIVE/BLOCKED
        (Admin/Teacher status badal sakte: ACTIVE ya BLOCKED)
        """
        if not (IsAdmin().has_permission(request, self) or IsTeacher().has_permission(request, self)):
            raise PermissionDenied("Only admin/teacher can change status.")
        enroll = self.get_object()
        status_val = request.data.get("status")
        if status_val not in dict(Enrollment.Status.choices):
            return Response({"detail": f"Invalid status. Use one of {list(dict(Enrollment.Status.choices).keys())}"},
                            status=status.HTTP_400_BAD_REQUEST)
        enroll.status = status_val
        enroll.save(update_fields=["status"])
        return Response(EnrollmentSerializer(enroll).data)

# learning/views.py
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from exams.permissions import IsAdminOrReadOnly
from .models import Tutorial, TutorialProgress
from .serializers import TutorialSerializer, TutorialProgressSerializer


class TutorialViewSet(viewsets.ModelViewSet):
    queryset = Tutorial.objects.all()
    serializer_class = TutorialSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)  

    @action(detail=True, methods=["get"], url_path="my-progress", permission_classes=[permissions.IsAuthenticated])
    def my_progress(self, request, pk=None):
        tutorial = self.get_object()
        tp, _ = TutorialProgress.objects.get_or_create(user=request.user, tutorial=tutorial)
        return Response(TutorialProgressSerializer(tp).data)

    @action(detail=True, methods=["post"], url_path="report", permission_classes=[permissions.IsAuthenticated])
    def report(self, request, pk=None):
        """
        Body: { "watched_seconds": 85 }
        """
        tutorial = self.get_object()
        tp, _ = TutorialProgress.objects.get_or_create(user=request.user, tutorial=tutorial)
        tp.mark_progress(int(request.data.get("watched_seconds", 0)))
        tp.try_autocomplete()
        tp.save()
        return Response(TutorialProgressSerializer(tp).data, status=200)

    @action(detail=True, methods=["post"], url_path="complete", permission_classes=[permissions.IsAuthenticated])
    def complete(self, request, pk=None):
        """
        Marks 'submitted' and completes if threshold met.
        """
        tutorial = self.get_object()
        tp, _ = TutorialProgress.objects.get_or_create(user=request.user, tutorial=tutorial)
        tp.submit()
        tp.save()
        if not tp.is_completed:
            return Response(
                {"detail": f"Watch at least {tutorial.min_watch_seconds}s before submitting."},
                status=400
            )
        return Response(TutorialProgressSerializer(tp).data, status=200)

