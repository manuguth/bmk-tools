import datetime
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from .models import Festival, Shift, Task, Participant
from .serializers import serialize_festival_to_yaml, parse_yaml_to_dict, validate_import_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_festival(name="Sommerfest", status="active", **kwargs):
    return Festival.objects.create(name=name, status=status, **kwargs)


def _make_shift(festival, name="Aufbau", date=None, **kwargs):
    if date is None:
        date = datetime.date(2026, 7, 1)
    return Shift.objects.create(
        festival=festival,
        name=name,
        date=date,
        start_time=datetime.time(8, 0),
        end_time=datetime.time(12, 0),
        **kwargs,
    )


def _make_task(shift, name="Kisten schleppen", required_helpers=3, **kwargs):
    return Task.objects.create(shift=shift, name=name, required_helpers=required_helpers, **kwargs)


def _make_participant(task, name="Max Muster", **kwargs):
    return Participant.objects.create(task=task, name=name, **kwargs)


def _make_staff_user(username="staff"):
    user = User.objects.create_user(username=username, password="testpass123")
    user.is_staff = True
    user.save()
    return user


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class FestivalModelTests(TestCase):
    def test_slug_auto_generated_from_name(self):
        f = _make_festival(name="Rock Am Ring 2026")
        self.assertEqual(f.slug, "rock-am-ring-2026")

    def test_slug_not_overwritten_on_resave(self):
        f = _make_festival(name="Testfest")
        original_slug = f.slug
        f.description = "Updated"
        f.save()
        self.assertEqual(f.slug, original_slug)

    def test_str_representation(self):
        f = _make_festival(name="Herbstfest")
        self.assertEqual(str(f), "Herbstfest")

    def test_status_choices_valid(self):
        choices = [c[0] for c in Festival.STATUS_CHOICES]
        self.assertIn("draft", choices)
        self.assertIn("active", choices)
        self.assertIn("completed", choices)

    def test_default_status_is_draft(self):
        f = Festival.objects.create(name="NeuFest")
        self.assertEqual(f.status, "draft")


class ShiftModelTests(TestCase):
    def test_str_representation(self):
        f = _make_festival()
        s = _make_shift(f, name="Abbau", date=datetime.date(2026, 8, 5))
        self.assertIn("Abbau", str(s))
        self.assertIn("2026-08-05", str(s))

    def test_shifts_ordered_by_date_then_start_time(self):
        f = _make_festival()
        s2 = Shift.objects.create(
            festival=f, name="Shift B",
            date=datetime.date(2026, 7, 2),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(14, 0),
        )
        s1 = Shift.objects.create(
            festival=f, name="Shift A",
            date=datetime.date(2026, 7, 1),
            start_time=datetime.time(8, 0),
            end_time=datetime.time(12, 0),
        )
        s3 = Shift.objects.create(
            festival=f, name="Shift C",
            date=datetime.date(2026, 7, 1),
            start_time=datetime.time(14, 0),
            end_time=datetime.time(18, 0),
        )
        ordered = list(f.shifts.all())
        self.assertEqual(ordered, [s1, s3, s2])


class TaskModelTests(TestCase):
    def setUp(self):
        f = _make_festival()
        self.shift = _make_shift(f)

    def test_str_representation(self):
        t = _make_task(self.shift, name="Bühne aufbauen")
        self.assertIn("Bühne aufbauen", str(t))

    def test_current_helpers_zero_when_no_participants(self):
        t = _make_task(self.shift)
        self.assertEqual(t.current_helpers, 0)

    def test_current_helpers_counts_participants(self):
        t = _make_task(self.shift, required_helpers=5)
        _make_participant(t, name="Alice")
        _make_participant(t, name="Bob")
        self.assertEqual(t.current_helpers, 2)

    def test_is_full_false_when_not_enough_helpers(self):
        t = _make_task(self.shift, required_helpers=3)
        _make_participant(t, name="Alice")
        self.assertFalse(t.is_full)

    def test_is_full_true_when_capacity_reached(self):
        t = _make_task(self.shift, required_helpers=2)
        _make_participant(t, name="Alice")
        _make_participant(t, name="Bob")
        self.assertTrue(t.is_full)

    def test_has_km_integration_false_without_id(self):
        t = _make_task(self.shift)
        self.assertIsNone(t.konzertmeister_event_id)
        self.assertFalse(t.has_km_integration)

    def test_has_km_integration_true_with_id(self):
        t = _make_task(self.shift, konzertmeister_event_id=42)
        self.assertTrue(t.has_km_integration)


class ParticipantModelTests(TestCase):
    def setUp(self):
        f = _make_festival()
        shift = _make_shift(f)
        self.task = _make_task(shift)

    def test_str_representation(self):
        p = _make_participant(self.task, name="Lena Müller")
        self.assertIn("Lena Müller", str(p))

    def test_default_km_response_status_is_unknown(self):
        p = _make_participant(self.task, name="Tester")
        self.assertEqual(p.konzertmeister_response_status, "unknown")

    def test_masked_default_false(self):
        p = _make_participant(self.task, name="Anonym")
        self.assertFalse(p.masked)

    def test_pinned_default_false(self):
        p = _make_participant(self.task, name="VIP")
        self.assertFalse(p.pinned)


# ---------------------------------------------------------------------------
# Admin view tests
# ---------------------------------------------------------------------------

class FestivalAdminViewTests(TestCase):
    def setUp(self):
        self.staff = _make_staff_user()
        self.client = Client()

    def test_admin_list_requires_staff_anonymous_redirected(self):
        resp = self.client.get(reverse("festival:admin_festival_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    def test_admin_list_accessible_to_staff(self):
        self.client.login(username="staff", password="testpass123")
        resp = self.client.get(reverse("festival:admin_festival_list"))
        self.assertEqual(resp.status_code, 200)

    def test_admin_list_shows_active_festivals_by_default(self):
        active = _make_festival(name="Aktives Fest", status="active")
        completed = _make_festival(name="Altes Fest", status="completed")
        self.client.login(username="staff", password="testpass123")
        resp = self.client.get(reverse("festival:admin_festival_list"))
        self.assertContains(resp, active.name)
        self.assertNotContains(resp, completed.name)

    def test_admin_list_show_archived_includes_completed(self):
        completed = _make_festival(name="Altes Fest", status="completed")
        self.client.login(username="staff", password="testpass123")
        resp = self.client.get(
            reverse("festival:admin_festival_list") + "?show_archived=true"
        )
        self.assertContains(resp, completed.name)

    def test_admin_overview_requires_staff(self):
        f = _make_festival()
        resp = self.client.get(reverse("festival:admin_overview", args=[f.slug]))
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# Public festival view tests
# ---------------------------------------------------------------------------

class FestivalDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("festival.views.sync_participants_for_task")
    def test_active_festival_accessible_by_anonymous(self, mock_sync):
        mock_sync.return_value = {"success": True, "synced_count": 0, "deleted_count": 0, "error": None, "warning": None}
        f = _make_festival(name="Öffentliches Fest", status="active")
        resp = self.client.get(reverse("festival:festival_detail", args=[f.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Öffentliches Fest")

    def test_draft_festival_redirects_anonymous_to_login(self):
        f = _make_festival(name="Draft Fest", status="draft")
        resp = self.client.get(reverse("festival:festival_detail", args=[f.slug]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    @patch("festival.views.sync_participants_for_task")
    def test_draft_festival_accessible_to_authenticated(self, mock_sync):
        mock_sync.return_value = {"success": True, "synced_count": 0, "deleted_count": 0, "error": None, "warning": None}
        f = _make_festival(name="Draft Fest", status="draft")
        user = User.objects.create_user(username="user1", password="testpass123")
        self.client.login(username="user1", password="testpass123")
        resp = self.client.get(reverse("festival:festival_detail", args=[f.slug]))
        self.assertEqual(resp.status_code, 200)

    @patch("festival.views.sync_participants_for_task")
    def test_task_signup_creates_participant(self, mock_sync):
        mock_sync.return_value = {"success": True, "synced_count": 0, "deleted_count": 0, "error": None, "warning": None}
        f = _make_festival(status="active")
        shift = _make_shift(f)
        task = _make_task(shift, required_helpers=10)
        url = reverse("festival:task_signup", args=[f.slug, task.id])
        resp = self.client.post(url, {"name": "Franz Huber", "notes": ""})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Participant.objects.filter(task=task).count(), 1)
        self.assertEqual(Participant.objects.get(task=task).name, "Franz Huber")

    @patch("festival.views.sync_participants_for_task")
    def test_task_signup_blocked_when_full(self, mock_sync):
        mock_sync.return_value = {"success": True, "synced_count": 0, "deleted_count": 0, "error": None, "warning": None}
        f = _make_festival(status="active")
        shift = _make_shift(f)
        task = _make_task(shift, required_helpers=1)
        _make_participant(task, name="Existing Person")
        url = reverse("festival:task_signup", args=[f.slug, task.id])
        resp = self.client.post(url, {"name": "New Person", "notes": ""})
        # Should NOT create a second participant
        self.assertEqual(Participant.objects.filter(task=task).count(), 1)


# ---------------------------------------------------------------------------
# Konzertmeister utility tests
# ---------------------------------------------------------------------------

class KmUtilsTests(TestCase):
    @patch("festival.utils_km.requests.post")
    def test_get_km_auth_token_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"X-AUTH-TOKEN": "test-token-abc"}
        mock_post.return_value = mock_response

        from festival.utils_km import get_km_auth_token
        with self.settings(KM_MAIL="test@example.com", KM_PASSWORD="secret"):
            token = get_km_auth_token()
        self.assertEqual(token, "test-token-abc")

    @patch("festival.utils_km.requests.post")
    def test_get_km_auth_token_failure_raises_runtime_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        from festival.utils_km import get_km_auth_token
        with self.assertRaises(RuntimeError):
            get_km_auth_token()

    @patch("festival.utils_km.get_km_auth_token", return_value="fake-token")
    @patch("festival.utils_km.requests.get")
    def test_km_get_meeting_info_success(self, mock_get, mock_token):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"org": {"name": "BMK"}, "users": []}]
        mock_get.return_value = mock_response

        from festival.utils_km import km_get_meeting_info
        result = km_get_meeting_info(123)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["org"]["name"], "BMK")

    @patch("festival.utils_km.get_km_auth_token", return_value="fake-token")
    @patch("festival.utils_km.requests.get")
    def test_km_get_meeting_info_non_200_returns_none(self, mock_get, mock_token):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        from festival.utils_km import km_get_meeting_info
        result = km_get_meeting_info(999)
        self.assertIsNone(result)

    @patch("festival.utils_km.extract_positive_maybe_participants")
    def test_sync_skipped_when_no_km_integration(self, mock_extract):
        f = _make_festival()
        shift = _make_shift(f)
        task = _make_task(shift)  # no konzertmeister_event_id
        from festival.utils_km import sync_participants_for_task
        result = sync_participants_for_task(task)
        self.assertTrue(result["success"])
        self.assertEqual(result["synced_count"], 0)
        mock_extract.assert_not_called()

    @patch("festival.utils_km.extract_positive_maybe_participants")
    def test_sync_creates_new_participants(self, mock_extract):
        mock_extract.return_value = [
            {"name": "New Helper", "kmUserId": 5, "positive": True, "maybe": False}
        ]
        f = _make_festival()
        shift = _make_shift(f)
        task = _make_task(shift, konzertmeister_event_id=99)

        from festival.utils_km import sync_participants_for_task
        result = sync_participants_for_task(task)

        self.assertTrue(result["success"])
        self.assertEqual(result["synced_count"], 1)
        self.assertEqual(Participant.objects.filter(task=task).count(), 1)
        p = Participant.objects.get(task=task)
        self.assertEqual(p.name, "New Helper")
        self.assertEqual(p.konzertmeister_response_status, "positive")

    @patch("festival.utils_km.extract_positive_maybe_participants")
    def test_sync_deletes_unmatched_non_pinned_participants(self, mock_extract):
        mock_extract.return_value = []  # KM has nobody
        f = _make_festival()
        shift = _make_shift(f)
        task = _make_task(shift, konzertmeister_event_id=99)
        existing = _make_participant(task, name="Old Helper")  # not pinned

        from festival.utils_km import sync_participants_for_task
        result = sync_participants_for_task(task)

        self.assertEqual(result["deleted_count"], 1)
        self.assertFalse(Participant.objects.filter(id=existing.id).exists())

    @patch("festival.utils_km.extract_positive_maybe_participants")
    def test_sync_preserves_pinned_participants(self, mock_extract):
        mock_extract.return_value = []  # KM has nobody
        f = _make_festival()
        shift = _make_shift(f)
        task = _make_task(shift, konzertmeister_event_id=99)
        pinned = _make_participant(task, name="VIP", pinned=True)

        from festival.utils_km import sync_participants_for_task
        sync_participants_for_task(task)

        self.assertTrue(Participant.objects.filter(id=pinned.id).exists())

    @patch("festival.utils_km.extract_positive_maybe_participants")
    def test_sync_updates_existing_participant(self, mock_extract):
        mock_extract.return_value = [
            {"name": "Alice", "kmUserId": 7, "positive": True, "maybe": False}
        ]
        f = _make_festival()
        shift = _make_shift(f)
        task = _make_task(shift, konzertmeister_event_id=99)
        existing = _make_participant(task, name="Alice")

        from festival.utils_km import sync_participants_for_task
        sync_participants_for_task(task)

        existing.refresh_from_db()
        self.assertEqual(existing.konzertmeister_user_id, 7)
        self.assertEqual(existing.konzertmeister_response_status, "positive")


# ---------------------------------------------------------------------------
# YAML serializer roundtrip tests
# ---------------------------------------------------------------------------

class YamlSerializerTests(TestCase):
    def _make_full_festival(self):
        f = _make_festival(
            name="YAML Fest",
            status="active",
            start_date=datetime.date(2026, 8, 1),
            end_date=datetime.date(2026, 8, 3),
        )
        shift = _make_shift(f, name="Aufbau", date=datetime.date(2026, 8, 1))
        task = _make_task(shift, name="Bühne", required_helpers=4)
        return f, shift, task

    def test_serialize_produces_yaml_string(self):
        f, _, _ = self._make_full_festival()
        output = serialize_festival_to_yaml(f)
        self.assertIsInstance(output, str)
        self.assertIn("YAML Fest", output)
        self.assertIn("Aufbau", output)
        self.assertIn("Bühne", output)

    def test_parse_yaml_roundtrip(self):
        f, shift, task = self._make_full_festival()
        yaml_str = serialize_festival_to_yaml(f)
        parsed = parse_yaml_to_dict(yaml_str)
        self.assertIn("festival", parsed)
        # The serializer puts festival metadata under 'festival' and shifts at top level
        shifts_data = parsed["shifts"]
        self.assertEqual(len(shifts_data), 1)
        self.assertEqual(shifts_data[0]["name"], "Aufbau")
        self.assertEqual(len(shifts_data[0]["tasks"]), 1)
        self.assertEqual(shifts_data[0]["tasks"][0]["name"], "Bühne")
        self.assertEqual(shifts_data[0]["tasks"][0]["required_helpers"], 4)

    def test_validate_import_data_passes_for_valid_dict(self):
        f, _, _ = self._make_full_festival()
        yaml_str = serialize_festival_to_yaml(f)
        parsed = parse_yaml_to_dict(yaml_str)
        errors = validate_import_data(parsed)
        self.assertEqual(errors, [])
