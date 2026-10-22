import base64
import io
import random
import secrets

from django.core.cache import cache
from PIL import Image, ImageDraw, ImageFilter, ImageFont


class CaptchaService:
    """CAPTCHA из латинских букв и цифр. Ответ хранится в кеше (Redis), одноразовый."""

    ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без похожих символов (0/O, 1/I)
    LENGTH = 5
    TTL = 300

    @staticmethod
    def _cache_key(key: str) -> str:
        return f"captcha:{key}"

    def issue(self):
        rnd = random.SystemRandom()
        code = "".join(rnd.choice(self.ALPHABET) for _ in range(self.LENGTH))
        key = secrets.token_urlsafe(16)
        cache.set(self._cache_key(key), code, self.TTL)
        return key, self._render(code)

    def issue_as_data_url(self):
        key, png = self.issue()
        return key, "data:image/png;base64," + base64.b64encode(png).decode()

    def verify(self, key: str, answer: str) -> bool:
        if not key:
            return False
        code = cache.get(self._cache_key(key))
        cache.delete(self._cache_key(key))  # одноразовая
        return bool(code) and code.lower() == (answer or "").strip().lower()

    def _render(self, code: str) -> bytes:
        width, height = 170, 60
        rnd = random.Random()
        img = Image.new("RGB", (width, height), (243, 244, 248))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default(size=36)
        for _ in range(6):
            shade = rnd.randint(120, 200)
            draw.line(
                [(rnd.randint(0, width), rnd.randint(0, height)), (rnd.randint(0, width), rnd.randint(0, height))],
                fill=(shade, shade, shade + 20),
                width=2,
            )
        for i, ch in enumerate(code):
            draw.text(
                (12 + i * 30, rnd.randint(6, 14)),
                ch,
                font=font,
                fill=(rnd.randint(0, 90), rnd.randint(0, 90), rnd.randint(40, 140)),
            )
        for _ in range(150):
            draw.point((rnd.randint(0, width - 1), rnd.randint(0, height - 1)), fill=(40, 40, 60))
        img = img.filter(ImageFilter.SMOOTH)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
