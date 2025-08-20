# -*- coding: utf-8 -*-

"""
Rutas de la aplicación Flask (blueprints).
Contiene todos los endpoints de la API.
"""

#--------
from flask import Blueprint, request, Response, jsonify, render_template #<---- agregado por gabriel
import traceback

from impresoraConf import obtener_impresora_actual
from impresoraConf import establecer_impresora_actual
from services import PrintService
from utils import ValidationUtils
from config import API_KEYS
from functools import wraps


def require_api_key(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key')
        if not key or key not in API_KEYS:
            return jsonify({"error": "No autorizado"}), 401
        return func(*args, **kwargs)
    return decorated

# Crear blueprint para las rutas principales
main_bp = Blueprint('main', __name__)

# --- NUEVO ENDPOINT DE IMPRESIÓN DE ETIQUETAS ---
@main_bp.route('/print/label', methods=['POST'])
@require_api_key
def imprimir_etiqueta_api(): # O el nombre que prefieras
    try:
        # 1. Recepción y Validación del Payload en Español (esto ya estaba bien)
        datos = request.get_json()
        ValidationUtils.validar_payload_label(datos)
        
        # --- INICIO DE LA CORRECCIÓN ---
        # 2. Extraer datos usando las claves correctas en español
        datos_producto = datos['datos_producto']
        config_impresora = datos['config_impresora']
        cantidad = datos['cantidad']

        # 3. Obtener la impresora predeterminada del middleware (ya que no viene en el payload)
        nombre_impresora = obtener_impresora_actual()
        if not nombre_impresora:
            raise ConnectionError("No hay una impresora predeterminada configurada en el middleware.")
        
        print(f"Petición para imprimir {cantidad} etiquetas en la impresora predeterminada '{nombre_impresora}'")
        # --- FIN DE LA CORRECCIÓN ---

        # 4. Generación de Códigos de Barras
        barcodes_b64 = PrintService.generar_barcodes_base64(datos_producto)

        # 5. Renderizado de la Plantilla HTML
        contexto_renderizado = {**datos, **barcodes_b64}
        html_string = render_template('label.html', **contexto_renderizado)

        # 6. Conversión de HTML a Imagen (PNG)
        imagen_bytes = PrintService.convertir_html_a_imagen(html_string, config_impresora)
        
        # 7. Bucle de Envío a la Impresora
        for i in range(cantidad):
            print(f"Enviando copia {i + 1}/{cantidad} a '{nombre_impresora}'...")
            PrintService.imprimir_imagen_windows(imagen_bytes, nombre_impresora)
        
        # 8. Respuesta Exitosa
        return jsonify({
            "success": True,
            "message": f"{cantidad} etiqueta(s) enviada(s) a la impresora '{nombre_impresora}'."
        }), 200

    except Exception as e:
        # El bloque de manejo de errores que tenías es muy bueno, lo mantenemos
        error_details = traceback.format_exc()
        print("--- TRACEBACK DETALLADO DEL ERROR ---")
        print(error_details)
        print("-------------------------------------")
        
        if isinstance(e, ValueError):
             return jsonify({"success": False, "error": str(e)}), 400
        
        return jsonify({
            "success": False, 
            "error": "Un error inesperado ha ocurrido en el middleware.", 
            "details": str(e)
        }), 500


@main_bp.route('/', methods=['GET'])
def estado_salud():
    """
    Endpoint de "health check" o verificación de estado.
    Permite comprobar rápidamente si el servidor está funcionando.
    Responde con un mensaje simple y un código de estado 200 OK.
    """
    return Response("Middleware de impresión activo", status=200)

## --------  METODO DE GET NUEVO GABRIEL LUJAN--------##

@main_bp.route('/printers', methods=['GET'])
@require_api_key
def listar_impresoras():
    """
    Endpoint que devuelve una lista de las impresoras activas
    detectadas en el sistema.
    """
    try:
        # Reutilizamos la validación para asegurarnos de que estamos en Windows
        ValidationUtils.validar_sistema_operativo()

        # Llamamos al nuevo método del servicio de impresión
        impresoras = PrintService.obtener_impresoras_activas()

        # Devolvemos la lista en formato JSON
        return jsonify(impresoras), 200

    except Exception as e:
        print(f"ERROR en /printers: {str(e)}")
        return Response(f"Error: {str(e)}", status=500)


@main_bp.route('/impresora/predeterminada', methods=['POST'])
@require_api_key
def establecer_predeterminada():
    """
    Endpoint para establecer una impresora como predeterminada.
    """
    data = request.get_json()
    if not data:
        return Response("Error: La petición debe contener un cuerpo JSON.", status=400)

    nombre_impresora = data.get('nombre')
    if not nombre_impresora:
        return Response("Error: El JSON debe contener la clave 'nombre' con el nombre de la impresora.", status=400)

    try:
        exito = PrintService.establecer_impresora_predeterminada(nombre_impresora)

        if exito:
            # --- LÍNEA AÑADIDA ---
            # Guardamos la impresora en nuestra configuración persistente.
            establecer_impresora_actual(nombre_impresora)
            # --------------------
            return jsonify({"mensaje": f"Impresora '{nombre_impresora}' establecida como predeterminada."}), 200
        else:
            return jsonify({"error": f"No se encontró la impresora con el nombre '{nombre_impresora}'."}), 404

    except Exception as e:
        print(f"ERROR en /impresora/predeterminada: {str(e)}")
        return Response(f"Error interno del servidor: {str(e)}", status=500)   


@main_bp.route('/print-pdf', methods=['POST'])
@require_api_key
def imprimir_pdf():
    """
    Endpoint principal que recibe un archivo y lo manda a imprimir.
    """
    try:
        # 1. Verificación del sistema operativo
        ValidationUtils.validar_sistema_operativo()
        
        # 2. Depuración: Muestra los encabezados de la petición entrante
        print("\n--- ENCABEZADOS DE LA PETICIÓN ENTRANTE ---")
        print(request.headers)
        
        # 3. Validación de la petición y archivo
        archivo = ValidationUtils.validar_peticion(request)
        ValidationUtils.validar_archivo(archivo)
        
         # 4. Procesar impresión
        impresion_exitosa = PrintService.procesar_impresion(archivo)
        
        # 5. Respuesta basada en el resultado
        if impresion_exitosa:
            return Response("Archivo enviado a impresión", status=200)
        else:
            return Response("Error: No se pudo completar la impresión. Revise los logs del servidor para más detalles.", status=500)

    except Exception as e:
        # Manejo de errores
        print(f"ERROR: {str(e)}")
        
        # Determinar código de estado basado en el tipo de error
        if "no soportado" in str(e).lower():
            status_code = 415 # Unsupported Media Type
        elif "no se recibió" in str(e).lower() or "vacío" in str(e).lower():
            status_code = 400 # Bad Request
        elif "solo es compatible" in str(e).lower():
            status_code = 400 # Bad Request
        else:
            status_code = 500 # Internal Server Error
            
        return Response(f"Error: {str(e)}", status=status_code)

