#!/bin/bash

# Script de entrada para el contenedor Docker
set -e

echo "🐳 Iniciando El Gringo Auto Taller API en Docker..."

# Verificar variables de entorno críticas
if [ -z "$GCS_BUCKET_NAME" ] || [ -z "$GOOGLE_CLOUD_PROJECT_ID" ]; then
    echo "❌ ERROR: Variables de entorno requeridas no configuradas:"
    echo "   - GCS_BUCKET_NAME: $GCS_BUCKET_NAME"
    echo "   - GOOGLE_CLOUD_PROJECT_ID: $GOOGLE_CLOUD_PROJECT_ID"
    echo ""
    echo "🔧 SOLUCIÓN: Configurar variables al ejecutar el contenedor:"
    echo "   docker run -e GCS_BUCKET_NAME=tu-bucket -e GOOGLE_CLOUD_PROJECT_ID=tu-project ..."
    exit 1
fi

# Verificar credenciales de Google Cloud
echo "🔑 Verificando credenciales de Google Cloud..."

if [ ! -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    if [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        echo "✅ Usando credenciales desde: $GOOGLE_APPLICATION_CREDENTIALS"
    else
        echo "❌ ERROR: Archivo de credenciales no encontrado: $GOOGLE_APPLICATION_CREDENTIALS"
        exit 1
    fi
elif [ -f "/app/credentials/service-account-key.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="/app/credentials/service-account-key.json"
    echo "✅ Usando credenciales desde: /app/credentials/service-account-key.json"
else
    echo "⚠️  ADVERTENCIA: No se encontraron credenciales específicas."
    echo "   El contenedor intentará usar las credenciales por defecto."
    echo "   Esto puede funcionar en Google Cloud Run o GKE con identidades de servicio."
fi

# Verificar conectividad con Google Cloud Storage (opcional)
if command -v gsutil >/dev/null 2>&1; then
    echo "🧪 Verificando conectividad con Google Cloud Storage..."
    if gsutil ls "gs://$GCS_BUCKET_NAME" >/dev/null 2>&1; then
        echo "✅ Conectividad con bucket verificada"
    else
        echo "⚠️  No se pudo verificar conectividad con el bucket (puede ser normal)"
    fi
fi

# Configurar variables de entorno por defecto
export ENVIRONMENT=${ENVIRONMENT:-production}
export DEBUG=${DEBUG:-false}

echo "📊 Configuración del contenedor:"
echo "   - Proyecto: $GOOGLE_CLOUD_PROJECT_ID"
echo "   - Bucket: $GCS_BUCKET_NAME"
echo "   - Entorno: $ENVIRONMENT"
echo "   - Debug: $DEBUG"
echo "   - Email configurado: $([ ! -z "$EMAIL_USER" ] && echo "✅" || echo "❌")"

echo "🚀 Iniciando servidor..."

# Ejecutar el comando pasado como argumentos
exec "$@"
