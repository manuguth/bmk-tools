"""YAML serialization/deserialization for Festival data."""

import yaml
from datetime import datetime, date, time
from typing import Dict, List, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Festival, Shift, Task, Participant


def serialize_festival_to_yaml(festival: Festival, include_participants: bool = False) -> str:
    """
    Convert a Festival and all related data to YAML format.

    Args:
        festival: Festival instance to serialize
        include_participants: If True, include all participants in export

    Returns:
        YAML-formatted string representing the festival
    """
    shifts_data = []

    for shift in festival.shifts.all().order_by('date', 'start_time'):
        shift_dict = {
            'name': shift.name,
            'date': shift.date.isoformat(),
            'start_time': shift.start_time.isoformat(),
            'end_time': shift.end_time.isoformat(),
            'description': shift.description,
            'tasks': []
        }

        for task in shift.tasks.all().order_by('name'):
            task_dict = {
                'name': task.name,
                'description': task.description,
                'required_helpers': task.required_helpers,
                'special_requirements': task.special_requirements,
            }

            if include_participants:
                participants_list = []
                for participant in task.participants.all().order_by('signed_up_at'):
                    participant_dict = {
                        'name': participant.name,
                        'attended': participant.attended,
                        'notes': participant.notes,
                        'signed_up_at': participant.signed_up_at.isoformat(),
                    }
                    participants_list.append(participant_dict)
                task_dict['participants'] = participants_list

            shift_dict['tasks'].append(task_dict)

        shifts_data.append(shift_dict)

    festival_dict = {
        'festival': {
            'name': festival.name,
            'description': festival.description,
            'start_date': festival.start_date.isoformat() if festival.start_date else None,
            'end_date': festival.end_date.isoformat() if festival.end_date else None,
            'status': festival.status,
        },
        'shifts': shifts_data
    }

    # Use custom representer for strings to ensure quotes around time/date values
    class CustomDumper(yaml.SafeDumper):
        pass

    def str_representer(dumper, data):
        # Always use quoted style for all strings to preserve format
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")

    CustomDumper.add_representer(str, str_representer)

    return yaml.dump(festival_dict, Dumper=CustomDumper, default_flow_style=False, sort_keys=False, allow_unicode=True)


def parse_yaml_to_dict(yaml_content: str) -> Dict:
    """
    Parse YAML content into a dictionary.

    Args:
        yaml_content: YAML-formatted string

    Returns:
        Parsed dictionary

    Raises:
        ValidationError: If YAML is malformed
    """
    try:
        data = yaml.safe_load(yaml_content)
        if not data:
            raise ValidationError("YAML file is empty")
        return data
    except yaml.YAMLError as e:
        raise ValidationError(f"Invalid YAML format: {str(e)}")


def validate_import_data(data: Dict) -> List[str]:
    """
    Validate imported data structure and content.

    Args:
        data: Dictionary parsed from YAML

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check festival section
    if 'festival' not in data:
        errors.append("Missing 'festival' section")
        return errors

    festival = data['festival']
    if not isinstance(festival, dict):
        errors.append("'festival' must be a dictionary")
        return errors

    # Festival name is required
    if not festival.get('name'):
        errors.append("Festival name is required")

    # Check festival date format if provided
    if festival.get('start_date'):
        try:
            _parse_date(festival['start_date'])
        except ValueError:
            errors.append(f"Invalid start_date format: {festival['start_date']} (expected YYYY-MM-DD)")

    if festival.get('end_date'):
        try:
            _parse_date(festival['end_date'])
        except ValueError:
            errors.append(f"Invalid end_date format: {festival['end_date']} (expected YYYY-MM-DD)")

    # Check status if provided
    if festival.get('status'):
        valid_statuses = ['draft', 'active', 'completed']
        if festival['status'] not in valid_statuses:
            errors.append(f"Invalid status: {festival['status']} (must be: {', '.join(valid_statuses)})")

    # Check shifts section
    if 'shifts' not in data:
        errors.append("Missing 'shifts' section")
        return errors

    if not isinstance(data['shifts'], list):
        errors.append("'shifts' must be a list")
        return errors

    if not data['shifts']:
        errors.append("At least one shift is required")
        return errors

    # Validate each shift
    for shift_idx, shift in enumerate(data['shifts']):
        shift_num = shift_idx + 1

        if not isinstance(shift, dict):
            errors.append(f"Shift {shift_num}: must be a dictionary")
            continue

        # Validate required shift fields
        if not shift.get('name'):
            errors.append(f"Shift {shift_num}: name is required")

        if not shift.get('date'):
            errors.append(f"Shift {shift_num}: date is required")
        else:
            try:
                _parse_date(shift['date'])
            except ValueError:
                errors.append(f"Shift {shift_num}: invalid date format '{shift['date']}' (expected YYYY-MM-DD)")

        if not shift.get('start_time'):
            errors.append(f"Shift {shift_num}: start_time is required")
        else:
            try:
                _parse_time(shift['start_time'])
            except ValueError:
                errors.append(f"Shift {shift_num}: invalid start_time format '{shift['start_time']}' (expected HH:MM:SS)")

        if not shift.get('end_time'):
            errors.append(f"Shift {shift_num}: end_time is required")
        else:
            try:
                _parse_time(shift['end_time'])
            except ValueError:
                errors.append(f"Shift {shift_num}: invalid end_time format '{shift['end_time']}' (expected HH:MM:SS)")

        # Validate tasks
        if 'tasks' not in shift:
            errors.append(f"Shift {shift_num}: missing 'tasks' section")
            continue

        if not isinstance(shift['tasks'], list):
            errors.append(f"Shift {shift_num}: 'tasks' must be a list")
            continue

        # Validate each task (empty task lists are allowed)
        for task_idx, task in enumerate(shift['tasks']):
            task_num = task_idx + 1

            if not isinstance(task, dict):
                errors.append(f"Shift {shift_num}, Task {task_num}: must be a dictionary")
                continue

            if not task.get('name'):
                errors.append(f"Shift {shift_num}, Task {task_num}: name is required")

            if 'required_helpers' in task:
                try:
                    helpers = int(task['required_helpers'])
                    if helpers < 1:
                        errors.append(f"Shift {shift_num}, Task {task_num}: required_helpers must be >= 1")
                except (ValueError, TypeError):
                    errors.append(f"Shift {shift_num}, Task {task_num}: required_helpers must be an integer")

            # Validate participants if present
            if 'participants' in task and isinstance(task['participants'], list):
                for participant_idx, participant in enumerate(task['participants']):
                    p_num = participant_idx + 1

                    if not isinstance(participant, dict):
                        errors.append(f"Shift {shift_num}, Task {task_num}, Participant {p_num}: must be a dictionary")
                        continue

                    if not participant.get('name'):
                        errors.append(f"Shift {shift_num}, Task {task_num}, Participant {p_num}: name is required")

                    if 'signed_up_at' in participant:
                        try:
                            _parse_datetime(participant['signed_up_at'])
                        except ValueError:
                            errors.append(f"Shift {shift_num}, Task {task_num}, Participant {p_num}: invalid signed_up_at format")

    return errors


def import_festival_data(festival: Festival, data: Dict, include_participants: bool = True, dry_run: bool = False) -> Dict:
    """
    Import festival data from validated dictionary.

    Uses atomic transactions to ensure all-or-nothing import.

    Args:
        festival: Festival instance to import data into
        data: Validated data dictionary
        include_participants: If True, import participants (default True)
        dry_run: If True, validate only without committing (default False)

    Returns:
        Dictionary with import results: {
            'success': bool,
            'message': str,
            'shifts_created': int,
            'tasks_created': int,
            'participants_created': int,
        }
    """
    try:
        with transaction.atomic():
            # Delete existing shifts (cascades to tasks and participants)
            festival.shifts.all().delete()

            shifts_created = 0
            tasks_created = 0
            participants_created = 0

            # Create shifts
            for shift_data in data['shifts']:
                shift = Shift.objects.create(
                    festival=festival,
                    name=shift_data['name'],
                    date=_parse_date(shift_data['date']),
                    start_time=_parse_time(shift_data['start_time']),
                    end_time=_parse_time(shift_data['end_time']),
                    description=shift_data.get('description', ''),
                )
                shifts_created += 1

                # Create tasks for this shift
                for task_data in shift_data['tasks']:
                    task = Task.objects.create(
                        shift=shift,
                        name=task_data['name'],
                        description=task_data.get('description', ''),
                        required_helpers=int(task_data.get('required_helpers', 1)),
                        special_requirements=task_data.get('special_requirements', ''),
                    )
                    tasks_created += 1

                    # Create participants if included
                    if include_participants and 'participants' in task_data:
                        for participant_data in task_data['participants']:
                            signed_up_at = _parse_datetime(participant_data['signed_up_at']) if 'signed_up_at' in participant_data else datetime.now()
                            Participant.objects.create(
                                task=task,
                                name=participant_data['name'],
                                attended=participant_data.get('attended', False),
                                notes=participant_data.get('notes', ''),
                                signed_up_at=signed_up_at,
                            )
                            participants_created += 1

            # Rollback if dry run
            if dry_run:
                transaction.set_rollback(True)

            return {
                'success': True,
                'message': 'Import successful',
                'shifts_created': shifts_created,
                'tasks_created': tasks_created,
                'participants_created': participants_created,
            }

    except Exception as e:
        return {
            'success': False,
            'message': f'Import failed: {str(e)}',
            'shifts_created': 0,
            'tasks_created': 0,
            'participants_created': 0,
        }


# Helper functions for date/time parsing

def _parse_date(date_str) -> date:
    """Parse ISO 8601 date string (YYYY-MM-DD)."""
    if isinstance(date_str, date):
        return date_str
    try:
        return datetime.strptime(str(date_str), '%Y-%m-%d').date()
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid date format: {date_str}") from e


def _parse_time(time_str) -> time:
    """Parse ISO 8601 time string (HH:MM:SS or sexagesimal number)."""
    if isinstance(time_str, time):
        return time_str

    time_str = str(time_str)

    # Handle sexagesimal numbers that YAML might parse (e.g., 00:00:00 becomes 0)
    if time_str == '0':
        return datetime.strptime('00:00:00', '%H:%M:%S').time()

    try:
        return datetime.strptime(time_str, '%H:%M:%S').time()
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid time format: {time_str}") from e


def _parse_datetime(datetime_str) -> datetime:
    """Parse ISO 8601 datetime string (with or without timezone)."""
    if isinstance(datetime_str, datetime):
        return datetime_str
    try:
        # Try with timezone (Z format)
        if isinstance(datetime_str, str) and datetime_str.endswith('Z'):
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        # Try standard ISO format
        return datetime.fromisoformat(str(datetime_str))
    except (ValueError, TypeError):
        # Fallback to basic parsing
        try:
            return datetime.strptime(str(datetime_str), '%Y-%m-%dT%H:%M:%S')
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid datetime format: {datetime_str}") from e
