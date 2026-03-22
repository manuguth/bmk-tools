from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    # Public views (no login required)
    path("", views.concert_list, name="concert_list"),
    path("admin/", views.admin_concert_list, name="admin_concert_list"),
    path("admin/konzert/neu/", views.admin_concert_create, name="admin_concert_create"),
    path(
        "admin/konzert/<slug:slug>/bestellungen/",
        views.admin_concert_bestellungen,
        name="admin_concert_bestellungen",
    ),
    path(
        "admin/konzert/<slug:slug>/",
        views.admin_concert_detail,
        name="admin_concert_detail",
    ),
    path(
        "admin/bestellungen/",
        views.admin_all_bestellungen,
        name="admin_all_bestellungen",
    ),
    path(
        "admin/bestellung/<int:order_id>/status/",
        views.admin_order_status_update,
        name="admin_order_status_update",
    ),
    path("<slug:slug>/", views.concert_detail, name="concert_detail"),
    path(
        "<slug:slug>/bestaetigung/<str:confirmation_code>/",
        views.bestaetigung,
        name="bestaetigung",
    ),
]
