"""Adaptadores de fuentes externas.

Cada fuente devuelve estructuras normalizadas y nunca toca la base de datos.
Un cuerpo inválido lanza ``InvalidSourcePayload`` para que el pipeline conserve
lo ya almacenado.
"""
