# -*- coding: utf-8 -*-
"""
Utilidades para verificar e instalar wkhtmltopdf/wkhtmltoimage en Windows
y para proporcionar una configuración compatible con imgkit.

Estrategia:
- Verificar si existen los binarios wkhtmltoimage y wkhtmltopdf en PATH o rutas conocidas.
- Si faltan en Windows, intentar instalación automática con winget; como respaldo, con Chocolatey si está disponible.
- Si no es posible instalarlos automáticamente, emitir un mensaje claro con la URL oficial.
- Exponer get_imgkit_config() para que imgkit use el binario detectado/instalado.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Optional, Tuple

# Rutas comunes de instalación en Windows
RUTAS_COMUNES = [
    r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltoimage.exe",
    r"C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltoimage.exe",
]

# Cache interno
_WKHTMLTOIMAGE_PATH: Optional[str] = None
_WKHTMLTOPDF_PATH: Optional[str] = None


def _es_windows() -> bool:
    return platform.system().lower().startswith("windows")


def _buscar_binarios() -> Tuple[Optional[str], Optional[str]]:
    """
    Busca wkhtmltoimage y wkhtmltopdf en PATH y en rutas comunes.
    """
    wkhtmltoimage = shutil.which("wkhtmltoimage")
    wkhtmltopdf = shutil.which("wkhtmltopdf")

    if not wkhtmltoimage:
        for ruta in RUTAS_COMUNES:
            if os.path.exists(ruta):
                wkhtmltoimage = ruta
                break

    # wkhtmltopdf suele estar en el mismo bin
    if not wkhtmltopdf:
        posibles = [
            r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
            r"C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        ]
        for ruta in posibles:
            if os.path.exists(ruta):
                wkhtmltopdf = ruta
                break

    return wkhtmltoimage, wkhtmltopdf


def _instalar_con_winget() -> bool:
    """Intenta instalar wkhtmltopdf usando winget (requiere Windows 10/11 y permisos)."""
    winget = shutil.which("winget")
    if not winget:
        return False
    try:
        # ID más común en winget
        cmd = [
            winget,
            "install",
            "-e",
            "--id",
            "wkhtmltopdf.wkhtmltopdf",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
        subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=600)
        return True
    except Exception:
        return False


def _instalar_con_choco() -> bool:
    """Intenta instalar wkhtmltopdf usando Chocolatey si está disponible."""
    choco = shutil.which("choco")
    if not choco:
        return False
    try:
        cmd = [choco, "install", "wkhtmltopdf", "-y"]
        subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=600)
        return True
    except Exception:
        return False


def ensure_wkhtml_installed() -> Tuple[Optional[str], Optional[str]]:
    """
    Asegura que wkhtmltoimage/wkhtmltopdf estén instalados en Windows.
    Devuelve las rutas detectadas si existen (wkhtmltoimage, wkhtmltopdf).

    Si no se logra instalar automáticamente, deja un mensaje claro en stdout
    para que el usuario lo instale manualmente.
    """
    global _WKHTMLTOIMAGE_PATH, _WKHTMLTOPDF_PATH

    # Si ya está cacheado, devolver
    if _WKHTMLTOIMAGE_PATH or _WKHTMLTOPDF_PATH:
        return _WKHTMLTOIMAGE_PATH, _WKHTMLTOPDF_PATH

    wkhtmltoimage, wkhtmltopdf = _buscar_binarios()

    if _es_windows() and not wkhtmltoimage:
        print("wkhtmltoimage no encontrado. Intentando instalación automática en Windows…")

        instalado = _instalar_con_winget()
        if not instalado:
            print("No se pudo instalar con winget o no está disponible. Intentando con Chocolatey…")
            instalado = _instalar_con_choco()

        # Reintentar detección tras la (posible) instalación
        wkhtmltoimage, wkhtmltopdf = _buscar_binarios()

        if not wkhtmltoimage:
            # Mensaje requerido por el usuario/IMGKit
            print("Otherwise please install wkhtmltopdf - http://wkhtmltopdf.org")
            print(
                "No fue posible instalar wkhtmltopdf automáticamente. "
                "Instálalo manualmente y asegúrate de que 'wkhtmltoimage.exe' esté en PATH."
            )

    _WKHTMLTOIMAGE_PATH = wkhtmltoimage
    _WKHTMLTOPDF_PATH = wkhtmltopdf
    return wkhtmltoimage, wkhtmltopdf


def get_imgkit_config():
    """
    Devuelve una configuración de imgkit que apunta al binario wkhtmltoimage (si existe).
    """
    try:
        import imgkit  # import local para no forzar dependencia si no se usa
    except Exception:
        return None

    wkhtmltoimage, _ = ensure_wkhtml_installed()
    if wkhtmltoimage:
        try:
            return imgkit.config(wkhtmltoimage=wkhtmltoimage)
        except Exception:
            return None
    return None

