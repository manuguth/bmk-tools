"""
WSGI config for bmk_tools project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
settings_module = (
    "bmk_tools.production"
    if ("DJANGO_ENV" in os.environ and os.environ["DJANGO_ENV"] == "production")
    else "bmk_tools.settings"
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)

application = get_wsgi_application()
