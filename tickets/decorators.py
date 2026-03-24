from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

_SCANNER_GROUPS = {"Tickets Admin", "Ticket Scanner"}


def tickets_admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings
            from django.shortcuts import redirect
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        if request.user.is_staff or request.user.groups.filter(name="Tickets Admin").exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped


def scanner_required(view_func):
    """Allow staff, Tickets Admin, and Ticket Scanner groups."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings
            from django.shortcuts import redirect
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        if request.user.is_staff or request.user.groups.filter(name__in=_SCANNER_GROUPS).exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped
