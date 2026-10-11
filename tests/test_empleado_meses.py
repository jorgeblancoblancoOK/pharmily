"""El empleado puede ver su horario de otros meses (‹ ›), si el servidor admite ?desde=&hasta=."""
import datetime as dt

from playwright.sync_api import expect

HOY = dt.date.today()


def base(turnos=()):
    return {'hoy': HOY.isoformat(), 'lunesSemana': (HOY - dt.timedelta(days=HOY.weekday())).isoformat(),
            'empleado': {'nombre': 'Ana López', 'rol': 'auxiliar'}, 'farmacia': {'nombre': 'Farmacia Test'},
            'proximosTurnos': list(turnos), 'diasSemana': [], 'ausencias': [], 'horasSemana': 0}


def mes_siguiente(d, n=1):
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 10)


def entrar_como_empleado(app, api):
    api.rol = 'empleado'
    app.abrir()
    app.login()
    app.page.wait_for_selector('#empMeses .emp-meses-nombre')


def test_meses_con_servidor_que_admite_rango(app, api):
    lejos = mes_siguiente(HOY, 3)
    api.mi_horario = base()

    def por_rango(desde, hasta):
        r = base([{'fecha': lejos.isoformat(), 'inicio': '09:00', 'fin': '14:00'}])
        r['proximosTurnos'] = [t for t in r['proximosTurnos'] if desde <= t['fecha'] <= hasta]
        r['ausencias'] = [{'tipo': 'vacaciones', 'inicio': lejos.isoformat(), 'fin': lejos.isoformat(), 'estado': 'aprobada'}] \
            if desde <= lejos.isoformat() <= hasta else []
        r.update(desde=desde, hasta=hasta)
        return r
    api.mi_horario_por_rango = por_rango
    entrar_como_empleado(app, api)
    p = app.page
    for _ in range(3):
        p.click('#empMesNext')
    meses = p.locator('#empMeses')
    expect(meses).to_contain_text('Vacaciones')       # ese día está de vacaciones
    expect(meses).to_contain_text('no cuenta')
    assert 'solo comparte' not in meses.inner_text()
    assert any(r == 'mi-horario' and auth == 'Bearer token-de-prueba' for _, r, auth in api.llamadas)
    assert app.errores == []


def test_meses_con_servidor_antiguo_avisa(app, api):
    manana = HOY + dt.timedelta(days=1)
    api.mi_horario = base([{'fecha': manana.isoformat(), 'inicio': '16:00', 'fin': '20:00'}])
    entrar_como_empleado(app, api)
    meses = app.page.locator('#empMeses')
    expect(meses).to_contain_text('14 días')
    app.page.click('#empMesNext')
    expect(meses).to_contain_text('No hay turnos a la vista')
    assert app.errores == []


def test_limites_de_navegacion(app, api):
    api.mi_horario = base()
    entrar_como_empleado(app, api)
    p = app.page
    for _ in range(10):
        if p.is_disabled('#empMesNext'):
            break
        p.click('#empMesNext')
    assert p.is_disabled('#empMesNext')
