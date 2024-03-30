from django.urls import path
from info_mail import views
from .views import FileUploadView

urlpatterns = [
    path("", views.home, name="home"),
    path("overview", views.info_mail_index, name="info_mail_index"),
    path("details/<str:reference>", views.info_mail_details, name="info_mail_detail"),
    path("upload/", FileUploadView.as_view(), name="file_upload"),
]
