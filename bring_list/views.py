from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BringItemForm, BringListForm
from .models import BringItem, BringList

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SESSION_KEY = "bring_owned_{token}"


def _owned_tokens(request, public_token):
    """Return the list of edit_token strings owned in this session for a list."""
    key = SESSION_KEY.format(token=str(public_token))
    return request.session.get(key, [])


def _add_owned_token(request, public_token, edit_token):
    key = SESSION_KEY.format(token=str(public_token))
    owned = request.session.get(key, [])
    if str(edit_token) not in owned:
        owned.append(str(edit_token))
    request.session[key] = owned
    request.session.modified = True


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------


def list_view(request, public_token):
    bring_list = get_object_or_404(BringList, public_token=public_token)
    items = bring_list.items.all()
    form = BringItemForm(show_quantity=bring_list.show_quantity)

    owned = set(_owned_tokens(request, public_token))

    return render(
        request,
        "bring_list/list.html",
        {
            "bring_list": bring_list,
            "items": items,
            "form": form,
            "owned": owned,
        },
    )


def add_item_view(request, public_token):
    bring_list = get_object_or_404(BringList, public_token=public_token)

    if request.method != "POST":
        return redirect("bring_list:list", public_token=public_token)

    form = BringItemForm(request.POST, show_quantity=bring_list.show_quantity)
    if form.is_valid():
        item = form.save(commit=False)
        item.bring_list = bring_list
        item.save()

        if bring_list.edit_mode == "own":
            _add_owned_token(request, public_token, item.edit_token)

        return redirect("bring_list:list", public_token=public_token)

    # Re-render with errors
    items = bring_list.items.all()
    owned = set(_owned_tokens(request, public_token))
    return render(
        request,
        "bring_list/list.html",
        {
            "bring_list": bring_list,
            "items": items,
            "form": form,
            "owned": owned,
        },
    )


def edit_item_view(request, public_token, edit_token):
    bring_list = get_object_or_404(BringList, public_token=public_token)
    item = get_object_or_404(BringItem, edit_token=edit_token, bring_list=bring_list)

    if bring_list.edit_mode == "insert_only":
        return HttpResponseForbidden("Bearbeiten ist für diese Liste nicht erlaubt.")

    if bring_list.edit_mode == "own":
        if str(edit_token) not in _owned_tokens(request, public_token):
            return HttpResponseForbidden("Du kannst nur deine eigenen Einträge bearbeiten.")

    if request.method == "POST":
        form = BringItemForm(request.POST, instance=item, show_quantity=bring_list.show_quantity)
        if form.is_valid():
            form.save()
            return redirect("bring_list:list", public_token=public_token)
    else:
        form = BringItemForm(instance=item, show_quantity=bring_list.show_quantity)

    return render(
        request,
        "bring_list/edit_item.html",
        {
            "bring_list": bring_list,
            "item": item,
            "form": form,
        },
    )


def list_by_slug_view(request, slug):
    bring_list = get_object_or_404(BringList, slug=slug)
    return redirect("bring_list:list", public_token=bring_list.public_token)


# ---------------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------------


@staff_member_required
def admin_overview_view(request):
    lists = BringList.objects.annotate(item_count=Count("items"))
    return render(request, "bring_list/admin_overview.html", {"lists": lists})


@staff_member_required
def admin_create_view(request):
    if request.method == "POST":
        form = BringListForm(request.POST)
        if form.is_valid():
            bring_list = form.save()
            return redirect("bring_list:admin_detail", slug=bring_list.slug)
    else:
        form = BringListForm()

    return render(request, "bring_list/admin_create.html", {"form": form})


@staff_member_required
def admin_detail_view(request, slug):
    bring_list = get_object_or_404(BringList, slug=slug)
    items = bring_list.items.all()
    return render(
        request,
        "bring_list/admin_detail.html",
        {"bring_list": bring_list, "items": items},
    )


@staff_member_required
def admin_edit_list_view(request, slug):
    bring_list = get_object_or_404(BringList, slug=slug)

    if request.method == "POST":
        form = BringListForm(request.POST, instance=bring_list)
        if form.is_valid():
            form.save()
            return redirect("bring_list:admin_detail", slug=bring_list.slug)
    else:
        form = BringListForm(instance=bring_list)

    return render(
        request,
        "bring_list/admin_edit_list.html",
        {"bring_list": bring_list, "form": form},
    )


@staff_member_required
def admin_edit_item_view(request, slug, pk):
    bring_list = get_object_or_404(BringList, slug=slug)
    item = get_object_or_404(BringItem, pk=pk, bring_list=bring_list)

    if request.method == "POST":
        form = BringItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect("bring_list:admin_detail", slug=bring_list.slug)
    else:
        form = BringItemForm(instance=item)

    return render(
        request,
        "bring_list/admin_edit_item.html",
        {"bring_list": bring_list, "item": item, "form": form},
    )


@staff_member_required
def admin_delete_item_view(request, slug, pk):
    bring_list = get_object_or_404(BringList, slug=slug)
    item = get_object_or_404(BringItem, pk=pk, bring_list=bring_list)

    if request.method == "POST":
        item.delete()

    return redirect("bring_list:admin_detail", slug=bring_list.slug)


@staff_member_required
def admin_toggle_quantity_view(request, slug):
    bring_list = get_object_or_404(BringList, slug=slug)
    if request.method == "POST":
        bring_list.show_quantity = not bring_list.show_quantity
        bring_list.save(update_fields=["show_quantity"])
    return redirect("bring_list:admin_detail", slug=bring_list.slug)
