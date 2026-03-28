from django.test import TestCase
from django.urls import reverse

from .models import BringItem, BringList


def _make_list(edit_mode, name=None):
    name = name or f"Test {edit_mode}"
    return BringList.objects.create(name=name, edit_mode=edit_mode)


def _make_item(bring_list, label="Testitem", contributor_name="Tester"):
    return BringItem.objects.create(
        bring_list=bring_list,
        label=label,
        contributor_name=contributor_name,
    )


def _edit_url(bring_list, item):
    return reverse(
        "bring_list:edit_item",
        kwargs={"public_token": bring_list.public_token, "edit_token": item.edit_token},
    )


# ---------------------------------------------------------------------------
# BringList model tests
# ---------------------------------------------------------------------------

class BringListModelTests(TestCase):
    def test_slug_auto_generated_from_name(self):
        bl = BringList.objects.create(name="Grillabend 2026", edit_mode="free")
        self.assertEqual(bl.slug, "grillabend-2026")

    def test_slug_not_overwritten_on_resave(self):
        bl = BringList.objects.create(name="Party", edit_mode="free")
        original_slug = bl.slug
        bl.description = "Updated description"
        bl.save()
        self.assertEqual(bl.slug, original_slug)

    def test_slug_collision_resolved_with_counter(self):
        bl1 = BringList.objects.create(name="Feier", edit_mode="free")
        bl2 = BringList.objects.create(name="Feier", edit_mode="free")
        self.assertEqual(bl1.slug, "feier")
        self.assertEqual(bl2.slug, "feier-1")

    def test_triple_slug_collision(self):
        bl1 = BringList.objects.create(name="Test", edit_mode="free")
        bl2 = BringList.objects.create(name="Test", edit_mode="free")
        bl3 = BringList.objects.create(name="Test", edit_mode="free")
        self.assertEqual(bl1.slug, "test")
        self.assertEqual(bl2.slug, "test-1")
        self.assertEqual(bl3.slug, "test-2")

    def test_str_representation(self):
        bl = BringList.objects.create(name="Meine Liste", edit_mode="free")
        self.assertEqual(str(bl), "Meine Liste")

    def test_show_quantity_default_true(self):
        bl = BringList.objects.create(name="Quantitätsliste", edit_mode="free")
        self.assertTrue(bl.show_quantity)

    def test_public_token_is_unique(self):
        bl1 = BringList.objects.create(name="Liste A", edit_mode="free")
        bl2 = BringList.objects.create(name="Liste B", edit_mode="free")
        self.assertNotEqual(bl1.public_token, bl2.public_token)

    def test_ordering_newest_first(self):
        bl1 = BringList.objects.create(name="Erste", edit_mode="free")
        bl2 = BringList.objects.create(name="Zweite", edit_mode="free")
        lists = list(BringList.objects.all())
        self.assertEqual(lists[0], bl2)
        self.assertEqual(lists[1], bl1)


# ---------------------------------------------------------------------------
# BringItem model tests
# ---------------------------------------------------------------------------

class BringItemModelTests(TestCase):
    def setUp(self):
        self.bl = BringList.objects.create(name="Testliste", edit_mode="free")

    def test_item_str_representation(self):
        item = BringItem.objects.create(
            bring_list=self.bl, label="Bier", contributor_name="Max"
        )
        self.assertIn("Bier", str(item))

    def test_edit_token_is_unique(self):
        item1 = _make_item(self.bl, label="Item 1")
        item2 = _make_item(self.bl, label="Item 2")
        self.assertNotEqual(item1.edit_token, item2.edit_token)


# ---------------------------------------------------------------------------
# Public list view tests
# ---------------------------------------------------------------------------

class BringListViewTests(TestCase):
    def test_list_view_returns_200(self):
        bl = _make_list("free")
        resp = self.client.get(
            reverse("bring_list:list", kwargs={"public_token": bl.public_token})
        )
        self.assertEqual(resp.status_code, 200)

    def test_list_view_shows_items(self):
        bl = _make_list("free")
        _make_item(bl, label="Würstchen")
        resp = self.client.get(
            reverse("bring_list:list", kwargs={"public_token": bl.public_token})
        )
        self.assertContains(resp, "Würstchen")

    def test_add_item_post_creates_item(self):
        bl = _make_list("free")
        url = reverse("bring_list:add_item", kwargs={"public_token": bl.public_token})
        resp = self.client.post(url, {
            "label": "Salat",
            "contributor_name": "Anna",
            "quantity": 1,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(BringItem.objects.filter(bring_list=bl, label="Salat").exists())

    def test_add_item_post_in_own_mode_adds_token_to_session(self):
        bl = _make_list("own")
        url = reverse("bring_list:add_item", kwargs={"public_token": bl.public_token})
        self.client.post(url, {
            "label": "Getränke",
            "contributor_name": "Bob",
            "quantity": 2,
        })
        item = BringItem.objects.get(bring_list=bl, label="Getränke")
        session_key = f"bring_owned_{bl.public_token}"
        owned = self.client.session.get(session_key, [])
        self.assertIn(str(item.edit_token), owned)

    def test_add_item_get_request_redirects(self):
        bl = _make_list("free")
        url = reverse("bring_list:add_item", kwargs={"public_token": bl.public_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_list_view_404_on_invalid_token(self):
        import uuid
        fake_token = uuid.uuid4()
        resp = self.client.get(
            reverse("bring_list:list", kwargs={"public_token": fake_token})
        )
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Edit-item permission tests (existing, preserved + extended)
# ---------------------------------------------------------------------------

class EditItemPermissionTests(TestCase):
    def test_insert_only_forbids_edit(self):
        bl = _make_list("insert_only")
        item = _make_item(bl)
        response = self.client.get(_edit_url(bl, item))
        self.assertEqual(response.status_code, 403)

    def test_insert_only_forbids_post(self):
        bl = _make_list("insert_only")
        item = _make_item(bl)
        response = self.client.post(
            _edit_url(bl, item),
            {"label": "New", "quantity": 1, "contributor_name": "x"},
        )
        self.assertEqual(response.status_code, 403)

    def test_own_mode_forbids_edit_without_session_ownership(self):
        bl = _make_list("own")
        item = _make_item(bl)
        # No owned token in session
        response = self.client.get(_edit_url(bl, item))
        self.assertEqual(response.status_code, 403)

    def test_own_mode_forbids_post_without_session_ownership(self):
        bl = _make_list("own")
        item = _make_item(bl)
        response = self.client.post(
            _edit_url(bl, item),
            {"label": "New", "quantity": 1, "contributor_name": "x"},
        )
        self.assertEqual(response.status_code, 403)

    def test_own_mode_allows_edit_with_session_ownership(self):
        bl = _make_list("own")
        item = _make_item(bl)
        session = self.client.session
        session[f"bring_owned_{bl.public_token}"] = [str(item.edit_token)]
        session.save()
        response = self.client.get(_edit_url(bl, item))
        self.assertEqual(response.status_code, 200)

    def test_free_mode_allows_edit(self):
        bl = _make_list("free")
        item = _make_item(bl)
        response = self.client.get(_edit_url(bl, item))
        self.assertEqual(response.status_code, 200)

    def test_free_mode_post_updates_label(self):
        bl = _make_list("free")
        item = _make_item(bl, label="Old Label")
        response = self.client.post(
            _edit_url(bl, item),
            {"label": "New Label", "quantity": 1, "contributor_name": "x"},
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.label, "New Label")
