import requests
from bs4 import BeautifulSoup
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from datetime import datetime
from database_models import engine, Configuracion
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

def get_tasa_bcv():
    ahora = datetime.now()
    hoy_str = ahora.strftime("%Y-%m-%d")
    
    session = Session()
    try:
        # Intentar leer los valores guardados en la BD
        tasa_config = session.query(Configuracion).filter_by(clave='bcv_tasa').first()
        tasa_eur_config = session.query(Configuracion).filter_by(clave='bcv_tasa_eur').first()
        fecha_config = session.query(Configuracion).filter_by(clave='bcv_fecha').first()
        
        # Si ya se consultó hoy, retornar la tasa guardada para evitar cambios a mitad del día (ej. a las 4:30pm)
        if tasa_config and fecha_config and fecha_config.valor == hoy_str:
            try:
                return float(tasa_config.valor)
            except ValueError:
                pass
                
        # Si no hay tasa o es un nuevo día, intentamos obtenerla de la web de BCV
        tasa_obtenida = None
        tasa_eur_obtenida = None
        try:
            # Petición a BCV. Usamos verify=False por problemas frecuentes en sus certificados SSL
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get('https://www.bcv.org.ve/', headers=headers, verify=False, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Buscar el div con id "dolar" y dentro el texto del strong
            dolar_div = soup.find('div', id='dolar')
            if dolar_div:
                valor_str = dolar_div.find('strong').text.strip()
                # La página usa coma para decimales. Convertirlo a formato float válido
                valor_str = valor_str.replace('.', '').replace(',', '.')
                tasa_obtenida = float(valor_str)
                
            # Buscar el div con id "euro" y dentro el texto del strong
            euro_div = soup.find('div', id='euro')
            if euro_div:
                valor_eur_str = euro_div.find('strong').text.strip()
                valor_eur_str = valor_eur_str.replace('.', '').replace(',', '.')
                tasa_eur_obtenida = float(valor_eur_str)
        except Exception as ex:
            print(f"Error raspando BCV de forma directa: {ex}")
            
        # Si pudimos obtener la nueva tasa de dólar, actualizamos la base de datos
        if tasa_obtenida is not None:
            if not tasa_config:
                tasa_config = Configuracion(clave='bcv_tasa', valor=str(tasa_obtenida))
                session.add(tasa_config)
            else:
                tasa_config.valor = str(tasa_obtenida)
                
            if tasa_eur_obtenida is not None:
                if not tasa_eur_config:
                    tasa_eur_config = Configuracion(clave='bcv_tasa_eur', valor=str(tasa_eur_obtenida))
                    session.add(tasa_eur_config)
                else:
                    tasa_eur_config.valor = str(tasa_eur_obtenida)
                    
            if not fecha_config:
                fecha_config = Configuracion(clave='bcv_fecha', valor=hoy_str)
                session.add(fecha_config)
            else:
                fecha_config.valor = hoy_str
                
            session.commit()
            return tasa_obtenida
            
        # Si falló la obtención de la tasa (ej. sin internet o caída de la web del BCV),
        # caemos en reversión (fallback) al último valor conocido que tengamos en base de datos.
        if tasa_config:
            try:
                tasa_respaldo = float(tasa_config.valor)
                print(f"[WARNING] Usando tasa BCV de respaldo ante fallo de conexión: {tasa_respaldo}")
                return tasa_respaldo
            except ValueError:
                pass
                
    except Exception as e:
        print(f"Error general en get_tasa_bcv: {e}")
    finally:
        session.close()
        
    return None

def get_tasa_eur_bcv():
    ahora = datetime.now()
    hoy_str = ahora.strftime("%Y-%m-%d")
    
    session = Session()
    try:
        tasa_eur_config = session.query(Configuracion).filter_by(clave='bcv_tasa_eur').first()
        fecha_config = session.query(Configuracion).filter_by(clave='bcv_fecha').first()
        
        # Si ya se consultó hoy y existe, retornamos el valor guardado
        if tasa_eur_config and fecha_config and fecha_config.valor == hoy_str:
            try:
                return float(tasa_eur_config.valor)
            except ValueError:
                pass
                
        # Forzar ejecución de get_tasa_bcv para actualizar ambas tasas
        get_tasa_bcv()
        
        # Re-consultar el valor actualizado de Euro
        tasa_eur_config = session.query(Configuracion).filter_by(clave='bcv_tasa_eur').first()
        if tasa_eur_config:
            return float(tasa_eur_config.valor)
            
    except Exception as e:
        print(f"Error general en get_tasa_eur_bcv: {e}")
    finally:
        session.close()
        
    return None