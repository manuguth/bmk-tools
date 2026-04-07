echo de_DE.UTF-8 UTF-8 >> /etc/locale.gen && locale-gen
python manage.py collectstatic --noinput
gunicorn --bind=0.0.0.0 --timeout 600 bmk_tools.wsgi
# see documentation here https://docs.microsoft.com/en-us/azure/developer/python/tutorial-deploy-app-service-on-linux-04