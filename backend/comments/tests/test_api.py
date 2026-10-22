import io
import shutil
import tempfile

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from comments.models import Attachment, Comment, Profile
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


class BaseApiTest(TestCase):
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

    def captcha_fields(self):
        key, answer = self.captcha()
        return {"captcha_key": key, "captcha_answer": answer}

    def payload(self, **extra):
        data = {
            "user_name": "John1",
            "email": "john@example.com",
            "text": "Hello <strong>world</strong>",
            **self.captcha_fields(),
        }
        data.update(extra)
        return data

    def post(self, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/api/comments/", data, format="multipart")

    def make_comment(self, name, email=None, text="x", anonymous=False, parent=None):
        profile, _ = Profile.objects.get_or_create(
            username=name, defaults={"email": email or f"{name.lower()}@x.com"}
        )
        return Comment.objects.create(
            profile=profile,
            parent=parent,
            root=(parent.root or parent) if parent else None,
            text=text,
            is_anonymous=anonymous,
            ip_address="127.0.0.1",
        )

    def register(self, username="alice1", email="alice@example.com", password="S3cure-pass-77", **extra):
        return self.client.post(
            "/api/auth/register/",
            {"username": username, "email": email, "password": password, **extra},
            format="json",
        )


class CommentApiTests(BaseApiTest):
    def test_create_and_list(self):
        resp = self.post(self.payload())
        self.assertEqual(resp.status_code, 201, resp.content)
        listing = self.client.get("/api/comments/").json()
        self.assertEqual(listing["count"], 1)
        item = listing["results"][0]
        self.assertEqual(item["user_name"], "John1")
        self.assertEqual(item["profile"], "John1")
        self.assertEqual(item["email"], "j***@example.com")  # e-mail публично не показывается
        comment = Comment.objects.get()
        self.assertTrue(comment.ip_address)

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

    def test_required_fields(self):
        resp = self.post({"text": "hi", **self.captcha_fields()})
        self.assertEqual(resp.status_code, 400)
        errors = resp.json()
        self.assertIn("user_name", errors)
        self.assertIn("email", errors)

    def test_unclosed_tag_rejected(self):
        resp = self.post(self.payload(text="<strong>oops"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("text", resp.json())

    def test_xss_stripped(self):
        resp = self.post(self.payload(text="hi<script>alert(1)</script>"))
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

    def test_reply_sends_email_to_parent_author(self):
        root = self.post(self.payload()).json()
        self.post(self.payload(user_name="Mike2", email="mike@example.com", text="reply", parent=root["id"]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["john@example.com"])

    def test_pagination_25_and_lifo(self):
        for i in range(30):
            self.make_comment("A", text=f"c{i}")
        page1 = self.client.get("/api/comments/").json()
        page2 = self.client.get("/api/comments/?page=2").json()
        self.assertEqual(len(page1["results"]), 25)
        self.assertEqual(len(page2["results"]), 5)
        self.assertEqual(page1["results"][0]["text"], "c29")  # новые сверху

    def test_sorting(self):
        for name in ("Bob", "Alice"):
            self.make_comment(name)
        asc = self.client.get("/api/comments/?ordering=user_name").json()["results"]
        desc = self.client.get("/api/comments/?ordering=-user_name").json()["results"]
        self.assertEqual(asc[0]["user_name"], "Alice")
        self.assertEqual(desc[0]["user_name"], "Bob")

    def test_sorting_does_not_reveal_anonymous_author(self):
        self.make_comment("Bob")
        self.make_comment("Alice", anonymous=True)  # реальное имя Alice идёт раньше Bob
        asc = self.client.get("/api/comments/?ordering=user_name").json()["results"]
        self.assertEqual([c["user_name"] for c in asc], ["Bob", "Аноним"])

    def test_bad_ordering_falls_back(self):
        resp = self.client.get("/api/comments/?ordering=profile__user__password")
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


class IdentityTests(BaseApiTest):
    def test_same_guest_can_post_again(self):
        self.assertEqual(self.post(self.payload()).status_code, 201)
        self.assertEqual(self.post(self.payload()).status_code, 201)
        self.assertEqual(Profile.objects.count(), 1)
        self.assertEqual(Comment.objects.count(), 2)

    def test_username_taken_by_other_email(self):
        self.post(self.payload())
        resp = self.post(self.payload(email="other@example.com"))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["user_name"], "Имя пользователя занято")

    def test_username_is_case_insensitive(self):
        self.post(self.payload())
        resp = self.post(self.payload(user_name="john1", email="other@example.com"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("user_name", resp.json())

    def test_email_bound_to_single_username(self):
        self.post(self.payload())
        resp = self.post(self.payload(user_name="Mike2"))  # тот же e-mail, другое имя
        self.assertEqual(resp.status_code, 400)
        self.assertIn("email", resp.json())

    def test_email_is_case_insensitive(self):
        self.post(self.payload())
        resp = self.post(self.payload(user_name="Mike2", email="JOHN@example.com"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("email", resp.json())

    def test_failed_post_does_not_create_profile(self):
        self.post(self.payload())
        self.post(self.payload(user_name="Mike2"))  # e-mail занят
        self.assertEqual(Profile.objects.count(), 1)

    def test_guest_cannot_use_registered_username(self):
        self.assertEqual(self.register().status_code, 201)
        resp = self.post(self.payload(user_name="alice1", email="alice@example.com"))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["user_name"], "Имя пользователя занято")

    def test_anonymous_hides_author(self):
        resp = self.post(self.payload(anonymous="true"))
        self.assertEqual(resp.status_code, 201, resp.content)
        item = self.client.get("/api/comments/").json()["results"][0]
        self.assertEqual(item["user_name"], "Аноним")
        self.assertIsNone(item["profile"])
        self.assertEqual(item["email"], "")
        self.assertEqual(item["home_page"], "")
        self.assertTrue(Comment.objects.get().is_anonymous)  # автор системе известен

    def test_anonymous_still_requires_fields(self):
        resp = self.post({"text": "hi", "anonymous": "true", **self.captcha_fields()})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("user_name", resp.json())
        self.assertIn("email", resp.json())


class RegistrationTests(BaseApiTest):
    def test_register_creates_profile(self):
        resp = self.register(home_page="https://alice.example.com")
        self.assertEqual(resp.status_code, 201, resp.content)
        profile = Profile.objects.get(username="alice1")
        self.assertTrue(profile.is_registered)
        self.assertEqual(profile.home_page, "https://alice.example.com")

    def test_register_username_taken(self):
        self.register()
        resp = self.register(email="other@example.com")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["username"], "Имя пользователя занято")

    def test_register_email_bound_to_other_username(self):
        self.register()
        resp = self.register(username="bob22")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("email", resp.json())

    def test_register_claims_guest_profile_with_history(self):
        self.post(self.payload())  # гость John1 написал комментарий
        resp = self.register(username="John1", email="john@example.com")
        self.assertEqual(resp.status_code, 201, resp.content)
        profile = Profile.objects.get(username="John1")
        self.assertTrue(profile.is_registered)
        self.assertEqual(profile.comments.count(), 1)
        self.assertEqual(Profile.objects.count(), 1)

    def test_register_guest_name_with_other_email_rejected(self):
        self.post(self.payload())
        resp = self.register(username="John1", email="other@example.com")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["username"], "Имя пользователя занято")

    def test_password_too_short(self):
        resp = self.register(password="ab12")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("password", resp.json())

    def test_password_without_digits(self):
        resp = self.register(password="onlyletters")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("password", resp.json())

    def test_password_without_letters(self):
        resp = self.register(password="123456789")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("password", resp.json())

    def test_password_minimum_valid(self):
        resp = self.register(password="abc123")
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_registered_user_fields_are_autofilled(self):
        token = self.register().json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "alice1")

        resp = self.post({"text": "no names needed", **self.captcha_fields()})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["user_name"], "alice1")

    def test_registered_user_still_needs_captcha(self):
        token = self.register().json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        resp = self.post({"text": "no captcha"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("captcha_answer", resp.json())

    def test_registered_user_can_post_anonymously(self):
        token = self.register().json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        resp = self.post({"text": "secret", "anonymous": "true", **self.captcha_fields()})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["user_name"], "Аноним")
        self.assertEqual(Comment.objects.get().profile.username, "alice1")

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)


class ProfilePageTests(BaseApiTest):
    def test_profile_lists_only_public_comments(self):
        root = self.make_comment("John1", text="root")
        self.make_comment("John1", text="reply", parent=root)
        self.make_comment("John1", text="secret", anonymous=True)
        self.make_comment("Mike2", text="other")

        data = self.client.get("/api/users/john1/").json()  # без учёта регистра
        self.assertEqual(data["profile"]["username"], "John1")
        self.assertEqual(data["count"], 2)
        texts = {c["text"]: c for c in data["results"]}
        self.assertNotIn("secret", texts)
        self.assertEqual(texts["root"]["root_id"], root.id)
        self.assertEqual(texts["reply"]["root_id"], root.id)
        self.assertTrue(texts["reply"]["is_reply"])
        self.assertFalse(texts["root"]["is_reply"])

    def test_profile_does_not_expose_email(self):
        self.make_comment("John1")
        data = self.client.get("/api/users/John1/").json()
        self.assertNotIn("email", data["profile"])

    def test_profile_created_by_first_post(self):
        self.post(self.payload(home_page="https://john.example.com"))
        data = self.client.get("/api/users/John1/").json()
        self.assertEqual(data["profile"]["home_page"], "https://john.example.com")
        self.assertFalse(data["profile"]["registered"])

    def test_profile_not_found(self):
        self.assertEqual(self.client.get("/api/users/nobody/").status_code, 404)

    def test_thread_opens_whole_branch(self):
        root = self.make_comment("John1", text="root")
        child = self.make_comment("Mike2", text="child", parent=root)
        grandchild = self.make_comment("John1", text="grandchild", parent=child)

        data = self.client.get(f"/api/comments/{grandchild.id}/thread/").json()
        self.assertEqual(data["focus"], grandchild.id)
        self.assertEqual(data["root"]["id"], root.id)
        self.assertEqual(data["root"]["replies"][0]["replies"][0]["text"], "grandchild")

    def test_thread_not_found(self):
        self.assertEqual(self.client.get("/api/comments/99999/thread/").status_code, 404)
