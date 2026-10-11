# Pruebas automáticas de Pharmily

La API del servidor del NAS (`/api/...`) se simula en memoria (`ApiSimulada` en `conftest.py`),
así que no hace falta tener el servidor encendido.

Recorren la app como un usuario (login de admin y de empleado, cierre de sesión, asistente, ventanas, empleados, plantillas, semanas, deshacer,
tema, copias de seguridad, enlaces, móvil), comprueban la seguridad (XSS, backups maliciosos, notificaciones y usuarios manipulados,
CSP/SRI, service worker, secretos, almacenamiento) y la accesibilidad básica.

```bash
pip install playwright pytest
python -m playwright install chromium   # no hace falta si ya tienes Chromium de Playwright
python -m pytest tests -q
```
