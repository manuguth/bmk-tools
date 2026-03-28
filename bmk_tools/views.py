"""
Project-level views for bmk-tools.

This module contains the main home/dashboard view that aggregates live stats
from all installed apps (tickets, festival, bring_list, info_mail) and presents
them on a single overview page.
"""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from bring_list.models import BringList
from festival.models import Festival
from info_mail.models import WeeklyMails
from tickets.models import Concert


@login_required
def home(request):
    """
    Main dashboard / home page.

    Aggregates live stats from every app so authenticated users get an instant
    overview of what's happening across all BMK tools.

    Context variables:
        active_concerts     -- QuerySet of currently active (on-sale) concerts
        next_concert        -- The nearest upcoming Concert, or None
        active_festivals    -- QuerySet of festivals with status='active'
        bring_list_count    -- Total number of Bring-Listen in the system
        latest_mail         -- Most recent WeeklyMails entry, or None
        today               -- Current date (used in template comparisons)
    """
    today = date.today()

    # Tickets: active / upcoming concerts – materialise once to avoid extra
    # count() + iteration queries.
    active_concerts = list(Concert.objects.filter(is_active=True).order_by("date"))
    next_concert = next(
        (c for c in active_concerts if c.date.date() >= today), None
    )

    # Festival: currently active festivals – same single-query approach.
    active_festivals = list(Festival.objects.filter(status="active").order_by("start_date"))

    # Bring-Listen: total list count
    bring_list_count = BringList.objects.count()

    # Info Mails: most recently uploaded weekly mail
    latest_mail = WeeklyMails.objects.order_by("-year", "-week").first()

    context = {
        "active_concerts": active_concerts,
        "next_concert": next_concert,
        "active_concerts_count": len(active_concerts),
        "active_festivals": active_festivals,
        "active_festivals_count": len(active_festivals),
        "bring_list_count": bring_list_count,
        "latest_mail": latest_mail,
        "today": today,
    }
    return render(request, "home.html", context)
