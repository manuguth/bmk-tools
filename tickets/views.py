import csv
import io
import json
import logging
from datetime import date as date_type

from django.contrib import messages
from .decorators import tickets_admin_required, scanner_required
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.conf import settings
from django.db import models as db_models, transaction
from django.db.models.functions import Least
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timezone import localtime
from django.views.decorators.http import require_http_methods

import qrcode

from .forms import AdminOrderEditForm, ConcertForm, TicketOrderForm
from .models import Concert, TicketOrder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: confirmation email
# ---------------------------------------------------------------------------

def _send_confirmation_email(order, request=None):
    """Send German-language confirmation email to the customer (HTML + plain text)."""
    if order.abendkasse:
        return False
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


def _send_order_update_email(order, request=None):
    """Send German-language update notification email to the customer (HTML + plain text)."""
    if order.abendkasse:
        return False
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
        "is_update": True,
    }

    subject = f"Aktualisierte Reservierungsbestätigung: {order.concert.name}"
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
            "Failed to send update email for order %s: %s",
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
        form = TicketOrderForm(initial={
            "adult_count": min(1, concert.adults_remaining),
            "child_count": 0,
        })

    adult_max_select = max(0, min(20, concert.adults_remaining))
    child_max_select = max(0, min(20, concert.children_remaining))

    context = {
        "concert": concert,
        "form": form,
        "adult_max_select": adult_max_select,
        "child_max_select": child_max_select,
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
        ).annotate(
            _effective_adults=db_models.Case(
                db_models.When(
                    collected=True,
                    collected_adult_count__isnull=False,
                    then=Least(
                        db_models.F("collected_adult_count"), db_models.F("adult_count")
                    ),
                ),
                default=db_models.F("adult_count"),
                output_field=db_models.IntegerField(),
            ),
            _effective_children=db_models.Case(
                db_models.When(
                    collected=True,
                    collected_child_count__isnull=False,
                    then=Least(
                        db_models.F("collected_child_count"), db_models.F("child_count")
                    ),
                ),
                default=db_models.F("child_count"),
                output_field=db_models.IntegerField(),
            ),
        ).aggregate(
            adults=db_models.Sum("_effective_adults"),
            children=db_models.Sum("_effective_children"),
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
@require_http_methods(["GET"])
def admin_export_orders_pdf(request):
    """Admin: export confirmed/pending orders as a PDF entrance list."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    concert_slug = request.GET.get("concert", "")
    orders = (
        TicketOrder.objects
        .select_related("concert")
        .exclude(status="storniert")
        .order_by("customer_lastname", "customer_firstname")
    )
    concert = None
    filename = "einlasskontrolle_alle.pdf"
    if concert_slug:
        concert = get_object_or_404(Concert, slug=concert_slug)
        orders = orders.filter(concert=concert)
        filename = f"einlasskontrolle_{concert.slug}.pdf"

    orders = list(orders)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Normal"],
        fontSize=13, fontName="Helvetica-Bold", spaceAfter=2 * mm,
    )
    subtitle_style = ParagraphStyle(
        "subtitle", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica", spaceAfter=6 * mm, textColor=colors.grey,
    )
    cell_style = ParagraphStyle(
        "cell", parent=styles["Normal"],
        fontSize=8, fontName="Helvetica", leading=10,
    )
    header_cell_style = ParagraphStyle(
        "header_cell", parent=styles["Normal"],
        fontSize=8, fontName="Helvetica-Bold", leading=10, textColor=colors.white,
    )

    story = []

    # Title block
    if concert:
        title_text = f"Einlasskontrolle: {concert.name}"
        date_text = (
            localtime(concert.date).strftime("%d.%m.%Y, %H:%M Uhr")
            + (f" · {concert.venue}" if concert.venue else "")
            if concert.date else ""
        )
    else:
        title_text = "Einlasskontrolle – alle Konzerte"
        date_text = ""
    story.append(Paragraph(title_text, title_style))
    if date_text:
        story.append(Paragraph(date_text, subtitle_style))
    else:
        story.append(Spacer(1, 4 * mm))

    # Table
    col_headers = ["#", "Name", "Telefon", "Erw.", "Ki.", "Preis", "Bestätigungscode", "Notizen", "Abgeholt", "Bezahlt"]
    # Column widths (total content width ~186 mm on A4 portrait with 12 mm margins each)
    col_widths = [7 * mm, 40 * mm, 28 * mm, 9 * mm, 9 * mm, 15 * mm, 26 * mm, 37 * mm, 10 * mm, 10 * mm]

    header_row = [Paragraph(h, header_cell_style) for h in col_headers]
    rows = [header_row]

    for idx, o in enumerate(orders, start=1):
        collected_cell = "\u2713" if o.collected else ""  # ✓ or empty
        paid_cell = "\u2713" if o.paid else ""
        rows.append([
            Paragraph(str(idx), cell_style),
            Paragraph(f"{o.customer_lastname}, {o.customer_firstname}", cell_style),
            Paragraph(o.customer_phone or "", cell_style),
            Paragraph(str(o.adult_count), cell_style),
            Paragraph(str(o.child_count), cell_style),
            Paragraph(f"{o.total_price:.2f}".replace(".", ",") + " €", cell_style),
            Paragraph(o.confirmation_code, cell_style),
            Paragraph(o.notes or "", cell_style),
            Paragraph(collected_cell, cell_style),
            Paragraph(paid_cell, cell_style),
        ])

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header styling
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        # Alignment
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 0), (4, -1), "CENTER"),   # Erw./Ki.
        ("ALIGN", (5, 0), (5, -1), "RIGHT"),    # Preis
        ("ALIGN", (8, 0), (8, -1), "CENTER"),   # Abgeholt
        ("ALIGN", (9, 0), (9, -1), "CENTER"),   # Bezahlt
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)

    doc.build(story)
    buf.seek(0)
    response = HttpResponse(buf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
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


@tickets_admin_required
def admin_order_edit(request, order_id):
    """Admin: display and process an edit form for a single TicketOrder."""
    order = get_object_or_404(TicketOrder.objects.select_related("concert"), id=order_id)

    if request.method == "POST":
        form = AdminOrderEditForm(request.POST, instance=order)
        if form.is_valid():
            updated_order = form.save(commit=False)
            # When unchecking Abgeholt, clear the per-item collected counts.
            if not updated_order.collected:
                updated_order.collected_adult_count = None
                updated_order.collected_child_count = None
            updated_order.save()  # model.save() auto-recalculates total_price
            order = updated_order
            send_email = request.POST.get("send_email") == "1"
            email_sent = False
            if send_email:
                email_sent = _send_order_update_email(order, request)
            if send_email and email_sent:
                messages.success(
                    request,
                    f"Bestellung {order.confirmation_code} gespeichert und Bestätigungs-E-Mail an {order.customer_email} gesendet.",
                )
            elif send_email and not email_sent:
                messages.warning(
                    request,
                    f"Bestellung {order.confirmation_code} gespeichert, aber E-Mail konnte nicht gesendet werden.",
                )
            else:
                messages.success(
                    request,
                    f"Bestellung {order.confirmation_code} erfolgreich gespeichert.",
                )
        else:
            messages.error(request, "Bitte korrigieren Sie die markierten Felder.")
    else:
        form = AdminOrderEditForm(instance=order)

    context = {
        "order": order,
        "form": form,
        "concert": order.concert,
    }
    return render(request, "tickets/admin_order_edit.html", context)


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
    today = date_type.today()
    active_concerts = Concert.objects.filter(is_active=True).order_by("date")
    # Determine if there is a single direct target for the Abendkasse button.
    today_concerts = [c for c in active_concerts if localtime(c.date).date() == today]
    if active_concerts.count() == 1:
        abendkasse_direct = active_concerts.first()
    elif len(today_concerts) == 1:
        abendkasse_direct = today_concerts[0]
    else:
        abendkasse_direct = None
    context = {
        "active_concerts": active_concerts,
        "abendkasse_direct": abendkasse_direct,
    }
    return render(request, "tickets/einlass_scanner.html", context)


@scanner_required
def einlass_name_search(request):
    """Scanner: search orders by customer name or confirmation code (JSON, GET)."""
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    # If the query looks like a bare confirmation code, try an exact match first
    # so the scanner can also type codes here without being redirected.
    code_like = query.upper()
    if len(code_like) >= 8 and code_like.replace(" ", "").isalnum():
        exact = TicketOrder.objects.select_related("concert").filter(
            confirmation_code=code_like.replace(" ", "")
        )
        if exact.exists():
            o = exact.first()
            return JsonResponse({"results": [{
                "code": o.confirmation_code,
                "name": o.customer_full_name,
                "concert": o.concert.name,
                "status": o.status,
                "status_display": o.get_status_display(),
                "collected": o.collected,
                "url": reverse("tickets:einlass_detail", args=[o.confirmation_code]),
            }]})

    terms = query.split()
    # Match any term against firstname, lastname, or confirmation code.
    combined = db_models.Q()
    for term in terms:
        combined |= (
            db_models.Q(customer_firstname__icontains=term)
            | db_models.Q(customer_lastname__icontains=term)
            | db_models.Q(confirmation_code__icontains=term.upper())
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
    context = {
        "order": order,
        "adults_can_add": order.concert.abendkasse_adults_remaining,
        "children_can_add": order.concert.abendkasse_children_remaining,
    }
    return render(request, "tickets/einlass_detail.html", context)


@scanner_required
@require_http_methods(["POST"])
def einlass_mark_collected(request, confirmation_code):
    """Scanner: mark a TicketOrder as collected, with optional count adjustment.

    Counts may be reduced below the ordered amount (no-shows → frees up VVK seats).
    Counts may be increased above the ordered amount only on the first scan; the
    extra tickets are automatically created as a separate Abendkasse order so they
    appear correctly in the Abendkasse stats and capacity is properly tracked.
    """
    order = get_object_or_404(TicketOrder, confirmation_code=confirmation_code)

    if order.status == "storniert":
        messages.error(
            request,
            f"Bestellung {confirmation_code} ist storniert und kann nicht als abgeholt markiert werden.",
        )
        return redirect("tickets:einlass_detail", confirmation_code=confirmation_code)

    try:
        raw_adult = int(request.POST.get("collected_adult_count", order.adult_count))
        raw_child = int(request.POST.get("collected_child_count", order.child_count))
    except (ValueError, TypeError):
        raw_adult = order.adult_count
        raw_child = order.child_count

    raw_adult = max(0, raw_adult)
    raw_child = max(0, raw_child)

    mark_paid = request.POST.get("mark_paid") == "1"

    with transaction.atomic():
        # Lock the order row so concurrent scans cannot both see collected=False,
        # both compute extras, and both create duplicate Abendkasse orders.
        order = TicketOrder.objects.select_for_update().select_related("concert").get(
            pk=order.pk
        )

        # Re-check status under the lock in case it changed since the outer fetch.
        if order.status == "storniert":
            messages.error(
                request,
                f"Bestellung {confirmation_code} ist storniert und kann nicht als abgeholt markiert werden.",
            )
            return redirect("tickets:einlass_detail", confirmation_code=confirmation_code)

        # Extras beyond the original reservation → separate Abendkasse order.
        # Recomputed under the lock so only one concurrent request can pass the
        # order.collected == False guard.
        extra_adult = max(0, raw_adult - order.adult_count)
        extra_child = max(0, raw_child - order.child_count)

        # Extras can only be granted on the first scan (order not yet collected).
        # Re-scans ignore extras.
        if order.collected:
            extra_adult = 0
            extra_child = 0

        adjusted = raw_adult != order.adult_count or raw_child != order.child_count

        # Price is based only on the original reservation; extras are tracked in the AK order.
        reserved_adult = min(raw_adult, order.adult_count)
        reserved_child = min(raw_child, order.child_count)
        new_price = (
            reserved_adult * order.concert.adult_price
            + reserved_child * order.concert.child_price
        )

        # Validate extras against remaining capacity; lock the Concert row so the
        # capacity check and the write are atomic.
        if extra_adult > 0 or extra_child > 0:
            concert_locked = Concert.objects.select_for_update().get(pk=order.concert_id)
            if extra_adult > concert_locked.abendkasse_adults_remaining:
                messages.error(
                    request,
                    f"Nicht genug freie Erwachsenen-Plätze für die Zusatztickets. "
                    f"Verfügbar: {concert_locked.abendkasse_adults_remaining}.",
                )
                return redirect("tickets:einlass_detail", confirmation_code=confirmation_code)
            if extra_child > concert_locked.abendkasse_children_remaining:
                messages.error(
                    request,
                    f"Nicht genug freie Kinder-Plätze für die Zusatztickets. "
                    f"Verfügbar: {concert_locked.abendkasse_children_remaining}.",
                )
                return redirect("tickets:einlass_detail", confirmation_code=confirmation_code)

        order.collected = True
        order.collected_adult_count = raw_adult  # full count for traceability
        order.collected_child_count = raw_child
        order.total_price = new_price
        order.paid = mark_paid
        order.save(update_fields=["collected", "collected_adult_count", "collected_child_count", "total_price", "paid"])

        if extra_adult > 0 or extra_child > 0:
            TicketOrder.objects.create(
                concert=order.concert,
                customer_firstname="Abendkasse",
                customer_lastname="",
                customer_email="abendkasse@abendkasse.local",
                adult_count=extra_adult,
                child_count=extra_child,
                status="bestaetigt",
                paid=True,
                collected=True,
                abendkasse=True,
                source_order=order,
            )

    if extra_adult > 0 or extra_child > 0:
        messages.success(
            request,
            f"Bestellung {confirmation_code} abgeholt — "
            f"{reserved_adult} Erw. / {reserved_child} Kinder aus Reservierung, "
            f"+ {extra_adult} Erw. / {extra_child} Kinder als Abendkasse-Zusatztickets.",
        )
    elif adjusted:
        messages.success(
            request,
            f"Bestellung {confirmation_code} abgeholt — Anzahl angepasst: "
            f"{reserved_adult} Erw. / {reserved_child} Kinder "
            f"(reserviert: {order.adult_count} Erw. / {order.child_count} Kinder). "
            f"Neuer Preis: {new_price:.2f} €.",
        )
    else:
        messages.success(request, f"Bestellung {confirmation_code} als abgeholt markiert.")

    return redirect("tickets:einlass_detail", confirmation_code=confirmation_code)


@scanner_required
@require_http_methods(["POST"])
def einlass_toggle_paid(request, confirmation_code):
    """Scanner: toggle the paid flag on a TicketOrder."""
    order = get_object_or_404(TicketOrder, confirmation_code=confirmation_code)
    order.paid = not order.paid
    order.save(update_fields=["paid"])
    return redirect("tickets:einlass_detail", confirmation_code=confirmation_code)


@scanner_required
def abendkasse_view(request, slug):
    """Abendkasse: live capacity stats and quick ticket sales for a concert."""
    concert = get_object_or_404(Concert, slug=slug)

    error = None
    success = request.method == "GET" and request.GET.get("success") == "1"

    if request.method == "POST":
        try:
            adult_count = int(request.POST.get("adult_count", 0))
            child_count = int(request.POST.get("child_count", 0))
        except (ValueError, TypeError):
            adult_count = 0
            child_count = 0

        adult_count = max(0, adult_count)
        child_count = max(0, child_count)

        if adult_count == 0 and child_count == 0:
            error = "Bitte mindestens ein Ticket auswählen."
        else:
            with transaction.atomic():
                # Re-read capacity inside the transaction to prevent races.
                concert_locked = Concert.objects.select_for_update().get(pk=concert.pk)
                if adult_count > concert_locked.abendkasse_adults_remaining:
                    error = (
                        f"Nicht genug freie Erwachsenen-Plätze. "
                        f"Verfügbar: {concert_locked.abendkasse_adults_remaining}."
                    )
                elif child_count > concert_locked.abendkasse_children_remaining:
                    error = (
                        f"Nicht genug freie Kinder-Plätze. "
                        f"Verfügbar: {concert_locked.abendkasse_children_remaining}."
                    )
                else:
                    TicketOrder.objects.create(
                        concert=concert_locked,
                        customer_firstname="Abendkasse",
                        customer_lastname="",
                        customer_email="abendkasse@abendkasse.local",
                        adult_count=adult_count,
                        child_count=child_count,
                        status="bestaetigt",
                        paid=True,
                        collected=True,
                        abendkasse=True,
                    )
                    return redirect(
                        reverse("tickets:abendkasse", kwargs={"slug": slug}) + "?success=1"
                    )

    # Compute stats for GET (and for POST with error, refresh concert data).
    active_statuses = ["ausstehend", "bestaetigt"]
    all_orders = concert.orders.filter(status__in=active_statuses)
    online_orders = all_orders.filter(abendkasse=False)
    box_orders = all_orders.filter(abendkasse=True)

    def sum_field(qs, field):
        from django.db.models import Sum
        return qs.aggregate(total=Sum(field))["total"] or 0

    def adjusted_sum(qs, count_field, collected_count_field):
        """Sum tickets using actual collected counts for scanned orders (same logic as adults_sold)."""
        return qs.aggregate(
            total=db_models.Sum(
                db_models.Case(
                    db_models.When(
                        collected=True,
                        **{f"{collected_count_field}__isnull": False},
                        then=Least(
                            db_models.F(collected_count_field),
                            db_models.F(count_field),
                        ),
                    ),
                    default=db_models.F(count_field),
                    output_field=db_models.IntegerField(),
                )
            )
        )["total"] or 0

    # Use adjusted counts for VVK so numbers are consistent with capacity (adults_sold).
    # AK orders always have collected_adult_count=None, so adjusted_sum == raw sum for them.
    online_adults = adjusted_sum(online_orders, "adult_count", "collected_adult_count")
    online_children = adjusted_sum(online_orders, "child_count", "collected_child_count")
    box_adults = sum_field(box_orders, "adult_count")
    box_children = sum_field(box_orders, "child_count")

    # Use model properties so the capacity bar uses the same basis as the POST check.
    # adults_sold substitutes collected_adult_count for scanned orders, so:
    #   adults_sold + adults_remaining == max_adults always.
    total_adults = concert.adults_sold
    total_children = concert.children_sold

    # Collected counts use adjusted values when available.
    collected_orders = all_orders.filter(collected=True)

    collected_adult_total = 0
    collected_child_total = 0
    for o in collected_orders:
        collected_adult_total += o.collected_adult_count if o.collected_adult_count is not None else o.adult_count
        collected_child_total += o.collected_child_count if o.collected_child_count is not None else o.child_count

    # Use the model property so the displayed number matches the POST capacity check.
    # The model accounts for collected_adult_count (actual attendees vs. ordered).
    adults_remaining = concert.abendkasse_adults_remaining
    children_remaining = concert.abendkasse_children_remaining

    # Seats reserved for late pickup (not yet collected, explicitly marked)
    late_orders = all_orders.filter(late_collection=True, collected=False)
    late_adults = sum_field(late_orders, "adult_count")
    late_children = sum_field(late_orders, "child_count")

    # Seats that will be freed once the pickup deadline passes:
    # uncollected online orders NOT marked for late collection.
    expiring_orders = online_orders.filter(late_collection=False, collected=False)
    expiring_adults = sum_field(expiring_orders, "adult_count")
    expiring_children = sum_field(expiring_orders, "child_count")

    after_deadline_adults = adults_remaining + expiring_adults
    after_deadline_children = children_remaining + expiring_children

    context = {
        "concert": concert,
        "error": error,
        "success": success,
        # Adults stats
        "online_adults": online_adults,
        "box_adults": box_adults,
        "total_adults": total_adults,
        "collected_adults": collected_adult_total,
        "adults_remaining": adults_remaining,
        "max_adults": concert.max_adults + concert.abendkasse_extra_adults,
        "abendkasse_extra_adults": concert.abendkasse_extra_adults,
        # Children stats
        "online_children": online_children,
        "box_children": box_children,
        "total_children": total_children,
        "collected_children": collected_child_total,
        "children_remaining": children_remaining,
        "max_children": concert.max_children + concert.abendkasse_extra_children,
        "abendkasse_extra_children": concert.abendkasse_extra_children,
        # Late collection & deadline stats
        "late_adults": late_adults,
        "late_children": late_children,
        "after_deadline_adults": after_deadline_adults,
        "after_deadline_children": after_deadline_children,
        "has_collection_deadline": concert.collection_deadline is not None,
        # Prices as strings for JS
        "adult_price": str(concert.adult_price),
        "child_price": str(concert.child_price),
    }
    return render(request, "tickets/abendkasse.html", context)
