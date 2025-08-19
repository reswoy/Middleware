# -*- coding: utf-8 -*-

"""
Rutas de la aplicación Flask (blueprints).
Contiene todos los endpoints de la API.
"""
                                               #--------
from flask import Blueprint, request, Response, jsonify, render_template #<---- agregado por gabriel

from services import PrintService
from utils import ValidationUtils
from impresoraConf import establecer_impresora_actual


# Crear blueprint para las rutas principales
main_bp = Blueprint('main', __name__)

# --- NUEVO ENDPOINT DE IMPRESIÓN DE ETIQUETAS ---
@main_bp.route('/print/label', methods=['POST'])
def imprimir_etiqueta_api():
    try:
        # 1. Recepción y Validación de Datos
        datos = request.get_json()
        ValidationUtils.validar_payload_label(datos)
        
        printer_config = datos['printer']
        label_config = datos['label']
        data_fields = datos['data']
        options = datos.get('options', {}) # Obtiene options o un dict vacío si no existe

        # 2. Generación de Contenido Dinámico (Códigos de Barras)
        barcodes_b64 = PrintService.generar_barcodes_base64(data_fields, options)
        
        # 3. Renderizado de la Plantilla HTML
        # Se combinan los datos originales con los códigos de barras generados
        contexto_renderizado = {**datos, **barcodes_b64}
        html_string = render_template('label.html', **contexto_renderizado)

        # 4. Conversión de HTML a Imagen (PNG)
        imagen_bytes = PrintService.convertir_html_a_imagen(html_string, label_config)
        
        # 5. Envío a la Impresora en Windows
        PrintService.imprimir_imagen_windows(imagen_bytes, printer_config['name'])
        
        # 6. Respuesta Exitosa
        return jsonify({
            "success": True,
            "message": f"Trabajo enviado a la impresora '{printer_config['name']}'."
        }), 200

    except ValueError as e: # Error de validación
        return jsonify({"success": False, "error": str(e)}), 400
    except (RuntimeError, ConnectionError, FileNotFoundError) as e: # Error de servidor
        return jsonify({"success": False, "error": "Error interno del servidor.", "details": str(e)}), 500
    except Exception as e: # Otros errores inesperados
        return jsonify({"success": False, "error": "Un error inesperado ha ocurrido.", "details": str(e)}), 500


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
    
