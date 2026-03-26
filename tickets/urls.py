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
        "admin/bestellungen/export/",
        views.admin_export_orders_csv,
        name="admin_export_orders_csv",
    ),
    path(
        "admin/bestellungen/export-pdf/",
        views.admin_export_orders_pdf,
        name="admin_export_orders_pdf",
    ),
    path(
        "admin/bestellung/<int:order_id>/status/",
        views.admin_order_status_update,
        name="admin_order_status_update",
    ),
    # QR code image (public – required for email embedding)
    path(
        "qr/<str:confirmation_code>/",
        views.ticket_qr_code,
        name="ticket_qr_code",
    ),
    # Einlass scanner and order detail (staff only)
    path("einlass/scanner/", views.einlass_scanner, name="einlass_scanner"),
    path("einlass/search/", views.einlass_name_search, name="einlass_name_search"),
    path(
        "einlass/<str:confirmation_code>/",
        views.einlass_detail,
        name="einlass_detail",
    ),
    path(
        "einlass/<str:confirmation_code>/collected/",
        views.einlass_mark_collected,
        name="einlass_mark_collected",
    ),
    path("<slug:slug>/", views.concert_detail, name="concert_detail"),
    path(
        "<slug:slug>/bestaetigung/<str:confirmation_code>/",
        views.bestaetigung,
        name="bestaetigung",
    ),
]
