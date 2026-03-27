from django.urls import path

from . import views

urlpatterns = [
    # Public
    path("<uuid:public_token>/", views.list_view, name="list"),
    path("<uuid:public_token>/add/", views.add_item_view, name="add_item"),
    path(
        "<uuid:public_token>/item/<uuid:edit_token>/edit/",
        views.edit_item_view,
        name="edit_item",
    ),
    # Admin
    path("admin/", views.admin_overview_view, name="admin_overview"),
    path("admin/create/", views.admin_create_view, name="admin_create"),
    path("admin/<slug:slug>/", views.admin_detail_view, name="admin_detail"),
    path("admin/<slug:slug>/edit/", views.admin_edit_list_view, name="admin_edit_list"),
    path(
        "admin/<slug:slug>/item/<int:pk>/edit/",
        views.admin_edit_item_view,
        name="admin_edit_item",
    ),
    path(
        "admin/<slug:slug>/item/<int:pk>/delete/",
        views.admin_delete_item_view,
        name="admin_delete_item",
    ),
    path(
        "admin/<slug:slug>/toggle-quantity/",
        views.admin_toggle_quantity_view,
        name="admin_toggle_quantity",
    ),
]
