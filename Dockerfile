FROM python:3.8.9

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.

RUN mkdir --parents /app
WORKDIR /app

RUN python3.8 -m pip install --upgrade \
        poetry==1.1.6
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-root --no-interaction --verbose

COPY . .

ENTRYPOINT ["poetry", "run"]
CMD ["python", "--version"]
