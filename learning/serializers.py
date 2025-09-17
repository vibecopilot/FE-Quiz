# learning/serializers.py
from django.conf import settings
from rest_framework import serializers
from .models import Course, Enrollment
from rest_framework import serializers
from .models import Tutorial, TutorialProgress
User = settings.AUTH_USER_MODEL

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "owner", "title", "code", "description", "is_active", "created_at"]
        read_only_fields = ["owner", "created_at"]

class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = ["id", "user", "course", "status", "joined_at"]
        read_only_fields = ["user", "joined_at"]

class EnrollmentCreateSerializer(serializers.Serializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())




class TutorialSerializer(serializers.ModelSerializer):
    # Accept file on create/update
    video = serializers.FileField(write_only=True, required=True)
    # Return absolute URL for convenience
    video_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Tutorial
        fields = [
            "id", "title", "slug", "description",
            "video",         # write-only in API (upload)
            "video_url",     # read-only absolute URL
            "min_watch_seconds", "require_submit_click",
            "created_at", "updated_at",
        ]

    def get_video_url(self, obj):
        request = self.context.get("request")
        url = obj.video_url
        return request.build_absolute_uri(url) if request and url else url
    

class TutorialProgressSerializer(serializers.ModelSerializer):
    tutorial = TutorialSerializer(read_only=True)

    class Meta:
        model = TutorialProgress
        fields = [
            "id", "tutorial", "watched_seconds", "last_watched_at",
            "is_completed", "submitted_at", "completed_at"
        ]