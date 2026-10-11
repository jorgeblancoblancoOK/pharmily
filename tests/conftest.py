"""Fixtures comunes: servidor estático local + navegador Chromium (Playwright)."""
import functools
import http.server
import os
import threading

import pytest
from playwright.sync_api import sync_playwright

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


class Sesion:
    """Página nueva y aislada que registra errores, diálogos y violaciones de CSP."""

    def __init__(self, page, base_url):
        self.page, self.base_url = page, base_url
        self.errores, self.dialogos, self.csp = [], [], []
        page.on('pageerror', lambda e: self.errores.append(str(e)))
        page.on('console', self._consola)
        page.on('dialog', self._dialogo)
        # Sin internet en CI: la librería de Supabase se sustituye por nada (modo 100% local).
        page.route('https://cdn.jsdelivr.net/**', lambda r: r.fulfill(status=200, body='', content_type='application/javascript'))

    def _consola(self, m):
        if 'Content Security Policy' in m.text:
            self.csp.append(m.text)

    def _dialogo(self, d):
        self.dialogos.append(d.message)
        d.accept()  # confirm() de la app → "Aceptar"; alert() de un XSS también queda registrado

    def abrir(self, ruta='/Pharmily.html'):
        self.page.goto(self.base_url + ruta)
        self.page.wait_for_load_state('networkidle')

    def completar_asistente(self, farmacia='Farmacia Test', provincia='Barcelona', empleados=('Ana', 'Luis')):
        p = self.page
        p.fill('#asNombre', farmacia)
        p.fill('#asProvincia', provincia)
        p.click('#asSiguiente1')
        for e in empleados:
            p.fill('#asEmpNombre', e)
            p.click('#asEmpAnadir')
        p.click('#asFinalizar')
        p.wait_for_selector('#topNav', state='visible')

    def abrir_dialogo(self, dlg):
        self.page.click(f'#topNav [data-dialog="{dlg}"]')
        self.page.wait_for_selector(f'#{dlg}:not(.hidden)')

    def estado(self):
        return self.page.evaluate("JSON.parse(localStorage.getItem('pharmily_v1'))")


@pytest.fixture
def app(browser, base_url):
    ctx = browser.new_context(accept_downloads=True, service_workers='block')
    page = ctx.new_page()
    s = Sesion(page, base_url)
    yield s
    ctx.close()


@pytest.fixture
def app_lista(app):
    """App con una farmacia ya creada mediante el asistente."""
    app.abrir()
    app.completar_asistente()
    return app
