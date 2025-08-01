# WhatsApp API - Productos Disponibles

API simple para consultar productos disponibles.

## Instalación

1. Crear entorno virtual:
```bash
python -m venv venv
```

2. Activar entorno virtual:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

## Ejecutar

```bash
python app.py
```

La API estará en: http://localhost:5000

## Endpoints

- `GET /` - Información de la API
- `GET /productos/disponibles` - Productos disponibles
- `GET /productos/buscar/<query>` - Buscar productos por nombre 