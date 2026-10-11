#!/bin/sh
# Creates .venv with the dev tools. Works without the python3-venv package: pip comes as one file from PyPA.
set -e
python3 -m venv --without-pip .venv
python3 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/pip/pip.pyz', '.venv/pip.pyz')"
.venv/bin/python .venv/pip.pyz install -q --disable-pip-version-check -r requirements-dev.txt
