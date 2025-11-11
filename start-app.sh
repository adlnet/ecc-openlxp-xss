#!/usr/bin/env bash
# start-server.sh

cd /tmp/openlxp-xss/app
python3 manage.py waitdb 
python3 manage.py migrate 
python3 manage.py loaddata admin_theme_data.json 
if [ -n "$TMP_SCHEMA_DIR" ] ; then
    (cd /tmp/openlxp-xss/app; install -d -o 1001 -p $TMP_SCHEMA_DIR)
else
    (cd /tmp/openlxp-xss/app; install -d -o 1001 -p tmp/schemas)
fi
cd /tmp/
pwd 
# service clamav-daemon restart
./start-server.sh
