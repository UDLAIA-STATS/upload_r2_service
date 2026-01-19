# Video Upload Service

Un servicio de subida de videos desarrollado en Django que permite la carga eficiente de videos a Cloudflare R2 con seguimiento de progreso en tiempo real y análisis automático posterior.

## 🚀 Tecnologías Utilizadas

### Backend
- **Django 5.2.8**: Framework web principal
- **Django REST Framework 3.16.1**: Para crear APIs REST
- **Python 3.13+**: Lenguaje de programación
- **SQLite**: Base de datos (desarrollo)
- **Boto3**: Cliente AWS/S3 compatible para interacción con Cloudflare R2
- **HTTPx**: Cliente HTTP asíncrono moderno
- **Pillow**: Procesamiento de imágenes
- **Tenacity**: Biblioteca para reintentos con backoff exponencial

### Servicios Externos
- **Cloudflare R2**: Almacenamiento de objetos compatible con S3
- **Cloudflare Workers**: Workers para generar URLs de subida presignadas
- **Servicio de Análisis**: Microservicio externo para procesamiento de videos

### Herramientas de Desarrollo
- **python-decouple**: Gestión de configuraciones y variables de entorno
- **django-cors-headers**: Manejo de CORS para integraciones frontend
- **UV**: Gestor de dependencias y entornos virtuales moderno

## 📋 Funcionalidades Principales

### 1. Generación de Claves Únicas
- Genera identificadores únicos para cada video antes de la subida
- Formato: `{UUID}_{nombre_archivo}`
- Previene colisiones y facilita el seguimiento

### 2. Subida de Videos con Progreso
- Subida eficiente por chunks de 5MB
- Notificaciones de progreso en tiempo real
- Soporte para archivos grandes (hasta 5GB)
- Validación de formatos (MP4, MOV, MKV, AVI)
- Reintentos automáticos con backoff exponencial

### 3. Integración con Cloudflare R2
- Utiliza URLs de subida presignadas para seguridad
- Subida directa sin pasar por el servidor Django
- Optimización de ancho de banda del servidor

### 4. Análisis Automático
- Dispara automáticamente el análisis del video tras la subida
- Integración con servicio de análisis externo
- Manejo de errores y reintentos

### 5. Gestión de Estados
- Seguimiento del estado del video: `uploaded`, `processing`, `ready`, `failed`
- Almacenamiento de metadatos del video
- Registro detallado de eventos

## 🏗️ Estructura del Proyecto

```
video_upload_service/
├── video_upload/                 # Configuración principal del proyecto Django
│   ├── __init__.py
│   ├── settings.py              # Configuraciones del proyecto
│   ├── urls.py                  # URLs principales
│   ├── wsgi.py                  # Punto de entrada WSGI
│   └── asgi.py                  # Punto de entrada ASGI
├── upload_service/               # Aplicación principal de subida
│   ├── models.py                # Modelo Video con metadatos
│   ├── views.py                 # Vistas API: generación de claves y subida
│   ├── serializers.py           # Validación de datos de entrada
│   ├── service.py               # Lógica de subida y progreso
│   ├── urls.py                  # URLs de la aplicación
│   ├── utils/                   # Utilidades
│   │   ├── responses.py         # Funciones de respuesta HTTP
│   │   └── format_serializer.py # Formateo de errores
│   └── migrations/              # Migraciones de base de datos
├── manage.py                     # Script de gestión Django
├── requirements.txt             # Dependencias (generado por UV)
├── pyproject.toml               # Configuración del proyecto y dependencias
├── settings.ini                 # Variables de configuración
├── db.sqlite3                   # Base de datos SQLite
└── README.md                    # Documentación
```

### Descripción de Componentes

#### `models.py`
- **Video**: Modelo principal que almacena metadatos del video
  - Información del archivo (nombre, tamaño, extensión, MIME type)
  - Metadatos de video (duración, resolución, bitrate)
  - Estado del procesamiento
  - Identificadores únicos (UUID, clave de archivo)

#### `views.py`
- **VideoKeyGenerate**: Genera claves únicas para videos
- **CloudflareVideoUpload**: Maneja la subida con validación y progreso

#### `service.py`
- Lógica asíncrona de subida con chunks
- Notificaciones de progreso
- Integración con Workers de Cloudflare
- Disparador de análisis automático

#### `serializers.py`
- Validación de archivos de video
- Validación de parámetros de entrada
- Límites de tamaño y formato

## 🔧 Instalación y Configuración

### Prerequisitos
- Python 3.13+
- UV (gestor de dependencias)

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd video_upload_service
```

### 2. Instalar dependencias
```bash
uv sync
```

### 3. Configurar variables de entorno
Edita `settings.ini` con tus valores:
```ini
[settings]
DEBUG=True
WORKER_URL=https://tu-worker.workers.dev
VIDEO_UPLOAD_NOTIFY_URL=http://localhost:8060/api
ANALISYS_SERVICE_URL=http://127.0.0.1:6070
```

### 4. Realizar migraciones
```bash
python manage.py migrate
```

### 5. Ejecutar el servidor
```bash
python manage.py runserver
```

El servicio estará disponible en el host en `http://localhost:8050` (mapeado al puerto interno `8000` dentro del contenedor Docker).

## 📡 API Endpoints

### 1. Generar Clave de Video
```http
POST /api/generate-key/
Content-Type: application/json

{
    "video_name": "mi_video.mp4"
}
```

**Respuesta:**
```json
{
    "video_key": "123e4567-e89b-12d3-a456-426614174000_mi_video.mp4"
}
```

### 2. Subir Video
```http
POST /api/upload/
Content-Type: multipart/form-data

video: [archivo]
video_key: "123e4567-e89b-12d3-a456-426614174000_mi_video.mp4"
id_partido: 123
```

**Respuesta exitosa:**
```json
{
    "key": "123e4567-e89b-12d3-a456-426614174000_mi_video.mp4",
    "message": "Video subido correctamente. El análisis comenzará automáticamente."
}
```

## 🔄 Flujo de Trabajo

1. **Generación de Clave**: El cliente solicita una clave única para el video
2. **Validación**: Se valida el archivo (formato, tamaño, tipo MIME)
3. **Obtención de URL**: Se solicita una URL de subida presignada al Worker
4. **Subida por Chunks**: El archivo se sube en chunks de 5MB con progreso
5. **Notificaciones**: Se envían notificaciones de progreso a un servicio externo
6. **Análisis**: Se dispara automáticamente el análisis del video
7. **Finalización**: Se actualiza el estado y se notifica la finalización

## 🧪 Testing

### Ejecutar pruebas
```bash
python manage.py test
```

### Ejemplo de uso con cURL
```bash
# Generar clave
curl -X POST http://localhost:8050/api/generate-key/ \
  -H "Content-Type: application/json" \
  -d '{"video_name": "test_video.mp4"}'

# Subir video
curl -X POST http://localhost:8050/api/upload/ \
  -F "video=@/path/to/video.mp4" \
  -F "video_key=generated_key_here" \
  -F "id_partido=123"
```

## 📝 Validaciones y Restricciones

- **Formatos permitidos**: MP4, MOV, MKV, AVI
- **Tamaño máximo**: 5GB
- **Tipo MIME**: Debe comenzar con `video/`
- **ID de partido**: Debe ser mayor a 0
- **Clave de video**: Campo obligatorio y único

## 🔒 Seguridad

- URLs de subida presignadas con expiración
- Validación exhaustiva de archivos
- CORS configurado para integraciones seguras
- Logging detallado para auditoría
- Manejo seguro de errores sin exposición de información sensible

## 🚀 Despliegue en Producción

1. Configurar `DEBUG=False` en `settings.ini`
2. Configurar base de datos PostgreSQL o MySQL
3. Configurar servidor web (Nginx + Gunicorn)
4. Configurar variables de entorno de servicios externos
5. Configurar SSL/TLS para HTTPS
6. Implementar monitoreo y logging centralizado

## 🤝 Contribución

1. Fork el proyecto
2. Crear una rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit los cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear un Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia especificada en el archivo LICENSE.
