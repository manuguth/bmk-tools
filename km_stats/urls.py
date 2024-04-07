from django.urls import path

from km_stats import views


urlpatterns = [
    path("", views.home, name="home"),
]
