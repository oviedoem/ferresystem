---
name: animate-app
description: Reglas de animación y micro-interacciones para los paneles del proyecto Ferretería Oviedo. Úsala siempre que se pida que el panel "se sienta vivo", "más profesional", "con transiciones", o al agregar/mejorar hover, estados activos, entrada de tarjetas, carruseles o cualquier movimiento en la interfaz. Aplica junto con web-design-guidelines, nunca sola — el motion viste al sistema visual, no lo reemplaza.
---

# Animación — Ferretería Oviedo

Vanilla JS/CSS, sin librerías de animación externas (no GSAP, no Framer). Todo con CSS transitions/animations y, cuando haga falta lógica de trigger, JS mínimo sin dependencias nuevas.

## Regla de oro

Motion con criterio, no decorativo. Cada animación debe responder una pregunta: ¿ordena la lectura, confirma una acción, o da feedback de estado? Si no responde ninguna, no se agrega. Un panel de gestión de bodega/ventas no es una landing — el exceso de movimiento distrae a alguien que está tratando de encontrar un dato rápido.

## Patrones aprobados (reutilizar, no inventar nuevos por defecto)

**Entrada escalonada de tarjetas/grupos** (al cargar una tab):
```css
.card{opacity:0;transform:translateY(10px);animation:rise .5s cubic-bezier(.22,1,.36,1) forwards}
.card:nth-child(1){animation-delay:.02s}
.card:nth-child(2){animation-delay:.07s}
/* +.05s por cada hijo siguiente */
@keyframes rise{to{opacity:1;transform:translateY(0)}}
```
Se dispara una sola vez al mostrar la sección, nunca se repite en cada clic dentro de la misma vista.

**Hover de ícono tipo "etiqueta colgando"**:
```css
.tag{transition:transform .35s cubic-bezier(.22,1,.36,1)}
.card:hover .tag{transform:rotate(-4deg) translateY(-1px) scale(1.04)}
```

**Subrayado deslizante en sub-pestañas** (reemplaza el `border-bottom` estático):
```css
.subtab::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:var(--gcolor);transform:scaleX(0);transform-origin:left;transition:transform .3s cubic-bezier(.22,1,.36,1)}
.subtab.on::after{transform:scaleX(1)}
```

**Transición de estado activo** (color/fondo, no solo posición):
```css
transition:background .25s ease, border-color .25s ease, stroke .25s ease;
```

## Accesibilidad — obligatorio en cada bloque de animación

Siempre incluir el bloque de reduced-motion junto con cualquier animación nueva:
```css
@media (prefers-reduced-motion: reduce){
  .card{animation:none;opacity:1;transform:none}
  .tag{transition:none}
  .card:hover .tag{transform:none}
}
```
No es opcional. Si se agrega una animación sin este bloque, la revisión de código debe rechazarla.

## Límites de duración

- Micro-interacciones (hover, focus): 150-250ms.
- Transiciones de estado (activo/inactivo): 250-350ms.
- Entrada de contenido (tarjetas, listas): 400-600ms, con stagger de 40-60ms entre elementos.
- Nunca superar ~700ms para una animación de UI de gestión — se siente lento cuando alguien repite la misma acción muchas veces al día (ej. un vendedor cambiando de tab constantemente).

## Qué NO animar

- Datos que cambian por polling/refresh automático (evita parpadeo constante que distrae).
- Números en `stat-val` al actualizarse — mejor un fade corto (150ms) que un contador animado, que es más costoso y no aporta en un panel de trabajo.
- Cualquier animación dentro de una fila de tabla con muchos registros (`.tbl`) — el costo de repintado no vale la pena con 6.000+ productos.

## Scope SCP

Los cambios de animación son solo CSS (+ a lo sumo clases toggle en JS si el trigger lo requiere). Nunca deben tocar la lógica de datos, `onclick` existentes, ni el orden de renderizado de `showTab`/`vadmSubTab`. Declarar explícitamente en el prompt qué selectores CSS se agregan.
