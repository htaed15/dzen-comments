import os

from PIL import Image, ImageSequence


class AttachmentError(ValueError):
    pass


class AttachmentValidator:
    """Проверка загружаемого файла: картинка JPG/GIF/PNG или текст TXT до 100 КБ."""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".gif", ".png"}
    IMAGE_FORMATS = {"JPEG", "GIF", "PNG"}
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    MAX_TEXT_BYTES = 100 * 1024
    MAX_PIXELS = 25_000_000  # защита от «бомб»: маленький файл, который разворачивается в огромную картинку

    def validate(self, uploaded) -> str:
        """Возвращает вид вложения: 'image' или 'text'."""
        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext in self.IMAGE_EXTENSIONS:
            self._check_image(uploaded)
            return "image"
        if ext == ".txt":
            self._check_text(uploaded)
            return "text"
        raise AttachmentError("Допустимые файлы: JPG, GIF, PNG или TXT")

    def _check_image(self, uploaded):
        if uploaded.size > self.MAX_IMAGE_BYTES:
            raise AttachmentError("Изображение слишком большое (максимум 5 МБ)")
        uploaded.seek(0)
        try:
            with Image.open(uploaded) as img:
                fmt = img.format
                if img.width * img.height > self.MAX_PIXELS:
                    raise AttachmentError("Изображение слишком большое по размерам")
                img.verify()
        except AttachmentError:
            raise
        except Exception:
            raise AttachmentError("Файл не является корректным изображением")
        finally:
            uploaded.seek(0)
        if fmt not in self.IMAGE_FORMATS:
            raise AttachmentError("Допустимые форматы изображений: JPG, GIF, PNG")

    def _check_text(self, uploaded):
        if uploaded.size > self.MAX_TEXT_BYTES:
            raise AttachmentError("Текстовый файл не должен быть больше 100 КБ")
        uploaded.seek(0)
        data = uploaded.read()
        uploaded.seek(0)
        if b"\x00" in data:
            raise AttachmentError("Файл не является текстовым")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise AttachmentError("Текстовый файл должен быть в кодировке UTF-8")


class AttachmentProcessor:
    """Фоновая обработка (Celery): пропорциональное уменьшение картинок до 320x240."""

    MAX_SIZE = (320, 240)

    def process(self, attachment) -> None:
        if attachment.kind == "image":
            self._resize(attachment.file.path)

    def _resize(self, path: str) -> None:
        with Image.open(path) as img:
            fmt = img.format
            if img.width <= self.MAX_SIZE[0] and img.height <= self.MAX_SIZE[1]:
                return
            if fmt == "GIF" and getattr(img, "n_frames", 1) > 1:
                self._resize_animated_gif(img, path)
                return
            img.load()
            resized = img.copy()
        resized.thumbnail(self.MAX_SIZE, Image.LANCZOS)  # сохраняет пропорции
        save_kwargs = {"quality": 90} if fmt == "JPEG" else {}
        resized.save(path, format=fmt, **save_kwargs)

    def _resize_animated_gif(self, img, path: str) -> None:
        """Уменьшает каждый кадр анимации, сохраняя задержки и повтор."""
        frames, durations = [], []
        for frame in ImageSequence.Iterator(img):
            durations.append(frame.info.get("duration", 100))
            small = frame.convert("RGBA")
            small.thumbnail(self.MAX_SIZE, Image.LANCZOS)
            frames.append(small)
        frames[0].save(
            path,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=img.info.get("loop", 0),
            disposal=2,
        )
