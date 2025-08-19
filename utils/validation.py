# -*- coding: utf-8 -*-

"""
Utilidades de validación.
Contiene funciones para validar archivos y peticiones.
"""

import os
import platform

from config import EXTENSIONES_SOPORTADAS

class ValidationUtils:
    @staticmethod
    def validar_payload_label(data):
        """
        Valida que el payload JSON de Odoo sea correcto.
        """
        if not data:
            raise ValueError("No se recibió un cuerpo JSON en la petición.")

        # Validar objetos principales
        if 'datos_producto' not in data or not isinstance(data['datos_producto'], dict):
            raise ValueError("El campo 'datos_producto' es requerido y debe ser un objeto.")
        if 'config_impresora' not in data or not isinstance(data['config_impresora'], dict):
            raise ValueError("El campo 'config_impresora' es requerido y debe ser un objeto.")
        if 'cantidad' not in data or not isinstance(data['cantidad'], int) or data['cantidad'] <= 0:
            raise ValueError("El campo 'cantidad' es requerido y debe ser un número entero mayor a 0.")

        # Validar campos anidados requeridos
        if 'nombre' not in data['datos_producto'] or 'referencia_interna' not in data['datos_producto']:
            raise ValueError("Los campos 'nombre' y 'referencia_interna' son requeridos en 'datos_producto'.")
        if 'ancho_mm' not in data['config_impresora'] or 'alto_mm' not in data['config_impresora']:
            raise ValueError("Los campos 'ancho_mm' y 'alto_mm' son requeridos en 'config_impresora'.")
        
        return True


    @staticmethod
    def validar_sistema_operativo():
        """
        Valida que el sistema operativo sea Windows.
        
        Returns:
            bool: True si es Windows
            
        Raises:
            Exception: Si no es Windows
        """
        if platform.system() != "Windows":
            raise Exception("Este middleware solo es compatible con Windows.")
        return True
    
    @staticmethod
    def validar_archivo(archivo):
        """
        Valida que el archivo recibido sea válido y tenga una extensión soportada.
        
        Args:
            archivo: Archivo recibido de la petición Flask
            
        Returns:
            bool: True si el archivo es válido
            
        Raises:
            Exception: Si el archivo no es válido
        """
        # Validar que el archivo existe
        if not archivo:
            raise Exception("No se recibió archivo. Asegúrate de que el campo del formulario se llame 'file'.")
        
        # Validar nombre de archivo
        if archivo.filename == '':
            raise Exception("Nombre de archivo vacío.")
        
        # Validar extensión
        _, extension = os.path.splitext(archivo.filename)
        extension = extension.lower()
        
        if extension not in EXTENSIONES_SOPORTADAS:
            raise Exception(f"Tipo de archivo no soportado: '{extension}'. Solo se admiten {', '.join(EXTENSIONES_SOPORTADAS)}.")
        
        return True
    
    @staticmethod
    def validar_peticion(request):
        """
        Valida que la petición HTTP contenga un archivo.
        
        Args:
            request: Objeto request de Flask
            
        Returns:
            file: El archivo de la petición
            
        Raises:
            Exception: Si la petición no es válida
        """
        if 'file' not in request.files:
            raise Exception("La petición no contiene el campo 'file'.")
        
        return request.files['file']
