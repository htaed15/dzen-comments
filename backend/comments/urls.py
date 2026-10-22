from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import CaptchaView, CommentViewSet, MeView, ProfileView, RegisterView

router = SimpleRouter()
router.register("comments", CommentViewSet, basename="comment")

urlpatterns = [
    path("captcha/", CaptchaView.as_view()),
    path("auth/register/", RegisterView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("auth/token/", TokenObtainPairView.as_view()),
    path("auth/token/refresh/", TokenRefreshView.as_view()),
    path("users/<str:username>/", ProfileView.as_view()),
    path("", include(router.urls)),
]
