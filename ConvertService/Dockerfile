FROM python:3.12-slim
LABEL authors="nws"

ENV PYTHONUNBUFFERED=1
ENV LANG=ja_JP.UTF-8
ENV LC_ALL=ja_JP.UTF-8

RUN mkdir -p /home/ConvertService
WORKDIR /home/ConvertService

ADD requirements.txt /home/ConvertService

RUN apt-get update \
    && apt-get install -y gettext locales libpq-dev task-japanese gcc git procps \
    && echo "ja_JP.UTF-8 UTF-8" >> /etc/locale.gen \
    && locale-gen ja_JP.UTF-8 \
    && update-locale LANG=ja_JP.UTF-8 \
    && pip3 install --upgrade pip \
    && pip3 install -r requirements.txt \
    && apt-get purge -y --autoremove gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8000
