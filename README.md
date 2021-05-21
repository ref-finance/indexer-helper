# ref-indexer-helper

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
