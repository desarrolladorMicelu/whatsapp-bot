import requests
from flask import Flask, jsonify
import functools
import time
import logging
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cache configuration
CACHE_DURATION = 300  # 5 minutes cache
cache = {}

def get_estado_texto(codigo_estado):
    """Convierte código de estado a texto descriptivo"""
    mapeo_estados = {
        'NU': 'Nuevo',
        'AA': 'Como nuevo', 
        'A': 'Seminuevo',
        'B': 'Usado',
        'C': 'Gangazo'
    }
    
    codigo_limpio = codigo_estado.strip().upper()
    return mapeo_estados.get(codigo_limpio, codigo_limpio)

def get_bodega_texto(codigo_bodega):
    """Convierte código de bodega a texto descriptivo"""
    mapeo_bodegas = {
        'BM': 'Medellin',
        'BB': 'Bogota',
        'TM': 'Tienda Medellin',
        'TB': 'Tienda Bogota'
    }
    
    codigo_limpio = codigo_bodega.strip().upper()
    return mapeo_bodegas.get(codigo_limpio, None)

def cache_with_timeout(timeout):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            # Check if we have a valid cached response
            if f.__name__ in cache:
                result, timestamp = cache[f.__name__]
                if current_time - timestamp < timeout:
                    return result
            
            # Get fresh data
            result = f(*args, **kwargs)
            cache[f.__name__] = (result, current_time)
            return result
        return wrapper
    return decorator

def get_products():
    """Fetch products from external API"""
    url = "http://20.109.21.246:8080/producto/listado"
    params = {"userKey": "B91C9AA92D0A457593B0805BD3FB94BF"}
    try:
        logger.debug(f"Haciendo petición a: {url}")
        response = requests.get(url, params=params)
        logger.debug(f"Status code: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Productos recibidos: {len(data.get('listado', []))}")
        return data.get("listado", [])
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        return []

def filter_products(products):
    """Filter products based on conditions"""
    logger.debug(f"Filtrando {len(products)} productos")
    
    filtered = []
    for product in products:
        # Verificar que esté en una de las bodegas permitidas
        bodega_texto = get_bodega_texto(product["BODEGA"])
        
        # Solo incluir si la bodega está en la lista permitida
        if (bodega_texto and  # bodega_texto no es None
            product["SALDO"] == 1 and 
            product["COLOR"].upper() != "N/A" and 
            product["ESTADO"].upper() in ["A", "AA", "NU", "B", "C"] and
            product["Precio"] != 0):
            
            filtered.append({
                "codigo": product["CODIGO"],
                "precio": product["Precio"],
                "color": product["COLOR"],
                "estado": get_estado_texto(product["ESTADO"]),
                "nombre": product["NOMBRE"],
                "bodega": bodega_texto
            })
    
    logger.debug(f"Productos filtrados: {len(filtered)}")
    return filtered

def buscar_urls_micelu(nombre_producto):
    """Busca URLs específicas de productos en micelu.co"""
    try:
        logger.debug(f"Buscando URLs para: {nombre_producto}")
        
        # Construir URL de búsqueda
        search_query = quote_plus(nombre_producto)
        search_url = f"https://micelu.co/?s={search_query}&e_search_props=51a8e97-78"
        
        # Hacer petición a micelu.co
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parsear HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscar enlaces de productos (ajustar selectores según la estructura real)
        productos_encontrados = []
        
        # Buscar enlaces que contengan "/producto/" en el href
        enlaces_productos = soup.find_all('a', href=lambda href: href and '/producto/' in href)
        
        for enlace in enlaces_productos:
            href = enlace.get('href')
            
            # Asegurar URL completa
            if href.startswith('/'):
                url_completa = f"https://micelu.co{href}"
            elif not href.startswith('http'):
                url_completa = f"https://micelu.co/{href}"
            else:
                url_completa = href
            
            # Intentar obtener el título del producto
            titulo = ""
            
            # Buscar título en diferentes elementos
            img = enlace.find('img')
            if img and img.get('alt'):
                titulo = img.get('alt').strip()
            elif enlace.get_text().strip():
                titulo = enlace.get_text().strip()
            elif enlace.get('title'):
                titulo = enlace.get('title').strip()
            
            # Solo agregar si tiene título y no es duplicado
            if titulo and url_completa not in [p['url'] for p in productos_encontrados]:
                productos_encontrados.append({
                    'titulo': titulo,
                    'url': url_completa
                })
        
        logger.debug(f"URLs encontradas: {len(productos_encontrados)}")
        
        return {
            'productos_web': productos_encontrados,
            'total_encontrados': len(productos_encontrados),
            'url_busqueda': search_url
        }
        
    except Exception as e:
        logger.error(f"Error buscando URLs en micelu.co: {str(e)}")
        return {
            'productos_web': [],
            'total_encontrados': 0,
            'error': str(e),
            'url_busqueda': search_url if 'search_url' in locals() else None
        }

@app.route('/')
def home():
    """Home endpoint"""
    return jsonify({
        "message": "WhatsApp API - Productos Disponibles",
        "endpoints": {
            "productos_disponibles": "/productos/disponibles",
            "buscar_productos": "/productos/buscar/<query>",
            "buscar_urls": "/productos/urls/<query>"
        }
    })

@app.route('/productos/disponibles', methods=['GET'])
@cache_with_timeout(CACHE_DURATION)
def get_available_products():
    """Get all available products that meet the criteria"""
    logger.debug("Iniciando búsqueda de productos disponibles")
    products = get_products()
    logger.debug(f"Total de productos obtenidos: {len(products)}")
    filtered_products = filter_products(products)
    logger.debug(f"Productos filtrados: {len(filtered_products)}")
    return jsonify({
        "status": "success",
        "count": len(filtered_products),
        "productos": filtered_products
    })

@app.route('/productos/buscar/<string:query>', methods=['GET'])
def search_products(query):
    """Search products by name"""
    logger.debug(f"Buscando productos con query: {query}")
    products = get_products()
    logger.debug(f"Total de productos obtenidos: {len(products)}")
    filtered_products = filter_products(products)
    logger.debug(f"Productos después del primer filtro: {len(filtered_products)}")
    
    # Search in filtered products
    search_results = [
        product for product in filtered_products
        if query.lower() in product["nombre"].lower()
    ]
    logger.debug(f"Productos encontrados con la búsqueda: {len(search_results)}")
    
    return jsonify({
        "status": "success",
        "count": len(search_results),
        "productos": search_results
    })

@app.route('/productos/urls/<string:query>', methods=['GET'])
def search_product_urls(query):
    """Buscar URLs específicas de productos en micelu.co"""
    logger.debug(f"Buscando URLs para: {query}")
    
    # Buscar URLs en micelu.co
    urls_data = buscar_urls_micelu(query)
    
    return jsonify({
        "status": "success",
        "query": query,
        "urls_encontradas": urls_data['productos_web'],
        "total_urls": urls_data['total_encontrados'],
        "url_busqueda_general": urls_data['url_busqueda'],
        "error": urls_data.get('error', None)
    })

@app.route('/productos/completo/<string:query>', methods=['GET'])
def search_products_complete(query):
    """Buscar productos en API + URLs en web (todo en uno)"""
    logger.debug(f"Búsqueda completa para: {query}")
    
    # 1. Buscar en API interna
    products = get_products()
    filtered_products = filter_products(products)
    search_results = [
        product for product in filtered_products
        if query.lower() in product["nombre"].lower()
    ]
    
    # 2. Buscar URLs en micelu.co
    urls_data = buscar_urls_micelu(query)
    
    return jsonify({
        "status": "success",
        "query": query,
        "productos_api": {
            "count": len(search_results),
            "productos": search_results
        },
        "productos_web": {
            "urls_encontradas": urls_data['productos_web'],
            "total_urls": urls_data['total_encontrados'],
            "url_busqueda_general": urls_data['url_busqueda']
        },
        "error_web": urls_data.get('error', None)
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)