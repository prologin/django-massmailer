
runserver:
	python3 manage.py runserver 8015

celeryworker:
	DJANGO_SETTINGS_MODULE=demoapp.settings celery -l debug -A demoapp -c 1 worker
