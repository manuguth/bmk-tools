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

run server to be also visible in entire network
```
python manage.py runserver 0.0.0.0:8000
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

# New Features - ToDos

* Adding overview page with all apps
* integrating weekly newsletters into webapp
  * everyone with access can edit and send from here
  * add machanics to avoid duplicate sending