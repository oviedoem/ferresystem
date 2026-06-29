"""
validator.py — Validador post-pipeline genérico (solo lectura).

Basado en validar_jsons.py de Ferretería Oviedo. Corre entre la generación
de JSONs (generar_jsons.py) y rotar_token.py / deploy. Si algún JSON de
salida quedó roto, vacío o a medio generar, bloquea el deploy con exit(1)
ANTES de publicar datos inconsistentes.

No escribe ni modifica ningún JSON. Solo lee y valida.

El esquema (SCHEMA) ya no es fijo por cliente: cada tenant puede declarar
su propio esquema en tenants/{tenant_id}.json -> "validacion", o usar un
esquema genérico mínimo (raw_dict/raw_list/wrapped) por archivo.

Uso: python validator.py <ruta_data_dir> <ruta_schema_json>
"""
import json
import os
import sys


def contar(valor):
    if isinstance(valor, list):
        return len(valor)
    if isinstance(valor, dict):
        return len(valor)
    return None


def validar_archivo(nombre, spec, base_dir):
    ruta = os.path.join(spec.get('dir', base_dir), nombre)

    if not os.path.isfile(ruta):
        if spec.get('optional'):
            return None, 'OMITIDO (opcional, no generado en esta corrida)'
        return False, 'NO EXISTE: ' + ruta

    if os.path.getsize(ruta) == 0:
        return False, 'ARCHIVO VACIO (0 bytes): ' + ruta

    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, 'JSON INVALIDO (' + str(e) + '): ' + ruta
    except Exception as e:
        return False, 'ERROR AL LEER (' + str(e) + '): ' + ruta

    kind = spec['kind']

    if kind == 'raw_list':
        if not isinstance(data, list):
            return False, 'SE ESPERABA UNA LISTA en la raiz: ' + ruta
        if len(data) < 1:
            return False, 'LISTA VACIA: ' + ruta
        return True, str(len(data)) + ' registros'

    if kind == 'raw_dict':
        if not isinstance(data, dict):
            return False, 'SE ESPERABA UN OBJETO en la raiz: ' + ruta
        if len(data) < 1:
            return False, 'OBJETO VACIO: ' + ruta
        return True, str(len(data)) + ' claves'

    if kind == 'wrapped':
        if not isinstance(data, dict):
            return False, 'SE ESPERABA UN OBJETO en la raiz: ' + ruta
        faltantes = [k for k in spec['keys'] if k not in data]
        if faltantes:
            return False, 'FALTAN CLAVES ' + str(faltantes) + ' en: ' + ruta

        array_field = spec.get('array_field')
        if array_field:
            cnt = contar(data.get(array_field))
            if cnt is None:
                return False, 'CAMPO "' + array_field + '" no es lista/objeto en: ' + ruta
            if cnt < 1:
                return False, 'CAMPO "' + array_field + '" VACIO en: ' + ruta
            return True, str(cnt) + ' registros'

        return True, 'OK (sin campo de conteo)'

    return False, 'KIND DESCONOCIDO EN SCHEMA: ' + kind


def main():
    if len(sys.argv) < 3:
        print('Uso: python validator.py <data_dir> <schema_json>')
        sys.exit(1)

    data_dir = sys.argv[1]
    schema_path = sys.argv[2]

    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)

    print('=' * 60)
    print('VALIDACION POST-PIPELINE DE JSONs')
    print('=' * 60)

    errores = []
    resumen = []

    for nombre, spec in schema.items():
        ok, msg = validar_archivo(nombre, spec, data_dir)
        if ok is None:
            resumen.append((nombre, 'OMITIDO', msg))
        elif ok:
            resumen.append((nombre, 'OK', msg))
        else:
            resumen.append((nombre, 'ERROR', msg))
            errores.append(nombre + ': ' + msg)

    print('')
    for nombre, estado, msg in resumen:
        print('[' + estado + '] ' + nombre + ' - ' + msg)

    print('')
    print('=' * 60)

    if errores:
        print('RESULTADO: BLOQUEADO -- ' + str(len(errores)) + ' archivo(s) con error')
        print('=' * 60)
        for e in errores:
            print('  - ' + e)
        sys.exit(1)

    print('RESULTADO: OK -- todos los JSONs validados correctamente')
    print('=' * 60)
    sys.exit(0)


if __name__ == '__main__':
    main()
