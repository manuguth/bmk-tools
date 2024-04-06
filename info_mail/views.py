import os

from azure.storage.blob import BlobServiceClient
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from info_mail.models import WeeklyMails

from .forms import UploadFileForm
from .serializers import WeeklyMailsSerializer


@login_required
def home(request):
    return render(request, "info_mail/home.html", {})


@login_required
def info_mail_index(request: HttpRequest) -> HttpResponse:
    weekly_mails = WeeklyMails.objects.order_by("-year", "-week")
    context = {"weekly_mails": weekly_mails}
    return render(request, "info_mail/info_mail_index.html", context)


def info_mail_details(request: HttpRequest, reference: str) -> HttpResponse:
    weekly_mails = WeeklyMails.objects.get(reference=reference)
    html_file = weekly_mails.html_file
    return HttpResponse(html_file.read(), content_type="text/html")


class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    authentication_classes = (TokenAuthentication,)
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        file_serializer = WeeklyMailsSerializer(data=request.data)

        if file_serializer.is_valid():
            file_serializer.save()
            return Response(file_serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        try:
            weekly_mail = WeeklyMails.objects.get(
                week=request.data["week"], year=request.data["year"]
            )
        except WeeklyMails.DoesNotExist:
            return Response(
                {"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = WeeklyMailsSerializer(weekly_mail, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@login_required
def media_upload(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES["file"]
            file_name = default_storage.save("mail_media/" + file.name, file)
            return render(request, "info_mail/upload_success.html")
    else:
        form = UploadFileForm()
    return render(request, "info_mail/media_upload.html", {"form": form})


@login_required
def display_media(request):
    _, filenames = default_storage.listdir("mail_media")
    media_urls = [default_storage.url("mail_media/" + name) for name in filenames]
    print(media_urls)
    return render(request, "info_mail/display_media.html", {"media_urls": media_urls})


def blob_redirect(request, blob_name):
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={os.environ['AZURE_ACCOUNT_NAME']};AccountKey={os.environ['AZURE_ACCOUNT_KEY']};EndpointSuffix=core.windows.net"
    container_name = os.environ["AZURE_CONTAINER"]

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)

    return redirect(blob_client.url)
