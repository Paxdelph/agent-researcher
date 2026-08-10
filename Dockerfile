FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    pandoc \
    chromium \
    fonts-liberation \
    fonts-dejavu-core \
    r-base \
    r-base-dev \
    pkg-config \
    cmake \
    libuv1-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libfontconfig1-dev \
    libfreetype6-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    libicu-dev \
    zlib1g-dev \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

ARG QUARTO_VERSION=1.6.40
RUN curl -fsSL -o /tmp/quarto.deb \
      "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.deb" \
    && dpkg -i /tmp/quarto.deb \
    && rm -f /tmp/quarto.deb \
    && quarto --version

# Knit stack + analytics/plotly (fs needs libuv1-dev above)
COPY docker/install_r_packages.R /tmp/install_r_packages.R
RUN Rscript /tmp/install_r_packages.R && rm -f /tmp/install_r_packages.R

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY quarto ./quarto
COPY config.example.yaml ./config.yaml

RUN pip install --upgrade pip \
    && pip install -e .

RUN mkdir -p /workspace /app-state

EXPOSE 8787

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
