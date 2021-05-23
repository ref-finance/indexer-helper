#!/bin/sh


pid=`ps -ef | grep "backend_update_farms.py" | grep -v grep | /usr/bin/awk '{print $2}'`

# echo ${pid}

if [ ! ${pid} ]; then
        # echo "is null"
        echo "No backend process rubbish to clean." >> log_backend.log
else
        # echo "not null"
        kill -s 9 ${pid}
        echo "Warning: clean backend process of last round." >> log_backend.log
fi
source ./venv/bin/activate
python backend_update_farms.py >> log_backend.log
echo 'OK'