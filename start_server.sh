#!/bin/sh
. ./venv/bin/activate
gunicorn -w 8 -b 0.0.0.0:8000 app:app