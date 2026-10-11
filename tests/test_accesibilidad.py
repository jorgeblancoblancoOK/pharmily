"""Pruebas de accesibilidad básicas (WCAG): etiquetas, nombres accesibles, teclado, alt."""


def _visibles_sin_etiqueta(page):
    return page.evaluate("""() => [...document.querySelectorAll('input:not([type=file]):not([type=hidden]), select, textarea')]
      .filter(i => i.offsetParent && !i.labels?.length && !i.getAttribute('aria-label') && !i.getAttribute('aria-labelledby'))
      .map(i => i.id || i.outerHTML.slice(0, 60))""")


def test_asistente_campos_etiquetados(app):
    app.abrir()
    assert _visibles_sin_etiqueta(app.page) == []


def test_ventanas_campos_etiquetados(app_lista):
    faltan = {}
    for dlg in ['dlgEmpleados', 'dlgPlantillas', 'dlgVacaciones', 'dlgComputo', 'dlgTexto', 'dlgConfig', 'dlgCuenta']:
        app_lista.abrir_dialogo(dlg)
        f = _visibles_sin_etiqueta(app_lista.page)
        if f:
            faltan[dlg] = f
        app_lista.page.keyboard.press('Escape')
    assert faltan == {}


def test_botones_con_nombre_accesible(app_lista):
    sin_nombre = app_lista.page.evaluate("""() => [...document.querySelectorAll('button')]
      .filter(b => b.offsetParent && !b.textContent.trim() && !b.getAttribute('aria-label') && !b.title)
      .map(b => b.id || b.outerHTML.slice(0, 60))""")
    assert sin_nombre == []


def test_imagenes_con_alt(app_lista):
    assert app_lista.page.evaluate("document.querySelectorAll('img:not([alt])').length") == 0


def test_navegacion_por_teclado_con_foco_visible(app_lista):
    p = app_lista.page
    vistos = set()
    for _ in range(15):
        p.keyboard.press('Tab')
        info = p.evaluate("""() => { const e = document.activeElement, s = getComputedStyle(e);
          return [e.tagName, e.id, s.outlineStyle !== 'none' || s.boxShadow !== 'none'] }""")
        if info[0] in ('BUTTON', 'INPUT', 'SELECT', 'A'):
            vistos.add(info[1])
            assert info[2], f'Sin indicador de foco: {info}'
    assert len(vistos) >= 5


def test_idioma_declarado(app):
    app.abrir()
    assert app.page.get_attribute('html', 'lang') == 'es'
