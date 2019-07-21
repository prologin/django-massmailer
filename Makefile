DJANGOADMIN=django-admin.py

translations:
	cd massmailer \
		&& $(DJANGOADMIN) makemessages -l fr -l en \
		&& $(DJANGOADMIN) compilemessages
