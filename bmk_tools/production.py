from .settings import *
import os

# setting admins
ADMINS = [("Manuel", "manuel.guth@bmk-buggingen.de")]

# Configure the domain name using the environment variable
# that Azure automatically creates for us.
ALLOWED_HOSTS = (
    [
        os.environ["WEBSITE_HOSTNAME"],
        "bmk-tools.azurewebsites.net",
        "tools.bmk-buggingen.de",
        "https://tools.bmk-buggingen.de",
        "https://bmk-tools.azurewebsites.net",
    ]
    if "WEBSITE_HOSTNAME" in os.environ
    else []
)
CSRF_TRUSTED_ORIGINS = [
    "https://tools.bmk-buggingen.de",
    "https://bmk-tools.azurewebsites.net",
]


# WhiteNoise configuration
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Add whitenoise middleware after the security middleware
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# DBHOST is only the server name, not the full URL
hostname = os.environ["DBHOST"]

SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = True

# Configure Postgres database; the full username is username@servername,
# which we construct using the DBHOST value.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DBNAME"],
        "HOST": hostname,
        "USER": os.environ["DBUSER"],
        "PASSWORD": os.environ["DBPASS"],
        "OPTIONS": {"sslmode": "require"},
    },
    "users_db": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DBNAME_USERS"],
        "HOST": hostname,
        "USER": os.environ["DBUSER"],
        "PASSWORD": os.environ["DBPASS"],
        "OPTIONS": {"sslmode": "require"},
    },
}


AZURE_ACCOUNT_NAME = os.environ["AZURE_ACCOUNT_NAME"]
AZURE_ACCOUNT_KEY = os.environ["AZURE_ACCOUNT_KEY"]
AZURE_CONTAINER = os.environ["AZURE_CONTAINER"]
DEFAULT_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"

STATICFILES_STORAGE = "storages.backends.azure_storage.AzureStorage"
AZURE_STATIC_CONTAINER = "static-files"