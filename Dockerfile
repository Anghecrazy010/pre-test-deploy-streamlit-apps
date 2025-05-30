FROM debian:latest

WORKDIR /render

ARG TAILSCALE_VERSION
ENV TAILSCALE_VERSION=$TAILSCALE_VERSION

ENV ACCEPT_EULA=Y
ENV DEBIAN_FRONTEND=noninteractive

# Instala paquetes base
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    gcc \
    g++ \
    python3-dev \
    python3-pip \
    python3 \
    apt-transport-https \
    ca-certificates \
    netcat-openbsd \
    wget \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Agrega el repositorio de Microsoft y el driver ODBC
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && apt-get install -y msodbcsql17

# Instala dependencias Python
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Configuración adicional
RUN echo "+search +short" > /root/.digrc
COPY run-tailscale.sh /render/
COPY install-tailscale.sh /tmp
RUN /tmp/install-tailscale.sh && rm -r /tmp/*

CMD ./run-tailscale.sh
