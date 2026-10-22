from html.parser import HTMLParser

import nh3


class HtmlValidationError(ValueError):
    """Теги в сообщении закрыты неправильно."""


class _TagChecker(HTMLParser):
    """Проверяет, что разрешённые теги правильно открыты и закрыты (валидный XHTML)."""

    def __init__(self, allowed):
        super().__init__(convert_charrefs=True)
        self.allowed = allowed
        self.stack = []
        self.error = None

    def handle_starttag(self, tag, attrs):
        if tag in self.allowed:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag in self.allowed and not self.error:
            self.error = f"Тег <{tag}/> должен иметь закрывающий тег </{tag}>"

    def handle_endtag(self, tag):
        if tag not in self.allowed or self.error:
            return
        if not self.stack or self.stack[-1] != tag:
            self.error = f"Неожиданный закрывающий тег </{tag}>"
        else:
            self.stack.pop()


class HtmlSanitizer:
    """Белый список HTML: <a href title>, <code>, <i>, <strong>. Всё остальное вырезается."""

    ALLOWED_TAGS = {"a", "code", "i", "strong"}
    ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}
    ALLOWED_SCHEMES = {"http", "https"}

    def validate_tags(self, text: str) -> None:
        checker = _TagChecker(self.ALLOWED_TAGS)
        checker.feed(text)
        checker.close()
        if checker.error:
            raise HtmlValidationError(checker.error)
        if checker.stack:
            raise HtmlValidationError(f"Не закрыт тег <{checker.stack[-1]}>")

    def clean(self, text: str) -> str:
        text = text.strip()
        self.validate_tags(text)
        return nh3.clean(
            text,
            tags=self.ALLOWED_TAGS,
            attributes=self.ALLOWED_ATTRIBUTES,
            url_schemes=self.ALLOWED_SCHEMES,
        ).strip()
