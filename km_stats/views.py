from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .dash_app import app


@login_required
def home(request):
    return render(request, "km_stats/home.html", {})

def dash_view(request):
    context = {'target_plot': app}
    return render(request, "km_stats/dashboard.html",context=context)