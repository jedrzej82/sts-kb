"""Raport 15.10 15:00 nr 8 (P77.1 „puchary tylko na papierze”): Union SG – Real Sociedad (--kontynentalny, oba kluby z Elo)
dostal „✔ NOGA DOPUSZCZONA” 1X i trafil do nogi.csv, a kupon.py wzial go do K5/MIX — przebieg odrzucal recznie.
Sprawdzone na bazie: stary kod zapisywal noge (1X @1.75, EV +16%), nowy wypisuje „NIE NA KUPON: PUCHAR” i nogi.csv pusty."""
import typuj


def test_zakaz_nogi_w_pucharze():
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B', '--kontynentalny'], None).startswith('PUCHAR')
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B'], {'turniej': 'Copa do Brasil', 'kraj': 'Brazil'}).startswith('PUCHAR')
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B'], {'turniej': 'Puchar Polski', 'kraj': 'Poland'})
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B'], {'turniej': 'Premier League', 'kraj': 'England'}) is None
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B'], None) is None


def test_werdykt_blokuje_noge_przy_zakazie():
    typuj.KONTEKST_MECZU.clear()
    typuj.KONTEKST_MECZU['zakaz_nogi'] = typuj.zakaz_pucharu(['--kontynentalny'], None)
    pk, powod = typuj.werdykt_nogi('1X', None)
    assert pk is None and powod.startswith('PUCHAR')
    typuj.KONTEKST_MECZU.clear()
