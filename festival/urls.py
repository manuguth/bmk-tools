from django.urls import path
from . import views

app_name = "festival"

urlpatterns = [
    path("admin/", views.admin_festival_list, name="admin_festival_list"),
    path("<slug:festival_slug>/admin/", views.admin_overview, name="admin_overview"),
    path("<slug:festival_slug>/admin/edit/", views.admin_edit, name="admin_edit"),
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
    # API endpoints for inline editing
    path(
        "<slug:festival_slug>/api/festival/update/",
        views.api_update_festival,
        name="api_update_festival",
    ),
    path(
        "<slug:festival_slug>/api/task/<uuid:task_id>/update/",
        views.api_update_task,
        name="api_update_task",
    ),
    path(
        "<slug:festival_slug>/api/shift/<uuid:shift_id>/update/",
        views.api_update_shift,
        name="api_update_shift",
    ),
    path(
        "<slug:festival_slug>/api/participant/<int:participant_id>/update/",
        views.api_update_participant,
        name="api_update_participant",
    ),
    path(
        "<slug:festival_slug>/api/participant/<int:participant_id>/delete/",
        views.api_delete_participant,
        name="api_delete_participant",
    ),
    path(
        "<slug:festival_slug>/api/shift/<uuid:shift_id>/task/create/",
        views.api_create_task,
        name="api_create_task",
    ),
    # Task template management URLs
    path('admin/templates/', views.admin_templates, name='admin_templates'),
    path('api/templates/', views.api_get_templates, name='api_get_templates'),
    path('api/templates/create/', views.api_create_template, name='api_create_template'),
    path('api/templates/<uuid:template_id>/update/', views.api_update_template, name='api_update_template'),
    path('api/templates/<uuid:template_id>/delete/', views.api_delete_template, name='api_delete_template'),
    # Print overview
    path('<slug:festival_slug>/admin/print/', views.admin_print_overview, name='admin_print_overview'),
    # Shift creation
    path('<slug:festival_slug>/api/shift/create/', views.api_create_shift, name='api_create_shift'),
    # YAML export/import
    path('<slug:festival_slug>/api/festival/export/yaml/', views.api_export_festival_yaml, name='api_export_yaml'),
    path('<slug:festival_slug>/api/festival/import/yaml/', views.api_import_festival_yaml, name='api_import_yaml'),
    path('<slug:festival_slug>/api/festival/import/yaml-file/', views.api_import_festival_yaml_file, name='api_import_yaml_file'),
    # Festival creation
    path('api/festival/create/', views.api_create_festival, name='api_create_festival'),
]

