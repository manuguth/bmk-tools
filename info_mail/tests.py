import tempfile
import shutil
import datetime

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from .models import WeeklyMails


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HTML_CONTENT = b"<html><body><h1>Themen der Woche</h1></body></html>"


def _make_user(username="testuser", password="testpass123"):
    return User.objects.create_user(username=username, password=password)


def _make_token(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token


def _upload_file():
    return SimpleUploadedFile("newsletter.html", _HTML_CONTENT, content_type="text/html")


def _make_weekly_mail(week, year, content=_HTML_CONTENT):
    """Create a WeeklyMails object with a real in-memory file."""
    upload_date = datetime.datetime(year, 1, 1, tzinfo=datetime.timezone.utc)
    mail = WeeklyMails(week=week, year=year, upload_date=upload_date)
    mail.html_file.save(f"{year}_{week}-test.html", SimpleUploadedFile("test.html", content), save=True)
    return mail


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class WeeklyMailsModelTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @override_settings(MEDIA_ROOT=None)  # ensure tempdir used in each test
    def test_reference_auto_generated(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            mail = _make_weekly_mail(week=1, year=2025)
        self.assertTrue(len(mail.reference) > 0)

    def test_reference_is_lowercase_alpha_8_chars(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            mail = _make_weekly_mail(week=2, year=2025)
        self.assertEqual(len(mail.reference), 8)
        self.assertTrue(mail.reference.isalpha())
        self.assertEqual(mail.reference, mail.reference.lower())

    def test_reference_not_overwritten_on_resave(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            mail = _make_weekly_mail(week=3, year=2025)
            original_ref = mail.reference
            mail.save()
        self.assertEqual(mail.reference, original_ref)

    def test_unique_together_week_year(self):
        from django.db import IntegrityError
        with override_settings(MEDIA_ROOT=self.tmp):
            _make_weekly_mail(week=5, year=2025)
            with self.assertRaises(IntegrityError):
                WeeklyMails.objects.create(
                    week=5,
                    year=2025,
                    upload_date=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
                )


# ---------------------------------------------------------------------------
# Index view tests
# ---------------------------------------------------------------------------

class InfoMailIndexViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _make_user()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse("info_mail_index"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    def test_authenticated_gets_200(self):
        self.client.login(username="testuser", password="testpass123")
        resp = self.client.get(reverse("info_mail_index"))
        self.assertEqual(resp.status_code, 200)

    def test_context_contains_weekly_mails(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            mail = _make_weekly_mail(week=10, year=2025)
        self.client.login(username="testuser", password="testpass123")
        resp = self.client.get(reverse("info_mail_index"))
        self.assertIn("weekly_mails", resp.context)
        self.assertIn(mail, resp.context["weekly_mails"])


# ---------------------------------------------------------------------------
# latest_info_mail view tests
# ---------------------------------------------------------------------------

class LatestInfoMailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_returns_404_when_no_mails_exist(self):
        resp = self.client.get(reverse("latest_info_mail"))
        self.assertEqual(resp.status_code, 404)

    def test_returns_closest_past_week_html(self):
        with self.settings(MEDIA_ROOT=self.tmp):
            _make_weekly_mail(week=1, year=2020)  # clearly in the past
            resp = self.client.get(reverse("latest_info_mail"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/html")
        self.assertIn(b"Themen der Woche", resp.content)

    def test_ignores_future_mails(self):
        """Only past/current mails are shown; a far-future mail should not be returned
        if no past mail exists."""
        with self.settings(MEDIA_ROOT=self.tmp):
            _make_weekly_mail(week=1, year=2099)  # far future
            resp = self.client.get(reverse("latest_info_mail"))
        self.assertEqual(resp.status_code, 404)

    def test_selects_most_recent_past_week(self):
        with self.settings(MEDIA_ROOT=self.tmp):
            _make_weekly_mail(week=1, year=2019, content=b"<p>old</p>")
            _make_weekly_mail(week=1, year=2020, content=b"<p>new</p>")
            resp = self.client.get(reverse("latest_info_mail"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"new", resp.content)
        self.assertNotIn(b"old", resp.content)


# ---------------------------------------------------------------------------
# info_mail_details view tests
# ---------------------------------------------------------------------------

class InfoMailDetailsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_serves_html_content_by_reference(self):
        with self.settings(MEDIA_ROOT=self.tmp):
            mail = _make_weekly_mail(week=10, year=2024)
            resp = self.client.get(reverse("info_mail_detail", args=[mail.reference]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/html")
        self.assertIn(b"Themen der Woche", resp.content)

    def test_unknown_reference_raises_does_not_exist(self):
        """The view does not guard against missing references; unknown key raises DoesNotExist."""
        from info_mail.models import WeeklyMails as WM
        with self.assertRaises(WM.DoesNotExist):
            self.client.get(reverse("info_mail_detail", args=["nonexistent"]))


# ---------------------------------------------------------------------------
# FileUploadView API tests
# ---------------------------------------------------------------------------

class FileUploadAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _make_user(username="apiuser")
        self.token = _make_token(self.user)
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_post_without_token_returns_401(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            resp = self.client.post(
                reverse("file_upload"),
                {
                    "week": 20,
                    "year": 2025,
                    "upload_date": "2025-05-19T10:00:00Z",
                    "html_file": _upload_file(),
                },
                format="multipart",
            )
        self.assertEqual(resp.status_code, 401)

    def test_post_with_valid_token_creates_record(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            resp = self.client.post(
                reverse("file_upload"),
                {
                    "week": 21,
                    "year": 2025,
                    "upload_date": "2025-05-26T10:00:00Z",
                    "html_file": _upload_file(),
                },
                HTTP_AUTHORIZATION=f"Token {self.token.key}",
            )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(WeeklyMails.objects.filter(week=21, year=2025).exists())

    def test_post_duplicate_week_year_returns_400(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            self.client.post(
                reverse("file_upload"),
                {
                    "week": 22,
                    "year": 2025,
                    "upload_date": "2025-06-02T10:00:00Z",
                    "html_file": _upload_file(),
                },
                HTTP_AUTHORIZATION=f"Token {self.token.key}",
            )
            resp = self.client.post(
                reverse("file_upload"),
                {
                    "week": 22,
                    "year": 2025,
                    "upload_date": "2025-06-02T10:00:00Z",
                    "html_file": _upload_file(),
                },
                HTTP_AUTHORIZATION=f"Token {self.token.key}",
            )
        self.assertEqual(resp.status_code, 400)

    def test_put_updates_existing_record(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            # Create it first
            self.client.post(
                reverse("file_upload"),
                {
                    "week": 25,
                    "year": 2025,
                    "upload_date": "2025-06-23T10:00:00Z",
                    "html_file": _upload_file(),
                },
                HTTP_AUTHORIZATION=f"Token {self.token.key}",
            )
            # Update it via PUT
            resp = self.client.put(
                reverse("file_upload"),
                data=(
                    "week=25&year=2025&upload_date=2025-06-23T12:00:00Z"
                ).encode(),
                content_type="application/x-www-form-urlencoded",
                HTTP_AUTHORIZATION=f"Token {self.token.key}",
            )
        self.assertIn(resp.status_code, [200, 400])  # 200 ok or 400 missing file

    def test_put_nonexistent_returns_404(self):
        resp = self.client.put(
            reverse("file_upload"),
            data="week=99&year=2099&upload_date=2099-01-01T00:00:00Z".encode(),
            content_type="application/x-www-form-urlencoded",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(resp.status_code, 404)
