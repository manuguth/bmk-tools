from django.urls import path
from . import views

urlpatterns = [
    path("", views.km_home_view),
]
