from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import CaptchaView, CommentViewSet, RegisterView

router = SimpleRouter()
router.register("comments", CommentViewSet, basename="comment")

urlpatterns = [
    path("captcha/", CaptchaView.as_view()),
    path("auth/register/", RegisterView.as_view()),
    path("auth/token/", TokenObtainPairView.as_view()),
    path("auth/token/refresh/", TokenRefreshView.as_view()),
    path("", include(router.urls)),
]
