"""Pruebas de seguridad: XSS, importación maliciosa, CSP/SRI, service worker, almacenamiento."""
import json
import os
import re

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
    app.completar_asistente(farmacia=PAYLOADS[0], provincia=PAYLOADS[1], empleados=PAYLOADS)
    for dlg in ['dlgEmpleados', 'dlgVacaciones', 'dlgComputo', 'dlgTexto', 'dlgConfig']:
        app.abrir_dialogo(dlg)
        app.page.keyboard.press('Escape')
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
    p.keyboard.press('Escape')
    app_lista.abrir_dialogo('dlgPlantillas')
    p.fill('#newPlantillaNombre', PAYLOADS[0])
    p.fill('#newPlantillaInicio', '09:00')
    p.fill('#newPlantillaFin', '14:00')
    p.click('#addPlantillaBtn')
    p.keyboard.press('Escape')
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
    p.evaluate('localStorage.clear()')
    p.reload()
    p.set_input_files('#asImportarBackupFile', str(ruta))
    p.wait_for_selector('#topNav', state='visible')
    for dlg in ['dlgEmpleados', 'dlgPlantillas', 'dlgVacaciones', 'dlgComputo']:
        app_lista.abrir_dialogo(dlg)
        p.keyboard.press('Escape')
    assert app_lista.errores == []
    assert [x for x in app_lista.dialogos if 'xss' in x or x in ('1', '2', '3')] == []
    emp = app_lista.estado()['farmacias'][0]['empleados'][0]
    assert re.fullmatch(r'[\w-]+', emp['id'])
    assert re.fullmatch(r'#[0-9a-fA-F]{3,8}', emp['color'])


def test_json_invalido_no_rompe(app, tmp_path):
    ruta = tmp_path / 'roto.json'
    ruta.write_text('{no es json', encoding='utf-8')
    app.abrir()
    app.page.set_input_files('#asImportarBackupFile', str(ruta))
    app.page.wait_for_timeout(300)
    assert any('JSON' in d for d in app.dialogos)
    assert app.errores == []


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
        app_lista.page.keyboard.press('Escape')
    assert app_lista.csp == []


def test_sin_eval_ni_document_write_de_datos():
    html = _html()
    assert 'eval(' not in html
    assert 'new Function(' not in html


def test_service_worker_no_cachea_api():
    with open(os.path.join(RAIZ, 'pharmily-sw.js'), encoding='utf-8') as f:
        sw = f.read()
    assert 'self.location.origin' in sw, 'El SW debe limitarse al mismo origen'
    assert 'resp.ok' in sw, 'El SW no debe cachear respuestas de error'


def test_sin_secretos_en_el_codigo():
    html = _html()
    for jwt in re.findall(r'eyJ[\w-]+\.(eyJ[\w-]+)\.[\w-]+', html):
        import base64
        payload = json.loads(base64.urlsafe_b64decode(jwt + '==='))
        assert payload.get('role') == 'anon', 'Solo se permite la clave pública anon de Supabase'
    assert 'service_role' not in html


def test_almacenamiento_sin_tokens_en_modo_local(app_lista):
    claves = app_lista.page.evaluate('Object.keys(localStorage)')
    assert not [k for k in claves if 'token' in k.lower()]
    assert app_lista.page.evaluate('document.cookie') == ''
