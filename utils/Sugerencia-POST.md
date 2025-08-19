Configurar impresora predeterminada desde Odoo (Middleware de impresión)
Objetivo

Recibir desde Odoo el JSON con nombre, ip y puerto de la impresora.
Validar el JSON.
Establecer esa impresora como predeterminada en Windows.
Actualizar la config en memoria para que los trabajos siguientes salgan por esa impresora sin intervención.
JSON esperado
{
  "nombre": "HP_LaserJet_001",
  "ip": "192.168.1.100",
  "puerto": 9100,
  "timestamp": "2025-08-04T15:30:45.123456"  // opcional
}
Resumen de cambios

config.py: agregar campos IP/puerto y función para actualizar la configuración en caliente.
utils/validation.py: agregar validador del payload JSON.
services/print_service.py: método para marcar impresora como predeterminada y leer siempre el nombre desde config.
main.py: nuevo endpoint POST /impresora/predeterminada que valida, aplica y actualiza la config.
Cambios en config.py
Añade IP/puerto y una función para actualizar la impresora activa.
# -*- coding: utf-8 -*-
# ...existing code...
import socket
# ...existing code...

NOMBRE_IMPRESORA = "PT-950NW"
# Nuevos campos dinámicos
PRINTER_IP = None
PRINTER_PORT = None
# ...existing code...

def obtener_ip_local():
    # ...existing code...
    return "127.0.0.1"

def actualizar_config_impresora(nombre: str, ip: str | None, puerto: int | None):
    """
    Actualiza en memoria la configuración de la impresora que usará el middleware.
    """
    global NOMBRE_IMPRESORA, PRINTER_IP, PRINTER_PORT
    NOMBRE_IMPRESORA = (nombre or "").strip()
    PRINTER_IP = ip
    PRINTER_PORT = puerto
    print(f"Configuración de impresora actualizada: nombre='{NOMBRE_IMPRESORA}', ip='{PRINTER_IP}', puerto='{PRINTER_PORT}'")

Cambios en validation.py
Agrega el validador del JSON entrante.

# -*- coding: utf-8 -*-

"""
Utilidades de validación.
Contiene funciones para validar archivos y peticiones.
"""

import os
import platform
import ipaddress
from datetime import datetime

from config import EXTENSIONES_SOPORTADAS


class ValidationUtils:
    """Utilidades para validación de archivos y sistema."""
    
    @staticmethod
    def validar_sistema_operativo():
        # ...existing code...
        return True
    
    @staticmethod
    def validar_archivo(archivo):
        # ...existing code...
        return True
    
    @staticmethod
    def validar_peticion(request):
        # ...existing code...
        return request.files['file']

    @staticmethod
    def validar_config_impresora_json(data: dict) -> dict:
        """
        Valida el JSON para configurar la impresora predeterminada.
        Requiere: nombre (str), ip (str), puerto (int). timestamp (str, ISO 8601) es opcional.
        Devuelve el payload normalizado.
        """
        if not isinstance(data, dict):
            raise Exception("El cuerpo debe ser un JSON válido.")

        for campo in ("nombre", "ip", "puerto"):
            if campo not in data:
                raise Exception(f"Falta el campo requerido: '{campo}'.")

        nombre = data.get("nombre")
        ip = data.get("ip")
        puerto = data.get("puerto")
        timestamp = data.get("timestamp")

        if not isinstance(nombre, str) or not nombre.strip():
            raise Exception("El campo 'nombre' debe ser un string no vacío.")

        try:
            ipaddress.ip_address(ip)
        except Exception:
            raise Exception("El campo 'ip' no es una dirección IP válida.")

        try:
            puerto = int(puerto)
        except Exception:
            raise Exception("El campo 'puerto' debe ser un número entero.")
        if not (1 <= puerto <= 65535):
            raise Exception("El campo 'puerto' debe estar entre 1 y 65535.")

        if timestamp is not None:
            if not isinstance(timestamp, str):
                raise Exception("El campo 'timestamp' debe ser string en formato ISO 8601.")
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                raise Exception("El campo 'timestamp' no tiene un formato ISO 8601 válido.")

        return {"nombre": nombre.strip(), "ip": ip, "puerto": puerto, "timestamp": timestamp}

Cambios en print_service.py
Asegúrate de usar siempre app_config.NOMBRE_IMPRESORA cuando imprimes.
Agrega un método para establecer la impresora predeterminada en Windows usando WMI.
Dependencias (si no están instaladas):

pip install WMI pypiwin32

# -*- coding: utf-8 -*-
# ...existing code...
import config as app_config
# ...existing code...
# Si no están, agrega estas importaciones:
import wmi
import pythoncom
# ...existing code...

class PrintService:
    # ...existing code...

    @staticmethod
    def imprimir_txt(ruta_archivo):
        # ...existing code...
        comando_ps = f'Get-Content "{ruta_archivo}" | Out-Printer -Name "{app_config.NOMBRE_IMPRESORA}"'
        # ...existing code...

    @staticmethod
    def imprimir_pdf(ruta_archivo):
        # ...existing code...
        resultado = subprocess.run([
            ruta_expandida,
            "-print-to", app_config.NOMBRE_IMPRESORA,
            "-silent",
            ruta_archivo
        ], capture_output=True, text=True, timeout=TIMEOUT_SUMATRA, check=False)
        # ...existing code...

    @staticmethod
    def imprimir_con_respaldo(ruta_archivo):
        # ...existing code...
        win32api.ShellExecute(0, "print", ruta_archivo, f'/d:"{app_config.NOMBRE_IMPRESORA}"', ".", 0)
        # ...existing code...

    @staticmethod
    def establecer_impresora_predeterminada(nombre_impresora: str) -> bool:
        """
        Establece 'nombre_impresora' como predeterminada en Windows.
        """
        print(f"Intentando establecer '{nombre_impresora}' como predeterminada...")
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            impresoras = c.Win32_Printer(Name=nombre_impresora)
            if not impresoras:
                print(f"No se encontró la impresora '{nombre_impresora}'.")
                return False
            impresoras[0].SetDefaultPrinter()
            print(f"Impresora '{nombre_impresora}' establecida como predeterminada.")
            return True
        except Exception as e:
            print(f"ERROR al establecer predeterminada: {e}")
            raise
        finally:
            pythoncom.CoUninitialize()
Cambios en main.py (endpoint nuevo)
Agrega el endpoint POST /impresora/predeterminada que valida, aplica y actualiza la config.

# -*- coding: utf-8 -*-
# ...existing code...
from flask import Flask, request, jsonify, Response
from utils.validation import ValidationUtils
from services.print_service import PrintService
import config as app_config
# ...existing code...

app = Flask(__name__)
# ...existing code...

@app.route('/impresora/predeterminada', methods=['POST'])
def establecer_predeterminada():
    """
    Recibe JSON {nombre, ip, puerto, timestamp?} desde Odoo,
    valida, establece la impresora como predeterminada en Windows y
    actualiza la configuración en memoria.
    """
    data = request.get_json(silent=True)
    if not data:
        return Response("Error: La petición debe contener un cuerpo JSON.", status=400)

    try:
        payload = ValidationUtils.validar_config_impresora_json(data)
    except Exception as e:
        return Response(f"Error de validación: {str(e)}", status=400)

    nombre = payload["nombre"]
    ip = payload["ip"]
    puerto = payload["puerto"]

    try:
        ok = PrintService.establecer_impresora_predeterminada(nombre)
        if not ok:
            return jsonify({"error": f"No se encontró la impresora '{nombre}'."}), 404

        app_config.actualizar_config_impresora(nombre, ip, puerto)

        return jsonify({
            "mensaje": f"Impresora '{nombre}' establecida como predeterminada.",
            "config": {
                "nombre": app_config.NOMBRE_IMPRESORA,
                "ip": app_config.PRINTER_IP,
                "puerto": app_config.PRINTER_PORT
            }
        }), 200
    except Exception as e:
        return Response(f"Error interno: {str(e)}", status=500)

# ...existing code...
if __name__ == '__main__':
    app.run(host=app_config.HOST, port=app_config.PORT, debug=app_config.DEBUG)
