# 🐳 Guía de Docker para RealSolveAI Backend

Esta guía te ayudará a configurar y ejecutar el backend de RealSolveAI usando Docker.

## 📋 Requisitos Previos

- Docker instalado (versión 20.10 o superior)
- Docker Compose instalado (versión 1.29 o superior)
- Git (para clonar el repositorio)

## 🚀 Configuración Inicial

### 1. Configurar Variables de Entorno

Copia el archivo de ejemplo y configura tus variables:

```bash
cp env.example .env
```

Edita el archivo `.env` con tus credenciales reales.

### 2. Desarrollo vs Producción

#### Desarrollo (Local)

```bash
# Usa docker-compose.yml (datos en ./postgres/data/)
docker compose up -d --build
```

**Características:**
- Los datos se guardan en `./postgres/data/` (fácil acceso y backup)
- Ideal para desarrollo y pruebas locales

#### Producción (VPS)

```bash
# Usa docker-compose.prod.yml (volumen nombrado de Docker)
docker compose -f docker-compose.prod.yml up -d --build
```

**Características:**
- Los datos se guardan en un volumen nombrado de Docker
- Mejor rendimiento y gestión
- Los datos no están en el directorio del proyecto

## 📦 Estructura de Contenedores

- **api-realsolve**: Contenedor de la aplicación FastAPI
- **postgres-realsolve**: Contenedor de PostgreSQL

## 🔧 Comandos Útiles

### Gestión de Contenedores

```bash
# Desarrollo
docker compose up -d
docker compose down

# Producción
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml down
```

### Backup de Base de Datos

#### Desarrollo (datos en ./postgres/data/)
```bash
# Los datos ya están en ./postgres/data/, solo copia el directorio
tar -czf backup-$(date +%Y%m%d).tar.gz postgres/data/
```

#### Producción (volumen nombrado)
```bash
# Crear backup desde el volumen
docker compose -f docker-compose.prod.yml exec db pg_dump -U postgres realsolveai > backup.sql

# O hacer backup del volumen completo
docker run --rm -v postgres-realsolve_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/backup-$(date +%Y%m%d).tar.gz /data
```

### Restaurar Base de Datos

```bash
# Desde un archivo SQL
docker compose exec db psql -U postgres -d realsolveai < backup.sql
```

## 📁 Estructura de Directorios

### Desarrollo
```
realsolve-back/
├── postgres/
│   └── data/          # Datos de PostgreSQL (en .gitignore)
├── docker-compose.yml
└── ...
```

### Producción
```
realsolve-back/
├── docker-compose.prod.yml
└── ...
# Los datos están en un volumen de Docker, no en el proyecto
```

## 🔒 Seguridad en Producción

1. **Cambiar credenciales por defecto:**
   ```env
   POSTGRES_USER=tu_usuario_seguro
   POSTGRES_PASSWORD=tu_contraseña_muy_segura
   ```

2. **No exponer el puerto de PostgreSQL:**
   En producción, considera remover o comentar:
   ```yaml
   # ports:
   #   - "5432:5432"  # Solo para acceso local, no necesario en producción
   ```

3. **Usar variables de entorno seguras:**
   - No subir `.env` a Git
   - Usar secretos de Docker o variables de entorno del sistema

## 🌐 Despliegue en VPS

### Opción 1: Usar docker-compose.prod.yml (Recomendado)

```bash
# En el VPS
git clone tu-repositorio
cd realsolve-back
cp env.example .env
# Editar .env con credenciales de producción
docker compose -f docker-compose.prod.yml up -d --build
```

### Opción 2: Modificar docker-compose.yml

Si prefieres usar el mismo archivo, cambia el volumen:

```yaml
volumes:
  # Cambiar de:
  - ./postgres/data:/var/lib/postgresql/data
  # A:
  - postgres_data:/var/lib/postgresql/data

# Y agregar al final:
volumes:
  postgres_data:
    driver: local
```

## 📝 Notas Importantes

- **Desarrollo:** `./postgres/data/` se crea automáticamente y está en `.gitignore`
- **Producción:** Usa volumen nombrado para mejor rendimiento y gestión
- **Backup:** En desarrollo, copia `postgres/data/`. En producción, usa `pg_dump` o backup del volumen
- **Migración:** Si cambias de desarrollo a producción, exporta/importa los datos

## 🐛 Solución de Problemas

### El directorio postgres/data/ ocupa mucho espacio

```bash
# Ver tamaño
du -sh postgres/data/

# Limpiar (⚠️ elimina todos los datos)
docker compose down -v
rm -rf postgres/data/
```

### Migrar de desarrollo a producción

```bash
# 1. Exportar datos
docker compose exec db pg_dump -U postgres realsolveai > backup.sql

# 2. Detener desarrollo
docker compose down

# 3. Iniciar producción
docker compose -f docker-compose.prod.yml up -d

# 4. Importar datos
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d realsolveai < backup.sql
```
