# serializers_play.py
from rest_framework import serializers
from .models import Round, RoundQuestion, RoundOption, QuestionOption

class PublicOptionSerializer(serializers.Serializer):
    round_option_id = serializers.CharField(allow_null=True)
    base_option_id  = serializers.CharField(allow_null=True)
    text  = serializers.CharField()
    image = serializers.CharField(allow_null=True)
    audio = serializers.CharField(allow_null=True)
    video = serializers.CharField(allow_null=True)
    order = serializers.IntegerField()

class PublicQuestionItemSerializer(serializers.Serializer):
    order = serializers.IntegerField()
    marks = serializers.FloatField()
    negative_marks = serializers.FloatField()
    time_limit_seconds = serializers.IntegerField()
    media = serializers.DictField()
    question = serializers.DictField()
    options = PublicOptionSerializer(many=True)

class PublicRoundSerializer(serializers.Serializer):
    id    = serializers.CharField()
    title = serializers.CharField()
    order = serializers.IntegerField()
    kind  = serializers.CharField()
    items = PublicQuestionItemSerializer(many=True)
