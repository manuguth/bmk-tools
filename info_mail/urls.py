import os

from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from info_mail import views

from .views import FileUploadView, media_upload, display_media, blob_redirect

urlpatterns = [
    path("", views.home, name="home"),
    path("overview", views.info_mail_index, name="info_mail_index"),
    path("details/<str:reference>", views.info_mail_details, name="info_mail_detail"),
    path("upload", FileUploadView.as_view(), name="file_upload"),
    path("media_upload/", media_upload, name="media_upload"),
    path("display_media/", display_media, name="display_media"),
    path("blob/<str:blob_name>/", blob_redirect),
] + static(
    settings.MEDIA_URL + "mail_media/",
    document_root=os.path.join(settings.MEDIA_ROOT, "mail_media"),
    show_indexes=True,
)
