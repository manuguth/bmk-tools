from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.


def say_hello(request):
    return render(request, "hello.html", {"name": "Manu"})


def home_view(request):
    return render(request, "home.html")
