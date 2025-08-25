# -*- coding: utf-8 -*-

"""
Utilidades de autenticación por API Key.
"""

from functools import wraps
from flask import request, jsonify
from config import API_KEY


def require_api_key(view_func):
    """Decorator que valida la cabecera X-API-KEY contra la API_KEY de config.

    - Si no hay API_KEY configurada, permite el acceso (modo abierto) pero advierte.
    - Si hay API_KEY configurada, exige coincidencia exacta con la cabecera X-API-KEY.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):

        provided = request.headers.get("X-API-KEY") or request.headers.get("Authorization")
        # Permitimos formato Authorization: Bearer <token>
        if provided and provided.lower().startswith("bearer "):
            provided = provided.split(" ", 1)[1]

        if not provided or provided.strip() != API_KEY:
            return jsonify({
                "success": False,
                "error": "No autorizado. Falta o es inválida la API Key.",
            }), 401

        return view_func(*args, **kwargs)

    return wrapper
