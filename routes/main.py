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
from utils.auth import require_api_key


# Crear blueprint para las rutas principales
main_bp = Blueprint('main', __name__)

# --- NUEVO ENDPOINT DE IMPRESIÓN DE ETIQUETAS ---
@main_bp.route('/print/label', methods=['POST'])
@require_api_key
def imprimir_etiqueta_api():
    ruta_temporal = None
    try:
        datos = request.get_json()
        ValidationUtils.validar_payload_label(datos)

        datos_producto = datos['datos_producto']
        config_impresora = datos['config_impresora']
        cantidad = datos['cantidad']
        
        # ===== INICIO DE LA MODIFICACIÓN CLAVE =====
        # 1. Leemos el nombre de la impresora directamente del payload que envía Odoo.
        nombre_impresora = config_impresora.get('printer_name')

        # 2. Añadimos una validación para asegurarnos de que el nombre no venga vacío.
        if not nombre_impresora:
            # Si Odoo no envía un nombre, devolvemos un error claro.
            raise ValueError("El payload de Odoo no incluyó el 'printer_name' en 'config_impresora'.")
            
        # La vieja línea "nombre_impresora = obtener_impresora_actual()" se ha eliminado.
        # ===== FIN DE LA MODIFICACIÓN CLAVE =====

        ancho_mm = config_impresora['ancho_mm']
        alto_mm = config_impresora['alto_mm']

        # --- Lógica de cálculo de fuente (sin cambios) ---
        dimension_minima = min(ancho_mm, alto_mm)
        base_font_size_pt = dimension_minima / 3.0
        
        print(f"Tamaño de etiqueta: {ancho_mm}x{alto_mm}mm. Tamaño de fuente base calculado: {base_font_size_pt:.2f}pt")
        
        barcodes_b64 = PrintService.generar_barcodes_base64(datos_producto)
        
        contexto_renderizado = {
            **datos, 
            **barcodes_b64,
            "base_font_size_pt": base_font_size_pt
        }
        html_string = render_template('label.html', **contexto_renderizado)

        ruta_temporal = PrintService.convertir_html_a_imagen(html_string, ancho_mm, alto_mm, nombre_impresora)
        
        for i in range(cantidad):
            print(f"Enviando copia de imagen {i + 1}/{cantidad} a '{nombre_impresora}'...")
            # Pasamos el nombre de impresora correcto al servicio de impresión
            PrintService.imprimir_imagen(ruta_temporal, nombre_impresora, ancho_mm, alto_mm)

        return jsonify({
            "success": True,
            "message": f"{cantidad} etiqueta(s) enviada(s) a la impresora '{nombre_impresora}'."
        }), 200

    except Exception as e:
        error_details = traceback.format_exc()
        print("--- ERROR DETALLADO EN /print/label ---")
        print(error_details)
        return jsonify({
            "success": False,
            "error": "Ocurrió un error interno en el middleware.",
            "details": str(e)
        }), 500

    finally:
        # La limpieza sigue desactivada para depuración
        if ruta_temporal:
            # PrintService.programar_limpieza(ruta_temporal)
            print(f"!! MODO DEBUG: La limpieza del archivo temporal '{ruta_temporal}' está desactivada.")

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
