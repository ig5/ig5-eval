FROM python:3.6.6

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

COPY requirements/ ./requirements/
RUN \
    pip install --no-cache-dir --upgrade pip flake8 black && \
    pip install -r /code/requirements/local.txt
