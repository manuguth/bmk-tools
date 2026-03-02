from django.urls import path
from . import views

app_name = "festival"

urlpatterns = [
    path("admin/", views.admin_festival_list, name="admin_festival_list"),
    path("<slug:festival_slug>/admin/", views.admin_overview, name="admin_overview"),
    path("<slug:festival_slug>/", views.festival_detail, name="festival_detail"),
    path("<slug:festival_slug>/shift/<uuid:shift_id>/", views.shift_detail, name="shift_detail"),
    path("<slug:festival_slug>/task/<uuid:task_id>/signup/", views.task_signup, name="task_signup"),
    path(
        "<slug:festival_slug>/confirmation/<int:participant_id>/",
        views.signup_confirmation,
        name="signup_confirmation",
    ),
    path(
        "<slug:festival_slug>/admin/participants/",
        views.participant_list_admin,
        name="participant_list_admin",
    ),
    path(
        "<slug:festival_slug>/admin/export/",
        views.export_participants_csv,
        name="export_participants_csv",
    ),
]

