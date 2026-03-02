import csv
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.db import models
from .models import Festival, Shift, Task, Participant, TaskTemplate
from .forms import ParticipantSignUpForm


@staff_member_required
def admin_festival_list(request):
    """Admin view to list all festivals with stats."""
    festivals = Festival.objects.all().order_by("-start_date")
    festivals_data = []
    total_all_participants = 0
    total_all_required_helpers = 0
    total_all_shifts = 0

    for festival in festivals:
        total_participants = Participant.objects.filter(task__shift__festival=festival).count()
        total_required_helpers = Task.objects.filter(shift__festival=festival).aggregate(
            total=models.Sum('required_helpers')
        )['total'] or 0
        attended_count = Participant.objects.filter(
            task__shift__festival=festival, attended=True
        ).count()
        total_shifts = festival.shifts.count()
        total_all_participants += total_participants
        total_all_required_helpers += total_required_helpers
        total_all_shifts += total_shifts

        festivals_data.append({
            "festival": festival,
            "total_participants": total_participants,
            "total_required_helpers": total_required_helpers,
            "attended_count": attended_count,
            "total_shifts": total_shifts,
        })

    context = {
        "festivals_data": festivals_data,
        "total_all_participants": total_all_participants,
        "total_all_required_helpers": total_all_required_helpers,
        "total_all_shifts": total_all_shifts,
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
        total_required_helpers = Task.objects.filter(shift=shift).aggregate(
            total=models.Sum('required_helpers')
        )['total'] or 0
        shifts_data.append({
            "shift": shift,
            "participant_count": participant_count,
            "total_required_helpers": total_required_helpers,
        })

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


@staff_member_required
def admin_edit(request, festival_slug):
    """Admin edit view for managing shifts, tasks, and participants."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    # Get all shifts with tasks and participants
    shifts = festival.shifts.all()
    shifts_data = []

    for shift in shifts:
        tasks_data = []
        for task in shift.tasks.all():
            participants = Participant.objects.filter(task=task).select_related('task__shift')
            tasks_data.append({
                'task': task,
                'participants': participants,
            })
        shifts_data.append({
            'shift': shift,
            'tasks': tasks_data,
        })

    context = {
        'festival': festival,
        'shifts_data': shifts_data,
    }
    return render(request, 'festival/admin_edit.html', context)


@staff_member_required
@require_http_methods(["POST"])
def api_update_task(request, festival_slug, task_id):
    """API endpoint to update task details."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    task = get_object_or_404(Task, id=task_id, shift__festival=festival)

    try:
        data = json.loads(request.body)

        # Validate and update required_helpers
        if 'required_helpers' in data:
            required_helpers = int(data['required_helpers'])
            if required_helpers < 1:
                return JsonResponse({'success': False, 'error': 'Required helpers must be at least 1'}, status=400)
            task.required_helpers = required_helpers

        # Update description
        if 'description' in data:
            task.description = data['description']

        task.save()
        return JsonResponse({
            'success': True,
            'message': 'Task updated successfully',
            'data': {
                'required_helpers': task.required_helpers,
                'description': task.description,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid required_helpers value'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_update_shift(request, festival_slug, shift_id):
    """API endpoint to update shift details."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    shift = get_object_or_404(Shift, id=shift_id, festival=festival)

    try:
        data = json.loads(request.body)

        # Update description
        if 'description' in data:
            shift.description = data['description']

        shift.save()
        return JsonResponse({
            'success': True,
            'message': 'Shift updated successfully',
            'data': {
                'description': shift.description,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_update_participant(request, festival_slug, participant_id):
    """API endpoint to update participant details."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    participant = get_object_or_404(Participant, id=participant_id, task__shift__festival=festival)

    try:
        data = json.loads(request.body)

        # Update name
        if 'name' in data:
            participant.name = data['name']

        # Update attended status
        if 'attended' in data:
            participant.attended = data['attended'] in ['true', True, 'True', '1', 1]

        # Update notes
        if 'notes' in data:
            participant.notes = data['notes']

        participant.save()
        return JsonResponse({
            'success': True,
            'message': 'Participant updated successfully',
            'data': {
                'name': participant.name,
                'attended': participant.attended,
                'notes': participant.notes,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_delete_participant(request, festival_slug, participant_id):
    """API endpoint to delete a participant."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    participant = get_object_or_404(Participant, id=participant_id, task__shift__festival=festival)

    try:
        participant_name = participant.name
        participant.delete()
        return JsonResponse({
            'success': True,
            'message': f'Participant "{participant_name}" deleted successfully',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_create_task(request, festival_slug, shift_id):
    """API endpoint to create a new task."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    shift = get_object_or_404(Shift, id=shift_id, festival=festival)

    try:
        data = json.loads(request.body)

        # Validate required fields
        if not data.get('name'):
            return JsonResponse({'success': False, 'error': 'Task name is required'}, status=400)

        required_helpers = int(data.get('required_helpers', 1))
        if required_helpers < 1:
            return JsonResponse({'success': False, 'error': 'Required helpers must be at least 1'}, status=400)

        # Get template data if template_id provided
        description = data.get('description', '')
        special_requirements = data.get('special_requirements', '')

        if data.get('template_id'):
            try:
                template = TaskTemplate.objects.get(id=data['template_id'])
                description = template.description
                required_helpers = template.required_helpers
                special_requirements = template.special_requirements
            except TaskTemplate.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Template not found'}, status=404)

        # Create the task
        task = Task.objects.create(
            shift=shift,
            name=data['name'],
            description=description,
            required_helpers=required_helpers,
            special_requirements=special_requirements
        )

        return JsonResponse({
            'success': True,
            'message': 'Task created successfully',
            'data': {
                'id': str(task.id),
                'name': task.name,
                'description': task.description,
                'required_helpers': task.required_helpers,
                'special_requirements': task.special_requirements,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid required_helpers value'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def admin_templates(request):
    """Admin view to manage task templates."""
    templates = TaskTemplate.objects.all()
    context = {
        'templates': templates,
    }
    return render(request, 'festival/admin_templates.html', context)


@staff_member_required
@require_http_methods(["GET"])
def api_get_templates(request):
    """API endpoint to get all task templates."""
    templates = TaskTemplate.objects.all().values('id', 'name', 'description', 'required_helpers', 'special_requirements')
    return JsonResponse({
        'success': True,
        'data': list(templates)
    })


@staff_member_required
@require_http_methods(["POST"])
def api_create_template(request):
    """API endpoint to create a new task template."""
    try:
        data = json.loads(request.body)

        # Validate required fields
        if not data.get('name'):
            return JsonResponse({'success': False, 'error': 'Template name is required'}, status=400)

        required_helpers = int(data.get('required_helpers', 1))
        if required_helpers < 1:
            return JsonResponse({'success': False, 'error': 'Required helpers must be at least 1'}, status=400)

        # Create the template
        template = TaskTemplate.objects.create(
            name=data['name'],
            description=data.get('description', ''),
            required_helpers=required_helpers,
            special_requirements=data.get('special_requirements', '')
        )

        return JsonResponse({
            'success': True,
            'message': 'Template created successfully',
            'data': {
                'id': str(template.id),
                'name': template.name,
                'description': template.description,
                'required_helpers': template.required_helpers,
                'special_requirements': template.special_requirements,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid required_helpers value'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_update_template(request, template_id):
    """API endpoint to update a task template."""
    template = get_object_or_404(TaskTemplate, id=template_id)

    try:
        data = json.loads(request.body)

        # Update name
        if 'name' in data:
            if not data['name']:
                return JsonResponse({'success': False, 'error': 'Template name is required'}, status=400)
            template.name = data['name']

        # Update description
        if 'description' in data:
            template.description = data['description']

        # Update required_helpers
        if 'required_helpers' in data:
            required_helpers = int(data['required_helpers'])
            if required_helpers < 1:
                return JsonResponse({'success': False, 'error': 'Required helpers must be at least 1'}, status=400)
            template.required_helpers = required_helpers

        # Update special_requirements
        if 'special_requirements' in data:
            template.special_requirements = data['special_requirements']

        template.save()
        return JsonResponse({
            'success': True,
            'message': 'Template updated successfully',
            'data': {
                'id': str(template.id),
                'name': template.name,
                'description': template.description,
                'required_helpers': template.required_helpers,
                'special_requirements': template.special_requirements,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid required_helpers value'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_delete_template(request, template_id):
    """API endpoint to delete a task template."""
    template = get_object_or_404(TaskTemplate, id=template_id)

    try:
        template_name = template.name
        template.delete()
        return JsonResponse({
            'success': True,
            'message': f'Template "{template_name}" deleted successfully',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def admin_print_overview(request, festival_slug):
    """Task-centric matrix view: tasks as columns, shifts as rows."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    # Get all shifts ordered by date and time
    shifts = festival.shifts.all().order_by('date', 'start_time')

    # Get unique task names across all shifts
    unique_task_names = (
        Task.objects.filter(shift__festival=festival)
        .values_list('name', flat=True)
        .distinct()
        .order_by('name')
    )

    # Build matrix data as a list of task rows, each with cells for each shift
    matrix_data = []

    for task_name in unique_task_names:
        task_row = {
            'task_name': task_name,
            'cells': []
        }

        # Get one task to determine required_helpers (they should be the same for same-named tasks)
        first_task_for_name = (
            Task.objects.filter(shift__festival=festival, name=task_name)
            .first()
        )
        required_helpers = first_task_for_name.required_helpers if first_task_for_name else 0

        for shift in shifts:
            # Find tasks with this name in this shift
            tasks_in_shift = Task.objects.filter(
                shift=shift,
                name=task_name
            )

            if tasks_in_shift.exists():
                # Get the first task (should typically be only one)
                task = tasks_in_shift.first()
                participants = Participant.objects.filter(
                    task=task
                ).order_by('name')

                current_count = participants.count()
                required_count = task.required_helpers

                # Calculate status
                if current_count >= required_count:
                    status = 'full'
                elif current_count == 0:
                    status = 'empty'
                else:
                    status = 'partial'

                shortage = max(0, required_count - current_count)

                cell = {
                    'status': status,
                    'participants': list(participants),
                    'current': current_count,
                    'required': required_count,
                    'shortage': shortage,
                }
            else:
                # Task doesn't exist in this shift - mark as empty
                cell = {
                    'status': 'empty',
                    'participants': [],
                    'current': 0,
                    'required': required_helpers,
                    'shortage': required_helpers if required_helpers > 0 else 0,
                }

            task_row['cells'].append(cell)

        task_row['required_helpers'] = required_helpers
        matrix_data.append(task_row)

    context = {
        'festival': festival,
        'shifts': shifts,
        'matrix_data': matrix_data,
    }
    return render(request, 'festival/admin_print_overview.html', context)
