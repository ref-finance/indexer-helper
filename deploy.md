# Deployment Instruction

## Common Prerequisite

Python 3.7+ is required.

Using a python VirtualEnv is recommended:
```shell
python3 -m venv venv
source venv/bin/activate
```

Following packages is needed:
```shell
pip install flask
pip install flask-cors
pip install gunicorn
# in some OS, need install dev package before install psycopg2
# apt-get install libpq-dev
pip install psycopg2
pip install base58
pip install redis
pip install requests
```

## Backend Deployment

Enter `<project_root_path>/backends`, eg:
```shell
cd ./backends
```

### Install Redis
Redis is required in this project. Please refer to [redis.io](https://redis.io/download#installation) for help.

### Using deploy scripts
Call deploy_xxx.sh to deploy backend shell scripts with correct network id.
```shell
python3 deploy_backend_farm_and_pool.py mainnet
python3 deploy_backend_token_price.py mainnet
```
You will see two scripts file, make them executable:
```shell
chmod a+x backend_token_price.sh
chmod a+x backend_farm_and_pool.sh
```
Finally, put them into crontab for periodically invoke:
```shell
*/5 * * * * /working_path/backend_farm_and_pool.sh > /dev/null
* * * * * /working_path/backend_token_price.sh > /dev/null
```

## Indexer Deployment

Enter `<project_root_path>`, if you are in backends dir, just go up one level:
```shell
cd ..
```
### Start Service
```
source start_server.sh
```

### Stop Service

```
pstree -ap|grep gunicorn
kill -9 <pid>
```