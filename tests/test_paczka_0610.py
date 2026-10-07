"""Paczka 06.10.2026 — usterki z Raportu 05.10 21:00."""
import pandas as pd

import dzienniki
import sporty
import tenis

D = '2026-10-02'


def test_remis_koncowy_przegrywa_rynek_regulaminowy_bez_wiedzy_o_dogrywce():
    # Wetzlar – Löwen 30:30, ako_log rynek „2” (czas regulaminowy), dogrywka nieznana (-1): bylo BRAK WYNIKU
    W = dict(pilka=None, tenis=None, inne=pd.DataFrame([dict(d=pd.Timestamp(D), sport='piłka ręczna', h='HSG Wetzlar',
                                                              a='Rhein-Neckar Löwen', pg=30, pa=30, ot=-1)]))
    r = dict(sport='reczna', zdarzenie='HSG Wetzlar - Rhein-Neckar Lowen', rynek='2', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('PRZEGRANY', '30:30')
    W['inne'].loc[0, ['pg', 'pa']] = [29, 30]           # wygrana bez wiedzy o dogrywce — dalej nie zgadujemy
    assert dzienniki.rozlicz_noge(r, W)[0] == 'BRAK WYNIKU'


def test_aliasy_lnb_argentyna():
    pula = {'Quimsa', 'Quimsa (W)', 'Atenas', 'Atletico Atenas', 'Club Atenas La Plata'}
    assert sporty.resolve('Quimsa Santiago del Estero', pula, 'koszykówka') == 'Quimsa'
    assert sporty.resolve('Atenas Cordoba', pula, 'koszykówka') == 'Atenas'


def test_tenis_jedna_spacja_w_nazwisku(tmp_path, monkeypatch):
    w = [dict(date=f'2026-06-{10 + i}', zwyciezca=z, przegrany=p, score='6-4 6-4', nawierzchnia='Hard', tour='WTA',
              poziom='C') for i, (z, p) in enumerate([('Alicia  Dudeney', 'Yidi Yang'), ('Alicia Dudeney', 'Himeno Sakatsume'),
                                                      ('Ashlyn Krueger', 'Alicia  Dudeney ')])]
    pd.DataFrame(w).to_csv(tmp_path / 'h.csv', index=False)
    monkeypatch.setattr(tenis, 'HIST', str(tmp_path / 'h.csv'))
    monkeypatch.setattr(tenis, 'DELTA', str(tmp_path / 'brak.csv'))
    d = tenis.load()
    n = set(d.winner_name) | set(d.loser_name)
    assert 'Alicia Dudeney' in n and not any('  ' in x or x != x.strip() for x in n)


def test_u35_p_do_kuponu_min_model_rynek():
    import rynek
    # Wlochy – Turcja 05.10, PDF 17:30: U3.5 1.62 / O3.5 2.30; model 70,4% -> rynek 58,7% (noga przegrala 2:3+)
    kursy = {'U3.5': 1.62, 'O3.5': 2.30, '1': 1.40, 'X': 5.10, '2': 7.75}
    p, uw = rynek.p_kuponu_wg_rynku('U3.5', 0.704, kursy)
    assert abs(p - 0.5868) < 0.001 and 'liczy sie mniejsze' in uw
    assert rynek.p_kuponu_wg_rynku('U3.5', 0.55, kursy) == (0.55, None)        # rynek wyzej — zostaje model (A2)
    assert rynek.p_kuponu_wg_rynku('U2.5', 0.704, {'U2.5': 1.30, 'O2.5': 3.5}) == (0.704, None)   # inne rynki bez zmian
    assert rynek.p_kuponu_wg_rynku('U3.5', 0.704, {}) == (0.704, None)          # bez kursow nic nie zmienia


def test_bt_ou35_rynek_z_kursow_na_25():
    import bt_ou35
    assert abs(bt_ou35.p_ponizej(bt_ou35.lam_z_over25(0.5), 2) - 0.5) < 1e-6
    p = bt_ou35.p_rynku_u35(1.80, 2.05)          # rynek ok. 53% na powyzej 2.5 -> ok. 69% na ponizej 3.5
    assert 0.68 < p < 0.70 and bt_ou35.p_rynku_u35(float('nan'), 2.0) is None


def test_u35_liga_bramkostrzelna_i_o25_reprezentacji(monkeypatch):
    import typuj
    monkeypatch.setattr(typuj, 'LIGA_BEZ_TESTU', None)
    dz = {'U3.5': 0.74, 'O2.5': 0.78, '1X': 0.80}
    typuj.KONTEKST_MECZU.clear(); typuj.KONTEKST_MECZU['sr_goli_ligi'] = 3.79      # OBOS-ligaen 2025/26
    p, powod = typuj.werdykt_nogi('U3.5', dz)
    assert p is None and 'Poprawka 146' in powod
    assert typuj.werdykt_nogi('1X', dz) == (0.80, None)
    typuj.KONTEKST_MECZU['sr_goli_ligi'] = 2.6
    assert typuj.werdykt_nogi('U3.5', dz) == (0.74, None)
    assert typuj.werdykt_nogi('O2.5', dz) == (0.78, None)                       # kluby: O2.5 bez zmian
    typuj.KONTEKST_MECZU.clear(); typuj.KONTEKST_MECZU['intl'] = True
    p, powod = typuj.werdykt_nogi('O2.5', dz)
    assert p is None and 'reprezentacje' in powod
    typuj.KONTEKST_MECZU.clear()


def test_srednia_goli_ligi():
    import typuj
    m = pd.DataFrame(dict(Division=['A'] * 40 + ['B'] * 10, MatchDate=pd.Timestamp('2026-09-01'),
                          FTHome=[3] * 40 + [5] * 10, FTAway=[1] * 40 + [5] * 10))
    assert typuj.srednia_goli_ligi(m, {'A', 'B'}, dzis='2026-10-06') == 4.0         # B ma < 30 meczow — pominieta
    assert typuj.srednia_goli_ligi(m, {'B'}, dzis='2026-10-06') is None
    assert typuj.srednia_goli_ligi(m, {'A'}, dzis='2027-12-01') is None            # stare mecze poza 12 mies.


def _nogi(tmp_path, w):
    f = tmp_path / 'nogi.csv'
    pd.DataFrame(w, columns=['mecz', 'rynek', 'p', 'kurs', 'szacunek', 'polski', 'marza', 'kryteria', 'sport', 'ev_dodatni']).to_csv(f, index=False)
    return str(f)


def test_ako_pilka_dnia_najpewniejszy_15_20(tmp_path, capsys):
    import kupon
    f = _nogi(tmp_path, [('A - B', '1X', 0.88, 1.20, 0, 0, '', '', 'pilka', 0),
                         ('C - D', 'U4.5', 0.90, 1.15, 0, 0, '', '', 'pilka', 0),
                         ('E - F', '12', 0.80, 1.30, 0, 0, '', '', 'pilka', 0),
                         ('G - H', 'O1.5', 0.70, 1.45, 0, 0, '', '', 'pilka', 1),
                         ('I - J', 'Z1', 0.95, 1.40, 0, 0, '', '', 'hokej', 1)])       # hokej — nie do AKO PILKA
    kupon.main([f, '--depozyt', '45.35'])
    out = capsys.readouterr().out
    linia = next(x for x in out.splitlines() if x.startswith('AKO PILKA DNIA'))
    assert 'kurs 1.56' in linia and 'laczne P 70.4%' in linia      # A-B 1X 1.20 x E-F 12 1.30 = 1.56; P 0.88 x 0.80
    assert 'I - J' not in out.split('AKO PILKA DNIA')[1]
    assert 'NIE za wlasne pieniadze' in out                            # EV <= 0 -> tylko bonus/papier (CZESC A)
    k1_k5 = out.split('NAJPEWNIEJSZY MIX')[0]
    assert 'A - B' not in k1_k5 and 'E - F' not in k1_k5             # nogi ev_dodatni=0 nie trafiaja do K1–K5


def test_ako_pilka_dnia_brak(tmp_path, capsys):
    import kupon
    kupon.main([_nogi(tmp_path, [('A - B', '1X', 0.88, 1.10, 0, 0, '', '', 'pilka', 0)]), '--depozyt', '45.35'])
    assert 'AKO PILKA DNIA (1.50–2.00): brak' in capsys.readouterr().out


def test_ako_bonus_lvbet_min_175(tmp_path, capsys):
    import kupon
    f = _nogi(tmp_path, [('A - B', '1X', 0.88, 1.25, 0, 0, '', '', 'pilka', 0),
                         ('C - D', 'U4.5', 0.86, 1.20, 0, 0, '', '', 'pilka', 0),
                         ('E - F', '12', 0.80, 1.20, 0, 0, '', '', 'pilka', 0),
                         ('G - H', 'O1.5', 0.60, 1.80, 1, 0, '', '', 'pilka', 1)])     # szacunek — nie do bonusu
    kupon.main([f, '--depozyt', '45.35'])
    out = capsys.readouterr().out.split('AKO BONUS LVBET')[1]
    assert '1. P 60.5% | kurs STS 1.80' in out                       # 1.25 x 1.20 x 1.20 = 1.80 >= 1.75; P 0.88 x 0.86 x 0.80
    assert 'G - H' not in out and 'trzy takie kupony pod rzad: ok. 22%' in out
    kupon.main([_nogi(tmp_path, [('A - B', '1X', 0.88, 1.25, 0, 0, '', '', 'pilka', 0)]), '--depozyt', '45.35'])
    assert 'AKO BONUS LVBET (kurs >= 1.75): brak' in capsys.readouterr().out


# ---- poszukiwanie usterek 06.10: rozliczenia 20.09–05.10 na danych z paczki 06.10 ----

def _Wp(*mecze):
    return dict(pilka=pd.DataFrame([dict(d=pd.Timestamp(d), h=h, a=a, g=g, ga=ga, hg=None, ha=None) for d, h, a, g, ga in mecze]),
                inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']), tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))


def test_godzina_w_nazwie_meczu_i_egzonim():
    # ako_log 20.09: „OGC Nice - LOSC Lille (17:15)”, „Dinamo Zagrzeb - Lokomotiva Zagrzeb (20:00)” — bylo „nie dopasowano”
    W = _Wp(('2026-09-20', 'OGC Nice', 'LOSC Lille', 2, 1), ('2026-09-20', 'Dinamo Zagreb', 'NK Lokomotiva Zagreb', 3, 2))
    r = dict(sport='pilka', zdarzenie='OGC Nice - LOSC Lille (17:15)', rynek='U4.5', data='2026-09-20', uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', '2:1')
    r = dict(sport='pilka', zdarzenie='Dinamo Zagrzeb - Lokomotiva Zagrzeb (20:00)', rynek='1X', data='2026-09-20', uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', '3:2')


def test_rynki_laczone_i_gole_druzyny():
    W = _Wp(('2026-10-03', 'Switzerland', 'Slovenia', 2, 1), ('2026-10-03', 'North Macedonia', 'Scotland', 0, 2))
    noga = lambda z, ry: dict(sport='pilka', zdarzenie=z, rynek=ry, data='2026-10-03', uwaga='')
    assert dzienniki.rozlicz_noge(noga('Switzerland - Slovenia', '1 + gosp_O2.5'), W)[0] == 'PRZEGRANY'   # 2 gole gosp.
    assert dzienniki.rozlicz_noge(noga('Switzerland - Slovenia', '1 + gosp_O1.5'), W)[0] == 'TRAFIONY'
    assert dzienniki.rozlicz_noge(noga('North Macedonia - Scotland', 'gość gole 1-2'), W)[0] == 'TRAFIONY'
    stan, _, uw = dzienniki.rozlicz_noge(noga('Switzerland - Slovenia', 'O1.5 + strzaly O29.5'), W)
    assert stan == 'BRAK WYNIKU' and 'spoza wyniku' in uw                                           # nie zgadujemy strzalow


def test_tenis_data_poczatku_turnieju():
    # czesc tenis_hist ma date poczatku turnieju (21.09), noga z 24.09 — bylo „nie dopasowano”
    W = dict(pilka=None, inne=None, tenis=pd.DataFrame([dict(d=pd.Timestamp('2026-09-21'), w='Maria Sakkari', l='Nao Hibino',
                                                             score='7-5 6-1')]))
    r = dict(sport='tenis', zdarzenie='Sakkari Maria - Hibino Nao', rynek='Zwyciezca Sakkari', data='2026-09-24', uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[0] == 'TRAFIONY'
    W['tenis'] = pd.concat([W['tenis'], pd.DataFrame([dict(d=pd.Timestamp('2026-09-19'), w='Nao Hibino', l='Maria Sakkari', score='6-1 6-1')])])
    assert dzienniki.rozlicz_noge(r, W)[0] == 'BRAK WYNIKU'            # dwa mecze tej pary z roznym zwyciezca — nie zgadujemy


def test_kotwica_jedyny_rywal_dnia_dwa_zrodla():
    # sporty_typy 19.09: Trinec – „Plzen” (w bazie HC Plzen 1929, ten sam mecz z 365 i Flashscore)
    mecze = [('2026-09-18', 'Třinec', 'Kometa Brno', 6, 5), ('2026-09-19', 'Třinec', 'HC Plzeň 1929', 3, 2),
             ('2026-09-19', 'Třinec', 'HC Plzeň 1929', 3, 2), ('2026-09-19', 'HC Plzeň 1929 B', 'Tabor', 1, 0)]
    W = dict(pilka=None, tenis=None, inne=pd.DataFrame([dict(d=pd.Timestamp(d), sport='hokej', h=h, a=a, pg=x, pa=y, ot=0)
                                                       for d, h, a, x, y in mecze]))
    r = dict(sport='hokej', zdarzenie='Třinec - Plzeň', rynek='1 (60 min)', data='2026-09-19', uwaga='')
    stan, wyn, uw = dzienniki.rozlicz_noge(r, W)
    assert (stan, wyn) == ('TRAFIONY', '3:2') and 'po jednej druzynie' in uw
    assert dzienniki._czlony_zawarte('Plzeň', 'HC Plzeň 1929') and not dzienniki._czlony_zawarte('Plzeň B', 'HC Plzeň 1929')


def test_aliasy_i_kraj_z_rozliczen_0610():
    import typuj
    assert typuj._kraj_pl('Wyspy Sw. Tomasza i Ksiazeca', {'São Tomé and Príncipe', 'Gibraltar'}) == 'São Tomé and Príncipe'
    assert sporty.resolve('Basquet Coruna', {'Leyma Coruña', 'Bilbao Basket'}, 'koszykówka') == 'Leyma Coruña'
    assert sporty.resolve('Oakland Athletics', {'Athletics', 'Cleveland Guardians'}, 'baseball') == 'Athletics'


def test_samokontrola_podejrzenie_i_brak():
    import samokontrola as s
    d = pd.DataFrame([dict(zrodlo='ako_log', sport='pilka', liga='Peru | Liga 1', rynek='U3.5', p=0.75, traf=int(i < 53))
                      for i in range(80)]
                     + [dict(zrodlo='ako_log', sport='pilka', liga='Spain | LaLiga', rynek='1X', p=0.80, traf=int(i < 42))
                        for i in range(50)])
    lin = s.linie(d)
    assert any('PODEJRZENIE: rynek U3.5 w lidze Peru | Liga 1 (pilka) zawyzony (P 75%, wchodzi 66%, n=80' in x for x in lin)
    assert not any('Spain' in x for x in lin)                      # 84% przy P 80% — w porzadku
    assert not any('PODEJRZENIE' in x for x in s.linie(d[d.liga == 'Spain | LaLiga']))
    assert not any('PODEJRZENIE' in x for x in s.linie(d.head(40)))  # n < 50 — za malo, zeby wskazywac


def test_samokontrola_rynki_sportow():
    import samokontrola as s
    assert s._rynek('pilka', 'Liczba goli ponizej 3.5') == 'U3.5'
    assert [s._rynek('hokej', x) for x in ('Z1 (Zwyciezca meczu)', 'zwyciezca_1', '1_60min')] == ['Z1', 'Z1', '1 (60 min)']
    assert s._sport('piłka nożna') == 'pilka' and s._sport('koszykowka') == 'koszykówka' and s._p('74,5') == 0.745
