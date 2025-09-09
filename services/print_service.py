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
    
    # Método para validar el payload de la etiqueta #
    
    @staticmethod
    def generar_barcodes_base64(datos_producto):
        """Genera códigos de barras en memoria y los devuelve como strings Base64 de una imagen PNG."""
        barcodes = {}
        try:
            if datos_producto.get('codigo_barras'):
                writer = ImageWriter()
                ean = barcode.get_barcode_class('ean13')
                
                # --- INICIO DE LA CORRECCIÓN CLAVE ---
                # Añadimos opciones para controlar el tamaño de la imagen generada
                writer_options = {
                    "write_text": False,
                    "module_height": 5.0  # <-- VALOR CLAVE: Reduce la altura de las barras
                }
                # --- FIN DE LA CORRECCIÓN CLAVE ---

                commercial_barcode = ean(datos_producto['codigo_barras'], writer=writer) 
                
                buffer_commercial = io.BytesIO()
                # Pasamos las nuevas opciones al método write
                commercial_barcode.write(buffer_commercial, writer_options)
                
                b64_commercial = base64.b64encode(buffer_commercial.getvalue()).decode('utf-8')
                barcodes['commercial_barcode_base64'] = b64_commercial
        except Exception as e:
            raise RuntimeError(f"Error al generar código de barras PNG: {str(e)}")
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
        Escanea el sistema en busca de impresoras listas y obtiene su
        configuración de papel predeterminada (ancho y alto).
        """
        print("Escaneando impresoras listas y su configuración de papel...")
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            impresoras_detalladas = []

            for printer in c.Win32_Printer():
                # Usamos los mismos filtros que ya tenías para impresoras listas
                es_fisicamente_online = (printer.PrinterState & 16) == 0
                esta_lista_para_imprimir = printer.PrinterStatus == 3

                if es_fisicamente_online and esta_lista_para_imprimir:
                    ancho_mm = None
                    alto_mm = None
                
                    # --- INICIO DE LA LÓGICA PARA OBTENER TAMAÑO DE PAPEL ---
                    try:
                        # Abrimos la impresora para obtener un "handle" o manejador
                        h_printer = win32print.OpenPrinter(printer.Name)
                        try:
                            # Obtenemos las propiedades de la impresora (nivel 2 para DEVMODE)
                            properties = win32print.GetPrinter(h_printer, 2)
                            devmode = properties['pDevMode']
                        
                            # Los valores en DEVMODE vienen en décimas de milímetro,
                            # los convertimos a mm dividiendo por 10.
                            if devmode.PaperWidth > 0 and devmode.PaperLength > 0:
                                ancho_mm = devmode.PaperWidth / 10.0
                                alto_mm = devmode.PaperLength / 10.0
                        finally:
                            # Es crucial cerrar el manejador de la impresora
                            win32print.ClosePrinter(h_printer)
                    except pywin_error as e:
                        print(f"ADVERTENCIA: No se pudo obtener el tamaño de papel para '{printer.Name}'. Error: {e}")
                    # --- FIN DE LA LÓGICA ---

                    printer_info = {
                        "name": printer.Name,
                        "port": printer.PortName,
                        "ancho_mm": ancho_mm, # <-- NUEVO CAMPO CON EL ANCHO
                        "alto_mm": alto_mm    # <-- NUEVO CAMPO CON EL ALTO
                    }
                    print(f"Impresora lista encontrada: {printer_info}")
                    impresoras_detalladas.append(printer_info)

            return impresoras_detalladas
    
        except Exception as e:
            print(f"ERROR al escanear impresoras: {e}")
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
        Convierte un HTML a imagen, usando un ZOOM DINÁMICO que se ajusta
        al DPI de la impresora y al tamaño de la etiqueta.
        """
        try:
            ruta_imagen_temporal = os.path.join(
                tempfile.gettempdir(),
                f"label_generada_{uuid.uuid4().hex}.png"
            )

            dpi = PrintService.obtener_dpi_impresora(nombre_impresora)
            
            # --- INICIO DE LA LÓGICA DE ZOOM DINÁMICO ---
            
            # Definimos un ancho de etiqueta "ideal" o de referencia (en mm)
            # para el cual nuestro diseño HTML con fuentes grandes se ve bien.
            ANCHO_REFERENCIA_MM = 100.0 
            
            # Calculamos un factor de escala basado en el tamaño real de la etiqueta.
            # Si la etiqueta es más pequeña que la referencia, este valor será < 1.
            # Si es más grande, será > 1.
            escala_por_tamano = ancho_mm / ANCHO_REFERENCIA_MM

            # Calculamos el zoom final combinando la corrección de DPI y la escala por tamaño.
            # Esto hace que el zoom se achique para etiquetas pequeñas y se agrande para las grandes.
            zoom_factor = (dpi / 96.0) * escala_por_tamano
            
            # --- FIN DE LA LÓGICA DE ZOOM DINÁMICO ---

            pixel_width = int((ancho_mm / 25.4) * dpi)
            pixel_height = int((alto_mm / 25.4) * dpi)

            print(f"Generando imagen de {pixel_width}x{pixel_height}px con un zoom DINÁMICO de {zoom_factor:.2f}x...")
            
            options = {
                'width': pixel_width,
                'height': pixel_height,
                'disable-smart-width': '',
                'encoding': "UTF-8",
                'quality': 100,
                'zoom': zoom_factor
            }

            config = get_imgkit_config()
            imgkit.from_string(html_string, ruta_imagen_temporal, options=options, config=config)
            
            print(f"Imagen adaptativa generada en: {ruta_imagen_temporal}")
            return ruta_imagen_temporal
        except Exception as e:
            raise RuntimeError(f"Error en el proceso de conversión de imagen adaptativa: {str(e)}")
        
    # print_service.py

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

                # --- INICIO DE LA MODIFICACIÓN CLAVE ---

                # 1. Se indica explícitamente al driver que el tamaño es personalizado.
                # El valor 256 (DMPAPER_USER) le dice que ignore los tamaños predefinidos.
                devmode.PaperSize = 256 

                # 2. Se establecen las dimensiones deseadas (en décimas de mm)
                devmode.PaperWidth = int(ancho_mm * 10)
                devmode.PaperLength = int(alto_mm * 10)
            
                # 3. Se actualizan los campos para que el driver sepa qué hemos cambiado.
                # Añadimos DM_PAPERSIZE a la lista.
                devmode.Fields = devmode.Fields | win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH | win32con.DM_PAPERSIZE

                # --- FIN DE LA MODIFICACIÓN CLAVE ---

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
