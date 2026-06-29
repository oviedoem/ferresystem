# Checklist de instalación — cliente nuevo

## 1. Datos del cliente
- [ ] `tenant_id` único definido (slug, sin espacios)
- [ ] Nombre comercial, RUT, contacto técnico
- [ ] ERP: tipo, host, puerto, usuario, password (a cifrar con DPAPI)
- [ ] Lista de bodegas: comerciales, logísticas, bodega principal

## 2. Firebase
- [ ] Crear proyecto Firebase nuevo (o confirmar uno existente)
- [ ] Habilitar Hosting + Firestore
- [ ] Configurar `firestore.rules` (copiar base genérica y ajustar)
- [ ] Reservar `hosting_url` (https://{tenant}.web.app o dominio propio)

## 3. Branding
- [ ] Logo en alta resolución (PNG transparente)
- [ ] Colores primario/secundario
- [ ] Completar `branding/{tenant_id}/branding.json`

## 4. ERP
- [ ] Elegir adapter (`justweb` | `transtecnia` | `rexplus` | `excel`)
- [ ] Probar `test_conexion()` antes de continuar
- [ ] Confirmar horario de sincronización del ERP (real-time vs batch nocturno)

## 5. Tenant config
- [ ] Completar `tenants/{tenant_id}.json` (copiar de `ejemplo_tenant.json`)
- [ ] Verificar que NO quedó ningún dato real fuera de ese archivo

## 6. Primer corrida
- [ ] `python setup/setup_tenant.py {tenant_id}`
- [ ] `pipeline/ACTUALIZAR_TODO.bat {tenant_id}`
- [ ] Validar JSONs generados (`core/validator.py`)
- [ ] `firebase deploy --project {project_id}`

## 7. Entrega
- [ ] Acceso panel-admin probado con usuario real del cliente
- [ ] Documentar credenciales y accesos en gestor seguro (no en el repo)
