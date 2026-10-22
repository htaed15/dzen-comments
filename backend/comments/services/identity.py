from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from ..models import Profile

USERNAME_TAKEN = "Имя пользователя занято"
EMAIL_BUSY = "Этот e-mail уже привязан к другому имени пользователя"


class IdentityError(Exception):
    """Конфликт имени или e-mail. kind: 'username' или 'email'."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


class IdentityService:
    """Правила владения именем и e-mail.

    * имя уникально без учёта регистра, e-mail привязан ровно к одному имени;
    * гость может писать под своим именем повторно, если указывает тот же e-mail;
    * имя зарегистрированного аккаунта гость использовать не может;
    * при регистрации с именем и e-mail гостевого профиля профиль закрепляется
      за аккаунтом вместе со всей историей комментариев.
    """

    def for_guest(self, username: str, email: str, home_page: str = "") -> Profile:
        email = email.lower()
        profile = self._by_username(username)
        if profile:
            if profile.user_id or profile.email.lower() != email:
                raise IdentityError("username", USERNAME_TAKEN)
            if home_page and not profile.home_page:
                profile.home_page = home_page
                profile.save(update_fields=["home_page"])
            return profile
        self._ensure_free(username, email)
        return self._create(username, email, home_page)

    def register(self, username: str, email: str, password: str, home_page: str = "") -> Profile:
        email = email.lower()
        profile = self._by_username(username)
        if profile:
            if profile.user_id or profile.email.lower() != email:
                raise IdentityError("username", USERNAME_TAKEN)
        else:
            self._ensure_free(username, email)
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(
                    username=profile.username if profile else username,
                    email=email,
                    password=password,
                )
                if profile:
                    profile.user = user
                    if home_page:
                        profile.home_page = home_page
                    profile.save(update_fields=["user", "home_page"])
                    return profile
                return Profile.objects.create(
                    user=user, username=username, email=email, home_page=home_page
                )
        except IntegrityError:
            raise self._diagnose(username)

    # ----- внутреннее -----

    @staticmethod
    def _by_username(username: str):
        return Profile.objects.filter(username__iexact=username).first()

    def _ensure_free(self, username: str, email: str) -> None:
        # Имена существующих аккаунтов без профиля (например, суперпользователя) тоже заняты.
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise IdentityError("username", USERNAME_TAKEN)
        if Profile.objects.filter(email__iexact=email).exists():
            raise IdentityError("email", EMAIL_BUSY)

    def _create(self, username: str, email: str, home_page: str) -> Profile:
        try:
            with transaction.atomic():
                return Profile.objects.create(username=username, email=email, home_page=home_page)
        except IntegrityError:
            raise self._diagnose(username)

    def _diagnose(self, username: str) -> IdentityError:
        # Гонка запросов: уникальность нарушена между проверкой и записью.
        if self._by_username(username):
            return IdentityError("username", USERNAME_TAKEN)
        return IdentityError("email", EMAIL_BUSY)
