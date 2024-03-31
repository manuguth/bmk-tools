from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from info_mail.models import WeeklyMails

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
            weekly_mail = WeeklyMails.objects.get(week=request.data['week'], year=request.data['year'])
        except WeeklyMails.DoesNotExist:
            return Response({"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = WeeklyMailsSerializer(weekly_mail, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)