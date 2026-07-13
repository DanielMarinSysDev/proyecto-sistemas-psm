FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para psycopg2 y utilidades
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Dar permisos de ejecución al script de entrada y convertir finales de línea si es necesario
RUN chmod +x entrypoint.sh

EXPOSE 5000

# Usar el script de entrada automatizado
ENTRYPOINT ["/bin/sh", "entrypoint.sh"]
