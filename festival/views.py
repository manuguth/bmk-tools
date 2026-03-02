import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from .models import Festival, Shift, Task, Participant
from .forms import ParticipantSignUpForm


@staff_member_required
def admin_festival_list(request):
    """Admin view to list all festivals with stats."""
    festivals = Festival.objects.all().order_by("-start_date")
    festivals_data = []

    for festival in festivals:
        total_participants = Participant.objects.filter(task__shift__festival=festival).count()
        attended_count = Participant.objects.filter(
            task__shift__festival=festival, attended=True
        ).count()
        total_shifts = festival.shifts.count()

        festivals_data.append({
            "festival": festival,
            "total_participants": total_participants,
            "attended_count": attended_count,
            "total_shifts": total_shifts,
        })

    context = {
        "festivals_data": festivals_data,
    }
    return render(request, "festival/admin_festival_list.html", context)


def festival_detail(request, festival_slug):
    """Display festival details and list of shifts."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    shifts = festival.shifts.all()

    context = {
        "festival": festival,
        "shifts": shifts,
    }
    return render(request, "festival/festival_detail.html", context)


def shift_detail(request, festival_slug, shift_id):
    """Display shift details and available tasks."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    shift = get_object_or_404(Shift, id=shift_id, festival=festival)
    tasks = shift.tasks.all()

    context = {
        "festival": festival,
        "shift": shift,
        "tasks": tasks,
    }
    return render(request, "festival/shift_detail.html", context)


def task_signup(request, festival_slug, task_id):
    """Sign up a participant for a task."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    task = get_object_or_404(Task, id=task_id, shift__festival=festival)

    # Check if task is full
    if task.is_full:
        context = {
            "festival": festival,
            "task": task,
            "error": "This task is already full. No more sign-ups are available.",
        }
        return render(request, "festival/task_full.html", context)

    if request.method == "POST":
        form = ParticipantSignUpForm(request.POST)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.task = task
            participant.save()
            return redirect("festival:signup_confirmation", festival_slug=festival_slug, participant_id=participant.id)
    else:
        form = ParticipantSignUpForm()

    context = {
        "festival": festival,
        "task": task,
        "form": form,
    }
    return render(request, "festival/task_signup.html", context)


def signup_confirmation(request, festival_slug, participant_id):
    """Display confirmation after successful sign-up."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    participant = get_object_or_404(Participant, id=participant_id, task__shift__festival=festival)

    context = {
        "festival": festival,
        "participant": participant,
    }
    return render(request, "festival/signup_confirmation.html", context)


@staff_member_required
def admin_overview(request, festival_slug=None):
    """Admin dashboard overview."""
    if festival_slug:
        festival = get_object_or_404(Festival, slug=festival_slug)
    else:
        # Get the most recent active festival if no slug provided
        festival = Festival.objects.filter(status="active").order_by("-start_date").first()
        if not festival:
            festival = Festival.objects.order_by("-start_date").first()

    if not festival:
        context = {"festival": None, "shifts_data": []}
        return render(request, "festival/admin_overview.html", context)

    # Get all shifts with their tasks and participants
    shifts = festival.shifts.all()
    shifts_data = []

    for shift in shifts:
        participant_count = Participant.objects.filter(task__shift=shift).count()
        shifts_data.append({"shift": shift, "participant_count": participant_count})

    # Calculate stats
    total_participants = Participant.objects.filter(task__shift__festival=festival).count()
    total_required_helpers = Task.objects.filter(shift__festival=festival).aggregate(
        total=models.Sum('required_helpers')
    )['total'] or 0
    attended_count = Participant.objects.filter(
        task__shift__festival=festival, attended=True
    ).count()
    pending_count = total_participants - attended_count
    total_shifts = shifts.count()

    from django.utils import timezone

    context = {
        "festival": festival,
        "shifts_data": shifts_data,
        "total_participants": total_participants,
        "total_required_helpers": total_required_helpers,
        "total_shifts": total_shifts,
        "attended_count": attended_count,
        "pending_count": pending_count,
        "now": timezone.now(),
    }
    return render(request, "festival/admin_overview.html", context)


@staff_member_required
def participant_list_admin(request, festival_slug):
    """Admin view to manage participants."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    participants = Participant.objects.filter(task__shift__festival=festival).select_related(
        "task", "task__shift"
    )

    # Filter by attended status if specified
    attended_filter = request.GET.get("attended")
    if attended_filter == "true":
        participants = participants.filter(attended=True)
    elif attended_filter == "false":
        participants = participants.filter(attended=False)

    context = {
        "festival": festival,
        "participants": participants,
    }
    return render(request, "festival/participant_list_admin.html", context)


@staff_member_required
def export_participants_csv(request, festival_slug):
    """Export participants as CSV."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    participants = Participant.objects.filter(task__shift__festival=festival).select_related(
        "task", "task__shift"
    )

    # Create CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename=festival_{festival_slug}_participants.csv"

    writer = csv.writer(response)
    writer.writerow(["Name", "Shift", "Date", "Task", "Time", "Signed Up", "Attended"])

    for participant in participants:
        shift = participant.task.shift
        writer.writerow([
            participant.name,
            shift.name,
            shift.date,
            participant.task.name,
            f"{shift.start_time} - {shift.end_time}",
            participant.signed_up_at.strftime("%Y-%m-%d %H:%M"),
            "Yes" if participant.attended else "No",
        ])

    return response
