all: install

install: 
	pip install -r requirements.txt
	pip install .

dev: 
	pip install -r requirements-dev.txt
	pip install -e .

freeze: 
	pip freeze | sort | grep -v 'clichain'
test: 
	cd tests && ( pytest -rXxs -vv --cov-report html --cov clichain )

doc: 
	cd docs && make html

