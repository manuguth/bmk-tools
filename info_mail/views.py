import os
from datetime import date

from azure.storage.blob import BlobServiceClient
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from info_mail.models import NewsletterSettings, WeeklyMails

from .forms import NewsletterComposeForm, UploadFileForm
from .serializers import WeeklyMailsSerializer
from .utils import render_newsletter


@login_required
def info_mail_index(request: HttpRequest) -> HttpResponse:
    weekly_mails = WeeklyMails.objects.order_by("-year", "-week")
    context = {"weekly_mails": weekly_mails}
    return render(request, "info_mail/info_mail_index.html", context)


def info_mail_details(request: HttpRequest, reference: str) -> HttpResponse:
    weekly_mails = WeeklyMails.objects.get(reference=reference)
    html_file = weekly_mails.html_file
    return HttpResponse(html_file.read(), content_type="text/html")

def latest_info_mail(request: HttpRequest) -> HttpResponse:
    today = date.today()
    current_year, current_week, _ = today.isocalendar()
    weekly_mails = (
        WeeklyMails.objects
        .order_by('-year', '-week')
        .values_list('year', 'week')
    )
    year_week_list = list(weekly_mails)
    closest = None
    for year, week in year_week_list:
        if (year < current_year) or (year == current_year and week <= current_week):
            closest = (year, week)
            break

    if closest is None:
        return HttpResponse("No info mail available.", status=404)

    weekly_mail = WeeklyMails.objects.get(year=closest[0], week=closest[1])

    # weekly_mail = WeeklyMails.objects.latest("upload_date")

    html_file = weekly_mail.html_file
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
    """
    Display the media files associated with the mail.

    This function retrieves the media files from either an Azure Blob Storage container
    or the local storage, depending on the environment. It then renders the media files
    in the 'display_media.html' template.

    Parameters:
    - request: The HTTP request object.

    Returns:
    - A rendered HTTP response containing the media URLs.

    """
    if ("DJANGO_ENV" in os.environ and os.environ["DJANGO_ENV"] == "production"):

        connection_string = f"DefaultEndpointsProtocol=https;AccountName={os.environ['AZURE_ACCOUNT_NAME']};AccountKey={os.environ['AZURE_ACCOUNT_KEY']};EndpointSuffix=core.windows.net"
        container_name = os.environ['AZURE_CONTAINER']
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_list = container_client.list_blobs(name_starts_with="mail_media/")
        media_urls = []
        for blob in blob_list:
            blob_client = container_client.get_blob_client(blob.name)
            media_urls.append(blob_client.url)
    else:
        _, filenames = default_storage.listdir("mail_media")
        media_urls = [default_storage.url("mail_media/" + name) for name in filenames]
        print(media_urls)

    # _, filenames = default_storage.listdir("mail_media")
    # media_urls = [default_storage.url("mail_media/" + name) for name in filenames]
    # print(media_urls)
    return render(request, "info_mail/display_media.html", {"media_urls": media_urls})


@login_required
def redirect_to_current_week(request):
    today = date.today()
    year, week, _ = today.isocalendar()
    return redirect("compose_newsletter", year=year, week=week)


def _prefill_sonstiges(mail_obj, ns, year, week):
    """Pre-populate the sonstiges field from the default template when a new mail is created."""
    from pathlib import Path
    template_path = Path(__file__).parent / "email_assets" / "sonstiges_default.html"
    if not template_path.exists():
        return
    content = template_path.read_text(encoding="utf-8")
    last_week = week - 1 if week > 1 else 52
    last_year = year if week > 1 else year - 1
    content = content.replace("{{mmv_url}}", ns.mmv_newsletter_url or "#")
    content = content.replace("{{mmv_month}}", ns.mmv_newsletter_month or "")
    content = content.replace("{{last_week}}", f"{last_week:02d}-{last_year}")
    mail_obj.sonstiges = content
    mail_obj.save(update_fields=["sonstiges"])


@login_required
def compose_newsletter(request, year, week):
    ns = NewsletterSettings.get_settings()
    mail_obj, created = WeeklyMails.objects.get_or_create(
        week=week, year=year,
    )

    if created:
        _prefill_sonstiges(mail_obj, ns, year, week)

    if request.method == "POST":
        form = NewsletterComposeForm(request.POST, instance=mail_obj)
        if form.is_valid():
            mail_obj = form.save(commit=False)
            action = request.POST.get("action", "save")

            if action == "save_settings":
                ns.mmv_newsletter_url = request.POST.get("mmv_newsletter_url", "").strip()
                ns.mmv_newsletter_month = request.POST.get("mmv_newsletter_month", "").strip()
                ns.save(update_fields=["mmv_newsletter_url", "mmv_newsletter_month"])
                _prefill_sonstiges(mail_obj, ns, year, week)
                messages.success(request, "MMV-Einstellungen gespeichert. Sonstiges-Abschnitt wurde aktualisiert.")
                return redirect("compose_newsletter", year=year, week=week)

            if action == "save":
                mail_obj.save()
                messages.success(request, "Entwurf gespeichert.")
                return redirect("compose_newsletter", year=year, week=week)

            if action in ("preview", "send", "send_test"):
                html = render_newsletter(mail_obj, ns)
                mail_obj.html_file.save(
                    f"{year}_{week:02d}-email_themen.html",
                    ContentFile(html.encode("utf-8")),
                    save=False,
                )
                mail_obj.save()

                if action == "preview":
                    return redirect("info_mail_detail", reference=mail_obj.reference)

                if action == "send_test":
                    test_email = request.POST.get("test_email", "").strip()
                    if test_email:
                        msg = EmailMessage(
                            subject=f"[TEST] Aktuelle Themen BMK KW {week}/{year}",
                            body=html,
                            from_email=ns.from_email,
                            to=[test_email],
                        )
                        msg.content_subtype = "html"
                        msg.send()
                        messages.success(request, f"Test-Mail an {test_email} gesendet.")
                    else:
                        messages.warning(request, "Bitte eine Test-E-Mail-Adresse angeben.")
                    return redirect("compose_newsletter", year=year, week=week)

                if action == "send":
                    msg = EmailMessage(
                        subject=f"Aktuelle Themen BMK KW {week}/{year}",
                        body=html,
                        from_email=ns.from_email,
                        to=[ns.recipient],
                    )
                    msg.content_subtype = "html"
                    msg.send()
                    mail_obj.status = "sent"
                    mail_obj.save()
                    messages.success(request, "Newsletter erfolgreich versendet!")
                    return redirect("info_mail_index")
    else:
        form = NewsletterComposeForm(instance=mail_obj)

    context = {
        "form": form,
        "mail": mail_obj,
        "week": week,
        "year": year,
        "ns": ns,
    }
    return render(request, "info_mail/compose_newsletter.html", context)
