"""Pruebas de seguridad: XSS, importación maliciosa, CSP/SRI, service worker, almacenamiento."""
import json
import os
import re

from playwright.sync_api import expect

from conftest import RAIZ

PAYLOADS = [
    '<img src=x onerror=alert("xss")>',
    '"><svg onload=alert("xss")>',
    "'><script>alert('xss')</script>",
]


def _html():
    with open(os.path.join(RAIZ, 'Pharmily.html'), encoding='utf-8') as f:
        return f.read()


def test_xss_en_asistente(app):
    app.abrir()
    app.login()
    app.completar_asistente(farmacia=PAYLOADS[0], provincia=PAYLOADS[1], empleados=PAYLOADS)
    for dlg in ['dlgEmpleados', 'dlgVacaciones', 'dlgComputo', 'dlgTexto', 'dlgConfig']:
        app.abrir_dialogo(dlg)
        app.cerrar_dialogos()
    app.page.reload()
    app.page.wait_for_load_state('networkidle')
    assert app.dialogos == []
    assert '<img src=x' in app.page.inner_text('body')  # se muestra como texto


def test_xss_en_empleados_y_plantillas(app_lista):
    p = app_lista.page
    app_lista.abrir_dialogo('dlgEmpleados')
    for x in PAYLOADS:
        p.fill('#newEmpName', x)
        p.click('#addEmpBtn')
    app_lista.cerrar_dialogos()
    app_lista.abrir_dialogo('dlgPlantillas')
    p.fill('#newPlantillaNombre', PAYLOADS[0])
    p.fill('#newPlantillaInicio', '09:00')
    p.fill('#newPlantillaFin', '14:00')
    p.click('#addPlantillaBtn')
    app_lista.cerrar_dialogos()
    p.reload()
    p.wait_for_load_state('networkidle')
    assert app_lista.dialogos == []


def test_backup_malicioso_queda_neutralizado(app_lista, tmp_path):
    p = app_lista.page
    app_lista.abrir_dialogo('dlgArchivo')
    with p.expect_download() as d:
        p.click('#saveFileBtn')
    ruta = tmp_path / 'malo.json'
    d.value.save_as(ruta)
    data = json.loads(ruta.read_text(encoding='utf-8'))
    f = data['farmacias'][0]
    f['nombre'] = PAYLOADS[0]
    e = f['empleados'][0]
    e.update({'id': 'e1" onmouseover="alert(2)', 'nombre': PAYLOADS[1],
              'color': 'red;" onload="alert(3)', 'notas': PAYLOADS[2]})
    f['plantillas'].append({'id': 'p9"><b>', 'nombre': PAYLOADS[0], 'inicio': '09:00', 'fin': '14:00'})
    ruta.write_text(json.dumps(data), encoding='utf-8')
    p.set_input_files('#openFileInput', str(ruta))  # el diálogo de Archivo sigue abierto
    app_lista.responder_dialogo_app()                # "¿Reemplazar todos los datos?"
    p.wait_for_timeout(500)
    if p.locator('.dialogo-app').count():
        app_lista.responder_dialogo_app()            # "Copia cargada"
    app_lista.cerrar_dialogos()
    assert app_lista.estado()['farmacias'][0]['nombre'] == PAYLOADS[0]
    for dlg in ['dlgEmpleados', 'dlgPlantillas', 'dlgVacaciones', 'dlgComputo']:
        app_lista.abrir_dialogo(dlg)
        app_lista.cerrar_dialogos()
    assert app_lista.errores == []
    assert [x for x in app_lista.dialogos if 'xss' in x or x in ('1', '2', '3')] == []
    emp = app_lista.estado()['farmacias'][0]['empleados'][0]
    assert re.fullmatch(r'[\w-]+', emp['id'])
    assert re.fullmatch(r'#[0-9a-fA-F]{3,8}', emp['color'])


def test_json_invalido_no_rompe(app_lista, tmp_path):
    ruta = tmp_path / 'roto.json'
    ruta.write_text('{no es json', encoding='utf-8')
    app_lista.abrir_dialogo('dlgArchivo')
    app_lista.page.set_input_files('#openFileInput', str(ruta))
    app_lista.page.wait_for_timeout(500)
    assert 'JSON' in app_lista.page.inner_text('body')
    assert app_lista.errores == []


def test_xss_en_notificaciones(app_lista, api):
    app = app_lista
    api.notificaciones = [{'id': '1"><img src=x onerror=alert("xss-id")>', 'leida': False,
                           'mensaje': PAYLOADS[0], 'creadaEn': '2026-10-11T00:00:00Z'}]
    app.page.reload()
    app.page.wait_for_load_state('networkidle')
    app.page.click('#notifBtnAdmin')
    app.page.wait_for_timeout(500)
    assert app.dialogos == []


def test_xss_en_lista_de_usuarios(app_lista, api):
    api.usuarios = [{'id': 2, 'displayName': PAYLOADS[0], 'username': PAYLOADS[1], 'role': 'empleado',
                     'active': True, 'lastLoginAt': None}]
    app_lista.abrir_dialogo('dlgUsuarios')
    expect(app_lista.page.locator('#usuariosBody')).to_contain_text('<img src=x')
    assert app_lista.dialogos == []
    assert '<img src=x' in app_lista.page.inner_text('#usuariosBody')


def test_xss_en_vista_empleado(app, api):
    api.rol = 'empleado'
    api.mi_horario = {'hoy': '2026-10-12', 'lunesSemana': '2026-10-12',
                      'empleado': {'nombre': PAYLOADS[0], 'rol': 'auxiliar'}, 'farmacia': {'nombre': PAYLOADS[1]},
                      'proximosTurnos': [], 'diasSemana': [],
                      'ausencias': [{'tipo': 'vacaciones', 'inicio': '2026-10-20', 'fin': '2026-10-22',
                                     'estado': 'pendiente', 'nota': PAYLOADS[2]}], 'horasSemana': 0}
    app.abrir()
    app.login()
    app.page.wait_for_timeout(500)
    assert app.dialogos == []


def test_csp_y_sri_presentes():
    html = _html()
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html)
    assert csp, 'Falta la CSP'
    for directiva in ["object-src 'none'", "base-uri 'none'", 'connect-src']:
        assert directiva in csp.group(1)
    for tag in re.findall(r'<script[^>]+src="https?://[^"]+"[^>]*>', html):
        assert 'integrity="sha384-' in tag and 'crossorigin' in tag, tag


def test_sin_violaciones_de_csp(app_lista):
    for dlg in ['dlgArchivo', 'dlgCalendario', 'dlgCuenta']:
        app_lista.abrir_dialogo(dlg)
        app_lista.cerrar_dialogos()
    assert app_lista.csp == []


def test_sin_eval_ni_document_write_de_datos():
    html = _html()
    assert 'eval(' not in html
    assert 'new Function(' not in html


def test_service_worker_no_cachea_api():
    with open(os.path.join(RAIZ, 'pharmily-sw.js'), encoding='utf-8') as f:
        sw = f.read()
    assert 'self.location.origin' in sw, 'El SW debe limitarse al mismo origen'
    assert "startsWith('/api/')" in sw, 'El SW no debe cachear la API del servidor'
    assert 'resp.ok' in sw, 'El SW no debe cachear respuestas de error'


def test_sin_secretos_en_el_codigo():
    html = _html()
    assert not re.search(r'eyJ[\w-]{10,}\.eyJ[\w-]{10,}\.[\w-]+', html), 'Hay un JWT incrustado'
    assert 'service_role' not in html


def test_sin_dependencias_de_terceros():
    html = _html()
    assert not re.findall(r'<script[^>]+src="https?://', html)
    assert not re.findall(r'fetch\([\'"`]https?://', html)
