# Auditoría UX + Seguridad — Pharmily

Fecha: 2026-10-11 · Entorno: servidor local (`python3 -m http.server`) + Chromium headless (Playwright) · Rama: `claude/app-full-auditor-uaq10b`

## Estado de las correcciones (2026-10-11)

| # | Estado | Cambio |
|---|--------|--------|
| 1 | ✅ Corregido | Función `esc()` aplicada en 42 interpolaciones de datos de usuario (nombres, notas, teléfono, provincia, festivos, plantillas) |
| 2 | ✅ Corregido | `sanearIdsYColores()` en `migrarDatosFarmacia` (se ejecuta al cargar, importar backup y bajar de la nube): ids y colores fuera de formato se reemplazan; CSP añadida |
| 3 | ✅ Corregido | `pharmily-sw.js` solo cachea mismo origen + supabase-js, y solo respuestas `ok` |
| 4 | ✅ Corregido | `integrity="sha384-…"` + `crossorigin` en supabase-js (hash calculado del paquete npm 2.45.4) y `<meta>` CSP |
| 5 | Falso positivo | — |
| 6 | ✅ Corregido | 50 `<label for>` asociados + `aria-label` en el selector de rol |

Verificación (Playwright): los payloads `<img src=x onerror=alert(...)>` en farmacia y empleado se muestran como texto y no disparan ningún diálogo; un empleado importado con `id`/`color` maliciosos queda saneado (`e_san0`, `#FF0000`); 0 errores de consola y 0 violaciones de CSP. Captura: `audit/03-xss-corregido.png`.

Pendiente fuera del código: confirmar RLS en la tabla `pharmily_sync` de Supabase y probar login/sincronización en un navegador con acceso a jsDelivr (aquí estaba bloqueado, así que la CSP no se pudo probar contra Supabase real).

## Mapa de la app
- `index.html` → redirige a `Pharmily.html` (SPA de un solo archivo, ~250 KB).
- Flujos: asistente inicial (farmacia + empleados), cuadrante semanal, empleados, ausencias/vacaciones, plantillas de turno, festivos, cómputo mensual, import/export JSON y CSV, cuenta y sincronización en la nube (Supabase, tabla `pharmily_sync`), modo oscuro, service worker offline.
- Datos: `localStorage` (`pharmily_v1`, `pharmily_sync_*`, tema, backups). Sin cookies.

## Tabla de criticidad

| # | Hallazgo | Tipo | Criticidad |
|---|----------|------|-----------|
| 1 | XSS almacenado: nombres de empleado/farmacia, notas y teléfono se insertan en `innerHTML` sin escapar | Seguridad | **Alta** |
| 2 | El XSS viaja en backups JSON importados y en la sincronización en la nube, y puede robar el token de sesión de Supabase | Seguridad | **Alta** |
| 3 | El service worker cachea *todas* las peticiones GET, incluidas las respuestas de la API de Supabase con datos de empleados | Seguridad/Privacidad | Media |
| 4 | `supabase-js` se carga de jsDelivr sin `integrity` (SRI) ni CSP | Seguridad | Media |
| 5 | ~~Error `null (reading 'empleados')` sin CDN~~ — **falso positivo**: lo provocó el propio script de prueba al abrir un diálogo antes de completar el asistente | — | — |
| 6 | 22 campos `input/select` sin `<label>` asociado ni `aria-label` | Accesibilidad | Media |
| 7 | 2 imágenes con `alt=""` (icono de la app; decorativo, aceptable) | Accesibilidad | Baja |
| 8 | Contraseña: sin requisitos mínimos visibles; el mensaje de error de Supabase se muestra en inglés | UX | Baja |

Aspectos correctos: foco visible por teclado (`:focus-visible` con `box-shadow`), botones con nombre accesible, `meta viewport` presente, no hay `eval`, la clave de Supabase incluida es la `anon` (pública por diseño, **siempre que RLS esté activo** en `pharmily_sync`; no se pudo verificar desde el cliente).

## Detalle y evidencias

### 1. XSS almacenado (Alta)
**Pasos:** abrir *Empleados* → nombre `<img src=x onerror=alert("XSS-empleado")>` → *Añadir*. También funciona en el nombre de la farmacia.

**Log (Playwright):**
```
DIALOG: XSS-farmacia
DIALOG: XSS-empleado   (×8, se ejecuta en cada render)
```
Captura: `audit/02-xss.png`.

**Código afectado** (ejemplos, `Pharmily.html`): líneas 1242, 1807, 1837, 1901, 2026, 2245 (`${emp.nombre}`), 3533/3573/3538/3834 (`value="${...}"` en atributos), 1217/1221 (`st.nombre`). No existe ninguna función de escape en el archivo (71 usos de `innerHTML`).

**Corrección de referencia:**
```js
function esc(s){
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
// Antes
pill.innerHTML = `${avatarHtml(emp, 20)}${emp.nombre}${rolBadgeHtml(emp)}`;
// Después
pill.innerHTML = `${avatarHtml(emp, 20)}${esc(emp.nombre)}${rolBadgeHtml(emp)}`;
// Atributos
`<input type="text" id="eeNombre" value="${esc(emp.nombre)}">`
```
Aplicar `esc()` a todo dato de usuario interpolado (nombres, notas, teléfono, nombre de plantilla, festivo, provincia). Donde solo hay texto, preferir `textContent`.

### 2. Propagación por backup y nube (Alta)
`importarBackup` / `openFileInput` (líneas 3896, 3982) aceptan cualquier JSON con la forma correcta, y `traerDeNube` (4195) sobrescribe el estado local. Un backup malicioso compartido, o una cuenta comprometida, ejecuta JS en todos los dispositivos sincronizados; el token `sb-*-auth-token` de `localStorage` queda al alcance. Se corrige con el punto 1; además conviene validar el esquema al importar (tipos y longitud máx. de strings) y añadir una CSP:
```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self' https://kfwebtprtgsradwsqxym.supabase.co; img-src 'self' data:; object-src 'none'; base-uri 'none'">
```

### 3. Service worker cachea respuestas de la API (Media)
`pharmily-sw.js` guarda en `pharmily-v1` cualquier GET, incluido `GET /rest/v1/pharmily_sync` con los datos de los empleados; persiste tras cerrar sesión y en dispositivos compartidos.
```js
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return; // solo mismo origen
  event.respondWith(
    fetch(event.request).then((resp) => {
      if (resp.ok) { const copia = resp.clone(); caches.open('pharmily-v1').then(c => c.put(event.request, copia)); }
      return resp;
    }).catch(() => caches.match(event.request))
  );
});
```
(Si se quiere offline para supabase-js, cachear solo esa URL exacta del CDN.)

### 4. CDN sin SRI (Media)
```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js"
        integrity="sha384-<HASH>" crossorigin="anonymous"></script>
```
Generar el hash con `curl -s URL | openssl dgst -sha384 -binary | openssl base64 -A`, o servir el archivo localmente.

### 5. Error en consola sin CDN — falso positivo
Log real (red del entorno bloqueaba jsDelivr):
```
reqfail: https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js
pageerror: Cannot read properties of null (reading 'empleados')
```
Ocurre en la primera carga sin datos (asistente abierto, `datos` nulo). Añadir una guarda `if(!datos) return;` en las funciones de render llamadas antes de completar el asistente.

### 6. Campos sin etiqueta (Media)
Los `<label>` del markup son hermanos, no están asociados. Corrección:
```html
<label for="newEmpName">Nuevo empleado</label>
<input type="text" id="newEmpName" placeholder="Nombre">
```

### 8. UX de cuenta (Baja)
Traducir los errores comunes de Supabase (`Invalid login credentials` → "Email o contraseña incorrectos") e indicar el mínimo de 6 caracteres.

## Límites de la auditoría
- No se pudo cargar supabase-js (proxy), así que el login/sincronización se revisó solo en código; RLS de `pharmily_sync` no verificado — compruébalo en el panel de Supabase.
- SQL injection no aplica (no hay backend propio; Supabase usa consultas parametrizadas).
