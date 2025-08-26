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
    
    # Método para validar el payload de la etiqueta #
    
    @staticmethod
    def generar_barcodes_base64(datos_producto):
        """Genera códigos de barras en memoria y los devuelve como strings Base64."""
        barcodes = {}
        try:
            if datos_producto.get('codigo_barras'):
                writer_options = {
                    'module_height': 4.0,  # Altura de barra reducida para mejor balance
                    'quiet_zone': 2.0,
                    'write_text': False  # El HTML renderizará el texto
                }
                writer = ImageWriter()
                ean = barcode.get_barcode_class('ean13')
                commercial_barcode = ean(datos_producto['codigo_barras'], writer=writer) 
                buffer_commercial = io.BytesIO()
                commercial_barcode.write(buffer_commercial, writer_options)
                b64_commercial = base64.b64encode(buffer_commercial.getvalue()).decode('utf-8')
                barcodes['commercial_barcode_base64'] = b64_commercial
        except Exception as e:
            raise RuntimeError(f"Error al generar código de barras: {str(e)}")
        return barcodes

    @staticmethod
    def imprimir_pdf_generico(ruta_pdf, nombre_impresora, ancho_mm, alto_mm):
        """
        Imprime un archivo PDF usando SumatraPDF, detectando automáticamente la
        orientación correcta (vertical u horizontal) y deshabilitando el escalado.
        """
        print(f"Intentando imprimir PDF en '{nombre_impresora}'...")

        # --- INICIO DEL CAMBIO: LÓGICA DE ORIENTACIÓN AUTOMÁTICA ---
        # Si el ancho es mayor o igual al alto, es una etiqueta horizontal (landscape).
        # De lo contrario, es vertical (portrait).
        if ancho_mm >= alto_mm:
            orientacion = "landscape"
        else:
            orientacion = "portrait"

        print(f"Orientación detectada para la etiqueta: {orientacion.upper()}")

        # Se construye el comando de configuración de impresión dinámicamente.
        print_settings = f"{orientacion},noscale"
        # --- FIN DEL CAMBIO ---

        for ruta_sumatra in RUTAS_SUMATRA:
            ruta_expandida = os.path.expanduser(ruta_sumatra)
            if os.path.exists(ruta_expandida):
                print(f"SumatraPDF encontrado en: {ruta_expandida}")

                comando = [
                    ruta_expandida,
                    "-print-to", nombre_impresora,
                    "-print-settings", print_settings, # <--- SE USA LA CONFIGURACIÓN DINÁMICA
                    "-silent",
                    "-exit-on-print",
                    ruta_pdf
                ]

                resultado = subprocess.run(
                    comando,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SUMATRA,
                    check=False
                )

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
        except Exception as e:
            # Si falla la detección, usamos 203 como un valor seguro para etiquetas
            print(f"ADVERTENCIA: No se pudo detectar el DPI. Usando valor por defecto (203). Error: {e}")
            return 203

    @staticmethod
    def convertir_html_a_imagen(html_string, ancho_mm, alto_mm, nombre_impresora):
        """
        Convierte un HTML a imagen, usando ZOOM para escalar el contenido
        y asegurar la proporción correcta del texto.
        """
        try:
            ruta_imagen_temporal = os.path.join(
                tempfile.gettempdir(),
                f"label_generada_{uuid.uuid4().hex}.png"
            )

            # Detectamos el DPI real de la impresora para el cálculo.
            dpi = PrintService.obtener_dpi_impresora(nombre_impresora)
            
            # wkhtmltoimage renderiza el contenido a 96 DPI por defecto.
            # Calculamos el factor de zoom necesario para escalar de 96 DPI al DPI de la impresora.
            zoom_factor = dpi / 96.0

            # Calculamos el tamaño del lienzo en píxeles usando el DPI de la impresora.
            pixel_width = int((ancho_mm / 25.4) * dpi)
            pixel_height = int((alto_mm / 25.4) * dpi)

            print(f"Generando imagen de {pixel_width}x{pixel_height}px con un zoom de {zoom_factor:.2f}x (DPI detectado: {dpi})...")
            
            options = {
                'width': pixel_width,
                'height': pixel_height,
                'disable-smart-width': '',
                'encoding': "UTF-8",
                'quality': 100,
                # --- LA LÍNEA CLAVE QUE RESUELVE TODO (versión compatible) ---
                'zoom': zoom_factor
            }

            config = get_imgkit_config()
            imgkit.from_string(html_string, ruta_imagen_temporal, options=options, config=config)
            
            print(f"Imagen adaptativa generada en: {ruta_imagen_temporal}")
            return ruta_imagen_temporal
        except Exception as e:
            raise RuntimeError(f"Error en el proceso de conversión de imagen adaptativa: {str(e)}")
        
    @staticmethod
    def imprimir_imagen(ruta_imagen, nombre_impresora):
        """
        Imprime una imagen, escalándola proporcionalmente y centrándola en el papel
        para evitar distorsiones.
        """
        print(f"Imprimiendo imagen '{ruta_imagen}' en '{nombre_impresora}' con escalado proporcional...")
        hDC = None
        memDC = None
        try:
            img = Image.open(ruta_imagen)
            img_width, img_height = img.size
            hDC = win32ui.CreateDC()
            hDC.CreatePrinterDC(nombre_impresora)
            printable_width = hDC.GetDeviceCaps(win32con.HORZRES)
            printable_height = hDC.GetDeviceCaps(win32con.VERTRES)
            scale_w = printable_width / img_width
            scale_h = printable_height / img_height
            scale = min(scale_w, scale_h)
            dest_width = int(img_width * scale)
            dest_height = int(img_height * scale)
            dest_x = (printable_width - dest_width) // 2
            dest_y = (printable_height - dest_height) // 2
            print(f"Destino en papel: {dest_width}x{dest_height}px en la posición ({dest_x},{dest_y})")
            memDC = hDC.CreateCompatibleDC()
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(hDC, img_width, img_height)
            memDC.SelectObject(saveBitMap)
            dib = ImageWin.Dib(img)
            dib.draw(memDC.GetHandleOutput(), (0, 0, img_width, img_height))
            hDC.StartDoc(ruta_imagen)
            hDC.StartPage()
            hDC.StretchBlt(
                (dest_x, dest_y), (dest_width, dest_height),
                memDC, (0, 0), (img_width, img_height),
                win32con.SRCCOPY
            )
            hDC.EndPage()
            hDC.EndDoc()
            print("Imagen escalada proporcionalmente y enviada a la impresora.")
            return True
        except pywin_error as e:
            raise RuntimeError(f"Error de la API de Windows al imprimir: {e}")
        except Exception as e:
            raise RuntimeError(f"Error inesperado al imprimir imagen: {e}")
        finally:
            if 'saveBitMap' in locals() and saveBitMap.GetHandle() != 0:
                win32gui.DeleteObject(saveBitMap.GetHandle())
            if memDC:
                memDC.DeleteDC()
            if hDC:
                hDC.DeleteDC()
