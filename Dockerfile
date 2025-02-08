FROM python:3.10-slim

COPY requirements.txt /requirements.txt
RUN pip3 install -r requirements.txt

COPY akv_cachehandler.py /akv_cachehandler.py
COPY playlistbuilder.py /playlistbuilder.py
COPY config.staging.json /config.staging.json

CMD ["python3", "playlistbuilder.py"]