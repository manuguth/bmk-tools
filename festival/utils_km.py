import requests
import os

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
                    "attended": attendance.get("attending", False),
                }
                positive_maybe_participants.append(participant)

    return positive_maybe_participants
