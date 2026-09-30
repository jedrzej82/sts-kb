"""Oferta 30.09 17:30 (okno 21:00): nazwy STS z Paragwaju i Wenezueli — alias trafia w klub z tej samej ligi."""
import typuj


def test_aliasy_typuj_oferta_3009():
    pula = {'Club Nacional', 'Nacional', 'Atletico Nacional', 'Zamora FC', 'Zamora FC B', 'Puerto Cabello U20', 'Yaracuyanos'}
    assert typuj.resolve('Nacional Asuncion', pula) == 'Club Nacional'
    assert typuj.resolve('Zamora FC II', pula) == 'Zamora FC B'
    assert typuj.resolve('Academia Puerto Cabello II', pula) == 'Puerto Cabello U20'


def test_alias_tylko_gdy_cel_w_puli():
    assert typuj.resolve('Zamora FC II', {'Zamora FC'}) is None   # rezerwa nie trafia w pierwsza druzyne


def test_aliasy_raport_3009_1800():
    """Raport 30.09 18:00, usterka 5: pary z Raportu — jedyny klub o tej nazwie w bazie; kobiety nie trafiaja."""
    import sporty
    assert typuj.resolve('CA Rentistas', {'Rentistas', 'Cerro Largo'}) == 'Rentistas'
    assert sporty.resolve('UMF Tindastoll', {'Tindastoll', 'Tindastoll W', 'Bristol Flyers'}, 'koszykówka') == 'Tindastoll'
    assert sporty.resolve('Tatran Presov', {'Presov', 'Bergischer HC'}, 'piłka ręczna') == 'Presov'
