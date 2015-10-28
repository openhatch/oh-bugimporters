FROM python:2.7

RUN apt-get update && apt-get install -y \
  libxml2-dev \
  libffi-dev \
  libssl-dev \
  python-lxml \
  python-lxml

COPY . /code
WORKDIR /code
RUN pip install -e .
RUN pip install -r devrequirements.txt
