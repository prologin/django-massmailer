PYTHON=python3
DJANGOADMIN=django-admin.py

translations:
	cd massmailer \
		&& $(DJANGOADMIN) makemessages -l fr -l en \
		&& $(DJANGOADMIN) compilemessages

dist:
	$(PYTHON) setup.py sdist bdist_wheel

upload-dev: dist
	$(PYTHON) -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

upload: dist
	$(PYTHON) -m twine upload dist/*

clean:
	$(RM) -r *.egg-info pip-wheel-metadata build dist


.PHONY: translations dist upload upload-dev clean
