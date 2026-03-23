import json
import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.db import models as db_models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localtime
from django.views.decorators.http import require_http_methods

from .forms import ConcertForm, TicketOrderForm
from .models import Concert, TicketOrder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: confirmation email
# ---------------------------------------------------------------------------

def _send_confirmation_email(order):
    """Send German-language confirmation email to the customer (HTML + plain text)."""
    context = {
        "order": order,
        "adult_subtotal": order.adult_count * order.concert.adult_price,
        "child_subtotal": order.child_count * order.concert.child_price,
    }

    subject = f"Ihre Kartenreservierung: {order.concert.name}"
    text_body = render_to_string("tickets/email_confirmation.txt", context)
    html_body = render_to_string("tickets/email_confirmation.html", context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.customer_email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send(fail_silently=False)
    except Exception as exc:
        logger.error(
            "Failed to send confirmation email for order %s: %s",
            order.confirmation_code,
            exc,
        )


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------

def concert_list(request):
    """Public: list of active concerts available for reservation."""
    concerts = Concert.objects.filter(is_active=True).order_by("date")
    context = {"concerts": concerts}
    return render(request, "tickets/concert_list.html", context)


def concert_detail(request, slug):
    """Public: concert detail page with reservation form."""
    concert = get_object_or_404(Concert, slug=slug)

    if request.method == "POST":
        if not concert.is_active:
            messages.error(
                request,
                "Der Vorverkauf für dieses Konzert ist leider beendet.",
            )
            return redirect("tickets:concert_detail", slug=slug)

        form = TicketOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.concert = concert

            capacity_errors = []
            if order.adult_count > concert.adults_remaining:
                if concert.adults_remaining == 0:
                    capacity_errors.append("Leider sind keine Erwachsenen-Tickets mehr verfügbar.")
                else:
                    capacity_errors.append(
                        f"Leider sind nur noch {concert.adults_remaining} Erwachsenen-Ticket(s) verfügbar."
                    )
            if order.child_count > concert.children_remaining:
                if concert.children_remaining == 0:
                    capacity_errors.append("Leider sind keine Kinder-Tickets mehr verfügbar.")
                else:
                    capacity_errors.append(
                        f"Leider sind nur noch {concert.children_remaining} Kinder-Ticket(s) (bis 12 Jahre) verfügbar."
                    )
            if capacity_errors:
                form.add_error(None, " ".join(capacity_errors))
            else:
                order.save()
                _send_confirmation_email(order)
                return redirect(
                    "tickets:bestaetigung",
                    slug=slug,
                    confirmation_code=order.confirmation_code,
                )
    else:
        form = TicketOrderForm(initial={"adult_count": 1, "child_count": 0})

    context = {
        "concert": concert,
        "form": form,
    }
    return render(request, "tickets/concert_detail.html", context)


def bestaetigung(request, slug, confirmation_code):
    """Public: confirmation page shown after a successful reservation."""
    concert = get_object_or_404(Concert, slug=slug)
    order = get_object_or_404(
        TicketOrder, confirmation_code=confirmation_code, concert=concert
    )
    context = {
        "concert": concert,
        "order": order,
    }
    return render(request, "tickets/bestaetigung.html", context)


# ---------------------------------------------------------------------------
# Admin views (staff only)
# ---------------------------------------------------------------------------

@staff_member_required
def admin_concert_list(request):
    """Admin: list all concerts with stats."""
    concerts = Concert.objects.all().order_by("date")
    concerts_data = []
    total_all_revenue = 0
    total_all_tickets = 0
    total_all_orders = 0

    for concert in concerts:
        agg = concert.orders.filter(
            status__in=["ausstehend", "bestaetigt"]
        ).aggregate(
            adults=db_models.Sum("adult_count"),
            children=db_models.Sum("child_count"),
            revenue=db_models.Sum("total_price"),
        )
        order_count = concert.orders.count()
        adults_sold = agg["adults"] or 0
        children_sold = agg["children"] or 0
        revenue = agg["revenue"] or 0

        total_all_revenue += revenue
        total_all_tickets += adults_sold + children_sold
        total_all_orders += order_count

        concerts_data.append(
            {
                "concert": concert,
                "order_count": order_count,
                "adults_sold": adults_sold,
                "children_sold": children_sold,
                "revenue": revenue,
            }
        )

    context = {
        "concerts_data": concerts_data,
        "total_all_revenue": total_all_revenue,
        "total_all_tickets": total_all_tickets,
        "total_all_orders": total_all_orders,
    }
    return render(request, "tickets/admin_concert_list.html", context)


@staff_member_required
def admin_concert_create(request):
    """Admin: create a new concert."""
    if request.method == "POST":
        form = ConcertForm(request.POST, request.FILES)
        if form.is_valid():
            concert = form.save()
            messages.success(
                request,
                f'Konzert "{concert.name}" wurde erfolgreich erstellt.',
            )
            return redirect("tickets:admin_concert_detail", slug=concert.slug)
    else:
        form = ConcertForm()

    context = {
        "form": form,
        "action": "Neues Konzert anlegen",
        "is_create": True,
    }
    return render(request, "tickets/admin_concert_create.html", context)


@staff_member_required
def admin_concert_detail(request, slug):
    """Admin: edit concert details and see a summary of its orders."""
    concert = get_object_or_404(Concert, slug=slug)

    if request.method == "POST":
        form = ConcertForm(request.POST, request.FILES, instance=concert)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Konzert "{concert.name}" wurde gespeichert.',
            )
            return redirect("tickets:admin_concert_detail", slug=concert.slug)
    else:
        form = ConcertForm(instance=concert)
        if concert.date:
            form.initial["date"] = localtime(concert.date).strftime("%Y-%m-%dT%H:%M")

    recent_orders = concert.orders.all().order_by("-created_at")[:10]
    order_stats = concert.orders.aggregate(
        total_orders=db_models.Count("id"),
        confirmed=db_models.Count(
            "id", filter=db_models.Q(status="bestaetigt")
        ),
        pending=db_models.Count(
            "id", filter=db_models.Q(status="ausstehend")
        ),
        cancelled=db_models.Count(
            "id", filter=db_models.Q(status="storniert")
        ),
        revenue=db_models.Sum(
            "total_price",
            filter=db_models.Q(status__in=["ausstehend", "bestaetigt"]),
        ),
    )

    context = {
        "concert": concert,
        "form": form,
        "recent_orders": recent_orders,
        "order_stats": order_stats,
    }
    return render(request, "tickets/admin_concert_detail.html", context)


@staff_member_required
def admin_concert_bestellungen(request, slug):
    """Admin: full order list for a single concert."""
    concert = get_object_or_404(Concert, slug=slug)
    status_filter = request.GET.get("status", "")

    orders = concert.orders.all().order_by("-created_at")
    if status_filter in ["ausstehend", "bestaetigt", "storniert"]:
        orders = orders.filter(status=status_filter)

    order_stats = concert.orders.aggregate(
        total_orders=db_models.Count("id"),
        confirmed=db_models.Count(
            "id", filter=db_models.Q(status="bestaetigt")
        ),
        pending=db_models.Count(
            "id", filter=db_models.Q(status="ausstehend")
        ),
        cancelled=db_models.Count(
            "id", filter=db_models.Q(status="storniert")
        ),
        total_adults=db_models.Sum(
            "adult_count",
            filter=db_models.Q(status__in=["ausstehend", "bestaetigt"]),
        ),
        total_children=db_models.Sum(
            "child_count",
            filter=db_models.Q(status__in=["ausstehend", "bestaetigt"]),
        ),
        revenue=db_models.Sum(
            "total_price",
            filter=db_models.Q(status__in=["ausstehend", "bestaetigt"]),
        ),
    )

    context = {
        "concert": concert,
        "orders": orders,
        "order_stats": order_stats,
        "status_filter": status_filter,
    }
    return render(request, "tickets/admin_concert_bestellungen.html", context)


@staff_member_required
def admin_all_bestellungen(request):
    """Admin: overview of ALL orders across all concerts."""
    status_filter = request.GET.get("status", "")
    concert_filter = request.GET.get("concert", "")

    orders = (
        TicketOrder.objects.all()
        .select_related("concert")
        .order_by("-created_at")
    )
    if status_filter in ["ausstehend", "bestaetigt", "storniert"]:
        orders = orders.filter(status=status_filter)
    if concert_filter:
        orders = orders.filter(concert__slug=concert_filter)

    all_concerts = Concert.objects.all().order_by("name")
    total_stats = TicketOrder.objects.filter(
        status__in=["ausstehend", "bestaetigt"]
    ).aggregate(
        total_adults=db_models.Sum("adult_count"),
        total_children=db_models.Sum("child_count"),
        total_revenue=db_models.Sum("total_price"),
    )

    context = {
        "orders": orders,
        "all_concerts": all_concerts,
        "status_filter": status_filter,
        "concert_filter": concert_filter,
        "total_stats": total_stats,
    }
    return render(request, "tickets/admin_all_bestellungen.html", context)


@staff_member_required
@require_http_methods(["POST"])
def admin_order_status_update(request, order_id):
    """Admin: update an order's status via AJAX POST."""
    order = get_object_or_404(TicketOrder, id=order_id)
    try:
        data = json.loads(request.body)
        new_status = data.get("status")
        valid_statuses = ["ausstehend", "bestaetigt", "storniert"]
        if new_status not in valid_statuses:
            return JsonResponse(
                {"success": False, "error": "Ungültiger Status"}, status=400
            )
        order.status = new_status
        order.save(update_fields=["status"])
        return JsonResponse(
            {
                "success": True,
                "status": order.status,
                "status_display": order.get_status_display(),
            }
        )
    except (json.JSONDecodeError, Exception) as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
