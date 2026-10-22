import ipaddress

from django.core.cache import cache
from django.db.models import Case, CharField, F, Value, When
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .events import get_version
from .models import Comment, Profile
from .serializers import (
    ANONYMOUS_NAME,
    CommentCreateSerializer,
    CommentSerializer,
    PreviewSerializer,
    ProfileCommentSerializer,
    ProfileSerializer,
    RegisterSerializer,
)
from .services.captcha import CaptchaService

# Белый список полей сортировки: защита от подстановки произвольных полей в ORDER BY.
# Для анонимных комментариев сортируем по отображаемому имени, чтобы порядок
# в списке не выдавал настоящее имя автора.
ORDERING_FIELDS = {
    "user_name": "sort_name",
    "email": "sort_email",
    "created_at": "created_at",
}
DEFAULT_ORDERING = "-created_at"  # LIFO
CACHE_TTL = 60


def sort_annotations():
    return {
        "sort_name": Lower(
            Case(
                When(is_anonymous=True, then=Value(ANONYMOUS_NAME)),
                default=F("profile__username"),
                output_field=CharField(),
            )
        ),
        "sort_email": Lower(
            Case(
                When(is_anonymous=True, then=Value("")),
                default=F("profile__email"),
                output_field=CharField(),
            )
        ),
    }


def normalize_ordering(raw):
    raw = raw or DEFAULT_ORDERING
    field = raw.lstrip("-")
    if field not in ORDERING_FIELDS:
        return DEFAULT_ORDERING
    return ("-" if raw.startswith("-") else "") + field


def db_ordering(ordering):
    desc = ordering.startswith("-")
    column = ORDERING_FIELDS[ordering.lstrip("-")]
    return [("-" if desc else "") + column, "-id" if desc else "id"]


def client_ip(request):
    candidates = []
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        candidates.append(forwarded.split(",")[0].strip())
    candidates.append(request.META.get("REMOTE_ADDR", ""))
    for value in candidates:
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            continue
    return "0.0.0.0"


def build_tree(roots, descendants):
    """Собирает дерево ответов в памяти: один запрос на всю страницу, без N+1."""
    nodes = {c.id: c for c in roots}
    for c in roots:
        c.children = []
    for d in descendants:
        d.children = []
        nodes[d.id] = d
    for d in descendants:  # descendants отсортированы по дате, родитель всегда раньше
        nodes[d.parent_id].children.append(d)
    return roots


class CommentPagination(PageNumberPagination):
    page_size = 25

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.page_size,
                "total_pages": self.page.paginator.num_pages,
                "results": data,
            }
        )


class CommentViewSet(viewsets.GenericViewSet):
    pagination_class = CommentPagination

    def list(self, request):
        ordering = normalize_ordering(request.query_params.get("ordering"))
        page_no = request.query_params.get("page", "1")
        if not page_no.isdigit():
            page_no = "1"

        cache_key = f"comments:list:{get_version()}:{ordering}:{page_no}"
        data = cache.get(cache_key)
        if data is None:
            roots_qs = (
                Comment.objects.filter(parent__isnull=True)
                .select_related("profile")
                .prefetch_related("attachments")
                .annotate(**sort_annotations())
                .order_by(*db_ordering(ordering))
            )
            roots = list(self.paginate_queryset(roots_qs))
            descendants = list(
                Comment.objects.filter(root__in=roots)
                .select_related("profile")
                .prefetch_related("attachments")
                .order_by("created_at", "id")
            )
            build_tree(roots, descendants)
            data = self.get_paginated_response(CommentSerializer(roots, many=True).data).data
            cache.set(cache_key, data, CACHE_TTL)
        return Response(data)

    def create(self, request):
        serializer = CommentCreateSerializer(
            data=request.data, context={"request": request, "ip": client_ip(request)}
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def preview(self, request):
        """Предпросмотр без перезагрузки: тот же санитайзер, что и при сохранении."""
        serializer = PreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"html": serializer.validated_data["text"]})

    @action(detail=True, methods=["get"])
    def thread(self, request, pk=None):
        """Вся ветка, в которой написан комментарий; focus: комментарий, к которому пришли."""
        comment = get_object_or_404(Comment.objects.select_related("root"), pk=pk)
        root_id = comment.root_id or comment.pk
        root = (
            Comment.objects.select_related("profile")
            .prefetch_related("attachments")
            .get(pk=root_id)
        )
        descendants = list(
            Comment.objects.filter(root_id=root_id)
            .select_related("profile")
            .prefetch_related("attachments")
            .order_by("created_at", "id")
        )
        build_tree([root], descendants)
        return Response({"focus": comment.pk, "root": CommentSerializer(root).data})


class CaptchaView(APIView):
    def get(self, request):
        key, image = CaptchaService().issue_as_data_url()
        response = Response({"key": key, "image": image})
        response["Cache-Control"] = "no-store"
        return response


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        refresh = RefreshToken.for_user(profile.user)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh), "username": profile.username},
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    """Данные своего профиля: ими форма заполняет поля 1-3 автоматически."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            return Response({"detail": "У аккаунта нет профиля"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProfileSerializer(profile).data)


class ProfileView(APIView):
    """Публичный профиль: только неанонимные комментарии пользователя."""

    def get(self, request, username):
        profile = get_object_or_404(Profile, username__iexact=username)
        queryset = (
            Comment.objects.filter(profile=profile, is_anonymous=False)
            .order_by("-created_at", "-id")
        )
        paginator = CommentPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        response = paginator.get_paginated_response(ProfileCommentSerializer(page, many=True).data)
        response.data["profile"] = {
            "username": profile.username,
            # у гостя Home page публично не раскрываем: он мог скрыть его в комментариях
            "home_page": profile.home_page if profile.is_registered else "",
            "registered": profile.is_registered,
            "joined": profile.created_at,
        }
        return response
