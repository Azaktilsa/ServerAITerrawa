import numpy as np
import joblib
from dotenv import load_dotenv
from decouple import config
import warnings
import requests
from google.cloud import storage
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app.routes import router as main_router
from app.stats import stats_manager

warnings.filterwarnings(
    "ignore", message="Skipping variable loading for optimizer")

app = FastAPI(
    title="Azaktilza S.A",
    description="Sistema CRUD con Google Cloud Storage para "
                "Alimentación del camarón",
    version="1.0.0"
)

load_dotenv()
# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambia por dominio real en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Motor de plantillas
templates = Jinja2Templates(directory="templates")

# Rutas de los archivos (modelo y scaler por finca)
modelos = {
    'CAMANOVILLO': {
        'modelo': config('MODELO_PATH_CAMANOVILLO'),
        'scaler': config('SCALER_PATH_CAMANOVILLO')
    },
    'EXCANCRIGRU': {
        'modelo': config('MODELO_PATH_EXCANCRIGRU'),
        'scaler': config('SCALER_PATH_EXCANCRIGRU')
    },
    'FERTIAGRO': {
        'modelo': config('MODELO_PATH_FERTIAGRO'),
        'scaler': config('SCALER_PATH_FERTIAGRO')
    },
    'GROVITAL': {
        'modelo': config('MODELO_PATH_GROVITAL'),
        'scaler': config('SCALER_PATH_GROVITAL')
    },
    'SUFAAZA': {
        'modelo': config('MODELO_PATH_SUFAAZA'),
        'scaler': config('SCALER_PATH_SUFAAZA')
    },
    'TIERRAVID': {
        'modelo': config('MODELO_PATH_TIERRAVID'),
        'scaler': config('SCALER_PATH_TIERRAVID')
    }
}

rendimiento_path = config("RENDIMIENTO_PATH")

# Descargar el JSON de rendimiento desde la URL
response = requests.get(rendimiento_path)

# Verificar si la solicitud fue exitosa
if response.status_code == 200:
    try:
        rendimiento_data = response.json()
    except requests.exceptions.JSONDecodeError:
        print("Error al decodificar el JSON, contenido de la respuesta:")
        print(response.text)  # Imprimir el contenido para ver qué se recibió
else:
    print(f"Error al descargar el archivo: {response.status_code}")
    print(response.text)  # Imprimir el mensaje de error

# Convertir a un diccionario de búsqueda
rendimiento_dict = {int(row["Gramos"]): int(row["Rendimiento"])
                    for row in rendimiento_data["rows"]}


# Modelos de datos para FastAPI
class PredictionRequest(BaseModel):
    finca: str
    AnimalesM: float
    Hectareas: float
    Piscinas: int


def obtener_rendimiento(gramos_predicho):
    return rendimiento_dict.get(gramos_predicho, rendimiento_dict[
        min(rendimiento_dict.keys(), key=lambda x: abs(x - gramos_predicho))])


def descargar_modelo(bucket_name, source_blob_name, destination_file_name):
    # Crear el cliente de Google Cloud Storage
    storage_client = storage.Client()

    # Referenciar el bucket
    bucket = storage_client.bucket(bucket_name)

    # Referenciar el blob (archivo dentro del bucket)
    blob = bucket.blob(source_blob_name)

    # Descargar el archivo al sistema local temporalmente
    blob.download_to_filename(destination_file_name)


def cargar_modelo_y_scaler(finca):
    modelo_path = modelos[finca]['modelo']
    scaler_path = modelos[finca]['scaler']

    modelo_bucket_name, modelo_blob_name = modelo_path.replace(
        "gs://", "").split("/", 1)
    scaler_bucket_name, scaler_blob_name = scaler_path.replace(
        "gs://", "").split("/", 1)

    modelo_local = f"/tmp/{finca}_modelo.pkl"
    scaler_local = f"/tmp/{finca}_scaler.pkl"

    descargar_modelo(modelo_bucket_name, modelo_blob_name, modelo_local)
    descargar_modelo(scaler_bucket_name, scaler_blob_name, scaler_local)

    best_model = joblib.load(modelo_local)
    scaler = joblib.load(scaler_local)

    return best_model, scaler


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/stats")
async def get_stats():
    """Endpoint para obtener estadísticas de la aplicación"""
    return stats_manager.get_all_stats()


@app.post("/predict")
async def predict(request: PredictionRequest):
    # Incrementar contador de solicitudes totales
    stats_manager.increment_total_requests()

    try:
        # Extraer los valores del modelo
        finca = request.finca
        animales_m = request.AnimalesM
        hectareas = request.Hectareas
        piscinas = request.Piscinas

        if not all([finca, animales_m, hectareas, piscinas]):
            raise HTTPException(
                status_code=400,
                detail="Faltan parámetros requeridos"
            )

        # Verificar que la finca sea válida
        if finca not in modelos:
            raise HTTPException(
                status_code=400,
                detail=f"Finca {finca} no válida"
            )

        # Cargar el modelo y el escalador para la finca especificada
        best_model, scaler = cargar_modelo_y_scaler(finca)

        # Parámetros iniciales de la predicción
        aniM_inicial = animales_m
        hect = hectareas
        pisc = piscinas

        # Configuración del margen de error
        margen_error = 0.01
        max_iteraciones = 100

        aniM = aniM_inicial
        for _ in range(max_iteraciones):
            nuevo_dato = np.array([[aniM, hect, pisc]])
            nuevo_dato_scaled = scaler.transform(nuevo_dato)
            prediccion = best_model.predict(nuevo_dato_scaled)

            # Recuperar valores
            hectareas_real = nuevo_dato[0][1]
            consumo_predicho = prediccion[0][0]
            gramos_predicho = int(round(prediccion[0][1]))
            peso = gramos_predicho
            rendimiento_predicho = obtener_rendimiento(gramos_predicho)

            # Recalcular variables dependientes
            kg_x_ha_predicho = round(consumo_predicho / hectareas_real, 2)
            libras_x_ha_predicho = round(
                kg_x_ha_predicho * (rendimiento_predicho / 100) * 100, 2)
            libras_total_predicho = round(
                hectareas_real * libras_x_ha_predicho, 2)
            error2_predicho = round(libras_total_predicho * 0.98, 2)
            animales_m = round(
                ((libras_x_ha_predicho * 454) / peso) / 10000, 2)

            # Verificar si se alcanzó el valor deseado
            if abs(animales_m - aniM_inicial) <= margen_error:
                break

            # Ajustar el valor de AnimalesM para la próxima iteración
            aniM -= (animales_m - aniM_inicial) * \
                0.1  # Factor de ajuste dinámico

        # Resultado de la predicción
        resultado = {
            "Consumo": consumo_predicho,
            "Gramos": gramos_predicho,
            "KGXHA": kg_x_ha_predicho,
            "LibrasTotal": libras_total_predicho,
            "LibrasXHA": libras_x_ha_predicho,
            "Error2": error2_predicho,
            "AnimalesM": animales_m
        }

        # Incrementar contador de solicitudes exitosas
        stats_manager.increment_successful_requests(finca)

        return resultado

    except HTTPException:
        # Incrementar contador de solicitudes fallidas
        stats_manager.increment_failed_requests()
        raise
    except Exception as e:
        # Incrementar contador de solicitudes fallidas
        stats_manager.increment_failed_requests()
        raise HTTPException(status_code=500, detail=str(e))


# Incluir otras rutas
app.include_router(main_router)
