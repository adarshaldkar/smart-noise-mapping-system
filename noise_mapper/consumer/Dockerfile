FROM python:3.8-slim

ENV NOISEMAPPER /opt/noisemapper

RUN mkdir -p $NOISEMAPPER

COPY requirements.txt $NOISEMAPPER/requirements.txt
COPY main.py $NOISEMAPPER/main.py
COPY .env $NOISEMAPPER/.env

ENV AM_I_IN_A_DOCKER_CONTAINER Yes

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg build-essential \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir -r $NOISEMAPPER/requirements.txt

WORKDIR $NOISEMAPPER
CMD ["python", "-u", "main.py"]