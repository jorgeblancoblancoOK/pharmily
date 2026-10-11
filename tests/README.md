# Pruebas automáticas de Pharmily

Recorren la app como un usuario (asistente, ventanas, empleados, plantillas, semanas, deshacer,
tema, copias de seguridad, enlaces, móvil), comprueban la seguridad (XSS, backups maliciosos,
CSP/SRI, service worker, secretos, almacenamiento) y la accesibilidad básica.

```bash
pip install playwright pytest
python -m playwright install chromium   # no hace falta si ya tienes Chromium de Playwright
python -m pytest tests -q
```
