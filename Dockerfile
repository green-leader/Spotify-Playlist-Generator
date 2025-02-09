FROM python:3.13-slim

COPY requirements.txt /requirements.txt
RUN pip3 install -r requirements.txt

COPY akv_cachehandler.py /akv_cachehandler.py
COPY playlistbuilder.py /playlistbuilder.py

CMD ["python3", "playlistbuilder.py"]