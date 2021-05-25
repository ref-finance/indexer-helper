#!/bin/sh
. ./venv/bin/activate
gunicorn -D -w 4 -b 0.0.0.0:8000 app:app