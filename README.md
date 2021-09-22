# ref-indexer-helper

A light web server using Flask + Gunicorn + Nginx, with CICD support

### Usage
Get user's action history of ref-finance
```shell
# request ref-user's latest 10 actions on mainnet
http://localhost/latest-actions/<account_id>
# response in json type
[
    ["<timestamp>", "<method>", "<args>", "<attached_deposit>"],
    ["<timestamp>", "<method>", "<args>", "<attached_deposit>"],
    ...
]
```

get user's liquidity pools
```shell
http://localhost/liquidity-pools/<account_id>
# response in json type
[
    {<pool info>},
    {<pool info>},
    ...
]
```

List pools with max liquidity in each token pair 
```shell
http://localhost/list-top-pools
# response in json type
[
    {<pool info>},
    {<pool info>},
    ...
]
```

list all token with cur market price from coingecko
```shell
http://localhost/list-token-price
# response in json type
{
    token_id: {"pirce": "", "decimal": 8, "symbol": ""},
    token_id: {"pirce": "", "decimal": 8, "symbol": ""},
    ...
}
```

list all pools in ref-finance
```shell
http://localhost/list-pools
# response in json type
[
    {<pool info>},
    {<pool info>},
    ...
]
```

given two tokens, list all pools using that token pair.
```shell
http://localhost/list-pools-by-tokens?token0=xxx&token1=xxxx
# response in json type
[
    {<pool info>},
    {<pool info>},
    ...
]
```

Get all farms in ref-farming
```shell
# request for mainnet
http://localhost:8000/list-farms
# response
[
    {...}, # FarmInfo
    {...}, # FarmInfo
    ...
    {...}, # FarmInfo
]
```

### Build
```
python3 -m venv venv
source venv/bin/activate
# apt-get install libpq-dev
pip install flask
pip install flask-cors
pip install gunicorn
pip install psycopg2
pip install base58
pip install redis
pip install requests
# Flask (2.0.0)
# gunicorn (20.1.0)
# psycopg2 (2.8.6)
```
#### deploy backend
Call deploy_xxx.sh to deploy backend shell scripts with correct network id.
Then make those scripts be periodically called.  
There are several ways to do that:
* crontab
* flask_apscheduler
* other third-party tools

### Start Service
```
source start_server.sh
```

### Stop Service

```
pstree -ap|grep gunicorn
kill -9 <pid>
```
