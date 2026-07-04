---
name: web-guidelines
description: Guías técnicas de la plataforma web (accesibilidad, performance, seguridad de front-end, PWA) para los paneles de Ferretería Oviedo — complementa a web-design-guidelines, que es solo visual. Úsala siempre que se toque HTML/JS que renderiza datos dinámicos (innerHTML, listas, tablas), formularios, el service worker, o cualquier cosa relacionada con cómo carga/funciona el sitio, no solo cómo se ve.
---

# Web Guidelines (técnico) — Ferretería Oviedo

Vanilla JS, PWA, sin frameworks ni build step. Estas reglas son sobre robustez y seguridad del front-end, no sobre estética (para eso ver `web-design-guidelines`).

## Seguridad en renderizado dinámico

El código arma mucho HTML por concatenación de strings (`'<div>'+variable+'</div>'`) para notificaciones, iconos dinámicos, listas de clientes, etc. Esto es un vector real de XSS si `variable` viene de un dato que un usuario pudo escribir (nombre de cliente, comentario, dirección).

- Cualquier dato que provenga de un input de usuario (no del catálogo fijo ni del ERP) debe pasar por un escape básico antes de insertarse vía `innerHTML` (reemplazar `<`, `>`, `&`, `"` como mínimo).
- Los iconos/emoji fijos definidos en el propio código (como los mapas `iconos={...}`) no son un riesgo — el riesgo está en nombres, direcciones, mensajes de WhatsApp guardados, etc.
- Al revisar código con `/revisar-codigo`, marcar como hallazgo cualquier `innerHTML` que incluya una variable de origen externo sin sanitizar.

## Datos públicos vs protegidos

Ya existe la arquitectura correcta (V37.28): `Datos-publico.json` sin precios, `precios/catalogo` protegido en Firestore. Al agregar cualquier campo nuevo al catálogo público, verificar explícitamente que no se esté filtrando precio, costo, margen ni datos de proveedor — ese es el error más caro posible en este proyecto.

## Service Worker / caché

- Cualquier cambio de asset (CSS/JS/HTML) requiere bump de versión en `sw.js` vía `update-sw-version.js` — si no, usuarios con la PWA instalada quedan con caché vieja indefinidamente.
- No cachear agresivamente `precios/catalogo` ni datos de sesión/autenticación.

## Accesibilidad mínima (aunque el público es interno/clientes, no gratis)

- Toda imagen de producto/banner necesita `alt` descriptivo, no vacío ni genérico ("imagen").
- Contraste mínimo AA (4.5:1) para texto sobre fondo — especialmente en los chips de color por categoría/estado, donde es fácil poner texto oscuro sobre un fondo pastel que no contrasta lo suficiente.
- Botones deben ser `<button>`, no `<div onclick>`, cuando sea posible — ya es el patrón dominante en el código, mantenerlo.

## Compatibilidad cross-browser real del proyecto

- iOS Safari: el clipboard requiere fallback vía `execCommand` (ya implementado) — cualquier función nueva de "copiar" debe replicar ese patrón, `navigator.clipboard` solo no basta.
- Android WebView / Chrome: verificar `inputmode` en campos numéricos y que el viewport no permita zoom accidental en inputs (`font-size` mínimo 16px en inputs evita el zoom automático de iOS).

## Performance con datos reales

- El catálogo tiene 6.000-9.000 productos y la base de clientes crece. Cualquier función nueva que itere sobre el catálogo completo en el cliente (no en el pipeline) debe evaluarse: ¿se puede paginar, filtrar en el servidor, o memoizar en vez de recorrer todo en cada render?
- Evitar agregar librerías o dependencias nuevas — el proyecto es deliberadamente vanilla para no aumentar peso de carga ni superficie de mantenimiento.

## Checklist antes de dar por cerrado un cambio técnico

- [ ] ¿Algún `innerHTML` nuevo inserta datos que un usuario pudo escribir, sin escapar?
- [ ] ¿Se subió la versión del service worker si se tocó CSS/JS/HTML servido?
- [ ] ¿Ningún campo nuevo del catálogo público expone precio/costo/margen?
- [ ] ¿Las imágenes nuevas tienen `alt`?
