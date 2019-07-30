PYTHON=python3
DJANGOADMIN=django-admin.py

all:

translations:
	cd massmailer \
		&& $(DJANGOADMIN) makemessages -l fr -l en \
		&& $(DJANGOADMIN) compilemessages

dist:
	$(MAKE) clean
	$(PYTHON) setup.py sdist bdist_wheel

upload-dev: dist
	$(PYTHON) -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

upload: dist
	$(PYTHON) -m twine upload dist/*

clean:
	$(RM) -r *.egg-info pip-wheel-metadata build dist


.PHONY: translations dist upload upload-dev clean
