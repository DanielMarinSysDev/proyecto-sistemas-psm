from database_models import engine
from sqlalchemy.orm import sessionmaker
from routes_precios import calcular_precio_interno

Session = sessionmaker(bind=engine)
session = Session()

data = {
    "tipo_trabajo": "Impresión",
    "material": "Vinil Brillante",
    "medida_ancho": 10,
    "medida_alto": 10,
    "medida_unidad": "cm",
    "cantidad": 10,
    "laminado": True,
    "instalacion_pvc": True,
    "grosor_pvc": "3mm"
}

res = calcular_precio_interno(session, data)
print(res)
session.close()
