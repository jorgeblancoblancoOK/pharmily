"""Pruebas a nivel usuario: flujos, ventanas (diálogos), navegación y enlaces."""
import json

import pytest

DIALOGOS = ['dlgArchivo', 'dlgEmpleados', 'dlgPlantillas', 'dlgVacaciones', 'dlgComputo',
            'dlgTexto', 'dlgCalendario', 'dlgConfig', 'dlgCuenta']


def test_index_redirige_a_la_app(app):
    app.abrir('/index.html')
    assert app.page.url.endswith('/Pharmily.html')


def test_primer_arranque_muestra_asistente_sin_errores(app):
    app.abrir()
    assert app.page.is_visible('#asNombre')
    assert app.errores == []


def test_asistente_crea_farmacia_y_empleados(app_lista):
    st = app_lista.estado()
    assert len(st['farmacias']) == 1
    f = st['farmacias'][0]
    assert [e['nombre'] for e in f['empleados']] == ['Ana', 'Luis']
    assert app_lista.errores == []


def test_asistente_no_avanza_sin_nombre(app):
    app.abrir()
    app.page.click('#asSiguiente1')
    assert app.page.is_visible('#asNombre')


@pytest.mark.parametrize('dlg', DIALOGOS)
def test_cada_ventana_abre_y_cierra(app_lista, dlg):
    p = app_lista.page
    app_lista.abrir_dialogo(dlg)
    p.click(f'#{dlg} [data-close="{dlg}"]')
    assert p.is_hidden(f'#{dlg}')
    app_lista.abrir_dialogo(dlg)
    p.keyboard.press('Escape')
    assert p.is_hidden(f'#{dlg}')
    assert app_lista.errores == []


def test_anadir_empleado(app_lista):
    p = app_lista.page
    app_lista.abrir_dialogo('dlgEmpleados')
    p.fill('#newEmpName', 'Marta')
    p.select_option('#newEmpRol', 'farmaceutico')
    p.click('#addEmpBtn')
    emps = app_lista.estado()['farmacias'][0]['empleados']
    assert emps[-1]['nombre'] == 'Marta' and emps[-1]['rol'] == 'farmaceutico'


def test_anadir_plantilla(app_lista):
    p = app_lista.page
    app_lista.abrir_dialogo('dlgPlantillas')
    p.fill('#newPlantillaNombre', 'Tarde')
    p.fill('#newPlantillaInicio', '16:00')
    p.fill('#newPlantillaFin', '21:00')
    p.click('#addPlantillaBtn')
    pl = app_lista.estado()['farmacias'][0]['plantillas']
    assert any(x['nombre'] == 'Tarde' and x['inicio'] == '16:00' for x in pl)


def test_navegacion_de_semanas(app_lista):
    p = app_lista.page
    hoy = p.text_content('#weekLabel')
    p.click('#nextWeek')
    assert p.text_content('#weekLabel') != hoy
    p.click('#prevWeek')
    p.click('#prevWeek')
    p.click('#todayWeek')
    assert p.text_content('#weekLabel') == hoy


def test_deshacer(app_lista):
    p = app_lista.page
    app_lista.abrir_dialogo('dlgEmpleados')
    p.fill('#newEmpName', 'Temporal')
    p.click('#addEmpBtn')
    p.keyboard.press('Escape')
    p.click('#undoBtn')
    nombres = [e['nombre'] for e in app_lista.estado()['farmacias'][0]['empleados']]
    assert 'Temporal' not in nombres


def test_tema_oscuro_persiste(app_lista):
    p = app_lista.page
    antes = p.evaluate("document.documentElement.dataset.theme || ''")
    p.click('#themeBtn')
    despues = p.evaluate("document.documentElement.dataset.theme || ''")
    assert antes != despues
    p.reload()
    assert p.evaluate("document.documentElement.dataset.theme || ''") == despues


def test_copia_de_seguridad_ida_y_vuelta(app_lista, tmp_path):
    p = app_lista.page
    app_lista.abrir_dialogo('dlgArchivo')
    with p.expect_download() as d:
        p.click('#saveFileBtn')
    ruta = tmp_path / 'backup.json'
    d.value.save_as(ruta)
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    assert datos['farmacias'][0]['nombre'] == 'Farmacia Test'
    # Borrar todo y restaurar desde el archivo
    p.evaluate('localStorage.clear()')
    p.reload()
    p.set_input_files('#asImportarBackupFile', str(ruta))
    p.wait_for_selector('#topNav', state='visible')
    assert app_lista.estado()['farmacias'][0]['nombre'] == 'Farmacia Test'


def test_enlaces_externos_seguros(app_lista):
    p = app_lista.page
    for dlg in DIALOGOS:
        app_lista.abrir_dialogo(dlg)
        p.keyboard.press('Escape')
    enlaces = p.eval_on_selector_all('a[href]', 'as => as.map(a => [a.href, a.target, a.rel])')
    for href, target, rel in enlaces:
        if href.startswith('http') and '127.0.0.1' not in href:
            assert href.startswith('https://'), href
            assert target == '_blank' and 'noopener' in rel, href


def test_movil_sin_scroll_horizontal(browser, base_url):
    ctx = browser.new_context(viewport={'width': 375, 'height': 740}, service_workers='block')
    p = ctx.new_page()
    p.route('https://cdn.jsdelivr.net/**', lambda r: r.fulfill(status=200, body=''))
    p.goto(base_url + '/Pharmily.html')
    p.wait_for_load_state('networkidle')
    ancho = p.evaluate('document.documentElement.scrollWidth')
    ctx.close()
    assert ancho <= 375
