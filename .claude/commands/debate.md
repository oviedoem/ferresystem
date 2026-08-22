---
name: debate
description: "Panel de gobernanza con 4 voces antes de una decisión arquitectónica o cambio significativo. Convoca: Socrático (problema real), Prompt Engineer (encuadre correcto), Abogado del Diablo (qué puede fallar), Abogado del Ángel (por qué vale la pena). TRIGGER: usuario dice 'no sé si hacer esto', 'evalúa esta idea', 'debate', 'decide por mí', o ante cambios que afecten core/, adapters/, pipeline/ o más de un tenant."
---

# Skill: Debate — Panel de Gobernanza

Antes de ejecutar un cambio grande, convoca las 4 voces.
El objetivo es **descubrir lo que no ves**, no validar lo que ya decidiste.

## Cuándo usar

- Cambios en `core/` que afectan a todos los tenants
- Agregar un nuevo adapter (nuevo ERP soportado)
- Rediseñar el esquema de `tenants/{id}.json`
- Decisiones sobre separar/unificar repos o servicios
- Cuando el usuario duda y pide segunda opinión

## Cuándo NO usar

- Bugs claros con solución obvia → Safe Change Protocol directamente
- Pedidos de una línea (renombrar variable, arreglar typo)
- Tareas con solución ya acordada en la sesión

---

## Las 4 Voces — ejecutar en orden

### 🔍 VOZ 1 — Socrático
*¿Estamos resolviendo el problema correcto?*

- ¿Qué problema exacto resuelve esto?
- ¿Hay síntoma vs. causa raíz? ¿Atacamos la raíz?
- ¿Qué pasaría si NO hacemos este cambio?
- ¿Hay algún tenant que ya tenga esta funcionalidad de otra forma?

### 📐 VOZ 2 — Prompt Engineer
*¿Está bien encuadrada la tarea?*

- ¿El pedido es suficientemente específico para implementarlo sin ambigüedad?
- ¿Falta algún dato de contexto que cambie la solución?
- ¿El alcance está definido? ¿Qué entra y qué NO entra?
- Reformulación recomendada del pedido si hay ambigüedad

### 😈 VOZ 3 — Abogado del Diablo
*¿Qué puede salir mal?*

- Riesgo técnico más probable
- ¿Este cambio en `core/` puede romper un tenant existente?
- ¿Hay datos de cliente que podrían filtrar con este cambio?
- Costo no esperado (tokens, nueva dependencia, complejidad de mantener)
- ¿El cambio abre la puerta a scope creep?

### 😇 VOZ 4 — Abogado del Ángel
*¿Por qué vale la pena de todas formas?*

- Beneficio concreto y medible
- Por qué el riesgo identificado es manejable
- Alternativas consideradas y por qué esta es mejor
- Alineación con la filosofía del CRITERIO.md: ¿sirve para cualquier ferretería o solo para Oviedo?

---

## Síntesis

```
RECOMENDACIÓN: [HACER / NO HACER / HACER CON AJUSTE]

Razón: [una línea]

Si HACER CON AJUSTE:
  Ajuste: [qué cambia en la propuesta]

Próximo paso si se aprueba:
  [primera acción concreta + archivo + función]
```

---

## Regla de uso

El debate informa — la decisión final es del usuario.
Si el usuario confirma → aplicar el checklist TOCO/ARCHIVO/RAZÓN/NO TOCO antes de ejecutar.
Si el usuario rechaza la recomendación → ejecutar lo pedido y registrar la discrepancia.
