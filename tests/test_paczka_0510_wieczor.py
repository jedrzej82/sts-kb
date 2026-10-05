"""Paczka wieczorna 05.10.2026 — usterki z Raportu 05.10 18:00 i rozliczenia 04.10 (Z1 / NFL)."""
import pandas as pd

import dzienniki
import oferta
import rynek
import sporty

D = '2026-10-04'


def _W(*mecze):
    inne = pd.DataFrame([dict(d=pd.Timestamp(D), sport=s, h=h, a=a, pg=pg, pa=pa, ot=ot) for s, h, a, pg, pa, ot in mecze])
    return dict(pilka=pd.DataFrame(columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha']), inne=inne,
                tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))


def test_z1_zwyciezca_meczu_rozliczany():
    # przed: „rynek »Z1 (Zwyciezca meczu)« nieobslugiwany” (Servette – Zug 2:1, Pardubice – Sparta 6:4)
    W = _W(('hokej', 'Servette Geneva', 'EV Zug', 2, 1, 1), ('hokej', 'Dynamo Pardubice', 'Sparta Praha', 3, 4, 0))
    r = dict(sport='hokej', zdarzenie='Servette Geneva - EV Zug', rynek='Z1 (Zwyciezca meczu)', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[0] == 'TRAFIONY'        # Z1 = z dogrywka: wygrana po dogrywce wchodzi
    r = dict(sport='hokej', zdarzenie='Servette Geneva - EV Zug', rynek='1', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[0] == 'PRZEGRANY'       # „1” = czas regulaminowy
    r = dict(sport='hokej', zdarzenie='Dynamo Pardubice - Sparta Praga', rynek='Z1', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[0] == 'PRZEGRANY'
    r = dict(sport='hokej', zdarzenie='Dynamo Pardubice - Sparta Praga', rynek='Z2 (Zwyciezca meczu)', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[0] == 'TRAFIONY'


def test_nfl_skroty_z_sporty_hist_rozliczane(tmp_path, monkeypatch):
    # przed: sporty_hist ma NFL jako „SEA - LAC”, dzienniki czytaly to bez rozwiniecia -> „nie dopasowano: Seattle Seahawks”
    pd.DataFrame([dict(data=D, sport='futbol amerykański', liga='NFL', gosp='SEA', gosc='LAC', pg=30, pa=23, dogrywka=0),
                  dict(data=D, sport='baseball', liga='MLB', gosp='SEA', gosc='NYA', pg=1, pa=2, dogrywka=0)]
                 ).to_csv(tmp_path / 'sporty_hist.csv', index=False)
    import zewn
    monkeypatch.setattr(zewn, 'inne', lambda: pd.DataFrame())
    w = dzienniki.wyniki_inne(str(tmp_path))
    assert set(w.h) == {'Seattle Seahawks', 'Seattle Mariners'}
    W = dict(pilka=None, inne=w, tenis=None)
    r = dict(sport='futbol amerykański', zdarzenie='Seattle Seahawks - Los Angeles Chargers', rynek='Z1', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', '30:23')


def test_kod_rynku_gosc_bez_ogonka():
    assert rynek.kod_rynku('gosc_O0.5') == 'gość_O0.5' and rynek.kod_rynku('Gość_O1.5') == 'gość_O1.5'
    assert rynek.kod_rynku('gosp_O0.5') == 'gosp_O0.5' and rynek.kod_rynku('X2') == 'X2'
    assert rynek.kursy_z_argv(['A', '--kurs', 'gosc_O0.5=1.65'])[1] == {'gość_O0.5': 1.65}


def test_zamkniecia_pdf_sprzed_przebiegu_pomijany():
    # 05.10 18:00: PDF 17:25 wpisal nogom AKOP-1800 „zamkniecie” = kurs typu (CLV 0)
    k = pd.DataFrame([dict(data_meczu='2026-10-05', godzina_meczu='20:00', sport='PIŁKA NOŻNA', gospodarz='UAI Urquiza',
                           gosc='CA Ituzaingo', rynek='U3.5', kurs=kurs, godzina_pobrania=p)
                      for kurs, p in (('1.21', '2026-10-05 17:25'), ('1.18', '2026-10-05 19:30'))])
    kol = ['data', 'godzina_uruchomienia', 'tag', 'nr_kuponu', 'noga_nr', 'sport', 'zdarzenie', 'rynek', 'kurs', 'uwaga',
           'kurs_zamkniecia']
    a = pd.DataFrame([dict(zip(kol, ('2026-10-05', '18:00', 'AKOP-1800-1', '1', '1', 'pilka', 'UAI Urquiza - CA Ituzaingo',
                                     'U3.5', '1.21', 'mecz 2026-10-05 20:00', '')))])
    z, _ = oferta.zamkniecia(k.iloc[:1], a)
    assert len(z) == 0                                   # tylko PDF sprzed przebiegu -> brak zamkniecia
    z, _ = oferta.zamkniecia(k, a)
    assert list(z.kurs_zamkniecia) == ['1.18']           # PDF po przebiegu, przed meczem


def test_tabela_apu_udine_przypieta_do_meczow(monkeypatch):
    mecze = pd.DataFrame([dict(data=pd.Timestamp('2026-09-2%d' % i), sport='koszykówka', liga='Italy | Lega A',
                               gosp='Amici Pallacanestro Udinese', gosc='Cantu', pg=80, pa=70, dogrywka=0) for i in range(1, 4)])
    monkeypatch.setattr(sporty, 'seeds', lambda sport: [(pd.Timestamp('2026-09-01'), 'APU Udine', 1550.0, 28, 'Lega A')])
    R, N, *_ = sporty.elo(mecze, 'koszykówka')
    assert 'APU Udine' not in R and 'Amici Pallacanestro Udinese' in R
    assert sporty.resolve('APU Udine', {'Amici Pallacanestro Udinese', 'Cantu'}, 'koszykówka') == 'Amici Pallacanestro Udinese'
