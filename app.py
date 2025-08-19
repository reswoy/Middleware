# -*- coding: utf-8 -*-

"""
Factory para crear la aplicación Flask.
Configura la aplicación y registra los blueprints.
"""

from flask import Flask

from routes import main_bp


def crear_app():
    """
    Factory function para crear y configurar la aplicación Flask.
    
    Returns:
        Flask: Instancia configurada de la aplicación
    """
    # Crear instancia de Flask
    app = Flask(__name__)
    
    # Registrar blueprints
    app.register_blueprint(main_bp)

    return app
