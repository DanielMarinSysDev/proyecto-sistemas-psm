#!/bin/sh

# 1. Esperar a que la base de datos esté disponible
if [ -n "$DATABASE_URL" ]; then
  echo "[INFO] Esperando a que PostgreSQL esté listo..."
  python -c "
import sys, time, sqlalchemy
from sqlalchemy import create_engine
engine = create_engine('$DATABASE_URL')
for i in range(30):
    try:
        engine.connect()
        print('[OK] Conexión establecida con PostgreSQL!')
        sys.exit(0)
    except Exception as e:
        time.sleep(1)
print('[ERROR] Tiempo de espera agotado al conectar con la base de datos.')
sys.exit(1)
"
  if [ $? -ne 0 ]; then
    exit 1
  fi
fi

# 2. Crear las tablas si no existen
echo "[INFO] Inicializando tablas de base de datos..."
python -c "from database_models import init_db; init_db()"

# 3. Sembrar datos por defecto si la base de datos está vacía
echo "[INFO] Comprobando si se requiere sembrar datos iniciales..."
python -c "
from database_models import engine, Usuario
from sqlalchemy.orm import sessionmaker
from seed import seed_users, seed_prices
Session = sessionmaker(bind=engine)
session = Session()
try:
    if session.query(Usuario).count() == 0:
        print('[INFO] Base de datos vacía detectada. Sembrando administrador y precios...')
        seed_users()
        seed_prices()
    else:
        print('[INFO] La base de datos ya está configurada con registros. Omitiendo sembrado.')
except Exception as e:
    print('[ERROR] Error al verificar/sembrar base de datos:', e)
finally:
    session.close()
"

# 4. Iniciar el servidor web
echo "[INFO] Iniciando servidor Flask..."
exec python app.py
