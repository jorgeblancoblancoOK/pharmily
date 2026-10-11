# Cambio necesario en el servidor del NAS: horario del empleado por meses

La app (vista de empleado → "Tu horario por meses") ya pide:

```
GET /api/mi-horario?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
Authorization: Bearer <token del empleado>
```

El servidor debe:

1. Si llegan `desde` y `hasta`, devolver el **mismo JSON** que hoy devuelve `/api/mi-horario`, pero con
   - `proximosTurnos`: todos los turnos **de ese empleado** con `fecha` entre `desde` y `hasta` (ambos incluidos),
   - `ausencias`: sus ausencias que se solapen con el rango,
   - y además los campos `"desde"` y `"hasta"` repetidos tal cual (así la app sabe que el servidor entiende el rango).
2. Validar las fechas (formato `YYYY-MM-DD`, `desde <= hasta`) y limitar el rango (p. ej. máximo 62 días) → si no, `400`.
3. Usar siempre el empleado vinculado al token, nunca uno que venga en la petición.
4. Sin parámetros, seguir respondiendo como ahora (14 días), para no romper versiones anteriores de la app.

La app deja navegar de 3 meses atrás a 6 meses adelante. Mientras el servidor no tenga este cambio, la app
muestra lo que haya en los 14 días y avisa: "Tu farmacia todavía solo comparte los próximos 14 días".
