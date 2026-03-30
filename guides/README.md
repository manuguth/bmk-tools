# Guides

Dieses Verzeichnis enthält die Bedienungsanleitungen für das BMK Ticketsystem.

## Inhalt

| Datei | Beschreibung |
|---|---|
| `Abendkasse_Anleitung.pdf` | Fertige Anleitung für Abendkasse-Personal (Ticket Scanner) |
| `generate_guide_pdf.py` | Skript zum (Neu-)Erstellen der Anleitung |
| `config.example.yaml` | Vorlage für die lokale Konfigurationsdatei |
| `config.yaml` | **Lokal, nicht in git** – Produktiv-URL und Scanner-Zugangsdaten |
| `screenshots/` | Automatisch erstellte Screenshots (werden vom Skript überschrieben) |

---

## Anleitung neu generieren

### Voraussetzungen

1. **Virtuelle Umgebung aktivieren** (einmalig pro Session):
   ```bash
   source .venv/bin/activate
   ```

2. **Playwright installieren** (einmalig, falls noch nicht vorhanden):
   ```bash
   pip install playwright
   python -m playwright install chromium
   ```

3. **Django-Entwicklungsserver starten** (in einem separaten Terminal):
   ```bash
   .venv/bin/python manage.py runserver 8742 --noreload
   ```
   Der Server muss auf Port **8742** laufen, da das Skript diesen hartcodiert verwendet.

4. **Scan-Benutzer muss existieren** mit der Gruppe `Ticket Scanner`.
   Wenn `config.yaml` vorhanden ist, wird das dort eingetragene Passwort verwendet.
   Der lokale DB-Benutzer muss dazu passen – siehe Abschnitt [Produktiv-URL und Zugangsdaten](#produktiv-url-und-zugangsdaten-configyaml) unten.

### Skript ausführen

Vom Projektroot aus:

```bash
.venv/bin/python guides/generate_guide_pdf.py
```

Das Skript:
1. Startet einen headless Chromium-Browser (Playwright)
2. Loggt sich als `scan`-Benutzer ein
3. Navigiert zu allen relevanten Seiten und erstellt 8 Screenshots → `guides/screenshots/`
4. Generiert die PDF-Datei → `guides/Abendkasse_Anleitung.pdf`

---

## Produktiv-URL und Zugangsdaten (config.yaml)

Die Datei `guides/config.yaml` kann angelegt werden, um die Produktiv-URL der Einlass-Seite sowie die Scanner-Zugangsdaten zu speichern. Die Datei ist in `.gitignore` eingetragen und wird **nicht** mit Git synchronisiert.

**Einmalige Einrichtung:**

```bash
cp guides/config.example.yaml guides/config.yaml
```

Danach `guides/config.yaml` öffnen und die echten Werte eintragen:

```yaml
# Produktive URL der Einlass-Scanner-Seite
einlass_url: https://deine-domain.de/tickets/einlass/scanner/

# Scanner-Benutzer für automatische Screenshots
scanner_username: scan
scanner_password: dein-echtes-passwort
```

Ist `config.yaml` vorhanden, passiert Folgendes automatisch beim nächsten Skriptlauf:
- Die produktive URL wird in **Abschnitt 1** des PDFs als Link eingebettet.
- Auf der **Titelseite** erscheinen die URL und ein **QR-Code**, den Mitarbeiter direkt scannen können.
- Beim Screenshot-Schritt werden die angegebenen Zugangsdaten verwendet.

Fehlt die Datei, läuft das Skript trotzdem – es verwendet dann die Standard-Zugangsdaten (`scan` / `scanpass123`) und verzichtet auf URL und QR-Code im PDF.

> **Wichtig – lokale Datenbank synchronisieren:**
> Die `scanner_username`/`scanner_password`-Werte in `config.yaml` müssen mit dem lokalen Entwicklungsserver-Benutzer übereinstimmen.
> Wenn du das Passwort in `config.yaml` änderst oder erstmalig einrichtest, musst du es auch in der lokalen SQLite-Datenbank setzen:
> ```bash
> .venv/bin/python manage.py shell -c "
> import yaml
> from django.contrib.auth.models import User
> cfg = yaml.safe_load(open('guides/config.yaml'))
> u = User.objects.get(username=cfg['scanner_username'])
> u.set_password(cfg['scanner_password'])
> u.save()
> print('Passwort gesetzt für:', u.username)
> "
> ```

### Konfiguration anpassen

Am Anfang von `generate_guide_pdf.py` können folgende Konstanten angepasst werden:

| Konstante | Standardwert | Bedeutung |
|---|---|---|
| `BASE` | `http://localhost:8742` | URL des laufenden Servers |
| `CONCERT_SLUG` | `kinderkonzert-2026` | Slug des Konzerts für Abendkasse-Screenshot |
| `CODE_NOT_COLLECTED` | `PC51B49J` | Bestätigungscode einer noch nicht abgeholten Bestellung |
| `CODE_COLLECTED` | `A7FC04AI` | Bestätigungscode einer bereits abgeholten Bestellung |

Die Codes für `CODE_NOT_COLLECTED` und `CODE_COLLECTED` müssen in der Datenbank existieren und die jeweilige Eigenschaft aufweisen (gesammelt / nicht gesammelt). Nach einem Datenbankreset müssen sie aktualisiert werden.
