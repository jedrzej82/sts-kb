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
    monkeypatch.setattr(zewn, 'ZD', zewn.ZD)
    monkeypatch.setattr(zewn, 'inne', lambda tylko_github=False: pd.DataFrame())
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


def test_rynek_typu_z_dziennika_sportow():
    assert [sporty._rynek_typu(m) for m in ('1', '2', 'Z1', 'zwyciezca_1', '2_dogrywka', 'AKOP_1', 'ODRZ_2', '1_60min', 'X')] == \
        ['Z1', 'Z2', 'Z1', 'Z1', 'Z2', 'Z1', 'Z2', '1 (60 min)', 'X']


def test_dziennik_typow_rozlicza_nazwy_z_oferty():
    # przed: sporty.py rozlicz porownywal nazwy doslownie — „Motor Ceske Budejovice” (oferta) nigdy nie trafial
    # w „HC České Budějovice” (baza): 200 z 216 typow bez rozliczenia. Wynik 05.10: 5:1 (flashscore).
    W = _W(('hokej', 'HC České Budějovice', 'Kometa Brno', 5, 1, 0), ('hokej', 'Servette Geneva', 'EV Zug', 2, 1, 1))
    W['inne'].loc[0, 'd'] = pd.Timestamp('2026-10-05')
    L = pd.DataFrame([dict(data='2026-10-05', sport='hokej', gosp='Motor Ceske Budejovice', gosc='Kometa Brno', rynek='Z1', p=0.567,
                           trafiony=None),
                      dict(data=D, sport='hokej', gosp='Servette Geneva', gosc='EV Zug', rynek='1_60min', p=0.5, trafiony=None),
                      dict(data=D, sport='hokej', gosp='Servette Geneva', gosc='EV Zug', rynek='1', p=0.6, trafiony=None)])
    L = sporty.rozlicz_typy(L, W)
    assert list(L.trafiony) == [1, 0, 1]      # Z1 trafiony; 1 w 60 min przegrany (dogrywka); „1” = z dogrywka


def test_nhl_z_365_do_rozliczen_tylko_po_koncu_github(tmp_path, monkeypatch):
    # GitHub NHL konczy sie 15.06 — mecze z pazdziernika tylko z 365scores; dni pokryte przez GitHub bez dubli
    import zewn
    monkeypatch.setattr(zewn, 'ZD', zewn.ZD)        # wyniki_inne ustawia zewn.ZD — po tescie wraca oryginal
    kol = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'.split(',')
    pd.DataFrame([['2026-09-30', 'hockey', 'USA', 'NHL', '', 'Philadelphia Flyers', 'Pittsburgh Penguins', 0, 7, '', '', 2, ''],
                  ['2026-06-15', 'hockey', 'USA', 'NHL', '', 'Vegas Golden Knights', 'Carolina Hurricanes', 0, 3, '', '', 2, ''],
                  ['2026-09-30', 'hockey', 'Finland', 'Liiga', '', 'Tappara', 'Ilves', 3, 2, '', '', 1, '']],
                 columns=kol).to_csv((tmp_path / 'zewn').mkdir() or tmp_path / 'zewn' / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    pd.DataFrame([dict(data='2026-06-15', sport='hokej', liga='NHL', gosp='Vegas Golden Knights', gosc='Carolina Hurricanes',
                       pg=0, pa=3, dogrywka=-1)]).to_csv(tmp_path / 'sporty_hist.csv', index=False)
    w = dzienniki.wyniki_inne(str(tmp_path))
    assert len(w[w.h == 'Philadelphia Flyers']) == 1 and len(w[w.h == 'Vegas Golden Knights']) == 1 and len(w[w.h == 'Tappara']) == 1
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path / 'zewn'))
    assert 'Philadelphia Flyers' not in set(zewn.inne().gosp)          # do sporty_hist (model) NHL z 365 nie wchodzi


def test_remis_koncowy_w_recznej_przegrywa_rynek_zwyciezcy():
    # HSG Wetzlar – Rhein-Neckar Löwen 02.10: 30:30 (Bundesliga, bez dogrywki) — typ „2” byl „sprawdz recznie”
    W = _W(('piłka ręczna', 'HSG Wetzlar', 'Rhein-Neckar Löwen', 30, 30, -1), ('hokej', 'Tappara', 'Ilves', 3, 3, -1))
    r = dict(sport='piłka ręczna', zdarzenie='HSG Wetzlar - Rhein-Neckar Lowen', rynek='Z2', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[0] == 'PRZEGRANY'
    r = dict(sport='hokej', zdarzenie='Tappara - Ilves', rynek='Z1', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[0] == 'BRAK WYNIKU'       # hokej: remis w danych = brak zapisu karnych


def test_bt_model_rynek_kursy_bez_marzy():
    import bt_model_rynek as bt
    r = pd.Series(dict(OddHome=2.0, OddDraw=3.5, OddAway=4.0, Over25=1.8, Under25=2.0))
    k = bt.kursy_rynku(r)
    assert abs(k['1'][1] + k['X'][1] + k['2'][1] - 1) < 1e-9 and abs(k['O2.5'][1] + k['U2.5'][1] - 1) < 1e-9
    assert abs(k['1X'][0] - 1 / (1 / 2.0 + 1 / 3.5)) < 1e-9 and abs(k['1X'][1] - (k['1'][1] + k['X'][1])) < 1e-9
    assert bt.kursy_rynku(pd.Series(dict(OddHome=float('nan'), OddDraw=3.5, OddAway=4.0, Over25=None, Under25=None))) == {}
