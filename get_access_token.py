import os
import sys

import django
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

settings_module = (
    "bmk_tools.production"
    if ("DJANGO_ENV" in os.environ and os.environ["DJANGO_ENV"] == "production")
    else "bmk_tools.settings"
)
os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
django.setup()

User = get_user_model()


def get_or_create_token(username):
    user = User.objects.get(username=username)
    token, created = Token.objects.get_or_create(user=user)
    if created:
        print(f"Created new token: {token.key}")
    else:
        print(f"Existing token: {token.key}")


# replace 'username' with the username of the user you want to get or create a token for
if len(sys.argv) != 2:
    print("Please provide a username as a command line argument.")
    sys.exit(1)

username = sys.argv[1]
get_or_create_token(username)
