#!/usr/bin/env bash
# start-server.sh
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] ; then
    (cd /tmp/openlxp-xss/app; python3 manage.py createsuperuser --no-input)
fi
(cd /tmp/openlxp-xss/app; gunicorn openlxp_xss_project.wsgi --reload --user 1001 --bind 0.0.0.0:8010 --workers 3)
