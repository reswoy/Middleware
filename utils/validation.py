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
        Valida que el payload JSON para la nueva API de etiquetas sea correcto.
        """
        if not data:
            raise ValueError("No se recibió un cuerpo JSON en la petición.")

        # Validar objetos principales
        if 'printer' not in data or not isinstance(data['printer'], dict):
            raise ValueError("El campo 'printer' es requerido y debe ser un objeto.")
        if 'label' not in data or not isinstance(data['label'], dict):
            raise ValueError("El campo 'label' es requerido y debe ser un objeto.")
        if 'data' not in data or not isinstance(data['data'], dict):
            raise ValueError("El campo 'data' es requerido y debe ser un objeto.")

        # Validar campos anidados requeridos
        if 'name' not in data['printer']:
            raise ValueError("El campo 'printer.name' es requerido.")
        if 'width_mm' not in data['label'] or 'height_mm' not in data['label'] or 'dpi' not in data['label']:
            raise ValueError("Los campos 'label.width_mm', 'label.height_mm' y 'label.dpi' son requeridos.")
        if 'product_name' not in data['data'] or 'barcode' not in data['data'] or 'sku' not in data['data']:
            raise ValueError("Los campos 'data.product_name', 'data.barcode' y 'data.sku' son requeridos.")
        
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
