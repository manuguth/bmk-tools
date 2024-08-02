from django.urls import path, include

from km_stats import views


urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard", views.dash_view, name="dashboard"),
    # path("django_plotly_dash/", include("django_plotly_dash.urls")),
]
