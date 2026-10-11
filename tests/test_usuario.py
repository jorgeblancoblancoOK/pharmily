"""Pruebas a nivel usuario: flujos, ventanas (diálogos), navegación y enlaces."""
import json

from playwright.sync_api import expect

import pytest

DIALOGOS = ['dlgArchivo', 'dlgEmpleados', 'dlgPlantillas', 'dlgVacaciones', 'dlgComputo', 'dlgTexto',
            'dlgCalendario', 'dlgConfig', 'dlgCuenta', 'dlgSabados', 'dlgUsuarios']


def test_index_redirige_a_la_app(app):
    app.abrir('/index.html')
    assert app.page.url.endswith('/Pharmily.html')


def test_sin_sesion_muestra_login(app):
    app.abrir()
    assert app.page.is_visible('#loginUsername')
    assert app.errores == []


def test_login_con_clave_incorrecta_muestra_error(app):
    app.abrir()
    app.login(password='mala')
    expect(app.page.locator('#loginError')).to_contain_text('incorrectos')
    assert app.page.evaluate("localStorage.getItem('pharmily_auth_token')") is None


def test_login_admin_muestra_asistente_y_envia_token(app, api):
    app.abrir()
    app.login()
    expect(app.page.locator('#asNombre')).to_be_visible()
    assert ('GET', 'auth/me', None) not in api.llamadas
    assert any(r == 'state' and auth == 'Bearer token-de-prueba' for _, r, auth in api.llamadas)
    assert app.errores == []


def test_recargar_justo_tras_un_cambio_no_pierde_datos(app_lista, api):
    """Regresión: el guardado en el servidor va con retardo; recargar antes no debe perder el cambio."""
    p = app_lista.page
    app_lista.abrir_dialogo('dlgEmpleados')
    p.fill('#newEmpName', 'Recién llegada')
    p.click('#addEmpBtn')
    p.reload()
    p.wait_for_load_state('networkidle')
    p.wait_for_timeout(2000)
    nombres = [e['nombre'] for e in api.state['farmacias'][0]['empleados']]
    assert 'Recién llegada' in nombres
    assert app_lista.dialogos == []


def test_sesion_se_recupera_al_recargar(app_lista):
    app_lista.page.reload()
    app_lista.page.wait_for_load_state('networkidle')
    assert app_lista.page.is_visible('#navHorario')


def test_cerrar_sesion_borra_datos_locales(app_lista):
    p = app_lista.page
    with p.expect_navigation():
        p.evaluate('cerrarSesionCuenta()')
    expect(p.locator('#loginUsername')).to_be_visible()
    claves = p.evaluate('Object.keys(localStorage)')
    assert not [k for k in claves if k.startswith('pharmily_auth') or k == 'pharmily_v1' or k.startswith('pharmily_sync')]


def test_vista_empleado(app, api):
    api.rol = 'empleado'
    api.mi_horario = {'hoy': '2026-10-12', 'lunesSemana': '2026-10-12',
                      'empleado': {'nombre': 'Ana López', 'rol': 'auxiliar'}, 'farmacia': {'nombre': 'Farmacia Test'},
                      'proximosTurnos': [{'fecha': '2026-10-12', 'inicio': '09:00', 'fin': '14:00'}],
                      'diasSemana': [{'fecha': '2026-10-12', 'turnos': [], 'ausencia': None}],
                      'ausencias': [], 'horasSemana': 5}
    app.abrir()
    app.login()
    app.page.wait_for_selector('#empleadoMain .emp-titulo')
    texto = app.page.inner_text('#empleadoMain')
    assert 'Ana' in texto and '09:00' in texto
    assert app.page.is_hidden('#navHorario')
    assert app.errores == []


def test_asistente_crea_farmacia_y_empleados(app_lista, api):
    app_lista.page.wait_for_timeout(1500)  # el guardado en el servidor va con un pequeño retardo
    assert api.state['farmacias'][0]['nombre'] == 'Farmacia Test'
    st = app_lista.estado()
    assert len(st['farmacias']) == 1
    f = st['farmacias'][0]
    assert [e['nombre'] for e in f['empleados']] == ['Ana', 'Luis']
    assert app_lista.errores == []


def test_asistente_no_avanza_sin_nombre(app):
    app.abrir()
    app.login()
    app.page.click('#asSiguiente1')
    assert app.page.is_visible('#asNombre')


@pytest.mark.parametrize('dlg', DIALOGOS)
def test_cada_ventana_abre_y_cierra(app_lista, dlg):
    p = app_lista.page
    app_lista.abrir_dialogo(dlg)
    p.click(f'#{dlg} [data-close="{dlg}"]')
    assert p.is_hidden(f'#{dlg}')
    app_lista.abrir_dialogo(dlg)
    app_lista.cerrar_dialogos()
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
    app_lista.cerrar_dialogos()
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
    # Cambiar algo y restaurar desde el archivo con el mismo diálogo de Archivo (sigue abierto)
    p.evaluate("state.farmacias[0].nombre = 'Cambiada'; save()")
    p.set_input_files('#openFileInput', str(ruta))
    app_lista.responder_dialogo_app()
    p.wait_for_timeout(500)
    assert app_lista.estado()['farmacias'][0]['nombre'] == 'Farmacia Test'


def test_enlaces_externos_seguros(app_lista):
    p = app_lista.page
    for dlg in DIALOGOS:
        app_lista.abrir_dialogo(dlg)
        app_lista.cerrar_dialogos()
    enlaces = p.eval_on_selector_all('a[href]', 'as => as.map(a => [a.href, a.target, a.rel])')
    for href, target, rel in enlaces:
        if href.startswith('http') and '127.0.0.1' not in href:
            assert href.startswith('https://'), href
            assert target == '_blank' and 'noopener' in rel, href


def test_movil_sin_scroll_horizontal(browser, base_url):
    ctx = browser.new_context(viewport={'width': 375, 'height': 740}, service_workers='block')
    p = ctx.new_page()
    p.goto(base_url + '/Pharmily.html')
    p.wait_for_load_state('networkidle')
    ancho = p.evaluate('document.documentElement.scrollWidth')
    ctx.close()
    assert ancho <= 375
