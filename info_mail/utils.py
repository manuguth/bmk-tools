import logging
from datetime import date, timedelta
from pathlib import Path

import css_inline
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent / "email_assets"


def get_appointments(url: str) -> str:
    """Fetch upcoming appointments from Konzertmeister and return filtered HTML."""
    if not url:
        return ""

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to fetch appointments from %s", url)
        return "<p><em>Termine konnten nicht geladen werden.</em></p>"

    soup = BeautifulSoup(response.text, "html.parser")
    body = soup.find("body")
    if not body:
        return ""

    for script in body.find_all("script"):
        script.extract()

    appointment_list = body.find(class_="km-appointment-list")
    if not appointment_list:
        return ""

    for footer in appointment_list.find_all(class_="list-footer"):
        footer.extract()

    excluded_names = (
        "Vorstandssitzung",
        "Vorstände Exklusiv",
        "Besprechung Jugend",
        "Hauptversammlung MMV",
    )
    for item in appointment_list.find_all(class_="km-list-item"):
        name_el = item.find(class_="km-appointment-name")
        if not name_el:
            continue
        name = name_el.text.strip()
        if name in excluded_names or "Landesverband" in name:
            item.extract()

    return appointment_list.prettify()


def render_newsletter(mail_obj, settings) -> str:
    """
    Assemble the full newsletter HTML from template + section fields + live appointments.

    Parameters
    ----------
    mail_obj : WeeklyMails instance with section fields populated
    settings : NewsletterSettings instance

    Returns
    -------
    str : Final HTML with inlined CSS
    """
    with open(ASSETS_DIR / "template_email.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    with open(ASSETS_DIR / "styles_bmk_news.css", "r", encoding="utf-8") as f:
        css_content = f.read()

    html_content = f"<style>{css_content}</style>\n{html_content}"

    # Title placeholder
    html_content = html_content.replace(
        "{{placeholder_title}}", f"{mail_obj.week}/{mail_obj.year}"
    )

    # Section placeholders — all replacements in one place so missing/renamed keys are visible.
    placeholders = {
        "intro": mail_obj.intro or "",
        "info": mail_obj.info_content or "",
        "events": mail_obj.events or "",
        "konzert": mail_obj.konzert or "",
        "sonstiges": mail_obj.sonstiges or "",
        "footer": "",  # not editable in compose
    }
    for key, value in placeholders.items():
        html_content = html_content.replace("{{" + key + "}}", value)

    # Last-week placeholder
    previous_week_date = date.fromisocalendar(mail_obj.year, mail_obj.week, 1) - timedelta(weeks=1)
    last_year, last_week, _ = previous_week_date.isocalendar()
    html_content = html_content.replace(
        "{{last_week}}", f"{last_week:02d}-{last_year}"
    )

    # Live appointments from Konzertmeister
    html_appointments = get_appointments(settings.km_appointments_url)
    html_requests = get_appointments(settings.km_requests_url)

    content_appointments = ""
    if html_appointments:
        content_appointments = "<h2>Anstehende Termine</h2>\n" + html_appointments
    if html_requests and "Keine Termine vorhanden" not in html_requests:
        content_appointments += "<h2>Anfragen</h2>\n" + html_requests

    html_content = html_content.replace("{{appointments}}", content_appointments)

    # Inline CSS for email client compatibility
    html_content = css_inline.inline(html_content)

    return html_content
