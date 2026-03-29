import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from .models import Concert, TicketOrder


def _create_concert(**overrides):
    defaults = {
        "name": "Testkonzert",
        "description": "Ein Testkonzert",
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


def _create_order(concert, **overrides):
    defaults = {
        "concert": concert,
        "customer_firstname": "Max",
        "customer_lastname": "Mustermann",
        "customer_email": "max@example.com",
        "adult_count": 2,
        "child_count": 1,
    }
    defaults.update(overrides)
    return TicketOrder.objects.create(**defaults)


class ConcertModelTests(TestCase):
    def test_slug_auto_generated(self):
        c = _create_concert(name="Sommerkonzert 2025")
        self.assertEqual(c.slug, "sommerkonzert-2025")

    def test_adults_sold_counts_active_orders(self):
        c = _create_concert()
        _create_order(c, adult_count=3, child_count=0)
        _create_order(c, adult_count=2, child_count=0, status="storniert")
        self.assertEqual(c.adults_sold, 3)

    def test_children_sold_counts_active_orders(self):
        c = _create_concert()
        _create_order(c, adult_count=0, child_count=4)
        _create_order(c, adult_count=0, child_count=2, status="storniert")
        self.assertEqual(c.children_sold, 4)

    def test_sold_counts_use_collected_when_available(self):
        c = _create_concert()
        order = _create_order(c, adult_count=5, child_count=3)
        order.collected = True
        order.collected_adult_count = 4
        order.collected_child_count = 2
        order.total_price = (
            4 * c.adult_price + 2 * c.child_price
        )
        order.save(update_fields=[
            "collected", "collected_adult_count", "collected_child_count", "total_price",
        ])
        self.assertEqual(c.adults_sold, 4)
        self.assertEqual(c.children_sold, 2)

    def test_remaining_capacity(self):
        c = _create_concert(max_adults=10, max_children=5)
        _create_order(c, adult_count=7, child_count=3)
        self.assertEqual(c.adults_remaining, 3)
        self.assertEqual(c.children_remaining, 2)

    def test_is_sold_out(self):
        c = _create_concert(max_adults=2, max_children=1)
        _create_order(c, adult_count=2, child_count=1)
        self.assertTrue(c.is_sold_out)


class TicketOrderModelTests(TestCase):
    def test_total_price_calculated_on_create(self):
        c = _create_concert(adult_price=Decimal("15.00"), child_price=Decimal("8.00"))
        order = _create_order(c, adult_count=2, child_count=3)
        self.assertEqual(order.total_price, Decimal("54.00"))

    def test_confirmation_code_generated(self):
        c = _create_concert()
        order = _create_order(c)
        self.assertEqual(len(order.confirmation_code), 8)
        self.assertTrue(order.confirmation_code.isalnum())

    def test_confirmation_code_unique(self):
        c = _create_concert()
        codes = set()
        for _ in range(20):
            o = _create_order(c)
            codes.add(o.confirmation_code)
        self.assertEqual(len(codes), 20)

    def test_save_with_update_fields_preserves_total_price(self):
        """The save() fix: update_fields including total_price should not recalculate."""
        c = _create_concert(adult_price=Decimal("10.00"), child_price=Decimal("5.00"))
        order = _create_order(c, adult_count=2, child_count=1)
        self.assertEqual(order.total_price, Decimal("25.00"))
        # Simulate einlass adjustment
        order.total_price = Decimal("15.00")
        order.save(update_fields=["total_price"])
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal("15.00"))

    def test_amount_adjusted_property(self):
        c = _create_concert()
        order = _create_order(c, adult_count=3, child_count=2)
        self.assertFalse(order.amount_adjusted)
        order.collected = True
        order.collected_adult_count = 2
        order.collected_child_count = 2
        self.assertTrue(order.amount_adjusted)

    def test_customer_full_name(self):
        c = _create_concert()
        order = _create_order(c, customer_firstname="Anna", customer_lastname="Schmidt")
        self.assertEqual(order.customer_full_name, "Anna Schmidt")


class PublicViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.concert = _create_concert()

    def test_concert_list_page(self):
        resp = self.client.get(reverse("tickets:concert_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.concert.name)

    def test_concert_detail_page(self):
        resp = self.client.get(
            reverse("tickets:concert_detail", args=[self.concert.slug])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.concert.name)

    @patch("tickets.views._send_confirmation_email", return_value=True)
    def test_reservation_creates_order(self, mock_email):
        url = reverse("tickets:concert_detail", args=[self.concert.slug])
        resp = self.client.post(url, {
            "customer_firstname": "Test",
            "customer_lastname": "User",
            "customer_email": "test@example.com",
            "adult_count": 1,
            "child_count": 0,
            "confirm_data": True,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(TicketOrder.objects.count(), 1)
        order = TicketOrder.objects.first()
        self.assertEqual(order.customer_firstname, "Test")
        self.assertEqual(order.total_price, self.concert.adult_price)
        mock_email.assert_called_once()

    @patch("tickets.views._send_confirmation_email", return_value=True)
    def test_capacity_enforcement(self, mock_email):
        concert = _create_concert(name="Kleine Show", max_adults=2, max_children=1)
        url = reverse("tickets:concert_detail", args=[concert.slug])
        # First order uses all capacity
        self.client.post(url, {
            "customer_firstname": "A",
            "customer_lastname": "B",
            "customer_email": "a@b.com",
            "adult_count": 2,
            "child_count": 1,
            "confirm_data": True,
        })
        # Second order should fail
        resp = self.client.post(url, {
            "customer_firstname": "C",
            "customer_lastname": "D",
            "customer_email": "c@d.com",
            "adult_count": 1,
            "child_count": 0,
            "confirm_data": True,
        })
        self.assertEqual(resp.status_code, 200)  # re-renders form
        self.assertEqual(TicketOrder.objects.count(), 1)

    @patch("tickets.views._send_confirmation_email", return_value=False)
    def test_email_failure_surfaces_in_confirmation(self, mock_email):
        url = reverse("tickets:concert_detail", args=[self.concert.slug])
        self.client.post(url, {
            "customer_firstname": "Test",
            "customer_lastname": "User",
            "customer_email": "test@example.com",
            "adult_count": 1,
            "child_count": 0,
            "confirm_data": True,
        })
        order = TicketOrder.objects.first()
        resp = self.client.get(
            reverse("tickets:bestaetigung", args=[self.concert.slug, order.confirmation_code])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "konnte leider nicht gesendet werden")

    def test_bestaetigung_page(self):
        order = _create_order(self.concert)
        resp = self.client.get(
            reverse("tickets:bestaetigung", args=[self.concert.slug, order.confirmation_code])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.confirmation_code)

    def test_qr_code_image(self):
        order = _create_order(self.concert)
        resp = self.client.get(
            reverse("tickets:ticket_qr_code", args=[order.confirmation_code])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")


class AdminViewTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="Tickets Admin")
        self.user = User.objects.create_user(username="admin", password="testpass123")
        self.user.groups.add(self.group)
        self.client = Client()
        self.client.login(username="admin", password="testpass123")
        self.concert = _create_concert()

    def test_admin_concert_list(self):
        resp = self.client.get(reverse("tickets:admin_concert_list"))
        self.assertEqual(resp.status_code, 200)

    def test_admin_concert_bestellungen(self):
        _create_order(self.concert)
        resp = self.client.get(
            reverse("tickets:admin_concert_bestellungen", args=[self.concert.slug])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mustermann")

    def test_admin_all_bestellungen(self):
        _create_order(self.concert)
        resp = self.client.get(reverse("tickets:admin_all_bestellungen"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mustermann")

    def test_admin_status_update(self):
        order = _create_order(self.concert)
        url = reverse("tickets:admin_order_status_update", args=[order.id])
        resp = self.client.post(
            url,
            json.dumps({"status": "bestaetigt"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        order.refresh_from_db()
        self.assertEqual(order.status, "bestaetigt")

    def test_admin_status_update_invalid_status(self):
        order = _create_order(self.concert)
        url = reverse("tickets:admin_order_status_update", args=[order.id])
        resp = self.client.post(
            url,
            json.dumps({"status": "invalid"}),
            content_type="application/json",
        )
        data = resp.json()
        self.assertFalse(data["success"])

    def test_admin_status_update_invalid_json(self):
        order = _create_order(self.concert)
        url = reverse("tickets:admin_order_status_update", args=[order.id])
        resp = self.client.post(url, "not json", content_type="application/json")
        data = resp.json()
        self.assertFalse(data["success"])

    def test_csv_export(self):
        _create_order(self.concert)
        resp = self.client.get(reverse("tickets:admin_export_orders_csv"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        content = resp.content.decode("utf-8-sig")
        self.assertIn("Mustermann", content)

    def test_csv_export_filtered_by_concert(self):
        _create_order(self.concert)
        resp = self.client.get(
            reverse("tickets:admin_export_orders_csv") + f"?concert={self.concert.slug}"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.concert.slug, resp["Content-Disposition"])

    def test_admin_requires_group(self):
        """Non-admin users should be redirected."""
        self.client.logout()
        normal_user = User.objects.create_user(username="normal", password="testpass123")
        self.client.login(username="normal", password="testpass123")
        resp = self.client.get(reverse("tickets:admin_concert_list"))
        self.assertNotEqual(resp.status_code, 200)


class ScannerViewTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="Ticket Scanner")
        self.user = User.objects.create_user(username="scanner", password="testpass123")
        self.user.groups.add(self.group)
        self.client = Client()
        self.client.login(username="scanner", password="testpass123")
        self.concert = _create_concert()

    def test_einlass_scanner_page(self):
        resp = self.client.get(reverse("tickets:einlass_scanner"))
        self.assertEqual(resp.status_code, 200)

    def test_einlass_detail(self):
        order = _create_order(self.concert)
        resp = self.client.get(
            reverse("tickets:einlass_detail", args=[order.confirmation_code])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.customer_full_name)

    def test_mark_collected(self):
        order = _create_order(self.concert, adult_count=2, child_count=1)
        url = reverse("tickets:einlass_mark_collected", args=[order.confirmation_code])
        resp = self.client.post(url, {
            "collected_adult_count": 2,
            "collected_child_count": 1,
        })
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertTrue(order.collected)
        self.assertEqual(order.collected_adult_count, 2)
        self.assertEqual(order.collected_child_count, 1)

    def test_mark_collected_with_adjustment(self):
        order = _create_order(self.concert, adult_count=3, child_count=2)
        original_price = order.total_price
        url = reverse("tickets:einlass_mark_collected", args=[order.confirmation_code])
        resp = self.client.post(url, {
            "collected_adult_count": 2,
            "collected_child_count": 1,
        })
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertTrue(order.collected)
        expected_price = 2 * self.concert.adult_price + 1 * self.concert.child_price
        self.assertEqual(order.total_price, expected_price)
        self.assertNotEqual(order.total_price, original_price)

    def test_mark_collected_cancelled_order_rejected(self):
        order = _create_order(self.concert, status="storniert")
        url = reverse("tickets:einlass_mark_collected", args=[order.confirmation_code])
        resp = self.client.post(url, {
            "collected_adult_count": 1,
            "collected_child_count": 0,
        })
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertFalse(order.collected)

    def test_name_search(self):
        _create_order(self.concert, customer_firstname="Anna", customer_lastname="Schmidt")
        resp = self.client.get(
            reverse("tickets:einlass_name_search") + "?q=Anna"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["name"], "Anna Schmidt")

    def test_name_search_too_short(self):
        resp = self.client.get(
            reverse("tickets:einlass_name_search") + "?q=A"
        )
        data = resp.json()
        self.assertEqual(data["results"], [])

    def test_scanner_requires_group(self):
        """Non-scanner users should be redirected."""
        self.client.logout()
        normal_user = User.objects.create_user(username="normal", password="testpass123")
        self.client.login(username="normal", password="testpass123")
        resp = self.client.get(reverse("tickets:einlass_scanner"))
        self.assertNotEqual(resp.status_code, 200)


class AbendkasseExtraCapacityTests(TestCase):
    """Tests for the extra Abendkasse capacity setting."""

    def setUp(self):
        scanner_group, _ = Group.objects.get_or_create(name="Ticket Scanner")
        self.scanner = User.objects.create_user(username="scanner2", password="testpass123")
        self.scanner.groups.add(scanner_group)
        self.client = Client()
        self.client.login(username="scanner2", password="testpass123")

    # ── Model property tests ──────────────────────────────────────────────

    def test_abendkasse_adults_remaining_no_extra(self):
        c = _create_concert(max_adults=10, max_children=5)
        _create_order(c, adult_count=4, child_count=0)
        self.assertEqual(c.abendkasse_adults_remaining, 6)

    def test_abendkasse_adults_remaining_with_extra(self):
        c = _create_concert(max_adults=10, max_children=5, abendkasse_extra_adults=5)
        _create_order(c, adult_count=10, child_count=0)
        # Regular capacity exhausted; extra allows 5 more
        self.assertEqual(c.adults_remaining, 0)
        self.assertEqual(c.abendkasse_adults_remaining, 5)

    def test_abendkasse_children_remaining_with_extra(self):
        c = _create_concert(max_adults=10, max_children=5, abendkasse_extra_children=3)
        _create_order(c, adult_count=0, child_count=5)
        self.assertEqual(c.children_remaining, 0)
        self.assertEqual(c.abendkasse_children_remaining, 3)

    def test_abendkasse_remaining_cannot_go_negative(self):
        # Even if somehow oversold, remaining should be 0 not negative
        c = _create_concert(max_adults=2, max_children=0, abendkasse_extra_adults=1)
        _create_order(c, adult_count=3, child_count=0)
        self.assertEqual(c.abendkasse_adults_remaining, 0)

    # ── Abendkasse view — direct sales ─────────────────────────────────

    def test_abendkasse_sale_blocked_when_no_extra_and_full(self):
        concert = _create_concert(max_adults=2, max_children=0)
        _create_order(concert, adult_count=2, child_count=0, status="bestaetigt")
        url = reverse("tickets:abendkasse", kwargs={"slug": concert.slug})
        resp = self.client.post(url, {"adult_count": 1, "child_count": 0})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(TicketOrder.objects.filter(abendkasse=True).exists())

    def test_abendkasse_sale_allowed_when_extra_set_and_full(self):
        concert = _create_concert(max_adults=2, max_children=0, abendkasse_extra_adults=5)
        _create_order(concert, adult_count=2, child_count=0, status="bestaetigt")
        url = reverse("tickets:abendkasse", kwargs={"slug": concert.slug})
        resp = self.client.post(url, {"adult_count": 3, "child_count": 0})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(TicketOrder.objects.filter(abendkasse=True).exists())

    def test_abendkasse_sale_blocked_beyond_extra_limit(self):
        concert = _create_concert(max_adults=2, max_children=0, abendkasse_extra_adults=2)
        _create_order(concert, adult_count=2, child_count=0, status="bestaetigt")
        url = reverse("tickets:abendkasse", kwargs={"slug": concert.slug})
        # Request 3 but only 2 extra allowed
        resp = self.client.post(url, {"adult_count": 3, "child_count": 0})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(TicketOrder.objects.filter(abendkasse=True).exists())

    # ── VVK pre-sales still capped at max_adults / max_children ─────────

    @patch("tickets.views._send_confirmation_email", return_value=True)
    def test_vvk_sale_still_blocked_by_regular_capacity_even_with_extra(self, mock_email):
        concert = _create_concert(max_adults=2, max_children=0, abendkasse_extra_adults=10)
        _create_order(concert, adult_count=2, child_count=0, status="bestaetigt")
        url = reverse("tickets:concert_detail", args=[concert.slug])
        resp = self.client.post(url, {
            "customer_firstname": "Test",
            "customer_lastname": "User",
            "customer_email": "test@example.com",
            "adult_count": 1,
            "child_count": 0,
            "confirm_data": True,
        })
        # Form re-renders (capacity error) — no new non-abendkasse order created
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TicketOrder.objects.filter(abendkasse=False).count(), 1)

    # ── Einlass extras use abendkasse capacity ────────────────────────────

    def test_einlass_extras_allowed_when_extra_capacity_set(self):
        concert = _create_concert(max_adults=2, max_children=0, abendkasse_extra_adults=5)
        order = _create_order(concert, adult_count=2, child_count=0, status="bestaetigt")
        # All regular capacity is taken by this order; extras should still work
        url = reverse("tickets:einlass_mark_collected", args=[order.confirmation_code])
        resp = self.client.post(url, {
            "collected_adult_count": 4,  # 2 from reservation + 2 extras
            "collected_child_count": 0,
        })
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertTrue(order.collected)
        # An extra AK order should have been created
        extra_orders = TicketOrder.objects.filter(source_order=order)
        self.assertEqual(extra_orders.count(), 1)
        self.assertEqual(extra_orders.first().adult_count, 2)

    def test_einlass_extras_blocked_beyond_abendkasse_limit(self):
        concert = _create_concert(max_adults=2, max_children=0, abendkasse_extra_adults=1)
        order = _create_order(concert, adult_count=2, child_count=0, status="bestaetigt")
        url = reverse("tickets:einlass_mark_collected", args=[order.confirmation_code])
        # Request 3 extras, but only 1 allowed
        resp = self.client.post(url, {
            "collected_adult_count": 5,
            "collected_child_count": 0,
        })
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        # Order was not marked collected because of capacity error
        self.assertFalse(order.collected)

