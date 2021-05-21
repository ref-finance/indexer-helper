# ref-indexer-helper

A light web server using Flask + Gunicorn + Nginx

### Usage
```shell
# request ref-user's latest 10 actions on mainnet
http://localhost:8000/latest-actions/<account_id>
# request ref-user's latest 10 actions on testnet
http://localhost:8000/latest-actions-testnet/<account_id>
# response in json type
[
    ["<timestamp>", "<method>", "<args>", "<attached_deposit>"],
    ["<timestamp>", "<method>", "<args>", "<attached_deposit>"],
    ...
]
```

### Build
```
# apt-get install libpq-dev
pip install flask
pip install gunicorn
pip install psycopg2
# Flask (2.0.0)
# gunicorn (20.1.0)
# psycopg2 (2.8.6)
```
### Start Service
```
srouce start_server.sh
```

### Stop Service

```
pstree -ap|grep gunicorn
kill -9 <pid>
```
