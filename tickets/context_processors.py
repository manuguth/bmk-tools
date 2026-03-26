def tickets_admin(request):
    is_tickets_admin = (
        request.user.is_authenticated and (
            request.user.is_staff or
            request.user.groups.filter(name="Tickets Admin").exists()
        )
    )
    is_scanner = (
        request.user.is_authenticated and (
            request.user.is_staff or
            request.user.groups.filter(name__in={"Tickets Admin", "Ticket Scanner"}).exists()
        )
    )
    return {"is_tickets_admin": is_tickets_admin, "is_scanner": is_scanner}
