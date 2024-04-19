FROM python:3.10

ADD ./ /indexer/
WORKDIR /indexer/

RUN python3 -m venv venv && \
    . ./venv/bin/activate && \
    python3 -m pip install -r requirements.txt

ENTRYPOINT ["/bin/bash", "/indexer/start_server.sh"]