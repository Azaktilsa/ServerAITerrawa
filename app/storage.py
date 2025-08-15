from google.cloud import storage
import os
import json
import logging
from dotenv import load_dotenv
from typing import Dict, List

load_dotenv()

# Al inicio del archivo
client = None
bucket = None


def init_storage():
    global client, bucket

    if client and bucket:
        return  # Ya está inicializado

    BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")

    if not BUCKET_NAME or not PROJECT_ID:
        raise ValueError("Variables de entorno necesarias no configuradas")

    try:
        credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_file and os.path.exists(credentials_file):
            logger.info(f"🔑 Usando credenciales desde: {credentials_file}")

        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)

        bucket.exists()
        logger.info(f"✅ Conectado exitosamente a bucket: {BUCKET_NAME}")

    except Exception as e:
        logger.error(f"❌ Error conectando a GCS: {e}")
        raise Exception(f"Error de configuración de GCS: {str(e)}")


# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")

# Validación de variables de entorno críticas
if not BUCKET_NAME or not PROJECT_ID:
    raise ValueError(
        "Variables de entorno GCS_BUCKET_NAME y "
        "GOOGLE_CLOUD_PROJECT_ID son requeridas"
    )

# Intentar conectar con Google Cloud Storage con mejor manejo de errores
try:
    # Verificar si hay credenciales específicas en el archivo
    credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_file and os.path.exists(credentials_file):
        logger.info(f"🔑 Usando credenciales desde: {credentials_file}")

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)

    # Test de conectividad
    bucket.exists()
    logger.info(f"✅ Conectado exitosamente a bucket: {BUCKET_NAME}")

except Exception as e:
    error_msg = str(e)
    logger.error(f"❌ Error conectando a Google Cloud Storage: {error_msg}")

    # Proporcionar instrucciones específicas según el tipo de error
    if ("DefaultCredentialsError" in error_msg or
            "credentials were not found" in error_msg):
        logger.error("🔧 SOLUCIÓN: Configurar credenciales de Google Cloud:")
        logger.error("   Opción 1: gcloud auth application-default login")
        logger.error("   Opción 2: Configurar GOOGLE_APPLICATION_CREDENTIALS")
        logger.error("   Opción 3: Usar service account key file")
    elif "does not exist" in error_msg:
        logger.error(
            f"🔧 SOLUCIÓN: Verificar que el bucket '{BUCKET_NAME}' existe"
        )
        logger.error(f"   Crear bucket: gsutil mb gs://{BUCKET_NAME}")
    elif "Access Denied" in error_msg:
        logger.error("🔧 SOLUCIÓN: Verificar permisos del bucket")
        logger.error("   El usuario debe tener permisos de Storage Admin")

    raise Exception(
        f"Error de configuración de Google Cloud Storage: {error_msg}"
    )


def read_json_file(filename: str) -> Dict:
    """
    Lee un archivo JSON desde Google Cloud Storage.

    Args:
        filename: Nombre del archivo a leer

    Returns:
        Dict con el contenido del archivo o {} si no existe

    Raises:
        Exception: Si hay error en la lectura del archivo
    """
    try:
        if not filename.endswith('.json'):
            filename += '.json'

        blob = bucket.blob(filename)

        if not blob.exists():
            logger.info(
                f"📄 Archivo {filename} no existe, creando estructura vacía"
            )
            return {}

        content = blob.download_as_text()
        data = json.loads(content)
        logger.info(f"✅ Archivo {filename} leído exitosamente")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"❌ Error decodificando JSON en {filename}: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Error leyendo archivo {filename}: {e}")
        raise Exception(f"Error leyendo archivo {filename}: {str(e)}")


def write_json_file(filename: str, data: Dict) -> bool:
    """
    Escribe un archivo JSON a Google Cloud Storage.

    Args:
        filename: Nombre del archivo a escribir
        data: Datos a escribir en formato dict

    Returns:
        bool: True si se escribió exitosamente

    Raises:
        Exception: Si hay error en la escritura
    """
    try:
        if not filename.endswith('.json'):
            filename += '.json'

        blob = bucket.blob(filename)
        json_string = json.dumps(data, indent=2, ensure_ascii=False)

        blob.upload_from_string(
            json_string,
            content_type="application/json; charset=utf-8"
        )

        logger.info(f"✅ Archivo {filename} guardado exitosamente")
        return True

    except Exception as e:
        logger.error(f"❌ Error escribiendo archivo {filename}: {e}")
        raise Exception(f"Error escribiendo archivo {filename}: {str(e)}")


def list_all_files() -> List[str]:
    """
    Lista todos los archivos en el bucket.

    Returns:
        List[str]: Lista de nombres de archivos
    """
    try:
        init_storage()
        files = [blob.name for blob in bucket.list_blobs()]
        logger.info(f"📋 Listados {len(files)} archivos en el bucket")
        return files
    except Exception as e:
        logger.error(f"❌ Error listando archivos: {e}")
        return []


def file_exists(filename: str) -> bool:
    """
    Verifica si un archivo existe en el bucket.

    Args:
        filename: Nombre del archivo a verificar

    Returns:
        bool: True si existe, False si no
    """
    try:
        if not filename.endswith('.json'):
            filename += '.json'
        blob = bucket.blob(filename)
        exists = blob.exists()
        status = 'existe' if exists else 'no existe'
        logger.info(f"🔍 Archivo {filename} {status}")
        return exists
    except Exception as e:
        logger.error(f"❌ Error verificando existencia de {filename}: {e}")
        return False


def delete_file(filename: str) -> bool:
    """
    Elimina un archivo del bucket.

    Args:
        filename: Nombre del archivo a eliminar

    Returns:
        bool: True si se eliminó exitosamente
    """
    try:
        if not filename.endswith('.json'):
            filename += '.json'

        blob = bucket.blob(filename)

        if not blob.exists():
            logger.warning(f"⚠️ Archivo {filename} no existe para eliminar")
            return False

        blob.delete()
        logger.info(f"🗑️ Archivo {filename} eliminado exitosamente")
        return True

    except Exception as e:
        logger.error(f"❌ Error eliminando archivo {filename}: {e}")
        return False
