#!/usr/bin/env python
"""
Generate a German-language staff guide PDF for the Tickets module (Abendkasse / Scanner).
Requires: playwright (chromium), reportlab
Run with: .venv/bin/python guides/generate_guide_pdf.py
"""

import io
import os
import sys
import time
from pathlib import Path

# ─── Playwright screenshots ──────────────────────────────────────────────────

BASE = "http://localhost:8742"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)
CONFIG_FILE = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    """Load local config.yaml if it exists (never committed — see .gitignore)."""
    if not CONFIG_FILE.exists():
        return {}
    import yaml
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f) or {}


CONCERT_SLUG = "kinderkonzert-2026"
CODE_NOT_COLLECTED = "PC51B49J"   # also has late_collection=True
CODE_COLLECTED     = "A7FC04AI"   # abendkasse order, already collected

def take_screenshots(username: str = "scan", password: str = "scanpass123"):
    from playwright.sync_api import sync_playwright

    shots = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 430, "height": 900},
            device_scale_factor=2,
        )
        page = context.new_page()

        # ── 1. Login page ────────────────────────────────────────────────────
        page.goto(f"{BASE}/accounts/login/?next=/tickets/einlass/scanner/")
        page.wait_for_load_state("networkidle")
        path = str(SCREENSHOT_DIR / "01_login.png")
        page.screenshot(path=path, full_page=False)
        shots["login"] = path
        print("  ✓ 01_login.png")

        # ── 2. Log in ────────────────────────────────────────────────────────
        page.fill("input[name=username]", username)
        page.fill("input[name=password]", password)
        page.click("button[type=submit]")
        page.wait_for_url(f"{BASE}/tickets/einlass/scanner/")
        time.sleep(0.5)

        # ── 3. Scanner home ──────────────────────────────────────────────────
        page.wait_for_load_state("networkidle")
        path = str(SCREENSHOT_DIR / "02_scanner_home.png")
        page.screenshot(path=path, full_page=True)
        shots["scanner_home"] = path
        print("  ✓ 02_scanner_home.png")

        # ── 4. Name search result ────────────────────────────────────────────
        page.fill("#unified-search-input", "PC51")
        page.click("#unified-search-btn")
        time.sleep(1)
        path = str(SCREENSHOT_DIR / "03_search_results.png")
        page.screenshot(path=path, full_page=True)
        shots["search_results"] = path
        print("  ✓ 03_search_results.png")

        # ── 5. Order detail – not yet collected (late collection) ────────────
        page.goto(f"{BASE}/tickets/einlass/{CODE_NOT_COLLECTED}/")
        page.wait_for_load_state("networkidle")
        path = str(SCREENSHOT_DIR / "04_order_not_collected.png")
        page.screenshot(path=path, full_page=True)
        shots["order_not_collected"] = path
        print("  ✓ 04_order_not_collected.png")

        # ── 6. Order detail – already collected ─────────────────────────────
        page.goto(f"{BASE}/tickets/einlass/{CODE_COLLECTED}/")
        page.wait_for_load_state("networkidle")
        path = str(SCREENSHOT_DIR / "05_order_collected.png")
        page.screenshot(path=path, full_page=True)
        shots["order_collected"] = path
        print("  ✓ 05_order_collected.png")

        # ── 7. Abendkasse page ───────────────────────────────────────────────
        page.goto(f"{BASE}/tickets/einlass/{CONCERT_SLUG}/abendkasse/")
        page.wait_for_load_state("networkidle")
        path = str(SCREENSHOT_DIR / "06_abendkasse.png")
        page.screenshot(path=path, full_page=True)
        shots["abendkasse"] = path
        print("  ✓ 06_abendkasse.png")

        # ── 8. Abendkasse – after incrementing counts (pre-submit) ───────────
        page.click("#inc-adult")
        page.click("#inc-adult")
        time.sleep(0.2)
        path = str(SCREENSHOT_DIR / "07_abendkasse_filled.png")
        page.screenshot(path=path, full_page=True)
        shots["abendkasse_filled"] = path
        print("  ✓ 07_abendkasse_filled.png")

        # ── 9. Abendkasse – confirm step (button turns green) ────────────────
        page.click("#sell-btn")   # first click → confirm mode
        time.sleep(0.3)
        path = str(SCREENSHOT_DIR / "08_abendkasse_confirm.png")
        page.screenshot(path=path, full_page=True)
        shots["abendkasse_confirm"] = path
        print("  ✓ 08_abendkasse_confirm.png")

        browser.close()

    return shots


# ─── PDF generation ──────────────────────────────────────────────────────────

def build_pdf(shots: dict, output_path: str, einlass_url: str = None,
              scanner_username: str = None, scanner_password: str = None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image,
        Table, TableStyle, HRFlowable, PageBreak, KeepTogether,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    W, H = A4
    NAVY  = colors.HexColor("#1e293b")
    GOLD  = colors.HexColor("#d97706")
    LIGHT = colors.HexColor("#f8fafc")
    MUTED = colors.HexColor("#64748b")
    GREEN = colors.HexColor("#059669")
    RED   = colors.HexColor("#dc2626")
    BLUE  = colors.HexColor("#1d4ed8")
    WARN  = colors.HexColor("#92400e")

    styles = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    title_s    = S("title",    fontSize=22, fontName="Helvetica-Bold",  textColor=NAVY,  spaceAfter=4*mm, leading=26)
    subtitle_s = S("subtitle", fontSize=11, fontName="Helvetica",       textColor=MUTED, spaceAfter=8*mm)
    h1_s       = S("h1",       fontSize=15, fontName="Helvetica-Bold",  textColor=NAVY,  spaceBefore=8*mm, spaceAfter=3*mm, borderPad=0)
    h2_s       = S("h2",       fontSize=12, fontName="Helvetica-Bold",  textColor=GOLD,  spaceBefore=5*mm, spaceAfter=2*mm)
    body_s     = S("body",     fontSize=9.5,fontName="Helvetica",       textColor=colors.black, spaceAfter=2*mm, leading=14)
    bullet_s   = S("bullet",   fontSize=9.5,fontName="Helvetica",       textColor=colors.black, spaceAfter=1.5*mm, leading=13, leftIndent=8*mm, bulletIndent=2*mm)
    caption_s  = S("caption",  fontSize=8,  fontName="Helvetica-Oblique",textColor=MUTED, spaceAfter=4*mm, alignment=TA_CENTER)
    note_s     = S("note",     fontSize=8.5,fontName="Helvetica-Oblique",textColor=WARN,  spaceAfter=3*mm, leftIndent=4*mm)
    tip_s      = S("tip",      fontSize=8.5,fontName="Helvetica",       textColor=GREEN, spaceAfter=3*mm, leftIndent=4*mm)
    warn_s     = S("warn",     fontSize=8.5,fontName="Helvetica",       textColor=RED,   spaceAfter=3*mm, leftIndent=4*mm)

    def screenshot(key, caption_text, max_w=None, max_h=None):
        path = shots.get(key)
        if not path or not Path(path).exists():
            return []
        max_w = max_w or (W - 40*mm)
        max_h = max_h or 140*mm
        img = Image(path)
        iw, ih = img.imageWidth, img.imageHeight
        scale = min(max_w / iw, max_h / ih, 1.0)
        img.drawWidth  = iw * scale
        img.drawHeight = ih * scale
        return [img, Paragraph(caption_text, caption_s)]

    def divider():
        return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=4*mm, spaceBefore=2*mm)

    def make_qr(url: str, size: float = 38 * mm):
        import qrcode as _qrcode
        qr = _qrcode.QRCode(version=None, box_size=10, border=2,
                             error_correction=_qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(url)
        qr.make(fit=True)
        pil_img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)
        img = Image(buf)
        img.drawWidth = size
        img.drawHeight = size
        return img

    def _creds_rows(username, password):
        if username and password:
            t = Table(
                [
                    [Paragraph("<b>Benutzername</b>", body_s), Paragraph(username, body_s)],
                    [Paragraph("<b>Passwort</b>",     body_s), Paragraph(password,  body_s)],
                ],
                colWidths=[45*mm, W - 85*mm],
            )
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
                ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTSIZE",      (0, 0), (-1, -1), 9),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ]))
            return [t, Spacer(1, 2*mm)]
        return [
            Paragraph("• <b>Benutzername</b>: dein persönlicher Login-Name", bullet_s),
            Paragraph("• <b>Passwort</b>: dein persönliches Passwort", bullet_s),
        ]

    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # TITELSEITE
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Spacer(1, 25*mm),
        Paragraph("BMK Tickets", title_s),
        Paragraph("Bedienungsanleitung für Abendkasse-Personal", subtitle_s),
        Paragraph("Rolle: Ticket Scanner (Abendkasse / Einlass)", subtitle_s),
        divider(),
        Spacer(1, 5*mm),
        Paragraph(
            "Diese Anleitung beschreibt Schritt für Schritt, wie du als Abendkasse-Mitarbeiter "
            "die Scanner- und Abendkasse-Funktionen des Ticketsystems verwendest. "
            "Sie gilt für alle Benutzer der Gruppe <b>\"Ticket Scanner\"</b> oder <b>\"Tickets Admin\"</b>.",
            body_s,
        ),
        Spacer(1, 5*mm),
    ]

    if einlass_url:
        story += [
            Paragraph("Produktiv-URL (Scanner-Einlass):", h2_s),
            Paragraph(
                f'<link href="{einlass_url}" color="#1d4ed8">{einlass_url}</link>',
                body_s,
            ),
            Spacer(1, 2*mm),
            make_qr(einlass_url),
            Paragraph("QR-Code → direkt zur Einlass-Scanner-Seite", caption_s),
            Spacer(1, 3*mm),
        ]

    # Inhaltsverzeichnis (manuell, da kein TOC-Plugin nötig)
    toc_data = [
        ["#", "Abschnitt"],
        ["1", "Anmeldung"],
        ["2", "Scanner-Startseite"],
        ["3", "Suche nach Name oder Code"],
        ["4", "Bestelldetails – Einlass & Zahlung"],
        ["5", "Abendkasse – Laufender Kartenverkauf"],
        ["6", "Häufige Situationen"],
        ["7", "Was du nicht kannst (Rollenbeschränkungen)"],
    ]
    toc_table = Table(toc_data, colWidths=[15*mm, W - 55*mm])
    toc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT, colors.white]),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [toc_table, PageBreak()]


    # ══════════════════════════════════════════════════════════════════════════
    # 1. ANMELDUNG
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("1. Anmeldung", h1_s),
        divider(),
        Paragraph(
            (
                f'Öffne <link href="{einlass_url}" color="#1d4ed8">{einlass_url}</link> im Browser '
                f'auf deinem Smartphone oder Tablet. Du wirst ggf. zur Anmeldeseite weitergeleitet.'
            ) if einlass_url else (
                "Öffne den Browser auf deinem Smartphone oder Tablet und rufe die Ticketsystem-URL auf. "
                "Du wirst automatisch zur Anmeldeseite weitergeleitet."
            ),
            body_s,
        ),
        Paragraph("Zugangsdaten eingeben:", h2_s),
    ] + _creds_rows(scanner_username, scanner_password) + [
        Paragraph(
            "Hinweis: Wende dich an einen Admin, wenn du dein Passwort nicht kennst oder vergessen hast.",
            note_s,
        ),
    ] + screenshot("login", "Abb. 1 – Anmeldeseite") + [
        Paragraph(
            "Nach erfolgreicher Anmeldung landest du direkt auf der <b>Scanner-Startseite</b>.",
            tip_s,
        ),
        PageBreak(),
    ]


    # ══════════════════════════════════════════════════════════════════════════
    # 2. SCANNER-STARTSEITE
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("2. Scanner-Startseite", h1_s),
        divider(),
        Paragraph(
            "Die Scanner-Startseite ist dein Ausgangspunkt am Konzerttag. "
            "Von hier aus erreichst du alle relevanten Funktionen.",
            body_s,
        ),
    ] + screenshot("scanner_home", "Abb. 2 – Scanner-Startseite") + [
        Paragraph("Abendkasse-Schaltfläche", h2_s),
        Paragraph(
            "Oben auf der Seite befindet sich der <b>Abendkasse</b>-Button:",
            body_s,
        ),
        Paragraph("• Wenn <b>genau ein</b> Konzert heute aktiv ist, führt ein einzelner Klick direkt zur Abendkasse dieses Konzerts.", bullet_s),
        Paragraph("• Wenn <b>mehrere</b> Konzerte aktiv sind, öffnet sich ein Auswahlmenü – wähle das richtige Konzert aus.", bullet_s),

        Paragraph("Kamera-Scanner", h2_s),
        Paragraph(
            "Tippe auf <b>\"Kamera starten\"</b>, um die Kamera zu aktivieren. "
            "Halte das Gerät auf den QR-Code in der Bestätigungs-E-Mail des Kunden. "
            "Bei erfolgreichem Scan wird die Bestelldetailseite automatisch geöffnet.",
            body_s,
        ),
        Paragraph(
            "Tipp: Tippe auf das × oben rechts im Kamerabild, um die Kamera zu schließen. "
            "Bei technischen Problemen steht die Schaltfläche \"Erneut versuchen\" zur Verfügung.",
            tip_s,
        ),
        PageBreak(),
    ]


    # ══════════════════════════════════════════════════════════════════════════
    # 3. SUCHE
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("3. Suche nach Name oder Code", h1_s),
        divider(),
        Paragraph(
            "Wenn ein Kunde seinen QR-Code nicht vorzeigen kann, nutze die manuelle Suche. "
            "Gib mindestens <b>2 Zeichen</b> ein – entweder einen Namensteil oder den "
            "8-stelligen Bestätigungscode.",
            body_s,
        ),
    ] + screenshot("search_results", "Abb. 3 – Suchergebnisse nach Name") + [
        Paragraph("Jedes Suchergebnis zeigt:", h2_s),
        Paragraph("• <b>Vollständiger Name</b> des Kunden", bullet_s),
        Paragraph("• <b>Konzertname</b>", bullet_s),
        Paragraph("• <b>Status-Badge</b>: ausstehend / bestätigt / storniert", bullet_s),
        Paragraph("• Ob die Bestellung bereits <b>abgeholt</b> wurde", bullet_s),
        Paragraph("• Link zur <b>Bestelldetailseite</b>", bullet_s),
        Paragraph(
            "Tipp: Ein vollständiger 8-stelliger Code (z. B. A3X7K2BQ) wird als exakte Suche behandelt "
            "und führt dich direkt zur richtigen Bestellung.",
            tip_s,
        ),
        PageBreak(),
    ]


    # ══════════════════════════════════════════════════════════════════════════
    # 4. BESTELLDETAILS
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("4. Bestelldetails – Einlass & Zahlung", h1_s),
        divider(),

        Paragraph("4.1  Statusanzeigen oben auf der Seite", h2_s),
        Paragraph(
            "Ganz oben siehst du farbige Hinweisbanner, die den aktuellen Zustand der Bestellung zeigen:",
            body_s,
        ),
    ]

    # Status-Tabelle
    status_data = [
        ["Farbe / Banner", "Bedeutung"],
        ["Gelb – \"Noch nicht abgeholt\"",       "Kunde noch nicht eingecheckt"],
        ["Grün – \"Bereits abgeholt\"",           "Einlass bereits erfolgt"],
        ["Orange – \"Späte Abholung\"",           "Admin-Ausnahme: Plätze NICHT freigeben!"],
        ["Blau – \"Zahlung bereits erhalten\"",   "Kein Kassenvorgang nötig"],
        ["Rot – \"storniert\"",                    "Ungültige Bestellung – kein Einlass"],
    ]
    st = Table(status_data, colWidths=[72*mm, W - 112*mm])
    st.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT, colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
    ]))
    story += [st, Spacer(1, 3*mm)]

    story += [
        Paragraph("4.2  Bestellung noch nicht abgeholt", h2_s),
    ] + screenshot("order_not_collected",
                   "Abb. 4 – Bestelldetails: Kunde noch nicht abgeholt (mit Späte-Abholung-Hinweis)",
                   max_h=120*mm) + [

        Paragraph("Personenzahl anpassen (falls nötig):", h2_s),
        Paragraph(
            "Unter <b>Einlass &amp; Zahlung</b> siehst du + / − Schaltflächen für Erwachsene und Kinder. "
            "Die Voreinstellung entspricht der Reservierung.",
            body_s,
        ),
        Paragraph("• <b>Weniger Personen</b>: tippe auf <b>−</b>, wenn nicht alle der Reservierung erscheinen (\"No-Shows\"). Die freien Plätze werden zurück ins Kontingent gebucht.", bullet_s),
        Paragraph("• <b>Mehr Personen</b>: tippe auf <b>+</b>, um Extras hinzuzufügen (nur wenn noch Abendkasse-Kapazität frei ist). Extras werden automatisch als eigene Abendkasse-Bestellung erfasst.", bullet_s),
        Paragraph("• Der <b>Preis beim Einlass</b> wird sofort aktualisiert – du siehst immer den zu kassierenden Betrag.", bullet_s),

        Paragraph("Zahlung &amp; Einlass bestätigen:", h2_s),
        Paragraph(
            "Tippe auf den großen grünen Button:",
            body_s,
        ),
        Paragraph("• <b>\"Abgeholt ✓\"</b> – wenn die Zahlung bereits vorab erfasst wurde (blauer Hinweis)", bullet_s),
        Paragraph("• <b>\"Abgeholt &amp; bezahlt ✓\"</b> – Zahlung jetzt entgegennehmen und gleichzeitig einchecken", bullet_s),
        Paragraph(
            "Achtung: Dieser Vorgang kann nicht rückgängig gemacht werden. "
            "Stelle sicher, dass die Personenzahl korrekt ist, bevor du bestätigst.",
            warn_s,
        ),
        PageBreak(),

        Paragraph("4.3  Bestellung bereits abgeholt", h2_s),
    ] + screenshot("order_collected",
                   "Abb. 5 – Bestelldetails: Kunde bereits abgeholt",
                   max_h=120*mm) + [
        Paragraph(
            "Wurde die Bestellung bereits abgeholt, ist das Einlass-Formular ausgeblendet. "
            "Du kannst nur noch den <b>Zahlungsstatus</b> korrigieren:",
            body_s,
        ),
        Paragraph("• \"Als bezahlt markieren\" – wenn die Zahlung nachträglich eintrifft", bullet_s),
        Paragraph("• \"Als unbezahlt markieren\" – wenn eine Zahlung irrtümlich erfasst wurde", bullet_s),
        PageBreak(),
    ]


    # ══════════════════════════════════════════════════════════════════════════
    # 5. ABENDKASSE
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("5. Abendkasse – Laufender Kartenverkauf", h1_s),
        divider(),
        Paragraph(
            "Die Abendkasse-Seite ermöglicht direkten Kartenverkauf an Laufkundschaft "
            "und zeigt die aktuelle Kapazitätslage in Echtzeit.",
            body_s,
        ),
    ] + screenshot("abendkasse",
                   "Abb. 6 – Abendkasse-Seite mit Kapazitätsanzeige") + [

        Paragraph("5.1  Kapazitätsanzeige", h2_s),
        Paragraph(
            "Zwei nebeneinander liegende Kacheln zeigen <b>Erwachsene</b> und <b>Kinder</b>:",
            body_s,
        ),
        Paragraph("• Große Zahl = freie Plätze, farbkodiert: <b>Grün</b> = gut, <b>Orange</b> = fast voll (≤ 5), <b>Rot</b> = ausverkauft", bullet_s),
        Paragraph("• <b>Fortschrittsbalken</b>: dunkelblaues Segment = Vorverkauf, goldenes Segment = Abendkasse", bullet_s),
        Paragraph("• Untere Zeile: VVK-Anzahl · AK-Anzahl · ✓ bereits abgeholt", bullet_s),

        Paragraph("5.2  Spät-Abholung &amp; Deadline", h2_s),
        Paragraph(
            "Unter den Kacheln erscheint eine Zusatzinfo:",
            body_s,
        ),
        Paragraph("• <b>Spät-Abholung reserviert</b>: Plätze, die auf Kundenwunsch nach Deadline freigehalten werden", bullet_s),
        Paragraph("• <b>Frei nach HH:MM Uhr</b>: Plätze, die nach Ablauf der Abholdeadline verfügbar werden (nicht abgeholte VVK ohne Sondervereinbarung)", bullet_s),

        Paragraph("5.3  Ticket verkaufen", h2_s),
    ] + screenshot("abendkasse_filled",
                   "Abb. 7 – Mengenauswahl für Abendkasse-Verkauf") + [
        Paragraph(
            "Nutze die <b>+</b> / <b>−</b> Schaltflächen, um die gewünschte Anzahl an Erwachsenen- und Kindertickets einzustellen. "
            "Der Gesamtpreis wird sofort angezeigt.",
            body_s,
        ),
    ] + screenshot("abendkasse_confirm",
                   "Abb. 8 – Bestätigungsschritt: Button wird grün") + [
        Paragraph(
            "Tippe auf <b>\"Verkaufen\"</b> – der Button wird grün und fordert eine zweite Bestätigung "
            "(\"✓ Sicher? XX,XX € – Bestätigen\"). Tippe erneut, um den Verkauf abzuschließen.",
            body_s,
        ),
        Paragraph(
            "Das verkaufte Ticket wird sofort als abgeholt und bezahlt erfasst und "
            "im Kapazitätszähler abgezogen.",
            tip_s,
        ),
        Paragraph(
            "Achtung: Wenn die Kapazität seit dem letzten Seitenaufruf erschöpft wurde, "
            "erscheint eine rote Fehlermeldung. Lade die Seite neu und prüfe die verbleibenden Plätze.",
            warn_s,
        ),
        PageBreak(),
    ]


    # ══════════════════════════════════════════════════════════════════════════
    # 6. HÄUFIGE SITUATIONEN
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("6. Häufige Situationen", h1_s),
        divider(),
    ]

    situations = [
        (
            "Kunde bringt mehr Personen als reserviert",
            "Auf der Bestelldetailseite + tippen, um die Mehrpersonen hinzuzufügen. "
            "Das System prüft die verbleibende Abendkasse-Kapazität. "
            "Extras werden automatisch als eigene Abendkasse-Bestellung erfasst.",
        ),
        (
            "Nicht alle erscheinen (No-Shows)",
            "Auf der Bestelldetailseite − tippen, um die Anzahl zu reduzieren. "
            "Der Preis wird neu berechnet und die freigewordenen Plätze stehen wieder zur Verfügung.",
        ),
        (
            "Kunde hat QR-Code vergessen",
            "Manuelle Suche auf der Scanner-Startseite nutzen: Nachnamen eingeben. "
            "Alternativ den 8-stelligen Bestätigungscode eingeben, falls der Kunde ihn kennt.",
        ),
        (
            "Konzert fast ausverkauft",
            "Die Kapazitätskacheln zeigen Orange (≤ 5 Plätze) oder Rot (0). "
            "Der + -Button ist bei ausverkaufter Kategorie deaktiviert.",
        ),
        (
            "Nach Ablauf der Abholdeadline",
            "Die Zeile \"Frei nach HH:MM Uhr\" auf der Abendkasse-Seite zeigt, "
            "wie viele Plätze durch nicht abgeholte Reservierungen freigegeben wurden.",
        ),
        (
            "Stornierte Bestellung",
            "Auf der Bestelldetailseite erscheint ein roter Hinweis. "
            "Das Einlass-Formular ist nicht verfügbar. Weise den Kunden an einen Admin.",
        ),
        (
            "Spare Abholung (Späte Abholung)",
            "Ein orangefarbener Hinweis erscheint auf der Bestelldetailseite. "
            "Die Plätze sind für diesen Kunden reserviert und dürfen nicht freigegeben werden, "
            "auch wenn die Deadline abgelaufen ist.",
        ),
        (
            "Zahlung nachträglich korrigieren",
            "Auf der Bestelldetailseite (nach Einlass) den Button "
            "\"Als bezahlt markieren\" bzw. \"Als unbezahlt markieren\" nutzen.",
        ),
    ]

    for title, text in situations:
        row = Table(
            [[Paragraph(f"<b>{title}</b>", S("sh", fontSize=9.5, fontName="Helvetica-Bold", textColor=NAVY)),
              Paragraph(text, body_s)]],
            colWidths=[55*mm, W - 95*mm],
        )
        row.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), LIGHT),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ]))
        story += [row, Spacer(1, 1.5*mm)]

    story += [PageBreak()]


    # ══════════════════════════════════════════════════════════════════════════
    # 7. ROLLENBESCHRÄNKUNGEN
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("7. Was du nicht kannst (Rollenbeschränkungen)", h1_s),
        divider(),
        Paragraph(
            "Als Mitglied der Gruppe <b>\"Ticket Scanner\"</b> hast du keinen Zugriff auf folgende Funktionen. "
            "Bei Bedarf wende dich an einen <b>Tickets Admin</b>.",
            body_s,
        ),
    ]

    restrictions = [
        ("✗", "Konzerte anlegen oder bearbeiten"),
        ("✗", "Bestellstatus ändern (ausstehend → bestätigt → storniert)"),
        ("✗", "Kundendaten bearbeiten (Name, E-Mail, Telefon, Anmerkungen)"),
        ("✗", "CSV- oder PDF-Exportberichte erstellen"),
        ("✗", "Späte-Abholung-Flag (late_collection) setzen"),
        ("✗", "Django-Administrationsbereich aufrufen"),
    ]

    for sym, text in restrictions:
        story.append(
            Paragraph(f"<b><font color='#dc2626'>{sym}</font></b>  {text}", bullet_s)
        )

    story += [
        Spacer(1, 6*mm),
        divider(),
        Paragraph(
            "Stand: März 2026 · BMK Ticketsystem",
            S("footer", fontSize=7.5, fontName="Helvetica-Oblique", textColor=MUTED, alignment=TA_CENTER),
        ),
    ]

    # ── Build ─────────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=18*mm,
        bottomMargin=18*mm,
        title="BMK Tickets – Anleitung Abendkasse / Scanner",
        author="BMK Ticketsystem",
    )
    doc.build(story)
    print(f"\n  ✓ PDF geschrieben: {output_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config = load_config()
    einlass_url = config.get("einlass_url")
    username = config.get("scanner_username", "scan")
    password = config.get("scanner_password", "scanpass123")

    if einlass_url:
        print(f"  Produktiv-URL aus config.yaml: {einlass_url}")

    print("=== Schritt 1: Screenshots erstellen ===")
    screenshots = take_screenshots(username=username, password=password)

    print("\n=== Schritt 2: PDF generieren ===")
    output = str(Path(__file__).parent / "Abendkasse_Anleitung.pdf")  # guides/Abendkasse_Anleitung.pdf
    build_pdf(screenshots, output, einlass_url=einlass_url,
             scanner_username=username, scanner_password=password)

    print(f"\nFertig! Öffne: {output}")
