import requests
import os
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def get_km_auth_token():
    """
    Retrieves an authentication token from the Konzertmeister API.

    Returns
    -------
    str
        The authentication token retrieved from the API response headers.

    Raises
    ------
    RuntimeError
        If init() has not been called or the login request fails.
    """

    login_url = "https://rest.konzertmeister.app/api/v2/login"
    password = os.getenv("KM_PASSWORD")
    mail = os.getenv("KM_MAIL")

    headers = {"Content-Type": "application/json"}

    payload = {
        "mail": mail,
        "password": password,
        "locale": "en_US",
        "timezone": "Europe/Berlin",
    }

    login_response = requests.post(login_url, json=payload, headers=headers)

    if login_response.status_code == 200:
        auth_token_header = login_response.headers.get("X-AUTH-TOKEN")
        if auth_token_header:
            print("Auth token retrieved")
            return auth_token_header

    raise RuntimeError(
        f"KM login failed with status {login_response.status_code}: {login_response.text}"
    )


def km_get_meeting_info(id: int):
    """
    Send an authorised GET request to the Konzertmeister API.

    Parameters
    ----------
    id : int
        The ID of the meeting to retrieve.

    Returns
    -------
    dict
        The JSON response from the GET request if successful.
    """
    token = get_km_auth_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    url = f"https://rest.konzertmeister.app/api/v3/att/grouped/{id}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            print("retrieved data")
            return data
        except ValueError:
            print("Failed to parse response as JSON")
            print("Response text:", response.text)


def extract_positive_maybe_participants(event_id: int) -> list:
    """
    Extract participants who responded with positive or maybe to an event.

    Parameters
    ----------
    event_id : int
        The ID of the event to retrieve participant data for.

    Returns
    -------
    list
        A list of participants with their details, filtered to only include those
        where attendance.positive is True or attendance.maybe is True.
    """
    grouped_data = km_get_meeting_info(event_id)
    positive_maybe_participants = []

    for org_group in grouped_data:
        org_name = org_group["org"]["name"]
        for user in org_group.get("users", []):
            attendance = user.get("attendance", {})
            if attendance.get("positive") or attendance.get("maybe"):
                participant = {
                    "org": org_name,
                    "name": user["kmUser"]["name"],
                    "kmUserId": user["kmUser"]["id"],
                    "firstname": user["kmUser"].get("firstname", ""),
                    "lastname": user["kmUser"].get("lastname", ""),
                    "positive": attendance.get("positive", False),
                    "maybe": attendance.get("maybe", False),
                }
                positive_maybe_participants.append(participant)

    return positive_maybe_participants


def _normalize_name(name: str) -> str:
    """Normalize name for matching: lowercase, strip whitespace."""
    return name.lower().strip()


def _find_participant_by_name(task, km_name: str):
    """
    Find single participant in task by normalized name match.
    Returns the first match if multiple exist (safest approach).
    """
    normalized_km = _normalize_name(km_name)
    for participant in task.participants.all():
        if _normalize_name(participant.name) == normalized_km:
            return participant
    return None


def _find_all_participants_by_name(task, km_name: str):
    """Find all participants matching name (for conflict detection)."""
    all_matching = []
    normalized_km = _normalize_name(km_name)
    for participant in task.participants.all():
        if _normalize_name(participant.name) == normalized_km:
            all_matching.append(participant)
    # Return as queryset for ordering
    if all_matching:
        return task.participants.filter(id__in=[p.id for p in all_matching])
    return task.participants.none()


def sync_participants_for_task(task) -> Dict:
    """
    Sync participants from Konzertmeister API for a specific task.

    Smart merge strategy:
    - Matches by name (case-insensitive, whitespace-normalized)
    - Updates existing participants or creates new ones
    - Deletes participants that don't match any KM data
    - Stores response status separately from notes

    Args:
        task: Task instance with konzertmeister_event_id set

    Returns:
        Dict with sync result:
        {
            'success': bool,
            'synced_count': int,  # participants added/updated
            'deleted_count': int,  # participants deleted
            'error': str or None,
            'warning': str or None,  # for name conflicts
        }
    """
    if not task.has_km_integration:
        return {'success': True, 'synced_count': 0, 'deleted_count': 0, 'error': None, 'warning': None}

    try:
        # Fetch from KM API
        km_participants = extract_positive_maybe_participants(task.konzertmeister_event_id)
        synced_count = 0
        deleted_count = 0
        conflicts = []
        matched_participant_ids = set()

        for km_person in km_participants:
            km_name = km_person['name']
            km_user_id = km_person['kmUserId']
            response_status = 'positive' if km_person.get('positive') else 'maybe'

            # Attempt to find matching participant
            matched_participant = _find_participant_by_name(task, km_name)

            if matched_participant:
                # UPDATE existing participant
                all_matches = list(_find_all_participants_by_name(task, km_name))
                if len(all_matches) > 1:
                    # Name conflict - warn but update oldest
                    conflicts.append(km_name)
                    matched_participant = (
                        _find_all_participants_by_name(task, km_name)
                        .order_by('signed_up_at')
                        .first()
                    )
                    matched_participant.notes += f"\n[KM SYNC WARNING] Duplicate name in KM - using oldest entry"

                matched_participant.konzertmeister_user_id = km_user_id
                matched_participant.konzertmeister_response_status = response_status

                # Update notes based on response status change
                if response_status == 'maybe':
                    # Status is "maybe" - ensure "vielleicht" is in notes
                    if 'vielleicht' not in matched_participant.notes:
                        if matched_participant.notes:
                            matched_participant.notes += "\nvielleicht"
                        else:
                            matched_participant.notes = "vielleicht"
                elif response_status == 'positive':
                    # Status is "positive" - remove "vielleicht" from notes if present
                    matched_participant.notes = matched_participant.notes.replace('\nvielleicht', '').replace('vielleicht', '').strip()

                matched_participant.save(update_fields=[
                    'konzertmeister_user_id',
                    'konzertmeister_response_status',
                    'notes'
                ])
                matched_participant_ids.add(matched_participant.id)
                synced_count += 1
                logger.info(f"Updated participant '{km_name}' for task {task.id}")
            else:
                # CREATE new participant
                from .models import Participant
                notes = ""
                # Only add comment if response is "maybe"
                if response_status == 'maybe':
                    notes = "vielleicht"

                new_participant = Participant.objects.create(
                    task=task,
                    name=km_name,
                    konzertmeister_user_id=km_user_id,
                    konzertmeister_response_status=response_status,
                    notes=notes
                )
                matched_participant_ids.add(new_participant.id)
                synced_count += 1
                logger.info(f"Created new participant '{km_name}' for task {task.id}")

        # Delete unmatched participants
        from .models import Participant
        unmatched_participants = task.participants.exclude(id__in=matched_participant_ids)
        for participant in unmatched_participants:
            logger.info(f"Deleted participant '{participant.name}' for task {task.id} (not in Konzertmeister)")
            deleted_count += 1
        unmatched_participants.delete()

        warning_msg = None
        if conflicts:
            warning_msg = f"Name conflicts in Konzertmeister: {', '.join(conflicts)}"
            logger.warning(f"Task {task.id}: {warning_msg}")

        return {
            'success': True,
            'synced_count': synced_count,
            'deleted_count': deleted_count,
            'error': None,
            'warning': warning_msg,
        }

    except RuntimeError as e:
        # KM API auth or connection error
        error_msg = f"Konzertmeister API error: {str(e)}"
        logger.error(f"Task {task.id}: {error_msg}")
        return {
            'success': False,
            'synced_count': 0,
            'deleted_count': 0,
            'error': error_msg,
            'warning': None,
        }
    except Exception as e:
        # Unexpected error
        error_msg = f"Sync failed for task {task.id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'synced_count': 0,
            'deleted_count': 0,
            'error': error_msg,
            'warning': None,
        }

