"""
validator.py — Validador post-pipeline genérico (solo lectura).

Migrado desde validar_jsons.py de Ferretería Oviedo: corre entre la
generación de JSONs y rotar_token.py / deploy. Si algún JSON de salida
quedó roto, vacío o a medio generar, bloquea el deploy ANTES de publicar
datos inconsistentes.

No escribe ni modifica ningún JSON. Solo lee y valida.

A diferencia del original, el esquema (qué archivos existen y qué forma
deben tener) no está hardcodeado: se recibe como parámetro. Cada tenant
declara su propio schema (típicamente en tenants/{id}.json -> "validacion"
o en un archivo aparte) y lo pasa a validar_pipeline().

Formato de schema (dict, clave = nombre de archivo dentro de output_dir):
    {
      'nombre.json': {
          'kind': 'wrapped' | 'raw_dict' | 'raw_list',
          'keys': [...],            # solo 'wrapped': claves raíz obligatorias
          'array_field': 'campo',   # opcional en 'wrapped': debe ser lista/dict no vacío
          'optional': True,         # si falta el archivo, se omite en vez de fallar
      },
      ...
    }
"""
import json
import os


def _contar(valor):
    if isinstance(valor, list):
        return len(valor)
    if isinstance(valor, dict):
        return len(valor)
    return None


def _validar_archivo(ruta, spec):
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
        faltantes = [k for k in spec.get('keys', []) if k not in data]
        if faltantes:
            return False, 'FALTAN CLAVES ' + str(faltantes) + ' en: ' + ruta

        array_field = spec.get('array_field')
        if array_field:
            cnt = _contar(data.get(array_field))
            if cnt is None:
                return False, 'CAMPO "' + array_field + '" no es lista/objeto en: ' + ruta
            if cnt < 1:
                return False, 'CAMPO "' + array_field + '" VACIO en: ' + ruta
            return True, str(cnt) + ' registros'

        return True, 'OK (sin campo de conteo)'

    return False, 'KIND DESCONOCIDO EN SCHEMA: ' + str(kind)


def validar_pipeline(output_dir: str, schema: dict) -> bool:
    """Valida todos los archivos declarados en schema dentro de output_dir.

    Imprime un resumen [OK]/[ERROR]/[OMITIDO] por archivo y un veredicto
    final. Devuelve True si no hubo errores (OMITIDOs no cuentan como
    error), False si al menos un archivo falló la validación.
    """
    print('=' * 60)
    print('VALIDACION POST-PIPELINE DE JSONs')
    print('=' * 60)

    errores = []
    resumen = []

    for nombre, spec in schema.items():
        ruta = os.path.join(output_dir, nombre)
        ok, msg = _validar_archivo(ruta, spec)
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
        return False

    print('RESULTADO: OK -- todos los JSONs validados correctamente')
    print('=' * 60)
    return True


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Uso: python validator.py <output_dir> <schema_json>')
        sys.exit(1)
    with open(sys.argv[2], 'r', encoding='utf-8') as f:
        _schema = json.load(f)
    sys.exit(0 if validar_pipeline(sys.argv[1], _schema) else 1)
