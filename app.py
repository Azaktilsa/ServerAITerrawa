from flask import Flask, jsonify, render_template_string, request
import json
import numpy as np
import joblib
from dotenv import load_dotenv
from decouple import config
import warnings
import requests
from google.cloud import storage
import os

warnings.filterwarnings(
    "ignore", message="Skipping variable loading for optimizer")

app = Flask(__name__)

load_dotenv()

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


@app.route('/')
def index():
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TERRAWA IA</title>
        <style>
            body {
                text-align: center;
                font-family: Arial, sans-serif;
                background-color: #F3ECE7;
                margin: 0;
                padding: 20px;
            }
            h1 {
                color: #2c3e50;
                font-size: 24px;
            }
            img {
                width: 300px;
                height: auto;
                margin-top: 20px;
                border-radius: 20px; /* Bordes redondeados */
                box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2); /* Sombra sutil */
            }
        </style>
    </head>
    <body>
        <h1>Implementación de IA para la Optimización de la Alimentación del Camarón</h1>
        <img src="{{ url_for('static', filename='images/Terrawa.jpeg') }}" alt="Terrawa">
    </body>
    </html>
    """
    return render_template_string(html_content)


@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()

        # Extraer los valores del JSON
        finca = data.get('finca')
        animales_m = data.get('AnimalesM')
        hectareas = data.get('Hectareas')
        piscinas = data.get('Piscinas')

        if not all([finca, animales_m, hectareas, piscinas]):
            return jsonify({"error": "Faltan parámetros requeridos"}), 400

        # Verificar que la finca sea válida
        if finca not in modelos:
            return jsonify({"error": f"Finca {finca} no válida"}), 400

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

        return jsonify(resultado)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
