# 🚀 Inicio Rápido con Docker

## Pasos para empezar

### 1. Configurar variables de entorno

```bash
# Copiar el archivo de ejemplo
cp env.example .env

# Editar con tus credenciales
# (Usa tu editor favorito: nano, vim, code, etc.)
nano .env
```

**Variables importantes a configurar:**
- `DATABASE_URL`: Ya está configurada para Docker, no cambiar
- `JWT_SECRET`: Cambia por una clave segura
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`: Tus credenciales de Twilio
- `OPENAI_API_KEY`: Tu clave de API de OpenAI
- `HOST`: Tu dominio o URL pública (para webhooks de Twilio)

### 2. Iniciar con Docker

**Opción A: Usando los scripts (recomendado)**

```bash
# En Linux/Mac, hacer ejecutables los scripts
chmod +x docker-start.sh docker-stop.sh docker-entrypoint.sh

# Iniciar
./docker-start.sh
```

**Opción B: Usando Docker Compose directamente**

```bash
# Construir e iniciar
docker-compose up -d --build

# Ver logs
docker-compose logs -f api
```

### 3. Verificar que funciona

```bash
# Verificar contenedores
docker-compose ps

# Probar el endpoint
curl http://localhost:8000/
```

Deberías ver: `{"message":"RealSolveAI Voice AI Platform is running!"}`

### 4. Inicializar la base de datos (primera vez)

```bash
# Crear superadmin
docker-compose exec api python create_superadmin.py
```

## 📝 Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f api

# Detener contenedores
docker-compose down

# Reiniciar
docker-compose restart

# Acceder al shell del contenedor
docker-compose exec api bash

# Acceder a PostgreSQL
docker-compose exec db psql -U realsolve -d realsolveai
```

## ⚠️ Notas Importantes

1. **Primera vez**: La base de datos se inicializa automáticamente al iniciar el contenedor
2. **Persistencia**: Los datos de PostgreSQL se guardan en `./postgres/data/`
3. **Logs**: Los logs están disponibles con `docker-compose logs`
4. **Reinicio**: Si cambias código, reconstruye: `docker-compose up -d --build`

## 🔧 Solución de Problemas

**Error: "PostgreSQL no está disponible"**
- Espera unos segundos más, el contenedor puede tardar en iniciar
- Verifica: `docker-compose logs db`

**Error: "Port already in use"**
- Cambia el puerto en `docker-compose.yml`: `"8001:8000"` en lugar de `"8000:8000"`

**Error: "Cannot connect to database"**
- Verifica que `DATABASE_URL` en `.env` sea: `postgresql://realsolve:superpassword@db:5432/realsolveai`
- El host debe ser `db` (nombre del servicio en docker-compose), no `localhost`

## 📚 Más Información

Consulta `README.Docker.md` para información detallada sobre:
- Configuración para VPS
- Uso de Nginx como proxy reverso
- Configuración de SSL/TLS
- Backups y seguridad

