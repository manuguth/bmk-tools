from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from info_mail.models import WeeklyMails
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    return render(request, "info_mail/home.html", {})

@login_required
def info_mail_index(request: HttpRequest) -> HttpResponse:
    weekly_mails = WeeklyMails.objects.order_by('-year', '-week')
    context = {"weekly_mails": weekly_mails}
    return render(request, "info_mail/info_mail_index.html", context)

def info_mail_details(request: HttpRequest, reference:str) -> HttpResponse:
    weekly_mails = WeeklyMails.objects.get(reference=reference)
    html_file = weekly_mails.html_file
    return HttpResponse(html_file.read(), content_type='text/html')