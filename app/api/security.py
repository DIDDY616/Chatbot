"""Clave de administración.

Con ADMIN_TOKEN definido (en .env), las rutas de administración piden el encabezado
`X-Admin-Token` con esa clave. Las que usa la página del avatar (conversar, voz, perfiles y
personajes en lectura, valorar una respuesta) siguen abiertas, porque los estudiantes no
tienen clave.
"""
import hmac

from fastapi import Header, HTTPException

from .. import config

HEADER = "X-Admin-Token"


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected = config.ADMIN_TOKEN
    if not expected:
        return  # sin clave configurada: uso local
    if not x_admin_token or not hmac.compare_digest(x_admin_token.encode(), expected.encode()):
        raise HTTPException(401, "Falta la clave de administración o no es correcta.")
