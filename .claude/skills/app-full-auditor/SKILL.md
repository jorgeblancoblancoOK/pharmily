---
name: app-full-auditor
description: Audita de extremo a extremo una aplicación web analizando la usabilidad (UX) y vulnerabilidades de seguridad simulando interacciones de usuario. Úsala cuando el usuario diga "audita mi aplicación" o "haz un test de usabilidad y seguridad de la app".
---

# Flujo de Auditoría Integral (UX + Seguridad)

## Paso 1: Mapeo y Exploración Dinámica

1. Utiliza `agent-browser` (o Playwright/Chromium si no está disponible) para acceder a la URL local o de staging de la app. En este repo, sirve los estáticos con `python3 -m http.server 8000` y abre `http://localhost:8000/index.html` y `Pharmily.html`.
2. Identifica todos los flujos posibles: login, registro, formularios, pasarelas y paneles.
3. Haz clic en cada elemento interactivo para registrar las respuestas de la interfaz.

## Paso 2: Análisis de Usabilidad (UX/UI)

Evalúa y reporta errores bajo los siguientes criterios:

- **Consistencia:** ¿Los elementos visuales cambian drásticamente?
- **Accesibilidad:** Contraste, etiquetas `alt` ausentes, navegación por teclado.
- **Flujo de Usuario:** Pasos innecesarios o callejones sin salida en los clics.

## Paso 3: Auditoría de Seguridad Operativa

1. Simula entradas maliciosas en formularios (XSS básico, SQL Injection si aplica).
2. Inspecciona el almacenamiento local (`localStorage` / cookies) en busca de tokens expuestos.
3. Revisa la consola del navegador por errores 500 o fugas de información.
4. Revisa el service worker (`pharmily-sw.js`) por cacheo de respuestas sensibles.

Solo prueba contra entornos locales o de staging del propio usuario.

## Paso 4: Reporte Final

Genera un informe markdown estructurado con:

- Tabla de criticidad (Alta, Media, Baja).
- Capturas o logs del paso exacto del problema.
- Código o diseño de referencia corregido.
