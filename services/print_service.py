# -*- coding: utf-8 -*-

"""
Servicios de impresión.
Contiene toda la lógica relacionada con la impresión de archivos.
"""

import os
import subprocess
import tempfile
import threading
import time
import uuid
import io
import base64

#Libreria Externas
import win32api
import wmi
import pythoncom
import imgkit
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageWin
import win32print
import win32ui
from pywintypes import error as pywin_error


from impresoraConf import obtener_impresora_actual
from config import ( 
    RUTAS_SUMATRA, 
    TIMEOUT_POWERSHELL, 
    TIMEOUT_SUMATRA, 
    TIMEOUT_LIMPIEZA,
)
from utils.wkhtml_check import get_imgkit_config  # <-- configuración de imgkit con wkhtmltoimage


class PrintService:
    """Servicio encargado de manejar todas las operaciones de impresión."""
    
    # Método para validar el payload de la etiqueta #
    
    @staticmethod
    def generar_barcodes_base64(datos_producto):
        """Genera códigos de barras en memoria y los devuelve como strings Base64."""
        barcodes = {}
        
        try:
            # Generar código de barras comercial (EAN-13) si existe
            if datos_producto.get('codigo_barras'):
                ean = barcode.get_barcode_class('ean13')
                commercial_barcode = ean(datos_producto['codigo_barras'], writer=ImageWriter())
                buffer_commercial = io.BytesIO()
                commercial_barcode.write(buffer_commercial)
                b64_commercial = base64.b64encode(buffer_commercial.getvalue()).decode('utf-8')
                barcodes['commercial_barcode_base64'] = b64_commercial
        
        except Exception as e:
            raise RuntimeError(f"Error al generar código de barras: {str(e)}")
            
        return barcodes

    @staticmethod
    def convertir_html_a_imagen(html_string, config_impresora):
        """Convierte un string HTML a una imagen PNG en memoria con dimensiones precisas."""
        try:
            # NOTA: El DPI se fija en 300. Para hacerlo dinámico, debe venir en el payload.
            dpi = config_impresora.get('dpi', 300)
            
            # Cálculo crítico de dimensiones en píxeles
            pixel_width = int((config_impresora['ancho_mm'] / 25.4) * dpi)
            pixel_height = int((config_impresora['alto_mm'] / 25.4) * dpi)

            options = {
                'format': 'png',
                'width': pixel_width,
                'height': pixel_height,
                'encoding': "UTF-8",
                'quiet': '',
                'disable-smart-shrinking': '',  # Desactiva el ajuste automático de tamaño
            }

            # Usar config que apunta al binario correcto de wkhtmltoimage si está disponible
            cfg = get_imgkit_config()
            imagen_bytes = imgkit.from_string(html_string, False, options=options, config=cfg)
            return imagen_bytes
        except Exception as e:
            raise RuntimeError(f"Error al convertir HTML a imagen: {str(e)}.")

    @staticmethod
    def imprimir_imagen_windows(imagen_bytes, nombre_impresora):
        """Envía una imagen (en bytes) directamente al spooler de impresión de Windows."""
        hPrinter = None
        try:
            # Cargar la imagen desde bytes usando Pillow
            image_file = io.BytesIO(imagen_bytes)
            img = Image.open(image_file)

            # Abrir la impresora
            hPrinter = win32print.OpenPrinter(nombre_impresora)
            
            # Crear un Device Context (DC) para la impresora
            hDC = win32ui.CreateDC()
            hDC.CreatePrinterDC(nombre_impresora)
            
            # Convertir la imagen de Pillow a un Device Independent Bitmap (DIB)
            dib = ImageWin.Dib(img)
            
            # Iniciar trabajo de impresión
            hDC.StartDoc(f"Etiqueta-{uuid.uuid4().hex}")
            hDC.StartPage()
            
            # Dibujar el DIB en el DC de la impresora
            dib.draw(hDC.GetHandleOutput(), (0, 0, img.width, img.height))
            
            # Finalizar trabajo
            hDC.EndPage()
            hDC.EndDoc()
            hDC.DeleteDC()
            
        except pywin_error as e:
            raise ConnectionError(f"Error de pywin32 al imprimir: {str(e)}. Verifica que el nombre de la impresora '{nombre_impresora}' sea correcto.")
        except Exception as e:
            raise RuntimeError(f"Error inesperado durante el proceso de impresión en Windows: {str(e)}")
        finally:
            if hPrinter:
                win32print.ClosePrinter(hPrinter)

    @staticmethod
    def guardar_archivo_temporal(archivo):
        """
        Guarda el archivo recibido en el directorio temporal del sistema.
        
        Args:
            archivo: Archivo recibido de la petición Flask
            
        Returns:
            str: Ruta del archivo temporal guardado
        """
        directorio_temporal = tempfile.gettempdir()
        nombre_base, extension = os.path.splitext(archivo.filename)
        extension = extension.lower()
        
        nombre_archivo_temporal = os.path.join(
            directorio_temporal, 
            f"etiqueta_{uuid.uuid4().hex}{extension}"
        )
        
        archivo.save(nombre_archivo_temporal)
        print(f"Archivo '{archivo.filename}' guardado temporalmente en: {nombre_archivo_temporal}")
        
        return nombre_archivo_temporal
    
    @staticmethod
    def imprimir_txt(ruta_archivo):
        """
        Imprime un archivo de texto plano usando PowerShell.
        
        Args:
            ruta_archivo (str): Ruta del archivo a imprimir
            
        Raises:
            Exception: Si hay error en la impresión
        """
        nombre_impresora = obtener_impresora_actual() # <-- OBTENER IMPRESORA ACTUAL
        print(f"Intentando imprimir archivo TXT en '{nombre_impresora}'...")
        comando_ps = f'Get-Content "{ruta_archivo}" | Out-Printer -Name "{nombre_impresora}"'
        
        resultado = subprocess.run(
            ["powershell", "-Command", comando_ps],
            capture_output=True, 
            text=True, 
            timeout=TIMEOUT_POWERSHELL, 
            check=False
        )
        
        if resultado.returncode == 0:
            print("Archivo TXT enviado directamente a la impresora.")
        else:
            mensaje_error = resultado.stderr.strip()
            raise Exception(f"Error al imprimir con PowerShell: {mensaje_error}")
    
    @staticmethod
    def imprimir_pdf(ruta_archivo, nombre_impresora=None):
        """
        Imprime un archivo PDF. Si no se especifica un nombre de impresora,
        usa la que está guardada por defecto.
        """
        # Si no se pasa un nombre de impresora, usamos la global.
        if nombre_impresora is None:
            nombre_impresora = obtener_impresora_actual()
        
        print(f"Intentando imprimir PDF con SumatraPDF en '{nombre_impresora}'...")
        sumatra_encontrado = False
        for ruta_sumatra in RUTAS_SUMATRA:
            ruta_expandida = os.path.expanduser(ruta_sumatra)
            if os.path.exists(ruta_expandida):
                print(f"SumatraPDF encontrado en: {ruta_expandida}")
                resultado = subprocess.run([
                    ruta_expandida,
                    "-print-to", nombre_impresora, # Usar la variable correcta
                    "-silent",
                    "-exit-on-print", # Asegura que Sumatra cierre después de imprimir
                    ruta_archivo
                ], capture_output=True, text=True, timeout=TIMEOUT_SUMATRA, check=False)
                
                sumatra_encontrado = True
                if resultado.returncode == 0:
                    print("PDF enviado a la impresora usando SumatraPDF.")
                else:
                    raise Exception(f"SumatraPDF falló al intentar imprimir: {resultado.stderr}")
                break
        
        if not sumatra_encontrado:
            raise Exception("SumatraPDF no encontrado en las rutas habituales.")
    
    @staticmethod
    def imprimir_con_respaldo(ruta_archivo):
        """
        Métodos de respaldo para impresión cuando fallan los métodos principales.
        
        Args:
            ruta_archivo (str): Ruta del archivo a imprimir
        """
        nombre_impresora = obtener_impresora_actual() # <-- OBTENER IMPRESORA ACTUAL
        try:
            print(f"Intentando método de respaldo con win32api en '{nombre_impresora}'...")
            win32api.ShellExecute(0, "print", ruta_archivo, f'/d:"{nombre_impresora}"', ".", 0)
            print("Archivo enviado a impresión usando el método de respaldo win32api.")
        except Exception as e2:
            print(f"ERROR con win32api: {str(e2)}")
            print("Último recurso: abriendo el archivo...")
            os.startfile(ruta_archivo)
    
    ###------------ Agregado Gabriel Lujan ---------------###
    @staticmethod
    def obtener_impresoras_activas():
        """
        Escanea el sistema en busca de impresoras que están listas para imprimir.
        """
        print("Escaneando impresoras listas en el sistema...")
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            impresoras_detalladas = []

            for printer in c.Win32_Printer():
                # El filtro definitivo y más preciso
                es_fisicamente_online = (printer.PrinterState & 16) == 0 
                esta_lista_para_imprimir = printer.PrinterStatus == 3

                if es_fisicamente_online and esta_lista_para_imprimir:
                    port_name = printer.PortName
                    port = port_name
            
                    printer_info = {
                        "name": printer.Name,
                        "port": port
                    }
                    print(f"Impresora lista encontrada: {printer_info}")
                    impresoras_detalladas.append(printer_info)

            if not impresoras_detalladas:
                print("ADVERTENCIA: No se encontraron impresoras en estado 'En Línea' y 'Lista/Inactiva'.")

            return impresoras_detalladas
        
        except Exception as e:
            print(f"ERROR al escanear impresoras con WMI: {e}")
            return []
        finally:
            pythoncom.CoUninitialize()

     # --- MÉTODO NUEVO PARA ESTABLECER LA IMPRESORA PREDETERMINADA ---
    @staticmethod
    def establecer_impresora_predeterminada(nombre_impresora):
        """
        Establece una impresora como la predeterminada del sistema en Windows.
        """
        print(f"Intentando establecer '{nombre_impresora}' como predeterminada en Windows...")
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            impresora = c.Win32_Printer(Name=nombre_impresora)

            if not impresora:
                print(f"ERROR: No se encontró ninguna impresora con el nombre '{nombre_impresora}'.")
                return False

            impresora[0].SetDefaultPrinter()
            print(f"Impresora '{nombre_impresora}' establecida como predeterminada en Windows.")
            return True

        except Exception as e:
            print(f"ERROR al intentar establecer la impresora predeterminada: {e}")
            raise e
        finally:
            pythoncom.CoUninitialize()

    @staticmethod
    def programar_limpieza(ruta_archivo):
        """
        Programa la eliminación del archivo temporal en segundo plano.
        """
        def limpiar_archivo():
            time.sleep(TIMEOUT_LIMPIEZA)
            try:
                os.remove(ruta_archivo)
                print(f"Archivo temporal '{ruta_archivo}' eliminado correctamente.")
            except Exception as e:
                print(f"ADVERTENCIA: No se pudo eliminar el archivo temporal. Error: {e}")
        
        threading.Thread(target=limpiar_archivo, daemon=True).start()
    
    @classmethod
    def procesar_impresion(cls, archivo):
        """
        Orquesta la impresión de un ARCHIVO SUBIDO y devuelve un booleano de éxito.
        """
        ruta_archivo = cls.guardar_archivo_temporal(archivo)
        exito = False

        try:
            _, extension = os.path.splitext(archivo.filename)
            if extension.lower() == '.txt':
                cls.imprimir_txt(ruta_archivo)
            elif extension.lower() == '.pdf':
                cls.imprimir_pdf(ruta_archivo)
            exito = True
        except Exception as e:
            print(f"ERROR en método principal: {str(e)}")
            try:
                # Intenta el respaldo y actualiza el éxito basado en su resultado
                exito = cls.imprimir_con_respaldo(ruta_archivo)
            except Exception as e_respaldo:
                print(f"ERROR en método de respaldo: {str(e_respaldo)}")
                exito = False
        finally:
            cls.programar_limpieza(ruta_archivo)
        
        return exito
