# Linux/amd64 is deliberate: this is the verified KiCad/atopile toolchain.
FROM ghcr.io/astral-sh/uv:0.12.18@sha256:34532673531cdce6019c0919595b2b7f9207ed3a46dabc606d563c4c569cf82a AS uv
FROM kicad/kicad:9.0.9@sha256:cef4a572df1465b98fa63cdac88780e0f8d39f03c5493434802bcd92f62123fb
USER root
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_NO_CACHE=1
COPY requirements.lock /opt/requirements.lock
RUN uv python install 3.14.7 && uv venv --python 3.14.7 /opt/atopile \
    && uv pip sync --python /opt/atopile/bin/python --require-hashes /opt/requirements.lock
COPY install_buf.py /opt/install_buf.py
RUN python3 /opt/install_buf.py
RUN apt-get update && apt-get install -y --no-install-recommends device-tree-compiler=1.6.1-4+b1 iverilog=11.0-1.1+b1 \
    build-essential=12.9 gcc-arm-none-eabi=15:12.2.rel1-1 libnewlib-dev=3.3.0-1.3+deb12u1 \
    && rm -rf /var/lib/apt/lists/*
COPY install_skylark.py /opt/install_skylark.py
RUN /opt/atopile/bin/python /opt/install_skylark.py
COPY system-requirements.txt /opt/system-requirements.txt
RUN uv pip install --python /usr/bin/python3 --break-system-packages --require-hashes --no-deps -r /opt/system-requirements.txt
ENV HOME=/tmp/home XDG_CACHE_HOME=/tmp/cache XDG_CONFIG_HOME=/tmp/config \
    PYTHONDONTWRITEBYTECODE=1 CI=1 QT_QPA_PLATFORM=offscreen
WORKDIR /work
ENTRYPOINT ["python3", "/source/environment/lab.py"]
