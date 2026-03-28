# bmk-tools

Collection of website/online tools useful for BMK (Blasmusikkapelle).

## Apps

| App | Description |
|-----|-------------|
| `tickets` | Concert ticket reservations, capacity management, QR-code generation, email confirmations |
| `festival` | Volunteer shift management with Konzertmeister API integration |
| `bring_list` | Collaborative shopping lists with session-based permissions |
| `info_mail` | Weekly HTML newsletters with REST API upload |
| `bmk_tools` | Core/home views and project configuration |

---

## Development Setup

### Prerequisites

- Python 3.12+
- [SQLite](https://www.sqlite.org/) (default, zero-config for local dev)
- PostgreSQL 16+ (optional locally; required in CI)

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd bmk-tools
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy or create a `.env` file:

```bash
# .env (minimum required for local dev)
SECRET_KEY=your-local-secret-key
DEFAULT_FROM_EMAIL=noreply@example.com

# Optional — omit to use SQLite
# DB_NAME=bmk
# DB_USER=bmk
# DB_PASSWORD=secret
# DB_HOST=localhost
# DB_PORT=5432
```

Load it into your shell:

```bash
set -a; source .env; set +a
```

> **Database selection**: if `DB_NAME` is set in the environment, the app uses PostgreSQL. Otherwise it falls back to `db.sqlite3`.

### 4. Apply migrations and create a superuser

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Run the development server

```bash
# Localhost only
python manage.py runserver

# Visible on the entire local network
python manage.py runserver 0.0.0.0:8000
```

---

## Running Tests

### Install test dependencies

```bash
pip install -r requirements-test.txt
```

### Run all tests

```bash
python manage.py test
```

### Run tests with verbose output

```bash
python manage.py test --verbosity=2
```

### Run tests for a specific app

```bash
python manage.py test tickets
python manage.py test festival
python manage.py test bring_list
python manage.py test info_mail
python manage.py test bmk_tools
```

### Run a single test class or method

```bash
python manage.py test tickets.tests.ConcertModelTests
python manage.py test tickets.tests.ConcertModelTests.test_slug_auto_generated
```

---

## Code Coverage

Coverage is configured in `pyproject.toml` with a minimum threshold of **60%**.

```bash
# Run tests and collect coverage data
coverage run manage.py test

# Print report in the terminal
coverage report

# Generate an HTML report (opens in browser)
coverage html
open htmlcov/index.html
```

> Branch coverage is enabled. The report omits migrations, `manage.py`, `asgi.py`, `wsgi.py`, and playground scripts.

---

## CI — GitHub Actions

Every pull request targeting `main` triggers the **Tests** workflow (`.github/workflows/test.yml`).

The workflow:
1. Spins up a **PostgreSQL 16** service container
2. Installs all dependencies (`requirements.txt` + `requirements-test.txt`)
3. Runs the full test suite via `coverage run manage.py test --verbosity=2`
4. Generates coverage XML + HTML reports
5. Uploads both as workflow artifacts (retained 14 days)

The job is named **`test`** — this is the name to reference when configuring branch protection.

### Require the check before merging (branch protection)

**GitHub UI**: Settings → Branches → Add branch protection rule → branch name: `main` → enable *"Require status checks to pass before merging"* → search for and add the check named **`test`**.

**GitHub CLI** (run after the workflow has executed at least once):

```bash
gh api repos/OWNER/REPO/branches/main/protection \
  --method PUT \
  --field 'required_status_checks={"strict":true,"contexts":["test"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews=null \
  --field restrictions=null
```

Replace `OWNER/REPO` with the actual repository path.

> The protection rule can only reference a check name *after* the workflow has run on at least one PR.

---

## Project Structure

```
bmk-tools/
├── bmk_tools/          # Django project settings, URLs, core views
├── tickets/            # Concert tickets app
├── festival/           # Festival / volunteer shift app
├── bring_list/         # Collaborative shopping list app
├── info_mail/          # Weekly newsletter app
├── templates/          # Global base templates
├── uploads/            # Media files (concert posters, HTML newsletters)
├── .github/
│   └── workflows/
│       └── test.yml    # PR CI workflow
├── requirements.txt        # Production dependencies
├── requirements-test.txt   # Test-only dependencies (coverage)
├── pyproject.toml          # Coverage and Black config
└── manage.py
```

---

## Tech Stack

- **Django 5.0.3** — web framework
- **Django REST Framework 3.15** — REST API for `info_mail` uploads
- **PostgreSQL 16** — production database
- **SQLite** — local development database (default)
- **Whitenoise** — static file serving
- **qrcode / reportlab** — QR code and PDF generation for tickets
- **pyyaml** — YAML import/export for festival shifts
- **azure-storage-blob / django-storages** — Azure Blob Storage for media files

---

## Roadmap

- Adding overview page with all apps
- Integrating weekly newsletters into webapp (edit + send from UI, duplicate-send protection)
- Implement Entra ID (Azure AD) login
