import re

import nh3


class HtmlValidationError(ValueError):
    """Теги в сообщении не соответствуют правилам XHTML."""


# Любой тег: <name attrs>, </name>, <name attrs/>
TAG_RE = re.compile(r"<(?P<close>/?)(?P<name>[A-Za-z][A-Za-z0-9]*)(?P<attrs>(?:\s[^<>]*)?)(?P<self>/?)>")
# Один атрибут строго в виде  name="value"  (двойные кавычки обязательны)
ATTR_RE = re.compile(r'\s+(?P<key>[a-z]+)="(?P<value>[^"<>]*)"')
HREF_RE = re.compile(r"^https?://[^\s\"<>]+$")


class HtmlSanitizer:
    """Белый список HTML: <a href title>, <code>, <i>, <strong>.

    Проверка идёт регулярными выражениями и следит за правилами XHTML:
    имена тегов и атрибутов в нижнем регистре, значения атрибутов в двойных
    кавычках, у <a> обязателен href, каждый открытый тег закрыт в правильном порядке.
    Все остальные теги вырезает nh3.
    """

    ALLOWED_TAGS = {"a", "code", "i", "strong"}
    ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}
    ALLOWED_SCHEMES = {"http", "https"}

    def _check_attrs(self, tag: str, raw: str) -> None:
        allowed = self.ALLOWED_ATTRIBUTES.get(tag, set())
        rest = raw
        found = {}
        while rest.strip():
            m = ATTR_RE.match(rest)
            if not m:
                raise HtmlValidationError(
                    f"Тег <{tag}>: атрибуты должны быть в виде имя=\"значение\" в двойных кавычках, в нижнем регистре"
                )
            key, value = m.group("key"), m.group("value")
            if key not in allowed:
                raise HtmlValidationError(f"Тег <{tag}>: атрибут {key} не разрешён")
            if key in found:
                raise HtmlValidationError(f"Тег <{tag}>: атрибут {key} указан дважды")
            if not value.strip():
                raise HtmlValidationError(f"Тег <{tag}>: атрибут {key} не может быть пустым")
            found[key] = value
            rest = rest[m.end():]
        if tag == "a":
            if "href" not in found:
                raise HtmlValidationError("Тег <a> должен содержать атрибут href")
            if not HREF_RE.match(found["href"]):
                raise HtmlValidationError("Адрес в href должен начинаться с http:// или https://")

    def validate_tags(self, text: str) -> None:
        stack = []
        for m in TAG_RE.finditer(text):
            raw_name = m.group("name")
            tag = raw_name.lower()
            if tag not in self.ALLOWED_TAGS:
                continue  # чужие теги вырежет nh3
            if raw_name != tag:
                raise HtmlValidationError(f"Тег <{raw_name}> должен быть в нижнем регистре: <{tag}>")
            if m.group("self"):
                raise HtmlValidationError(f"Тег <{tag}/> должен иметь закрывающий тег </{tag}>")
            if m.group("close"):
                if m.group("attrs").strip():
                    raise HtmlValidationError(f"У закрывающего тега </{tag}> не может быть атрибутов")
                if not stack or stack[-1] != tag:
                    raise HtmlValidationError(f"Неожиданный закрывающий тег </{tag}>")
                stack.pop()
            else:
                self._check_attrs(tag, m.group("attrs"))
                stack.append(tag)
        if stack:
            raise HtmlValidationError(f"Не закрыт тег <{stack[-1]}>")

    def clean(self, text: str) -> str:
        text = text.strip()
        self.validate_tags(text)
        return nh3.clean(
            text,
            tags=self.ALLOWED_TAGS,
            attributes=self.ALLOWED_ATTRIBUTES,
            url_schemes=self.ALLOWED_SCHEMES,
        ).strip()
