from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from festival.models import Festival
from tickets.models import Concert


def _create_concert(**overrides):
    defaults = {
        "name": "Testkonzert",
        "date": timezone.now() + timezone.timedelta(days=30),
        "venue": "Festhalle",
        "adult_price": Decimal("15.00"),
        "child_price": Decimal("8.00"),
        "max_adults": 100,
        "max_children": 50,
        "is_active": True,
    }
    defaults.update(overrides)
    return Concert.objects.create(**defaults)


def _create_festival(**overrides):
    defaults = {
        "name": "Testfestival",
        "status": "active",
    }
    defaults.update(overrides)
    return Festival.objects.create(**defaults)


class HomeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("home")
        self.user = User.objects.create_user(username="testuser", password="pass")

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response["Location"])

    def test_authenticated_user_gets_200(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_context_keys_present(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        for key in (
            "active_concerts",
            "next_concert",
            "active_concerts_count",
            "active_festivals",
            "active_festivals_count",
            "bring_list_count",
            "latest_mail",
            "today",
        ):
            self.assertIn(key, response.context, msg=f"Missing context key: {key}")

    def test_active_concert_appears_in_context(self):
        concert = _create_concert()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertIn(concert, response.context["active_concerts"])
        self.assertEqual(response.context["active_concerts_count"], 1)

    def test_next_concert_is_nearest_upcoming(self):
        soon = _create_concert(
            name="Bald",
            date=timezone.now() + timezone.timedelta(days=5),
        )
        _create_concert(
            name="Später",
            date=timezone.now() + timezone.timedelta(days=60),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.context["next_concert"], soon)

    def test_inactive_concert_excluded(self):
        _create_concert(is_active=False)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.context["active_concerts_count"], 0)

    def test_active_festival_appears_in_context(self):
        festival = _create_festival()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertIn(festival, response.context["active_festivals"])
        self.assertEqual(response.context["active_festivals_count"], 1)

    def test_today_is_current_date(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.context["today"], date.today())
