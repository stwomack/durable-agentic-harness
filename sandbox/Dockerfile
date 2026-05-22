FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Build deps for TA-Lib (C library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential wget tar && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library.
# The 0.4.0 tarball ships a 2006-era config.guess that can't recognize aarch64,
# so we pass --build explicitly to skip autodetect (works on amd64 and arm64).
RUN wget -q https://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr --build=$(uname -m)-unknown-linux-gnu \
    && make \
    && make install \
    && cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Python deps for backtests
RUN pip install --upgrade pip && pip install \
    numpy==1.26.4 \
    pandas==2.2.2 \
    pyarrow==17.0.0 \
    ta-lib==0.4.32 \
    yfinance==0.2.40

WORKDIR /work
COPY runner.py /work/runner.py

# Sandbox is launched with the user-supplied entrypoint by the host;
# default holds the container open if no command is given (so we can `docker exec`).
CMD ["python", "-c", "import time; time.sleep(3600)"]
