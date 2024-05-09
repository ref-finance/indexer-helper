#!/bin/sh

pid=`ps -ef | grep "history_token_price_report.py MAINNET" | grep -v grep | /usr/bin/awk '{print $2}'`

cd "/www/wwwroot/mainnet-indexer.ref-finance.com/indexer-helper/backends"

# echo ${pid}
date >> backend_history_token_price_report.log

if [ ! ${pid} ]; then
        # echo "is null"
        echo "No backend process rubbish to clean." >> backend_history_token_price_report.log
else
        # echo "not null"
        kill -s 9 ${pid}
        echo "Warning: clean backend process of last round." >> backend_history_token_price_report.log
fi
. ../venv/bin/activate
python history_token_price_report.py MAINNET >> backend_history_token_price_report.log
echo 'OK'
