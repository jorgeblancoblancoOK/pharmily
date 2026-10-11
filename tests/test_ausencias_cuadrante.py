"""Quien está de vacaciones, baja o permiso no ocupa fila en el cuadrante semanal: sale en el
apartado "Vacaciones, bajas y ausencias" de esa semana."""
import pytest

PREPARAR = """() => {
  const lunes = datos.semanaActual;
  const ana = datos.empleados.find(e => e.nombre === 'Ana');
  const luis = datos.empleados.find(e => e.nombre === 'Luis');
  const w = getWeek(lunes);
  for (const dia of [0, 1, 2, 3]) {
    w.turnos.push({ id: 't_ana' + dia, empleadoId: ana.id, dia, inicio: '09:00', fin: '14:00' });
    w.turnos.push({ id: 't_luis' + dia, empleadoId: luis.id, dia, inicio: '15:00', fin: '20:00' });
  }
  datos.ausencias.push({ id: 'a_vac', empleadoId: ana.id, tipo: 'vacaciones', inicio: lunes,
                         fin: addDaysIso(lunes, 2), estado: 'aprobada', nota: 'Viaje' });
  save(); render();
  return { ana: ana.id, luis: luis.id };
}"""


@pytest.mark.parametrize('ancho', [1280, 375])
def test_ausente_fuera_del_cuadrante_y_en_su_apartado(app_lista, ancho):
    p = app_lista.page
    p.set_viewport_size({'width': ancho, 'height': 900})
    ids = p.evaluate(PREPARAR)
    p.wait_for_timeout(300)
    panel = p.locator('#semanaContenido .aus-semana').first
    panel.wait_for()
    texto = panel.inner_text()
    assert 'Ana' in texto and 'Vacaciones' in texto and 'Viaje' in texto
    assert 'tenía turno' in texto
    if ancho == 1280:
        # Lunes (fila 0): solo Luis tiene barra; Ana no aparece ni como turno ni como marca.
        lunes = p.locator('#semanaContenido .thoriz-day-row').nth(0)
        assert lunes.locator(f'[data-emp="{ids["ana"]}"]').count() == 0
        assert lunes.locator(f'.thoriz-bar[data-emp="{ids["luis"]}"]').count() == 1
        # Jueves (fila 3): Ana ya ha vuelto y trabaja.
        jueves = p.locator('#semanaContenido .thoriz-day-row').nth(3)
        assert jueves.locator(f'.thoriz-bar[data-emp="{ids["ana"]}"]').count() == 1
    app_lista.page.screenshot(path=f'/tmp/aus-{ancho}.png', full_page=True)
    assert app_lista.errores == []


def test_click_en_ausencia_abre_su_ficha(app_lista):
    p = app_lista.page
    p.set_viewport_size({'width': 1280, 'height': 900})
    p.evaluate(PREPARAR)
    p.locator('#semanaContenido .aus-semana-item').first.click()
    p.wait_for_timeout(300)
    assert p.locator('#modalRoot :is(input,select)').count() > 0 or p.locator('.modal-backdrop:visible').count() > 0
