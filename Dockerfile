FROM python:3.12-slim AS build

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

ARG MILLER_VERSION
RUN if [ -n "$MILLER_VERSION" ]; then \
      SETUPTOOLS_SCM_PRETEND_VERSION="$MILLER_VERSION" pip install --prefix=/install --no-cache-dir .[dev]; \
    else \
      pip install --prefix=/install --no-cache-dir .[dev]; \
    fi

FROM python:3.12-slim

WORKDIR /app

COPY --from=build /install /usr/local
COPY pyproject.toml README.md ./
COPY tests ./tests
COPY test_data ./test_data

ENTRYPOINT ["miller"]
