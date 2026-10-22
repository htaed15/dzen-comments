import io
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from comments.models import Attachment, Author, Comment
from comments.services.captcha import CaptchaService
from comments.services.sanitizer import HtmlSanitizer, HtmlValidationError


class SanitizerTests(SimpleTestCase):
    def setUp(self):
        self.s = HtmlSanitizer()

    def test_allowed_tags_kept(self):
        out = self.s.clean('<strong>a</strong> <i>b</i> <code>c</code> <a href="https://x.com" title="t">l</a>')
        for part in ("<strong>a</strong>", "<i>b</i>", "<code>c</code>", 'href="https://x.com"'):
            self.assertIn(part, out)

    def test_script_and_js_links_removed(self):
        out = self.s.clean('<script>alert(1)</script><a href="javascript:alert(1)">x</a><img src=x onerror=alert(1)>')
        self.assertNotIn("<script", out)
        self.assertNotIn("javascript:", out)
        self.assertNotIn("onerror", out)

    def test_unclosed_tag_rejected(self):
        with self.assertRaises(HtmlValidationError):
            self.s.clean("<strong>abc")

    def test_wrong_nesting_rejected(self):
        with self.assertRaises(HtmlValidationError):
            self.s.clean("<i><strong>abc</i></strong>")


class ApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def captcha(self):
        key, _ = CaptchaService().issue()
        return key, cache.get(f"captcha:{key}")

    def payload(self, **extra):
        key, answer = self.captcha()
        data = {
            "user_name": "John1",
            "email": "john@example.com",
            "text": "Hello <strong>world</strong>",
            "captcha_key": key,
            "captcha_answer": answer,
        }
        data.update(extra)
        return data

    def post(self, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/api/comments/", data, format="multipart")

    def test_create_and_list(self):
        resp = self.post(self.payload())
        self.assertEqual(resp.status_code, 201, resp.content)
        listing = self.client.get("/api/comments/").json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["results"][0]["user_name"], "John1")
        author = Author.objects.get()
        self.assertTrue(author.ip_address)

    def test_wrong_captcha(self):
        resp = self.post(self.payload(captcha_answer="nope"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("captcha_answer", resp.json())

    def test_captcha_is_single_use(self):
        data = self.payload()
        self.assertEqual(self.post(data).status_code, 201)
        self.assertEqual(self.post(data).status_code, 400)

    def test_invalid_user_name(self):
        resp = self.post(self.payload(user_name="bad name!"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("user_name", resp.json())

    def test_unclosed_tag_rejected(self):
        resp = self.post(self.payload(text="<strong>oops"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("text", resp.json())

    def test_xss_stripped(self):
        resp = self.post(self.payload(text='hi<script>alert(1)</script>'))
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn("<script", resp.json()["text"])

    def test_reply_tree(self):
        root = self.post(self.payload()).json()
        child = self.post(self.payload(text="reply", parent=root["id"])).json()
        self.post(self.payload(text="grandchild", parent=child["id"]))
        listing = self.client.get("/api/comments/").json()
        self.assertEqual(listing["count"], 1)  # в таблице только заглавные
        reply = listing["results"][0]["replies"][0]
        self.assertEqual(reply["text"], "reply")
        self.assertEqual(reply["replies"][0]["text"], "grandchild")

    def test_pagination_25_and_lifo(self):
        author = Author.objects.create(user_name="A", email="a@a.com", ip_address="127.0.0.1")
        for i in range(30):
            Comment.objects.create(author=author, text=f"c{i}")
        page1 = self.client.get("/api/comments/").json()
        page2 = self.client.get("/api/comments/?page=2").json()
        self.assertEqual(len(page1["results"]), 25)
        self.assertEqual(len(page2["results"]), 5)
        self.assertEqual(page1["results"][0]["text"], "c29")  # новые сверху

    def test_sorting(self):
        for name in ("Bob", "Alice"):
            a = Author.objects.create(user_name=name, email=f"{name}@x.com", ip_address="127.0.0.1")
            Comment.objects.create(author=a, text=name)
        asc = self.client.get("/api/comments/?ordering=user_name").json()["results"]
        desc = self.client.get("/api/comments/?ordering=-user_name").json()["results"]
        self.assertEqual(asc[0]["user_name"], "Alice")
        self.assertEqual(desc[0]["user_name"], "Bob")

    def test_bad_ordering_falls_back(self):
        resp = self.client.get("/api/comments/?ordering=author__user__password")
        self.assertEqual(resp.status_code, 200)

    def test_preview(self):
        resp = self.client.post("/api/comments/preview/", {"text": "<i>x</i><script>1</script>"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["html"], "<i>x</i>")

    def test_big_image_is_resized(self):
        buf = io.BytesIO()
        Image.new("RGB", (800, 600), "red").save(buf, "PNG")
        upload = SimpleUploadedFile("big.png", buf.getvalue(), content_type="image/png")
        resp = self.post(self.payload(file=upload))
        self.assertEqual(resp.status_code, 201, resp.content)
        att = Attachment.objects.get()
        att.refresh_from_db()
        self.assertEqual(att.status, "ready")
        with Image.open(att.file.path) as img:
            self.assertLessEqual(img.width, 320)
            self.assertLessEqual(img.height, 240)

    def test_text_file_too_large(self):
        upload = SimpleUploadedFile("big.txt", b"a" * (101 * 1024), content_type="text/plain")
        resp = self.post(self.payload(file=upload))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("file", resp.json())

    def test_wrong_file_type(self):
        upload = SimpleUploadedFile("evil.exe", b"MZ", content_type="application/octet-stream")
        resp = self.post(self.payload(file=upload))
        self.assertEqual(resp.status_code, 400)

    def test_jwt_user_skips_captcha(self):
        reg = self.client.post(
            "/api/auth/register/",
            {"username": "alice1", "email": "alice@example.com", "password": "S3cure-pass-77"},
            format="json",
        )
        self.assertEqual(reg.status_code, 201, reg.content)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + reg.json()["access"])
        resp = self.post({"text": "no captcha needed"})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["user_name"], "alice1")
