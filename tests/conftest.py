"""Fixtures comunes: servidor estático local, API del NAS simulada y navegador Chromium (Playwright)."""
import functools
import json
import http.server
import os
import threading

import pytest
from playwright.sync_api import expect, sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMIUM = '/opt/pw-browsers/chromium'


@pytest.fixture(scope='session')
def base_url():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=RAIZ)
    handler = type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
    handler = functools.partial(handler, directory=RAIZ)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{srv.server_port}'
    srv.shutdown()


@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as p:
        kw = {'executable_path': CHROMIUM} if os.path.exists(CHROMIUM) else {}
        b = p.chromium.launch(headless=True, **kw)
        yield b
        b.close()


class ApiSimulada:
    """Imita la API del servidor del NAS (/api/...) en memoria, con un único usuario."""

    def __init__(self, rol='admin'):
        self.rol = rol
        self.state = {'farmacias': []}
        self.updated = '2026-01-01T00:00:00Z'
        self.notificaciones = []
        self.usuarios = []
        self.mi_horario = None
        self.mi_horario_por_rango = None  # función (desde, hasta) -> respuesta; None = servidor antiguo
        self.llamadas = []

    def usuario(self):
        return {'id': 1, 'username': 'prueba', 'displayName': 'Usuario Prueba', 'role': self.rol,
                'mustChangePassword': False}

    def __call__(self, route):
        req = route.request
        ruta = req.url.split('/api/', 1)[1].split('?')[0]
        self.llamadas.append((req.method, ruta, req.headers.get('authorization')))

        def ok(body, status=200):
            route.fulfill(status=status, content_type='application/json', body=json.dumps(body))

        if ruta == 'auth/login':
            datos = json.loads(req.post_data or '{}')
            if datos.get('password') != 'clave-buena':
                return ok({'error': 'Usuario o contraseña incorrectos.'}, 401)
            return ok({'token': 'token-de-prueba', 'usuario': self.usuario()})
        if ruta == 'auth/me':
            return ok({'usuario': self.usuario()})
        if ruta == 'state':
            if req.method == 'PUT':
                self.state = json.loads(req.post_data)['state']
                self.updated = '2026-01-01T00:00:01Z'
                return ok({'updatedAt': self.updated})
            return ok({'state': self.state, 'updatedAt': self.updated})
        if ruta.startswith('notificaciones'):
            return ok({'noLeidas': sum(not n['leida'] for n in self.notificaciones), 'notificaciones': self.notificaciones})
        if ruta == 'usuarios':
            return ok({'usuarios': self.usuarios})
        if ruta == 'mi-horario':
            q = dict(x.split('=') for x in req.url.split('?', 1)[1].split('&')) if '?' in req.url else {}
            if q and self.mi_horario_por_rango is not None:
                return ok(self.mi_horario_por_rango(q['desde'], q['hasta']))
            return ok(self.mi_horario)
        if ruta == 'backups':
            return ok({'backups': []})
        return ok({})


class Sesion:
    """Página nueva y aislada que registra errores, diálogos y violaciones de CSP."""

    def __init__(self, page, base_url, api):
        self.page, self.base_url, self.api = page, base_url, api
        self.errores, self.dialogos, self.csp = [], [], []
        page.on('pageerror', lambda e: self.errores.append(str(e)))
        page.on('console', self._consola)
        page.on('dialog', self._dialogo)
        page.route('**/api/**', api)

    def _consola(self, m):
        if 'Content Security Policy' in m.text:
            self.csp.append(m.text)

    def _dialogo(self, d):
        self.dialogos.append(d.message)
        d.accept()  # confirm() de la app → "Aceptar"; alert() de un XSS también queda registrado

    def abrir(self, ruta='/Pharmily.html'):
        self.page.goto(self.base_url + ruta)
        self.page.wait_for_load_state('networkidle')

    def login(self, password='clave-buena'):
        p = self.page
        p.fill('#loginUsername', 'prueba')
        p.fill('#loginPassword', password)
        with p.expect_response('**/api/auth/login'):
            p.click('#loginSubmitBtn')
        p.wait_for_load_state('networkidle')
        p.wait_for_selector('#loginSubmitBtn:not([disabled])', state='attached')

    def completar_asistente(self, farmacia='Farmacia Test', provincia='Barcelona', empleados=('Ana', 'Luis')):
        p = self.page
        p.fill('#asNombre', farmacia)
        p.fill('#asProvincia', provincia)
        p.click('#asSiguiente1')
        for e in empleados:
            p.fill('#asEmpNombre', e)
            p.click('#asEmpAnadir')
        p.click('#asFinalizar')
        p.wait_for_selector('#navHorario', state='visible')
        p.wait_for_load_state('networkidle')
        self.cerrar_dialogos()

    def abrir_dialogo(self, dlg):
        boton = self.page.locator(f'[data-dialog="{dlg}"]:visible')
        if boton.count():
            boton.first.click()
        else:  # opciones que en pantallas estrechas están dentro del menú "Más"
            self.page.evaluate('id => document.querySelector(`[data-dialog="${id}"]`).click()', dlg)
        self.page.wait_for_selector(f'#{dlg}:not(.hidden)')

    def responder_dialogo_app(self, aceptar=True):
        """Pulsa Aceptar/Cancelar en el diálogo propio de la app (confirmar/avisar)."""
        boton = self.page.locator(f'.dialogo-app [data-r="{1 if aceptar else 0}"]')
        boton.wait_for()
        boton.click()

    def cerrar_dialogos(self):
        self.page.keyboard.press('Escape')
        expect(self.page.locator('.modal-backdrop:visible')).to_have_count(0)

    def estado(self):
        return self.page.evaluate("JSON.parse(localStorage.getItem('pharmily_v1'))")


@pytest.fixture
def api():
    return ApiSimulada()


@pytest.fixture
def app(browser, base_url, api):
    ctx = browser.new_context(accept_downloads=True, service_workers='block')
    page = ctx.new_page()
    s = Sesion(page, base_url, api)
    yield s
    ctx.close()


@pytest.fixture
def app_lista(app):
    """Admin con sesión iniciada y una farmacia ya creada mediante el asistente."""
    app.abrir()
    app.login()
    app.completar_asistente()
    return app
