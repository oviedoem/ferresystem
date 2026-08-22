# CRITERIO.md — Motor FerreSystem
# El "cerebro" del agente: criterios de decisión antes de ejecutar.
# Este archivo dice POR QUÉ y CUÁNDO — CLAUDE.md dice CÓMO.

## QUÉ ES ESTE ARCHIVO

`CLAUDE.md` describe instrucciones técnicas y procedimientos.
Este archivo describe los **criterios de juicio** que el agente aplica cuando hay una decisión que tomar —
no una instrucción exacta que seguir.

Antes de ejecutar cualquier tarea no trivial, el agente pasa este filtro.

---

## JERARQUÍA DE DECISIÓN

En orden de prioridad. Si hay conflicto, gana el nivel más alto:

1. **Seguridad de datos** — ningún dato real de cliente llega a git ni a código motor
2. **No romper producción** — si algo funciona, mejora encima; nunca reescribe
3. **Separación motor/cliente** — `core/` ignora qué cliente existe
4. **Un cambio a la vez** — un prompt = una función; nunca agregar scope no pedido
5. **Economía de tokens** — leer lo mínimo necesario; no explorar sin dirección

---

## CRITERIOS DE ACEPTACIÓN DE UN CAMBIO

Antes de proponer o ejecutar cualquier cambio, confirmar:

| Criterio | Pregunta |
|---|---|
| **Alcance mínimo** | ¿Este cambio hace SOLO lo que se pidió? |
| **No rompe nada** | ¿Hay función existente que dependa de lo que voy a modificar? |
| **Dato de cliente protegido** | ¿El cambio podría filtrar tenant_id, IP, credencial o bodega real? |
| **Reversible** | ¿Se puede deshacer con un `git revert` si falla? |
| **Documentado** | ¿Hay que actualizar CLAUDE.md, docs/ o ejemplo_tenant.json? |

Si alguno falla → declarar el problema antes de ejecutar, no ignorar y seguir.

---

## CUÁNDO DECIR NO SIN PREGUNTAR

- Hardcodear datos de cliente en `core/`, `adapters/`, `paneles/`
- Commitear archivos reales de tenants (solo `tenants/ejemplo_tenant.json`)
- Modificar `pipeline_runner.py`, `json_writer.py` o `validator.py` sin declarar alcance completo
- Agregar features no pedidos ("ya que estoy, también agregué...")
- Reescribir código que funciona en producción

---

## CUÁNDO PEDIR CONFIRMACIÓN

- El cambio afecta a más de un tenant (todos los clientes, no solo el del pedido)
- La modificación toca un archivo de `core/` que no fue mencionado en el pedido
- El alcance del pedido es ambiguo y hay 2+ interpretaciones válidas
- Se detecta deuda técnica mayor al hacer el cambio — documentarla, no arreglarla sin permiso

---

## FILOSOFÍA DE FONDO

**Motor genérico primero, cliente después.**

`ferresystem` es una herramienta que funciona para cualquier ferretería.
Ferretería Oviedo es el primer inquilino — no el dueño del motor.

Cada decisión de diseño pasa este filtro:
> ¿Esto sirve para cualquier ferretería, o solo para Oviedo?

Si sirve solo para Oviedo → va en `tenants/oviedo.json`, no en `core/`.
Si sirve para cualquier cliente → va en `core/` o `adapters/`.

**La generalidad del motor es su principal activo.**
Un motor que solo funciona para un cliente no es un motor — es un script de cliente.
