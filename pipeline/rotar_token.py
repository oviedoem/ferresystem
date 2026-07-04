"""
rotar_token.py — Mitigación de seguridad genérica (sin Storage/Blaze).

Migrado desde rotar_token_data.py de Ferretería Oviedo. Mueve los JSON
sensibles de un tenant a una subcarpeta con nombre aleatorio nuevo en cada
corrida, borra la carpeta del token anterior, y publica el token vigente
en Firestore (dataAccessToken/current), protegido por firestore.rules
(solo roles autenticados pueden leerlo).

Por qué: los JSON de datos quedan públicos en Firebase Hosting con ruta
fija si no se rotan — cualquiera los descarga sin login viendo el código
fuente del panel. Esto no es auth real a nivel HTTP (Hosting sigue
sirviendo estático), pero cierra el escaneo casual y la exposición por
código fuente: la URL ya no es fija ni adivinable.

Todo lo específico de cliente (qué archivos son sensibles, dónde está la
clave de servicio Firebase, TTL del token) viene en tenant_config — nunca
hardcodeado en este módulo.

tenant_config esperado (subconjunto de tenants/{id}.json):
    {
      'data_dir': 'E:/.../data/{tenant_id}',
      'archivos_sensibles': ['ventas.json', 'stock.json', ...],
      'service_account_path': 'E:/config/{tenant_id}-service-account.json',
      'ttl_token_horas': 8,   # opcional, default 8
    }
"""
import os
import json
import shutil
import secrets
from datetime import datetime, timedelta, timezone


def rotar_token(tenant_config: dict) -> str:
    """Rota el token de acceso a los archivos sensibles de un tenant.

    Mueve cada archivo de tenant_config['archivos_sensibles'] desde
    data_dir/ a data_dir/{token_nuevo}/, publica el token en Firestore
    (dataAccessToken/current) y borra la carpeta del token anterior.

    Devuelve el token nuevo (str, 32 chars hex).
    """
    import firebase_admin
    from firebase_admin import credentials, firestore

    data_dir = tenant_config['data_dir']
    archivos_sensibles = tenant_config['archivos_sensibles']
    service_account_path = tenant_config['service_account_path']
    ttl_horas = tenant_config.get('ttl_token_horas', 8)

    if not os.path.isfile(service_account_path):
        raise FileNotFoundError('No existe la clave de servicio en ' + service_account_path)

    marker_file = os.path.join(data_dir, '.token-actual')
    token_anterior = None
    if os.path.isfile(marker_file):
        with open(marker_file, 'r') as f:
            token_anterior = f.read().strip()

    token_nuevo = secrets.token_hex(16)  # 32 chars hex, no adivinable
    carpeta_nueva = os.path.join(data_dir, token_nuevo)
    os.makedirs(carpeta_nueva, exist_ok=True)

    movidos, faltantes = 0, []
    for nombre in archivos_sensibles:
        origen = os.path.join(data_dir, nombre)
        if not os.path.isfile(origen):
            faltantes.append(nombre)
            continue
        shutil.copy2(origen, os.path.join(carpeta_nueva, nombre))
        os.remove(origen)
        movidos += 1

    print('[OK] %d archivos movidos a %s' % (movidos, carpeta_nueva))
    if faltantes:
        print('[AVISO] no encontrados (omitidos):', ', '.join(faltantes))

    cred = credentials.Certificate(service_account_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    expira = datetime.now(timezone.utc) + timedelta(hours=ttl_horas)
    db.collection('dataAccessToken').document('current').set({
        'token': token_nuevo,
        'actualizado': firestore.SERVER_TIMESTAMP,
        'expires_at': expira,
    })
    print('[OK] Firestore dataAccessToken/current actualizado (expira en %dh)' % ttl_horas)

    with open(marker_file, 'w') as f:
        f.write(token_nuevo)

    if token_anterior and token_anterior != token_nuevo:
        carpeta_anterior = os.path.join(data_dir, token_anterior)
        if os.path.isdir(carpeta_anterior):
            shutil.rmtree(carpeta_anterior)
            print('[OK] Carpeta anterior borrada: ' + carpeta_anterior)

    return token_nuevo


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Uso: python rotar_token.py <tenant_config.json>')
        sys.exit(1)
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        _config = json.load(f)
    rotar_token(_config)
