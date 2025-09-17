# core/urls.py
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from rest_framework.routers import DefaultRouter

from exams.views import (
    QuestionViewSet, QuizViewSet, QuizStageViewSet, StageQuestionViewSet,
    StageRandomRuleViewSet, PaperView, AttemptStartView, StageAttemptStartView,
    AnswerSubmitView, StageSubmitView, AttemptSubmitView, LeaderboardTopView,
    AttemptPaperView, StageAttemptPaperView, LeaderboardZoneTopsView,
    StartQuizAndFetchView, StartStageAndGetQuestionsView, StartActiveQuizView,
    AntiCheatReportView, AntiCheatSummaryView, AnswerUpsertView ,MyStageAnswersView,StageLeaderboardView,StageAdmissionSelectTopsView,
    StageAdmissionListView,StartOpenQuizUnifiedView,BulkQuestionCreateAPIView
)



from learning.views import CourseViewSet, EnrollmentViewSet, TutorialViewSet

from accounts.views import (
    LoginStartView, LoginVerifyView, LoginAnyIdentifierView,
    RegisterStartView, RegisterVerifyView, RegisterCompleteView, RegisterResendView,
    UsersViewSet,AdminDashboardSummaryView,AdminDirectRegisterView,
    StageUserAnswersView,LoginEmailPasswordView
)

from exams.views_play_v2 import StartStageV2View, SubmitRoundV2View

router = DefaultRouter()
router.register(r"questions", QuestionViewSet, basename="question")

router.register(r"quizzes", QuizViewSet, basename="quiz")
router.register(r"stages", QuizStageViewSet, basename="quizstage")
router.register(r"stage-questions", StageQuestionViewSet, basename="stagequestion")  # ← as requested
router.register(r"stage-random-rules", StageRandomRuleViewSet, basename="stagerandomrule")

router.register(r"courses", CourseViewSet, basename="course")
router.register(r"enrollments", EnrollmentViewSet, basename="enrollment")
router.register(r"tutorials", TutorialViewSet, basename="tutorial")


router.register(r"users", UsersViewSet, basename="user")
router.register(r"stages/(?P<stage_id>[0-9a-f-]+)/users/(?P<user_id>[0-9a-f-]+)/answers",StageUserAnswersView, basename="stage-user-answers")


urlpatterns = [
    path('admin/', admin.site.urls),

    path("api/auth/register/admin", AdminDirectRegisterView.as_view()),

    path("api/auth/register/start/",    RegisterStartView.as_view(),    name="auth-register-start"),
    path("api/auth/register/verify/",   RegisterVerifyView.as_view(),   name="auth-register-verify"),
    path("api/auth/register/complete/", RegisterCompleteView.as_view(), name="auth-register-complete"),
    path("api/auth/register/resend/",   RegisterResendView.as_view(),   name="auth-register-resend"),

    path("api/auth/otp/start/",   LoginStartView.as_view(),   name="auth-otp-start"),
    path("api/auth/otp/verify/",  LoginVerifyView.as_view(),  name="auth-otp-verify"),
    path("api/auth/login/",       LoginAnyIdentifierView.as_view(), name="auth-login"),
    path("api/auth/login/email", LoginEmailPasswordView.as_view(), name="login-email-password"),
    path("api/anticheat/report/",  AntiCheatReportView.as_view()),
    path("api/anticheat/summary/", AntiCheatSummaryView.as_view()),

    path("questions/bulk/", BulkQuestionCreateAPIView.as_view(), name="questions-bulk-create"),
    path("api/stages/<uuid:stage_id>/admissions/select-tops/",StageAdmissionSelectTopsView.as_view(),name="stage-admissions-select-tops",),
    path("api/stages/<uuid:stage_id>/admissions/",StageAdmissionListView.as_view(),name="stage-admissions-list",),


    path("api/quiz/start/",        StartActiveQuizView.as_view()),
    path("api/answers/upsert/",    AnswerUpsertView.as_view(), name="answers-upsert"),
    path("api/start/open/", StartOpenQuizUnifiedView.as_view(), name="start-open-unified"),


    path("api/quizzes/<uuid:quiz_id>/start/", StartStageAndGetQuestionsView.as_view()),
    path("api/stage-attempts/<uuid:stage_attempt_id>/paper/", StageAttemptPaperView.as_view()),
    path("api/attempts/<uuid:attempt_id>/paper/", AttemptPaperView.as_view()),
    path("api/leaderboard/<uuid:quiz_id>/zones/", LeaderboardZoneTopsView.as_view()),
    path("api/quizzes/<uuid:quiz_id>/paper/", PaperView.as_view()),
    path("api/attempts/start/", AttemptStartView.as_view()),

    path("api/stage-attempts/start/", StageAttemptStartView.as_view()),
    path("api/attempts/start-and-fetch/", StartQuizAndFetchView.as_view()),

    path("api/attempts/submit/", AttemptSubmitView.as_view()),

    path("api/leaderboard/<uuid:quiz_id>/top/", LeaderboardTopView.as_view()),


    path("api/answers/submit/", AnswerSubmitView.as_view()),
    path("api/stage/submit/", StageSubmitView.as_view()),
    path("api/stages/<uuid:stage_id>/my-answers/", MyStageAnswersView.as_view(), name="my-stage-answers"),


    path("api/admin/summary/", AdminDashboardSummaryView.as_view()),

    path("api/leaderboard/stage/", StageLeaderboardView.as_view()),
    path("api/leaderboard/stage/<uuid:stage_id>/", StageLeaderboardView.as_view()),



# newwwww
    path("api/v2/start/", StartStageV2View.as_view(), name="v2-start-stage"),
    path("api/v2/rounds/<uuid:round_id>/submit/", SubmitRoundV2View.as_view(), name="v2-round-submit"),

    path("api/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
