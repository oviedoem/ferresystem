---
name: web-design-guidelines
description: Guía de diseño visual para los 3 paneles del proyecto Ferretería Oviedo (panel-admin.html, panel-cliente.html, panel-empleado.html). Úsala SIEMPRE que se pida rediseñar, mejorar, unificar o crear iconos, tarjetas, botones, menús, tabs o cualquier elemento visual del panel — incluso si el usuario solo dice "mejora el diseño" o "se ve feo". No aplica a lógica de negocio, Firestore, pipelines de datos ni JS de flujo (para eso ver AGENTS.md y las skills de Safe Change Protocol del proyecto).
---

# Guía de diseño web — Ferretería Oviedo

Vanilla JS, sin frameworks. Todo el diseño vive en `<style>` inline dentro de cada panel HTML. Esta guía fija el lenguaje visual para que cada mejora de diseño sea consistente con las anteriores, no un parche aislado.

## Principio rector

Este es un panel de gestión para una ferretería real (bodegas, vendedores, ERP), no una landing genérica. Las decisiones visuales deben sentirse ancladas en ese mundo (herramientas, etiquetas de precio, bodega) y no en el default genérico de "dashboard SaaS" o "blog minimalista con acento cálido". Antes de proponer una paleta o forma nueva, pregúntate: ¿esto podría ser el diseño de cualquier panel admin, o se nota que es de una ferretería?

## Tokens de color existentes (no duplicar, reutilizar)

```
--naranja:#DA0000   (marca principal — pese al nombre, es rojo)
--naranja2:#c93a08
--dark:#111827
--gris:#6b7280
--verde:#059669
--rojo:#dc2626
--azul:#2563eb
--amarillo:#d97706
--border:#e5e7eb
```

Tokens agregados en las propuestas de iconos (julio 2026), disponibles para reutilizar en futuras mejoras visuales:

```
--graphite:#20232A / #23262B   (trazo de ícono, texto de etiqueta)
--kraft:#E7D9BD / #EBDFC6      (relleno tipo cartulina de etiqueta de herramienta)
--kraft-edge:#C9B48C           (borde de la etiqueta)
--brass:#A97C3F                (ojal/rivet — acento del grupo "Ventas")
--teal:#0f766e                 (acento del grupo "Árbol Retail")
--slate:#475569                (acento del grupo "Adquisiciones")
--hazard:#F2B705               (franja de alerta, SOLO para stock crítico/merma)
```

Regla: antes de inventar un color nuevo, revisar si alguno de estos ya cubre la necesidad. Si hace falta uno nuevo, que tenga una razón de negocio (ej. un color por grupo del sidebar), no solo estética.

## Sistema de iconos: "Etiqueta de herramienta"

Reemplaza el emoji suelto (que se ve distinto en cada dispositivo/SO — un problema real cuando el equipo usa Android, HP corporativo e iOS) por un componente único `.tag`:

- Forma: rectángulo redondeado con esquina en punta (`border-radius: 6px 11px 11px 6px`), no un círculo ni cuadrado genérico.
- Ojal perforado: círculo pequeño (4-5px) en la esquina superior izquierda, con anillo de color (`box-shadow`) — referencia a una etiqueta de precio real colgando de una herramienta.
- Tamaños: 40px (tarjetas/accesos destacados), 32-34px (sidebar nivel 1), 13-16px sin caja (sub-pestañas nivel 2/3, donde el espacio horizontal es limitado).
- Ícono interno: SVG de línea (stroke 2px, `currentColor` o color explícito), nunca emoji, para consistencia entre dispositivos.
- Estado activo: la etiqueta se "voltea" — fondo sólido del color del grupo/módulo, ícono en blanco. Esto reemplaza el patrón actual donde todo activo se pinta rojo sin importar la sección.
- Acento de alerta (cinta de peligro): reservado solo para íconos que señalan un problema real de bodega (quiebre, merma). No usar en el resto — pierde fuerza si se generaliza.

## Jerarquía de menús (aplica a los 3 paneles)

1. **Nivel 1 — sidebar/menú principal**: ítem con `.tag` completo (32-40px) + texto. Un color de acento por grupo/sección.
2. **Nivel 2/3 — sub-pestañas horizontales (`vadm-stab` y similares)**: glifo mini sin caja (13-16px) + subrayado de color en el estado activo. Nunca poner una caja de 32-40px aquí — rompe el layout en celular cuando hay 7-9 pestañas en una fila.
3. **Filtros tipo pastilla** (números, letras A/B/C/D, "Todos"): sin ícono. No forzar un glifo donde el contenido ya es autoexplicativo.

## Qué NO tocar al rediseñar solo iconos/estilo

- `onclick`, `id`, nombres de función (`showTab`, `vadmGrupo`, `vadmSubTab`, etc.)
- Cualquier lectura/escritura a Firestore o `localStorage`
- Estructura de datos o pipeline (`csv_a_json.py`, Datos-publico.json, etc.)

Declarar explícitamente el alcance en cada prompt SCP: "solo se toca el bloque `<style>` y el contenido interno (emoji→SVG) de los `<button>` de X sección".

## Antes de proponer, revisar

- ¿Ya existe un componente similar en el panel? (`tc-icon`, `mejora-card-icon`, `stat-icon`, `notif-icon`, `red-icon`, `tut-icon` — todos deben converger al mismo componente `.tag` con el tiempo, no seguir multiplicando variantes).
- ¿La propuesta resuelve un problema de uso real (ej. no distinguir en qué sección estás) o es solo decoración?
