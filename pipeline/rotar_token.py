"""
rotar_token.py — Mitigación de seguridad genérica (sin Storage/Blaze).

Basado en rotar_token_data.py de Ferretería Oviedo. Mueve los JSON
sensibles de data/{tenant_id}/ a una subcarpeta data/{tenant_id}/<token>/
con nombre aleatorio nuevo en cada corrida, borra la carpeta del token
anterior, y publica el token vigente en Firestore (dataAccessToken/current)
protegido por firestore.rules (solo admin/vendedor autenticados pueden
leerlo).

Por qué: data/*.json queda público en Firebase Hosting con ruta fija y
visible en el código fuente de panel-admin.html si no se rota — cualquiera
lo descarga sin login. Esto no es auth real a nivel HTTP (Hosting sigue
sirviendo estático), pero cierra el escaneo casual y la exposición por
código fuente: la URL ya no es fija ni adivinable.

ARCHIVOS_SENSIBLES y el archivo público (no rotado) son específicos de
cada tenant — vienen de tenants/{tenant_id}.json -> "seguridad", nunca
hardcodeados aquí.

Requiere: ruta a la clave de servicio Firebase, también definida en el
tenant (tenants/{tenant_id}.json -> "firebase" -> "service_account_path").

Uso: python rotar_token.py <tenant_id>
"""
import os
import json
import shutil
import secrets
from datetime import datetime, timedelta, timezone

# TODO: import firebase_admin solo cuando se complete la implementación
# import firebase_admin
# from firebase_admin import credentials, firestore

TOKEN_TTL_HORAS_DEFAULT = 8


def cargar_config_seguridad(tenant_id: str) -> dict:
    """TODO: leer tenants/{tenant_id}.json -> 'seguridad' con:
    archivos_sensibles (list), service_account_path, ttl_token_horas."""
    raise NotImplementedError


def main(tenant_id: str):
    # TODO: adaptar la lógica de Oviedo:
    # 1. cargar_config_seguridad(tenant_id)
    # 2. leer data/{tenant_id}/.token-actual (token anterior)
    # 3. generar token_nuevo = secrets.token_hex(16)
    # 4. mover ARCHIVOS_SENSIBLES a data/{tenant_id}/{token_nuevo}/
    # 5. publicar en Firestore dataAccessToken/current (con TTL)
    # 6. escribir .token-actual y borrar carpeta del token anterior
    raise NotImplementedError


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Uso: python rotar_token.py <tenant_id>')
        sys.exit(1)
    main(sys.argv[1])
