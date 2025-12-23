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
import win32con
import win32gui

from barcode.writer import ImageWriter
from flask import render_template
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
    
    # ===== INICIO DE LA FUNCIÓN MODIFICADA =====
    @staticmethod
    def generar_barcodes_base64(datos_producto):
        """
        Genera códigos de barras en memoria y los devuelve como strings Base64.
        Selecciona dinámicamente entre EAN-13 (si es numérico) y Code 128 (si es alfanumérico).
        """
        barcodes = {}
        try:
            codigo = datos_producto.get('codigo_barras')
            if not codigo:
                return barcodes # Si no hay código de barras, no hacemos nada.

            # --- LÓGICA INTELIGENTE DE SELECCIÓN ---
            
            barcode_class = None
            # Si el código contiene solo números y tiene la longitud correcta para EAN-13 (12 dígitos para generar el 13)...
            if codigo.isdigit() and len(codigo) == 12:
                print(f"INFO: Detectado código numérico apto para EAN-13: {codigo}")
                barcode_class = barcode.get_barcode_class('ean13')
            else:
                # Para cualquier otro caso (alfanumérico, longitud diferente, etc.), usamos el versátil Code 128.
                print(f"INFO: Detectado código alfanumérico o no estándar. Usando Code 128 para: {codigo}")
                barcode_class = barcode.get_barcode_class('code128')
                
            # --- FIN DE LA LÓGICA INTELIGENTE ---

            writer = ImageWriter()
            # Estas opciones funcionan bien para ambos estándares
            writer_options = {
                "write_text": False,
                "module_height": 5.0
            }

            # Usamos la clase de barcode que seleccionamos dinámicamente
            generated_barcode = barcode_class(codigo, writer=writer) 
            
            buffer = io.BytesIO()
            generated_barcode.write(buffer, writer_options)
            
            b64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
            barcodes['commercial_barcode_base64'] = b64_image
            
        except Exception as e:
            # Mejoramos el mensaje de error para saber qué código falló
            codigo_problematico = datos_producto.get('codigo_barras', '[NO DISPONIBLE]')
            raise RuntimeError(f"Error al generar código de barras para '{codigo_problematico}': {str(e)}")
            
        return barcodes
    # ===== FIN DE LA FUNCIÓN MODIFICADA =====

    @staticmethod
    def imprimir_pdf_generico(ruta_pdf, nombre_impresora, ancho_mm, alto_mm):
        """
        Imprime un archivo PDF usando SumatraPDF, detectando automáticamente la
        orientación correcta (vertical u horizontal) y deshabilitando el escalado.
        """
        print(f"Intentando imprimir PDF en '{nombre_impresora}'...")

        if ancho_mm >= alto_mm:
            orientacion = "landscape"
        else:
            orientacion = "portrait"

        print(f"Orientación detectada para la etiqueta: {orientacion.upper()}")
        print_settings = f"{orientacion},noscale"

        for ruta_sumatra in RUTAS_SUMATRA:
            ruta_expandida = os.path.expanduser(ruta_sumatra)
            if os.path.exists(ruta_expandida):
                print(f"SumatraPDF encontrado en: {ruta_expandida}")
                comando = [ruta_expandida, "-print-to", nombre_impresora, "-print-settings", print_settings, "-silent", "-exit-on-print", ruta_pdf]
                resultado = subprocess.run(comando, capture_output=True, text=True, timeout=TIMEOUT_SUMATRA, check=False)

                if resultado.returncode == 0:
                    print(f"PDF enviado a la impresora con orientación '{orientacion}' y sin escalado.")
                    return True
                else:
                    raise RuntimeError(f"SumatraPDF falló: {resultado.stderr}")

        raise FileNotFoundError("SumatraPDF no encontrado en las rutas configuradas.")

    @staticmethod
    def guardar_archivo_temporal(archivo):
        """
        Guarda el archivo recibido en el directorio temporal del sistema.
        """
        directorio_temporal = tempfile.gettempdir()
        nombre_base, extension = os.path.splitext(archivo.filename)
        extension = extension.lower()
        
        nombre_archivo_temporal = os.path.join(directorio_temporal, f"etiqueta_{uuid.uuid4().hex}{extension}")
        
        archivo.save(nombre_archivo_temporal)
        print(f"Archivo '{archivo.filename}' guardado temporalmente en: {nombre_archivo_temporal}")
        
        return nombre_archivo_temporal
    
    @staticmethod
    def imprimir_txt(ruta_archivo):
        """
        Imprime un archivo de texto plano usando PowerShell.
        """
        nombre_impresora = obtener_impresora_actual()
        print(f"Intentando imprimir archivo TXT en '{nombre_impresora}'...")
        comando_ps = f'Get-Content "{ruta_archivo}" | Out-Printer -Name "{nombre_impresora}"'
        
        resultado = subprocess.run(["powershell", "-Command", comando_ps], capture_output=True, text=True, timeout=TIMEOUT_POWERSHELL, check=False)
        
        if resultado.returncode == 0:
            print("Archivo TXT enviado directamente a la impresora.")
        else:
            raise Exception(f"Error al imprimir con PowerShell: {resultado.stderr.strip()}")
    
    @staticmethod
    def imprimir_pdf(ruta_archivo, nombre_impresora=None):
        """
        Imprime un archivo PDF. Si no se especifica un nombre de impresora,
        usa la que está guardada por defecto.
        """
        if nombre_impresora is None:
            nombre_impresora = obtener_impresora_actual()
        
        print(f"Intentando imprimir PDF con SumatraPDF en '{nombre_impresora}'...")
        for ruta_sumatra in RUTAS_SUMATRA:
            ruta_expandida = os.path.expanduser(ruta_sumatra)
            if os.path.exists(ruta_expandida):
                print(f"SumatraPDF encontrado en: {ruta_expandida}")
                resultado = subprocess.run([ruta_expandida, "-print-to", nombre_impresora, "-silent", "-exit-on-print", ruta_archivo], capture_output=True, text=True, timeout=TIMEOUT_SUMATRA, check=False)
                
                if resultado.returncode == 0:
                    print("PDF enviado a la impresora usando SumatraPDF.")
                    return
                else:
                    raise Exception(f"SumatraPDF falló al intentar imprimir: {resultado.stderr}")
        
        raise Exception("SumatraPDF no encontrado en las rutas habituales.")
    
    @staticmethod
    def imprimir_con_respaldo(ruta_archivo):
        """
        Métodos de respaldo para impresión cuando fallan los métodos principales.
        """
        nombre_impresora = obtener_impresora_actual()
        try:
            print(f"Intentando método de respaldo con win32api en '{nombre_impresora}'...")
            win32api.ShellExecute(0, "print", ruta_archivo, f'/d:"{nombre_impresora}"', ".", 0)
            print("Archivo enviado a impresión usando el método de respaldo win32api.")
        except Exception as e2:
            print(f"ERROR con win32api: {str(e2)}")
            print("Último recurso: abriendo el archivo...")
            os.startfile(ruta_archivo)
    
    @staticmethod
    def obtener_impresoras_activas():
        """
        Escanea el sistema en busca de impresoras listas y obtiene su
        configuración de papel predeterminada (ancho y alto).
        """
        print("Escaneando impresoras listas y su configuración de papel...")
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            impresoras_detalladas = []

            for printer in c.Win32_Printer():
                if (printer.PrinterState & 16) == 0 and printer.PrinterStatus == 3:
                    ancho_mm, alto_mm = None, None
                    try:
                        h_printer = win32print.OpenPrinter(printer.Name)
                        try:
                            properties = win32print.GetPrinter(h_printer, 2)
                            devmode = properties['pDevMode']
                            if devmode.PaperWidth > 0 and devmode.PaperLength > 0:
                                ancho_mm = devmode.PaperWidth / 10.0
                                alto_mm = devmode.PaperLength / 10.0
                        finally:
                            win32print.ClosePrinter(h_printer)
                    except pywin_error as e:
                        print(f"ADVERTENCIA: No se pudo obtener el tamaño de papel para '{printer.Name}'. Error: {e}")
                    
                    printer_info = {"name": printer.Name, "port": printer.PortName, "ancho_mm": ancho_mm, "alto_mm": alto_mm}
                    print(f"Impresora lista encontrada: {printer_info}")
                    impresoras_detalladas.append(printer_info)

            return impresoras_detalladas
        except Exception as e:
            print(f"ERROR al escanear impresoras: {e}")
            return []
        finally:
            pythoncom.CoUninitialize()

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
            if extension.lower() == '.txt': cls.imprimir_txt(ruta_archivo)
            elif extension.lower() == '.pdf': cls.imprimir_pdf(ruta_archivo)
            exito = True
        except Exception as e:
            print(f"ERROR en método principal: {str(e)}")
            try: exito = cls.imprimir_con_respaldo(ruta_archivo)
            except Exception as e_respaldo: print(f"ERROR en método de respaldo: {str(e_respaldo)}"); exito = False
        finally:
            cls.programar_limpieza(ruta_archivo)
        return exito

    @staticmethod
    def obtener_dpi_impresora(nombre_impresora):
        """
        Se conecta a una impresora y devuelve su resolución DPI.
        """
        try:
            hDC = win32ui.CreateDC()
            hDC.CreatePrinterDC(nombre_impresora)
            dpi_x = hDC.GetDeviceCaps(win32con.LOGPIXELSX)
            hDC.DeleteDC()
            print(f"DPI detectado para '{nombre_impresora}': {dpi_x}")
            return dpi_x
        except Exception:
            print("ADVERTENCIA: No se pudo detectar el DPI. Usando valor por defecto (203).")
            return 203

    @staticmethod
    def convertir_html_a_imagen(html_string, ancho_mm, alto_mm, nombre_impresora):
        """
        Convierte un HTML a imagen, usando un ZOOM DINÁMICO que se ajusta
        al DPI de la impresora y al tamaño de la etiqueta.
        """
        try:
            ruta_imagen_temporal = os.path.join(tempfile.gettempdir(), f"label_generada_{uuid.uuid4().hex}.png")
            dpi = PrintService.obtener_dpi_impresora(nombre_impresora)
            
            ANCHO_REFERENCIA_MM = 100.0 
            escala_por_tamano = ancho_mm / ANCHO_REFERENCIA_MM
            zoom_factor = (dpi / 96.0) * escala_por_tamano
            
            pixel_width = int((ancho_mm / 25.4) * dpi)
            pixel_height = int((alto_mm / 25.4) * dpi)

            print(f"Generando imagen de {pixel_width}x{pixel_height}px con un zoom DINÁMICO de {zoom_factor:.2f}x...")
            
            options = {'width': pixel_width, 'height': pixel_height, 'disable-smart-width': '', 'encoding': "UTF-8", 'quality': 100, 'zoom': zoom_factor}
            config = get_imgkit_config()
            imgkit.from_string(html_string, ruta_imagen_temporal, options=options, config=config)
            
            print(f"Imagen adaptativa generada en: {ruta_imagen_temporal}")
            return ruta_imagen_temporal
        except Exception as e:
            raise RuntimeError(f"Error en el proceso de conversión de imagen adaptativa: {str(e)}")
        
    @staticmethod
    def imprimir_imagen(ruta_imagen, nombre_impresora, ancho_mm, alto_mm):
        """
        Imprime una imagen, forzando al driver de la impresora a usar un
        tamaño de papel personalizado y definido por el usuario para este trabajo.
        """
        print(f"Forzando impresión en '{nombre_impresora}' con tamaño {ancho_mm}x{alto_mm} mm...")
        hDC_handler = None
        try:
            h_printer = win32print.OpenPrinter(nombre_impresora)
            try:
                properties = win32print.GetPrinter(h_printer, 2)
                devmode = properties['pDevMode']
                devmode.PaperSize = 256 
                devmode.PaperWidth = int(ancho_mm * 10)
                devmode.PaperLength = int(alto_mm * 10)
                devmode.Fields |= win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH | win32con.DM_PAPERSIZE
                raw_hdc = win32gui.CreateDC("WINSPOOL", nombre_impresora, devmode)
                hDC_handler = win32ui.CreateDCFromHandle(raw_hdc)
            finally:
                win32print.ClosePrinter(h_printer)
        
            img = Image.open(ruta_imagen)
            printable_width = hDC_handler.GetDeviceCaps(win32con.HORZRES)
            printable_height = hDC_handler.GetDeviceCaps(win32con.VERTRES)

            hDC_handler.StartDoc(ruta_imagen)
            hDC_handler.StartPage()
            dib = ImageWin.Dib(img)
            dib.draw(hDC_handler.GetHandleOutput(), (0, 0, printable_width, printable_height))
            hDC_handler.EndPage()
            hDC_handler.EndDoc()
        
            print("Imagen enviada a la impresora con la configuración de papel personalizada.")
            return True
        except pywin_error as e:
            raise RuntimeError(f"Error de la API de Windows al imprimir: {e}")
        except Exception as e:
            raise RuntimeError(f"Error inesperado al imprimir imagen: {e}")
        finally:
            if hDC_handler:
                hDC_handler.DeleteDC()
