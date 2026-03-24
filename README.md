# bmk-tools
Collection of website/online tools useful for BMK


## Setup

```bash
source .django_venv/bin/activate
```

### On first setup

1. migrate
```bash
python manage.py migrate
```

1. Create new superuser
```bash
python manage.py createsuperuser
```



http://192.168.1.93:8000/festival/admin
http://192.168.1.93:8000/festival/bugginger-fescht-2026/
http://192.168.1.93:8000/festival/vorspielnachmittag-2026/

local dev user
admin
pw: admin


next steps:


### set env vars from .venv

```
set -a; source .env; set +a
```