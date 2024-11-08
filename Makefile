.PHONY: default
SHELL := /bin/bash

default: build

cleanup:
	rm -rf dist build certbot_plugin_websupport.egg-info
	find . -name "*.pyc" -delete
	find . -name "*.egg-info" -delete
	find . -name "*.pyo" -delete

build: cleanup
	python setup.py bdist_wheel

upload:
	twine upload dist/*

test:
	python -m pytest
