import csv
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db import transaction
from django.db.models import Count, Sum, Prefetch
from django.utils.html import strip_tags
from django.conf import settings

from .models import Order, OrderTemplate, OrderMenuItem, OrderLineItem
from .forms import (
    OrderForm, OrderTemplateForm, OrderMenuItemForm,
    OrderMenuItemFormSet, OrderLineItemForm
)


# ============================================================================
# PUBLIC VIEWS
# ============================================================================

def order_form(request):
    """Public view for submitting orders."""
    # Get the active template for current year
    template = OrderTemplate.objects.filter(is_active=True).first()

    if not template:
        context = {
            'no_template': True,
            'message': 'Bestellungen sind aktuell nicht verfügbar. Bitte versuchen Sie es später erneut.'
        }
        return render(request, 'orders/order_form.html', context)

    if request.method == 'POST':
        form = OrderForm(request.POST, template=template)

        # Collect quantities from form
        menu_items = OrderMenuItem.objects.filter(template=template)
        line_item_data = {}

        for item in menu_items:
            qty_key = f'quantity_{item.id}'
            if qty_key in request.POST:
                try:
                    quantity = int(request.POST[qty_key])
                    if quantity > 0:
                        line_item_data[item.id] = quantity
                except (ValueError, TypeError):
                    pass

        # Check that at least one item was selected
        if not line_item_data and form.is_valid():
            form.add_error(None, 'Bitte wählen Sie mindestens einen Artikel aus.')

        if form.is_valid() and line_item_data:
            # Create order
            order = form.save(commit=False)
            order.template = template

            with transaction.atomic():
                order.save()

                # Create line items
                for menu_item_id, quantity in line_item_data.items():
                    menu_item = OrderMenuItem.objects.get(id=menu_item_id)
                    OrderLineItem.objects.create(
                        order=order,
                        menu_item=menu_item,
                        quantity=quantity,
                        unit_price=menu_item.price,
                    )

                # Send confirmation email
                send_order_confirmation_email(order)

            return redirect('bestellung:order_confirmation', order_id=order.id)
    else:
        form = OrderForm(template=template)

    # Prepare menu items grouped by category
    menu_items_by_category = {}
    for item in OrderMenuItem.objects.filter(template=template):
        cat = item.get_category_display()
        if cat not in menu_items_by_category:
            menu_items_by_category[cat] = []
        menu_items_by_category[cat].append(item)

    context = {
        'form': form,
        'template': template,
        'menu_items_by_category': menu_items_by_category,
        'no_template': False,
    }
    return render(request, 'orders/order_form.html', context)


def order_confirmation(request, order_id):
    """Display order confirmation after submission."""
    order = get_object_or_404(Order, id=order_id)

    context = {
        'order': order,
        'line_items': order.line_items.select_related('menu_item'),
        'total_price': order.total_price,
    }
    return render(request, 'orders/order_confirmation.html', context)


# ============================================================================
# ADMIN VIEWS - TEMPLATE MANAGEMENT
# ============================================================================

@staff_member_required
def admin_template_list(request):
    """List all order templates."""
    templates = OrderTemplate.objects.annotate(
        menu_item_count=Count('menu_items'),
        order_count=Count('orders'),
    ).order_by('-year')

    context = {
        'templates': templates,
    }
    return render(request, 'orders/admin_template_list.html', context)


@staff_member_required
def admin_template_create(request):
    """Create a new order template."""
    if request.method == 'POST':
        form = OrderTemplateForm(request.POST)
        if form.is_valid():
            template = form.save()
            return redirect('bestellung:admin_menu_items', template_id=template.id)
    else:
        form = OrderTemplateForm()

    context = {
        'form': form,
        'is_create': True,
    }
    return render(request, 'orders/admin_template_edit.html', context)


@staff_member_required
def admin_template_edit(request, template_id):
    """Edit an existing order template."""
    template = get_object_or_404(OrderTemplate, id=template_id)

    if request.method == 'POST':
        form = OrderTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            return redirect('bestellung:admin_menu_items', template_id=template.id)
    else:
        form = OrderTemplateForm(instance=template)

    context = {
        'form': form,
        'template': template,
        'is_create': False,
    }
    return render(request, 'orders/admin_template_edit.html', context)


@staff_member_required
def admin_menu_items(request, template_id):
    """Edit menu items for a template."""
    template = get_object_or_404(OrderTemplate, id=template_id)

    # Group items by category for display
    items_by_category = {}
    for item in template.menu_items.all():
        cat = item.get_category_display()
        if cat not in items_by_category:
            items_by_category[cat] = []
        items_by_category[cat].append(item)

    # Create a blank form for the add item section (not a formset)
    blank_form = OrderMenuItemForm()

    context = {
        'template': template,
        'blank_form': blank_form,
        'items_by_category': items_by_category,
    }
    return render(request, 'orders/admin_menu_items.html', context)


@staff_member_required
@require_http_methods(["POST"])
def create_menu_item_ajax(request, template_id):
    """AJAX endpoint to create a single menu item."""
    template = get_object_or_404(OrderTemplate, id=template_id)

    # Create form with POST data
    form = OrderMenuItemForm(request.POST)

    if form.is_valid():
        # Create the menu item
        menu_item = form.save(commit=False)
        menu_item.template = template
        try:
            menu_item.save()
            return JsonResponse({
                'success': True,
                'message': 'Artikel erfolgreich hinzugefügt',
                'item_id': menu_item.id,
                'category': menu_item.get_category_display(),
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Fehler beim Speichern: {str(e)}',
            }, status=400)
    else:
        # Return validation errors
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = error_list[0] if error_list else 'Unknown error'

        return JsonResponse({
            'success': False,
            'message': 'Validierungsfehler',
            'errors': errors,
        }, status=400)


# ============================================================================
# ADMIN VIEWS - ORDERS MANAGEMENT
# ============================================================================

@staff_member_required
def admin_orders_list(request):
    """List all submitted orders."""
    orders = Order.objects.select_related('template').prefetch_related('line_items')

    # Filter by template year
    template_year = request.GET.get('template_year')
    if template_year:
        orders = orders.filter(template__year=template_year)

    # Filter by status
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)

    # Search by company name or email
    search = request.GET.get('search')
    if search:
        orders = orders.filter(company_name__icontains=search)

    # Get distinct template years for filter
    template_years = OrderTemplate.objects.values_list('year', flat=True).distinct().order_by('-year')

    # Add computed fields
    orders_with_totals = []
    for order in orders:
        order.total = order.total_price
        orders_with_totals.append(order)

    context = {
        'orders': orders_with_totals,
        'template_years': template_years,
        'selected_year': template_year,
        'selected_status': status,
        'search_query': search,
    }
    return render(request, 'orders/admin_orders_list.html', context)


@staff_member_required
def admin_order_detail(request, order_id):
    """View details of a single order."""
    order = get_object_or_404(
        Order.objects.prefetch_related('line_items__menu_item'),
        id=order_id
    )

    if request.method == 'POST':
        # Allow updating status and notes
        status = request.POST.get('status')
        notes = request.POST.get('notes')

        if status in dict(Order.STATUS_CHOICES):
            order.status = status
        if notes is not None:
            order.notes = notes

        order.save()
        return redirect('bestellung:admin_order_detail', order_id=order.id)

    context = {
        'order': order,
        'line_items': order.line_items.all(),
        'total_price': order.total_price,
        'status_choices': Order.STATUS_CHOICES,
    }
    return render(request, 'orders/admin_order_detail.html', context)


@staff_member_required
@require_http_methods(["GET"])
def admin_orders_export(request):
    """Export orders to CSV."""
    template_year = request.GET.get('template_year')

    orders = Order.objects.select_related('template').prefetch_related('line_items__menu_item')

    if template_year:
        orders = orders.filter(template__year=template_year)

    # Create CSV response
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="bestellungen_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    # BOM for UTF-8
    response.write('\ufeff')

    writer = csv.writer(response)

    # Header
    writer.writerow([
        'Unternehmen',
        'Ansprechperson',
        'E-Mail',
        'Telefon',
        'Ankunftszeit',
        'Zahlungsweise',
        'Rechnungsadresse',
        'Artikel',
        'Gesamtpreis',
        'Status',
        'Bestelldatum',
        'Anmerkungen',
    ])

    # Data
    for order in orders:
        items_str = '; '.join([
            f"{li.quantity}x {li.menu_item.name} (€{li.unit_price})"
            for li in order.line_items.all()
        ])

        writer.writerow([
            order.company_name,
            order.contact_name,
            order.contact_email,
            order.contact_phone,
            order.arrival_time,
            order.get_payment_method_display(),
            order.invoice_address,
            items_str,
            f"€{order.total_price:.2f}",
            order.get_status_display(),
            order.created_at.strftime('%d.%m.%Y %H:%M'),
            order.notes,
        ])

    return response


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def send_order_confirmation_email(order):
    """Send confirmation email to company."""
    subject = f'Bestellbestätigung - BMK Festival {order.template.year}'

    # Prepare context for email template
    context = {
        'order': order,
        'line_items': order.line_items.select_related('menu_item'),
        'total_price': order.total_price,
        'year': order.template.year,
    }

    # Render both text and HTML versions
    html_message = render_to_string('orders/emails/order_confirmation.html', context)
    text_message = render_to_string('orders/emails/order_confirmation.txt', context)

    send_mail(
        subject,
        text_message,
        settings.DEFAULT_FROM_EMAIL,
        [order.contact_email],
        html_message=html_message,
        fail_silently=False,
    )
