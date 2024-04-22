#!/bin/sh
. ./venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:8000 app:app