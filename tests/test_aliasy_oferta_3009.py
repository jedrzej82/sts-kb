"""Oferta 30.09 17:30 (okno 21:00): nazwy STS z Paragwaju i Wenezueli — alias trafia w klub z tej samej ligi."""
import typuj


def test_aliasy_typuj_oferta_3009():
    pula = {'Club Nacional', 'Nacional', 'Atletico Nacional', 'Zamora FC', 'Zamora FC B', 'Puerto Cabello U20', 'Yaracuyanos'}
    assert typuj.resolve('Nacional Asuncion', pula) == 'Club Nacional'
    assert typuj.resolve('Zamora FC II', pula) == 'Zamora FC B'
    assert typuj.resolve('Academia Puerto Cabello II', pula) == 'Puerto Cabello U20'


def test_alias_tylko_gdy_cel_w_puli():
    assert typuj.resolve('Zamora FC II', {'Zamora FC'}) is None   # rezerwa nie trafia w pierwsza druzyne
