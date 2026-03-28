from django.test import TestCase
from django.urls import reverse

from .models import BringItem, BringList


def _make_list(edit_mode):
    return BringList.objects.create(name=f"Test {edit_mode}", edit_mode=edit_mode)


def _make_item(bring_list):
    return BringItem.objects.create(
        bring_list=bring_list,
        label="Testitem",
        contributor_name="Tester",
    )


def _edit_url(bring_list, item):
    return reverse(
        "bring_list:edit_item",
        kwargs={"public_token": bring_list.public_token, "edit_token": item.edit_token},
    )


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
