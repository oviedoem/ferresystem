---
name: ui-ux-pro-max
description: Checklist de calidad UX/UI para que el panel Ferretería Oviedo se vea ordenado y profesional, no genérico ni improvisado. Úsala como capa final de revisión SIEMPRE que se entregue una propuesta visual o un cambio de diseño ya implementado — antes de darlo por terminado, pasar esta lista. Se aplica junto con web-design-guidelines y animate-app, no las reemplaza.
---

# UX/UI Pro — checklist final

Esta skill no define un estilo nuevo: es el filtro de calidad que se pasa DESPUÉS de aplicar `web-design-guidelines` y `animate-app`, antes de decir que una propuesta está lista.

## Checklist de orden visual

- [ ] **Un solo componente por función.** Si hay más de una clase CSS haciendo lo mismo (ej. `stat-icon`, `notif-icon`, `tc-icon`, `tut-icon`, `red-icon`, `mejora-card-icon` — todos "chip con emoji"), la propuesta debe converger a un único componente (`.tag`), no agregar una variante más.
- [ ] **Tamaños consistentes por nivel jerárquico**, no por sección. Nivel 1 = un tamaño. Nivel 2/3 = otro. Nunca "cada card decide su propio tamaño de ícono".
- [ ] **Un color = un significado**, fijo en todo el panel. Rojo (`--naranja`/`#DA0000`) = marca/alerta crítica real (quiebre de stock), no "cualquier cosa activa". Si el color de "activo" varía según el grupo, debe quedar explícito y documentado (ver tabla de colores por grupo en `web-design-guidelines`).
- [ ] **Espaciado en escala**, no valores sueltos. Usar una progresión simple (4/6/8/10/12/14/16/20px) en vez de mezclar `padding:9px 16px` en un botón y `padding:14px` en el de al lado sin motivo.
- [ ] **Jerarquía tipográfica clara**: tamaño/peso decrece de forma predecible (ej. 18/14/12.5/11/10px), no valores arbitrarios por componente.

## Checklist de "no genérico"

- [ ] La propuesta usa al menos un elemento anclado en el negocio real (ferretería: etiquetas de herramienta, bodega, cinta de peligro), no solo un patrón de dashboard SaaS genérico.
- [ ] Si se usó una paleta cálida tipo "crema + acento terracota" (`#F4F1EA` + naranja quemado), revisar dos veces — es el default más común en diseño generado por IA y puede no distinguirse de cualquier otra propuesta genérica.
- [ ] Cada decisión de color/forma tiene una razón de negocio articulable en una frase (ej. "el ojal cambia de color por grupo para no perderse en un sidebar de 9 acordeones"), no solo "se ve mejor".

## Checklist de profesionalismo funcional

- [ ] Funciona igual de bien en el ancho angosto de un celular (los paneles se usan en Android de vendedores) como en desktop.
- [ ] Ningún cambio visual rompe algo que ya distingue estados reales del negocio (ej. no eliminar el rojo fijo de "Quiebre" solo por unificar colores — esa alerta debe seguir gritando).
- [ ] Se explicita qué queda **fuera de alcance** (pastillas de filtro, sub-tabs duplicados, etc.) — una propuesta "completa" también es la que dice con claridad qué no tocó y por qué.
- [ ] El texto de la propuesta declara el alcance SCP exacto (qué `<style>`/`<button>` se tocan) para que se pueda pasar directo a Claude Code con `/revisar-codigo` sin ambigüedad.

## Señal de alerta (parar y reconsiderar)

Si al revisar la propuesta contra esta lista aparecen 2+ ítems sin marcar, no está lista para enviarse — falta una pasada más de orden antes de mostrarla.
