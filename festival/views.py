import json
import logging
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from .models import Festival, Shift, Task, Participant, TaskTemplate
from .forms import ParticipantSignUpForm
from .serializers import serialize_festival_to_yaml, parse_yaml_to_dict, validate_import_data, import_festival_data
from .utils_km import sync_participants_for_task

logger = logging.getLogger(__name__)


def get_api_base_url(request):
    """Determine API base URL based on current request path."""
    if request.path.startswith('/event/'):
        return '/event/'
    elif request.path.startswith('/festival/'):
        return '/festival/'
    return '/festival/'  # default fallback


def check_festival_draft_access(request, festival):
    """Check if user can access draft festival. Redirects to login if needed."""
    if festival.status == 'draft' and not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")
    return None


@staff_member_required
def admin_festival_list(request):
    """Admin view to list all festivals with stats."""
    show_archived = request.GET.get('show_archived', 'false').lower() == 'true'

    if show_archived:
        festivals = Festival.objects.all().order_by("start_date")
    else:
        festivals = Festival.objects.filter(status__in=['active', 'draft']).order_by("start_date")

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
        "show_archived": show_archived,
        "api_base_url": get_api_base_url(request),
    }
    return render(request, "festival/admin_festival_list.html", context)


def festival_detail(request, festival_slug):
    """Display festival details and list of shifts."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    draft_check = check_festival_draft_access(request, festival)
    if draft_check:
        return draft_check

    shifts = festival.shifts.all()

    # Enrich shifts with tasks that have KM URLs
    shifts_with_tasks = []
    for shift in shifts:
        tasks_with_km = []
        for task in shift.tasks.all():
            # Sync participants from Konzertmeister if configured
            sync_result = sync_participants_for_task(task)
            if not sync_result['success']:
                logger.warning(f"KM sync failed for task {task.id}: {sync_result['error']}")

            # Refresh task to get updated participant count after sync
            task.refresh_from_db()

            task_data = {
                'task': task,
                'km_url': None,
            }
            if task.has_km_integration:
                task_data['km_url'] = f"https://web.konzertmeister.app/appointment/{task.konzertmeister_event_id}"
            tasks_with_km.append(task_data)

        shifts_with_tasks.append({
            'shift': shift,
            'tasks_with_km': tasks_with_km,
        })

    context = {
        "festival": festival,
        "shifts_with_tasks": shifts_with_tasks,
    }
    return render(request, "festival/festival_detail.html", context)


def shift_detail(request, festival_slug, shift_id):
    """Display shift details and available tasks."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    draft_check = check_festival_draft_access(request, festival)
    if draft_check:
        return draft_check

    shift = get_object_or_404(Shift, id=shift_id, festival=festival)
    tasks = shift.tasks.all()

    # Enrich tasks with KM URLs
    tasks_with_km = []
    for task in tasks:
        task_data = {
            'task': task,
            'km_url': None,
        }
        if task.has_km_integration:
            task_data['km_url'] = f"https://web.konzertmeister.app/appointment/{task.konzertmeister_event_id}"
        tasks_with_km.append(task_data)

    context = {
        "festival": festival,
        "shift": shift,
        "tasks_with_km": tasks_with_km,
    }
    return render(request, "festival/shift_detail.html", context)


def task_signup(request, festival_slug, task_id):
    """Sign up a participant for a task."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    draft_check = check_festival_draft_access(request, festival)
    if draft_check:
        return draft_check

    # Check if festival is completed
    if festival.status == 'completed':
        context = {
            "festival": festival,
            "error": "Dieses Festival ist abgeschlossen. Anmeldungen sind nicht mehr möglich.",
        }
        return render(request, "festival/festival_completed.html", context)

    task = get_object_or_404(Task, id=task_id, shift__festival=festival)

    # Check if task has Konzertmeister integration - if so, sign up is locked
    if task.has_km_integration:
        context = {
            "festival": festival,
            "task": task,
            "error": "Die Anmeldung für diese Aufgabe wird über Konzertmeister verwaltet. Manuelle Anmeldungen sind nicht möglich.",
        }
        return render(request, "festival/task_full.html", context)

    # Sync participants from Konzertmeister if configured
    sync_result = sync_participants_for_task(task)
    if not sync_result['success']:
        logger.warning(f"KM sync failed for task {task_id}: {sync_result['error']}")

    # Refresh task to get updated participant count after sync
    task.refresh_from_db()

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
        "km_sync_warning": sync_result.get('warning'),
    }
    return render(request, "festival/task_signup.html", context)


def signup_confirmation(request, festival_slug, participant_id):
    """Display confirmation after successful sign-up."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    draft_check = check_festival_draft_access(request, festival)
    if draft_check:
        return draft_check

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
        context = {"festival": None, "shifts_data": [], "api_base_url": get_api_base_url(request)}
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
        "api_base_url": get_api_base_url(request),
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
def admin_edit(request, festival_slug):
    """Admin edit view for managing shifts, tasks, and participants."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    # Get all shifts with tasks and participants
    shifts = festival.shifts.all()
    shifts_data = []

    for shift in shifts:
        tasks_data = []
        for task in shift.tasks.all():
            # Sync participants from Konzertmeister if configured
            sync_result = sync_participants_for_task(task)
            if not sync_result['success']:
                logger.warning(f"KM sync failed for task {task.id}: {sync_result['error']}")

            # Refresh participant count
            task.refresh_from_db()
            participants = Participant.objects.filter(task=task).select_related('task__shift')

            tasks_data.append({
                'task': task,
                'participants': participants,
                'km_sync_warning': sync_result.get('warning'),
            })
        shifts_data.append({
            'shift': shift,
            'tasks': tasks_data,
        })

    context = {
        'festival': festival,
        'shifts_data': shifts_data,
        'api_base_url': get_api_base_url(request),
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

        # Update name
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return JsonResponse({'success': False, 'error': 'Task name cannot be empty'}, status=400)
            task.name = name

        # Validate and update required_helpers
        if 'required_helpers' in data:
            required_helpers = int(data['required_helpers'])
            if required_helpers < 1:
                return JsonResponse({'success': False, 'error': 'Required helpers must be at least 1'}, status=400)
            task.required_helpers = required_helpers

        # Update description
        if 'description' in data:
            task.description = data['description']

        # Update konzertmeister_event_id with validation
        if 'konzertmeister_event_id' in data:
            km_id = data['konzertmeister_event_id']

            # Allow null/empty to unlink without validation
            if km_id is None or km_id == '' or km_id == 0:
                task.konzertmeister_event_id = None
            else:
                # Validate the KM event ID by attempting to sync
                try:
                    km_id_int = int(km_id)
                    if km_id_int < 1:
                        return JsonResponse({'success': False, 'error': 'Konzertmeister Event ID must be a positive number'}, status=400)

                    # Try to fetch meeting info from Konzertmeister to validate the ID exists
                    from .utils_km import km_get_meeting_info
                    try:
                        km_get_meeting_info(km_id_int)
                        # If successful, save the ID
                        task.konzertmeister_event_id = km_id_int
                    except Exception as km_error:
                        logger.warning(f"KM validation failed for event {km_id_int}: {str(km_error)}")
                        return JsonResponse({
                            'success': False,
                            'error': f'Konzertmeister Event ID {km_id_int} could not be validated. Please check if the ID exists in Konzertmeister.'
                        }, status=400)
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Konzertmeister Event ID must be a number'}, status=400)

        task.save()
        return JsonResponse({
            'success': True,
            'message': 'Task updated successfully',
            'data': {
                'name': task.name,
                'required_helpers': task.required_helpers,
                'description': task.description,
                'konzertmeister_event_id': task.konzertmeister_event_id,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid field value'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_update_shift(request, festival_slug, shift_id):
    """API endpoint to update shift details."""
    from datetime import time

    festival = get_object_or_404(Festival, slug=festival_slug)
    shift = get_object_or_404(Shift, id=shift_id, festival=festival)

    try:
        data = json.loads(request.body)

        # Update name
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return JsonResponse({'success': False, 'error': 'Shift name cannot be empty'}, status=400)
            shift.name = name

        # Update date
        if 'date' in data:
            try:
                date_str = data['date']
                shift.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        # Update start_time
        if 'start_time' in data:
            try:
                time_str = data['start_time']
                shift.start_time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid start time format. Use HH:MM'}, status=400)

        # Update end_time
        if 'end_time' in data:
            try:
                time_str = data['end_time']
                shift.end_time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid end time format. Use HH:MM'}, status=400)

        # Validate that end_time is after start_time
        if shift.start_time >= shift.end_time:
            return JsonResponse({'success': False, 'error': 'End time must be after start time'}, status=400)

        # Update description
        if 'description' in data:
            shift.description = data['description']

        shift.save()
        return JsonResponse({
            'success': True,
            'message': 'Shift updated successfully',
            'data': {
                'name': shift.name,
                'date': shift.date.isoformat(),
                'start_time': shift.start_time.strftime('%H:%M'),
                'end_time': shift.end_time.strftime('%H:%M'),
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
def api_delete_shift(request, festival_slug, shift_id):
    """API endpoint to delete a shift and all associated tasks and participants."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    shift = get_object_or_404(Shift, id=shift_id, festival=festival)

    try:
        shift_name = shift.name
        shift.delete()
        return JsonResponse({
            'success': True,
            'message': f'Shift "{shift_name}" and all associated tasks and participants deleted successfully',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_delete_task(request, festival_slug, task_id):
    """API endpoint to delete a task and all associated participants."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    task = get_object_or_404(Task, id=task_id, shift__festival=festival)

    try:
        task_name = task.name
        task.delete()
        return JsonResponse({
            'success': True,
            'message': f'Task "{task_name}" and all associated participants deleted successfully',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_create_participant(request, festival_slug, task_id):
    """API endpoint to create a new participant for a task."""
    festival = get_object_or_404(Festival, slug=festival_slug)
    task = get_object_or_404(Task, id=task_id, shift__festival=festival)

    try:
        data = json.loads(request.body)

        # Validate required field
        if not data.get('name'):
            return JsonResponse({'success': False, 'error': 'Participant name is required'}, status=400)

        # Create the participant
        participant = Participant.objects.create(
            task=task,
            name=data['name'].strip(),
            notes=data.get('notes', '').strip()
        )

        return JsonResponse({
            'success': True,
            'message': 'Participant created successfully',
            'data': {
                'id': participant.id,
                'name': participant.name,
                'notes': participant.notes,
                'attended': participant.attended,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_delete_festival(request, festival_slug):
    """API endpoint to delete a festival and all associated shifts, tasks, and participants."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    try:
        festival_name = festival.name
        festival.delete()
        api_base_url = get_api_base_url(request)
        return JsonResponse({
            'success': True,
            'message': f'Festival "{festival_name}" and all associated data deleted successfully',
            'redirect': f'{api_base_url}admin/',
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
        'api_base_url': get_api_base_url(request),
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
                # Task doesn't exist in this shift - mark as not applicable
                cell = {
                    'status': 'not_applicable',
                    'participants': [],
                    'current': 0,
                    'required': 0,
                    'shortage': 0,
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


@staff_member_required
@require_http_methods(["POST"])
def api_update_festival(request, festival_slug):
    """API endpoint to update festival details."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    try:
        data = json.loads(request.body)

        # Update name
        if 'name' in data:
            new_name = data['name'].strip()
            if not new_name:
                return JsonResponse({'success': False, 'error': 'Festival name cannot be empty'}, status=400)
            festival.name = new_name

        # Update status
        if 'status' in data:
            new_status = data['status'].strip()
            valid_statuses = ['draft', 'active', 'completed']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}, status=400)
            festival.status = new_status

        festival.save()
        return JsonResponse({
            'success': True,
            'message': 'Festival updated successfully',
            'data': {
                'name': festival.name,
                'status': festival.status,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_create_shift(request, festival_slug):
    """API endpoint to create a new shift."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    try:
        data = json.loads(request.body)

        # Validate required fields
        if not data.get('name'):
            return JsonResponse({'success': False, 'error': 'Shift name is required'}, status=400)

        if not data.get('date'):
            return JsonResponse({'success': False, 'error': 'Date is required'}, status=400)

        if not data.get('start_time'):
            return JsonResponse({'success': False, 'error': 'Start time is required'}, status=400)

        if not data.get('end_time'):
            return JsonResponse({'success': False, 'error': 'End time is required'}, status=400)

        # Create the shift
        shift = Shift.objects.create(
            festival=festival,
            name=data['name'],
            date=data['date'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            description=data.get('description', '')
        )

        # Format date and time for response
        date_str = shift.date.isoformat() if hasattr(shift.date, 'isoformat') else str(shift.date)
        start_time_str = shift.start_time.isoformat() if hasattr(shift.start_time, 'isoformat') else str(shift.start_time)
        end_time_str = shift.end_time.isoformat() if hasattr(shift.end_time, 'isoformat') else str(shift.end_time)

        return JsonResponse({
            'success': True,
            'message': 'Shift created successfully',
            'data': {
                'id': str(shift.id),
                'name': shift.name,
                'date': date_str,
                'start_time': start_time_str,
                'end_time': end_time_str,
                'description': shift.description,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': f'Invalid field format: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_create_festival(request):
    """API endpoint to create a new festival."""
    try:
        data = json.loads(request.body)

        # Validate required fields
        if not data.get('name'):
            return JsonResponse({'success': False, 'error': 'Festival name is required'}, status=400)

        name = data['name'].strip()
        if len(name) > 255:
            return JsonResponse({'success': False, 'error': 'Festival name cannot exceed 255 characters'}, status=400)

        if not data.get('start_date'):
            return JsonResponse({'success': False, 'error': 'Start date is required'}, status=400)

        if not data.get('end_date'):
            return JsonResponse({'success': False, 'error': 'End date is required'}, status=400)

        try:
            from datetime import datetime
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        if end_date < start_date:
            return JsonResponse({'success': False, 'error': 'End date must be on or after start date'}, status=400)

        # Create the festival
        festival = Festival.objects.create(
            name=name,
            start_date=start_date,
            end_date=end_date,
            description=data.get('description', ''),
            status='draft'
        )

        return JsonResponse({
            'success': True,
            'message': 'Festival created successfully',
            'data': {
                'id': festival.id,
                'name': festival.name,
                'slug': festival.slug,
                'start_date': festival.start_date.isoformat(),
                'end_date': festival.end_date.isoformat(),
                'description': festival.description,
                'status': festival.status,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["GET"])
def api_export_festival_yaml(request, festival_slug):
    """API endpoint to export festival data as YAML file."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    try:
        # Get include_participants parameter
        include_participants = request.GET.get('include_participants', 'false').lower() == 'true'

        # Serialize festival to YAML
        yaml_content = serialize_festival_to_yaml(festival, include_participants=include_participants)

        # Determine export mode for filename
        mode = 'full' if include_participants else 'structure-only'
        timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        filename = f'festival_{festival_slug}_{mode}_{timestamp}.yaml'

        # Create response with YAML content
        response = HttpResponse(
            content=yaml_content.encode('utf-8'),
            content_type='text/yaml; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Export failed: {str(e)}'}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_import_festival_yaml(request, festival_slug):
    """API endpoint to import festival data from YAML content."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    try:
        data = json.loads(request.body)
        yaml_content = data.get('yaml_content', '')
        include_participants = data.get('include_participants', True)
        dry_run = data.get('dry_run', False)

        if not yaml_content:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'YAML content is required',
                    'data': {'validation_errors': ['YAML content is required']}
                },
                status=400
            )

        # Parse YAML
        try:
            parsed_data = parse_yaml_to_dict(yaml_content)
        except ValidationError as e:
            return JsonResponse(
                {
                    'success': False,
                    'message': str(e),
                    'data': {'validation_errors': [str(e)]}
                },
                status=400
            )

        # Validate data
        validation_errors = validate_import_data(parsed_data)
        if validation_errors:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'Validation failed',
                    'data': {'validation_errors': validation_errors}
                },
                status=400
            )

        # Import data
        result = import_festival_data(
            festival,
            parsed_data,
            include_participants=include_participants,
            dry_run=dry_run
        )

        if result['success']:
            return JsonResponse({
                'success': True,
                'message': result['message'],
                'data': {
                    'shifts_created': result['shifts_created'],
                    'tasks_created': result['tasks_created'],
                    'participants_created': result['participants_created'],
                }
            })
        else:
            return JsonResponse(
                {
                    'success': False,
                    'message': result['message'],
                    'data': {'validation_errors': []}
                },
                status=500
            )

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse(
            {
                'success': False,
                'message': f'Import failed: {str(e)}',
                'data': {'validation_errors': []}
            },
            status=500
        )


@staff_member_required
@require_http_methods(["POST"])
def api_import_festival_yaml_file(request, festival_slug):
    """API endpoint to import festival data from uploaded YAML file."""
    festival = get_object_or_404(Festival, slug=festival_slug)

    try:
        # Get uploaded file
        if 'yaml_file' not in request.FILES:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'YAML file is required',
                    'data': {'validation_errors': ['YAML file is required']}
                },
                status=400
            )

        yaml_file = request.FILES['yaml_file']

        # Check file size (limit to 10MB)
        if yaml_file.size > 10 * 1024 * 1024:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'File size exceeds 10MB limit',
                    'data': {'validation_errors': ['File size exceeds 10MB limit']}
                },
                status=400
            )

        # Read file content
        yaml_content = yaml_file.read().decode('utf-8')

        # Get parameters
        include_participants = request.POST.get('include_participants', 'true').lower() == 'true'
        dry_run = request.POST.get('dry_run', 'false').lower() == 'true'

        # Parse YAML
        try:
            parsed_data = parse_yaml_to_dict(yaml_content)
        except ValidationError as e:
            return JsonResponse(
                {
                    'success': False,
                    'message': str(e),
                    'data': {'validation_errors': [str(e)]}
                },
                status=400
            )

        # Validate data
        validation_errors = validate_import_data(parsed_data)
        if validation_errors:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'Validation failed',
                    'data': {'validation_errors': validation_errors}
                },
                status=400
            )

        # Import data
        result = import_festival_data(
            festival,
            parsed_data,
            include_participants=include_participants,
            dry_run=dry_run
        )

        if result['success']:
            return JsonResponse({
                'success': True,
                'message': result['message'],
                'data': {
                    'shifts_created': result['shifts_created'],
                    'tasks_created': result['tasks_created'],
                    'participants_created': result['participants_created'],
                }
            })
        else:
            return JsonResponse(
                {
                    'success': False,
                    'message': result['message'],
                    'data': {'validation_errors': []}
                },
                status=500
            )

    except UnicodeDecodeError:
        return JsonResponse(
            {
                'success': False,
                'message': 'Invalid file encoding. Please use UTF-8 encoding.',
                'data': {'validation_errors': ['Invalid file encoding']}
            },
            status=400
        )
    except Exception as e:
        return JsonResponse(
            {
                'success': False,
                'message': f'Import failed: {str(e)}',
                'data': {'validation_errors': []}
            },
            status=500
        )
