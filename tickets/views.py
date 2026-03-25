import csv
import io
import json
import logging

from django.contrib import messages
from .decorators import tickets_admin_required, scanner_required
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.conf import settings
from django.db import models as db_models, transaction
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timezone import localtime
from django.views.decorators.http import require_http_methods

import qrcode

from .forms import ConcertForm, TicketOrderForm
from .models import Concert, TicketOrder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: confirmation email
# ---------------------------------------------------------------------------

def _send_confirmation_email(order, request=None):
    """Send German-language confirmation email to the customer (HTML + plain text)."""
    qr_url = None
    if request is not None:
        qr_url = request.build_absolute_uri(
            reverse("tickets:ticket_qr_code", args=[order.confirmation_code])
        )
    context = {
        "order": order,
        "adult_subtotal": order.adult_count * order.concert.adult_price,
        "child_subtotal": order.child_count * order.concert.child_price,
        "qr_url": qr_url,
    }

    subject = f"Reservierungsbestätigung: {order.concert.name}"
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
        return True
    except Exception as exc:
        logger.error(
            "Failed to send confirmation email for order %s: %s",
            order.confirmation_code,
            exc,
        )
        return False


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

            # Lock the concert row to prevent overselling under concurrency.
            with transaction.atomic():
                concert = Concert.objects.select_for_update().get(pk=concert.pk)
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

            if not form.errors:
                email_sent = _send_confirmation_email(order, request=request)
                request.session["email_sent"] = email_sent
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
    email_sent = request.session.pop("email_sent", True)
    context = {
        "concert": concert,
        "order": order,
        "email_sent": email_sent,
    }
    return render(request, "tickets/bestaetigung.html", context)


# ---------------------------------------------------------------------------
# Admin views (staff only)
# ---------------------------------------------------------------------------

@tickets_admin_required
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


@tickets_admin_required
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


@tickets_admin_required
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


@tickets_admin_required
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

    paginator = Paginator(orders, 50)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "concert": concert,
        "orders": page,
        "order_stats": order_stats,
        "status_filter": status_filter,
    }
    return render(request, "tickets/admin_concert_bestellungen.html", context)


@tickets_admin_required
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

    paginator = Paginator(orders, 50)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "orders": page,
        "all_concerts": all_concerts,
        "status_filter": status_filter,
        "concert_filter": concert_filter,
        "total_stats": total_stats,
    }
    return render(request, "tickets/admin_all_bestellungen.html", context)


@tickets_admin_required
def admin_export_orders_csv(request):
    """Admin: export orders as CSV download, optionally filtered by concert."""
    concert_slug = request.GET.get("concert", "")
    orders = TicketOrder.objects.select_related("concert").order_by("-created_at")
    filename = "bestellungen_alle.csv"
    if concert_slug:
        concert = get_object_or_404(Concert, slug=concert_slug)
        orders = orders.filter(concert=concert)
        filename = f"bestellungen_{concert.slug}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # BOM for Excel UTF-8

    writer = csv.writer(response, delimiter=";")
    writer.writerow([
        "Konzert", "Datum", "Vorname", "Nachname", "E-Mail", "Telefon",
        "Erwachsene", "Kinder", "Gesamtpreis", "Status", "Abgeholt",
        "Bestätigungscode", "Erstellt am",
    ])
    for o in orders.iterator():
        writer.writerow([
            o.concert.name,
            localtime(o.concert.date).strftime("%d.%m.%Y %H:%M") if o.concert.date else "",
            o.customer_firstname,
            o.customer_lastname,
            o.customer_email,
            o.customer_phone or "",
            o.adult_count,
            o.child_count,
            f"{o.total_price:.2f}".replace(".", ","),
            o.get_status_display(),
            "Ja" if o.collected else "Nein",
            o.confirmation_code,
            localtime(o.created_at).strftime("%d.%m.%Y %H:%M"),
        ])
    return response


@tickets_admin_required
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
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Ungültige Anfrage."}, status=400)
    except Exception as exc:
        logger.error("Error updating order %s status: %s", order_id, exc)
        return JsonResponse({"success": False, "error": "Interner Fehler."}, status=400)


# ---------------------------------------------------------------------------
# QR code and Einlass views
# ---------------------------------------------------------------------------

def ticket_qr_code(request, confirmation_code):
    """Public: generate and serve a QR code PNG with the confirmation code payload."""
    order = get_object_or_404(TicketOrder, confirmation_code=confirmation_code)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    # Encode only the ticket code so scanning is independent from host/proxy setup.
    qr.add_data(order.confirmation_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@scanner_required
def einlass_scanner(request):
    """Scanner: mobile QR code scanner page for Einlass."""
    return render(request, "tickets/einlass_scanner.html")


@scanner_required
def einlass_name_search(request):
    """Scanner: search orders by customer name (JSON, GET)."""
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})
    terms = query.split()
    # Build a broad OR filter: any term matching firstname or lastname qualifies.
    combined = db_models.Q()
    for term in terms:
        combined |= (
            db_models.Q(customer_firstname__icontains=term)
            | db_models.Q(customer_lastname__icontains=term)
        )
    qs = (
        TicketOrder.objects.select_related("concert")
        .filter(combined)
        .order_by("customer_lastname", "customer_firstname")[:50]
    )
    results = [
        {
            "code": o.confirmation_code,
            "name": o.customer_full_name,
            "concert": o.concert.name,
            "status": o.status,
            "status_display": o.get_status_display(),
            "collected": o.collected,
            "url": reverse("tickets:einlass_detail", args=[o.confirmation_code]),
        }
        for o in qs
    ]
    return JsonResponse({"results": results})


@scanner_required
def einlass_detail(request, confirmation_code):
    """Scanner: show order details and allow marking as collected."""
    order = get_object_or_404(TicketOrder, confirmation_code=confirmation_code)
    context = {"order": order}
    return render(request, "tickets/einlass_detail.html", context)


@scanner_required
@require_http_methods(["POST"])
def einlass_mark_collected(request, confirmation_code):
    """Scanner: mark a TicketOrder as collected, with optional count adjustment."""
    order = get_object_or_404(TicketOrder, confirmation_code=confirmation_code)

    if order.status == "storniert":
        messages.error(
            request,
            f"Bestellung {confirmation_code} ist storniert und kann nicht als abgeholt markiert werden.",
        )
        return redirect("tickets:einlass_detail", confirmation_code=confirmation_code)

    try:
        collected_adult = int(request.POST.get("collected_adult_count", order.adult_count))
        collected_child = int(request.POST.get("collected_child_count", order.child_count))
    except (ValueError, TypeError):
        collected_adult = order.adult_count
        collected_child = order.child_count

    collected_adult = max(0, collected_adult)
    collected_child = max(0, collected_child)

    adjusted = (
        collected_adult != order.adult_count or collected_child != order.child_count
    )

    new_price = (
        collected_adult * order.concert.adult_price
        + collected_child * order.concert.child_price
    )

    order.collected = True
    order.collected_adult_count = collected_adult
    order.collected_child_count = collected_child
    order.total_price = new_price
    order.save(update_fields=["collected", "collected_adult_count", "collected_child_count", "total_price"])

    if adjusted:
        messages.success(
            request,
            f"Bestellung {confirmation_code} abgeholt — Anzahl angepasst: "
            f"{collected_adult} Erw. / {collected_child} Kinder "
            f"(reserviert: {order.adult_count} Erw. / {order.child_count} Kinder). "
            f"Neuer Preis: {new_price:.2f} €.",
        )
    else:
        messages.success(request, f"Bestellung {confirmation_code} als abgeholt markiert.")

    return redirect("tickets:einlass_detail", confirmation_code=confirmation_code)
