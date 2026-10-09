"""Raport 09.10 18:00 nr 1: AKO PILKA DNIA „brak” mimo 201 nog pilkarskich po bramkach.
_kombinacje bralo 25 nog o najwyzszym P — same O0.5/U4.5 @1,01–1,10; iloczyn 3 takich nog < 1,50.
Pula odtworzona z raportu (nogi AKON-1800 i AKOP-1800 z ich kursami i P; Braga gosc_O0.5 1,28, PSV O2.5 1,19,
Portadown 12 1,22 — P tych trzech nog przyjete, w raporcie ich nie ma). nogi_f.csv tego przebiegu nie trafia na Dysk."""
import pandas as pd

import kupon

NISKIE = [  # AKON-1800 (P z typuj.py ok. 0,95–0,97) i AKOP-1800
    ('NAC Breda - MVV', 'O0.5', .97, 1.01), ('Almere - Eindhoven', 'O0.5', .97, 1.01),
    ('Dortmund - Werder', 'O0.5', .96, 1.02), ('Volendam - Vitesse', 'O0.5', .97, 1.01),
    ('De Graafschap - Jong Utrecht', 'O0.5', .97, 1.01), ('Dordrecht - Emmen', 'O0.5', .96, 1.02),
    ('Anderlecht U23 - Eupen', 'O0.5', .96, 1.02), ('Roda - Jong PSV', 'O0.5', .96, 1.02),
    ('Braga - Sporting', 'O0.5', .93, 1.07), ('TOP Oss - Helmond', 'O0.5', .96, 1.02),
    ('Shelbourne - Sligo', 'O0.5', .899, 1.01), ('Montpellier - Grenoble', 'O0.5', .888, 1.05),
    ('Moreirense - Gil Vicente', 'U4.5', .861, 1.06), ('Montevideo City - Danubio', 'U4.5', .861, 1.09),
]
NISKIE += [(f'Mecz U45 {i}', 'U4.5', .95 - i * .002, 1.04 + (i % 5) / 100) for i in range(14)]
SREDNIE = [('Braga - Sporting', 'gość_O0.5', .82, 1.28), ('PSV - Heerenveen', 'O2.5', .84, 1.19),
           ('Portadown - Glentoran', '12', .82, 1.22), ('Almere - Eindhoven', '12', .835, 1.15),
           ('Nyonnais - Aarau', 'X2', .831, 1.15), ('Tetouan - FUS Rabat', '1X', .71, 1.62)]


def _pula():
    d = pd.DataFrame([dict(mecz=m, rynek=r, p=p, kurs=k) for m, r, p, k in NISKIE + SREDNIE])
    for c, v in (('sport', 'pilka'), ('szacunek', 0), ('polski', 0), ('marza', 1.06), ('kryteria', 6)):
        d[c] = v
    return d


def test_pilka_dnia_nie_brak_przy_pelnej_puli_niskich_kursow():
    d = _pula()
    assert len(d) == 34 and (d.sort_values('p', ascending=False).kurs.head(kupon.MAKS_NOG_KANDYDATOW) <= 1.10).all()
    o = kupon.najlepszy(d, 'PILKA')
    assert o is not None                                   # przed: None („brak”)
    assert kupon.PILKA_KURS[0] <= o['kurs'] <= kupon.PILKA_KURS[1]
    assert len({d.at[i, 'mecz'] for i in o['nogi']}) == len(o['nogi'])
    assert o['p'] > 0.55


def test_bonus_i_mix_tez_siegaja_po_nogi_z_kursem():
    d = _pula()
    assert kupon.najlepszy(d, 'BONUS')                      # 1,75–2,20 z 2–3 nog
    assert kupon.najlepszy(d, 'MIX')['kurs'] >= kupon.MIX_MIN_KURS


def test_bez_progu_kursu_pula_bez_zmian():
    # K1/K2/K3/K5 (kupony za pieniadze) — nadal 25 nog o najwyzszym P
    d = _pula()
    idx = set(i for c in kupon._kombinacje(d, 1, 1) for i in c)
    assert idx == set(d.sort_values('p', ascending=False).index[:kupon.MAKS_NOG_KANDYDATOW])


# ---------------------------------------------------------------- nr 2: sporty.py wypisuje EV, gdy dostal kurs rynku
import sporty  # noqa: E402


def test_werdykt_z_kursem_ma_ev():
    # sprawdzone na bazie 07.10: Eisbaren Berlin Z1, P do kuponu 77,5% @1,45 -> EV -1,1% (0,775 × 1,45 × 0,88 − 1)
    w = sporty.linia_dopuszczona('Eisbären Berlin', True, 0.775, 40, 'Z1', {'Z1': 1.45, 'Z2': 2.60})
    assert w == ('WERDYKT: NOGA DOPUSZCZONA — Eisbären Berlin (z dogrywka), P do kuponu 77.5% | kurs Z1 1.45 | '
                 'EV -1.1% (P × kurs × 0,88 − 1)')
    # z raportu 18:00: Rouen Z1 78,8% @1,18 -> -18,2%
    assert 'EV -18.2%' in sporty.linia_dopuszczona('Rouen', True, 0.788, 30, 'Z1', {'Z1': 1.18})


def test_werdykt_bez_kursu_jak_dotad():
    w = sporty.linia_dopuszczona('A', False, 0.70, 5)
    assert w == 'WERDYKT: NOGA DOPUSZCZONA — A, P do kuponu 70.0% (SZACUNEK: < 10 meczow); EV licz z TEGO P: P × kurs × 0,88 − 1'
    assert sporty.linia_dopuszczona('A', False, 0.70, 20, 'Z1', {'Z2': 2.0}).endswith('EV licz z TEGO P: P × kurs × 0,88 − 1')


# ---------------------------------------------------------------- nr 3: LVBET „RSCA Futures” = STS „RSC Anderlecht U23”
import kursy3  # noqa: E402


def test_lvbet_rsca_futures_to_anderlecht_u23():
    # plik z telefonu 09.10 14:46: LVBET „RSCA Futures - KAS Eupen” 20:00 (O2.5 1,45, X2 1,25); przed: LVBET „brak”
    buk = pd.DataFrame([dict(bukmacher='LVBET', sport='PIŁKA NOŻNA', data_meczu='2026-10-09', godzina_meczu='20:00',
                             gospodarz='RSCA Futures', gosc='KAS Eupen', rynek=r, kurs=k)
                        for r, k in (('O2.5', '1.45'), ('X2', '1.25'))])
    sts = pd.DataFrame([dict(sport='PIŁKA NOŻNA', data_meczu='2026-10-09', godzina_meczu='20:00', gospodarz='RSC Anderlecht U23',
                             gosc='KAS Eupen', rynek=r, kurs=k) for r, k in (('O2.5', '1.45'), ('X2', '1.25'))])
    tab, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['LVBET']['jednoznaczne'] == 1 and list(tab.LVBET) == [1.45, 1.25]
    # pierwsza druzyna Anderlechtu to nie U23 — znaczniki dalej sie roznia
    sts.loc[:, 'gospodarz'] = 'RSC Anderlecht'
    assert kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))[1]['LVBET']['jednoznaczne'] == 0


def test_kupon_wypisuje_liczby_dopasowan(tmp_path, capsys):
    # nr 4 (P157.4): „mecze STS dopasowane N” takze w trybie kupon (dotad tylko porownaj)
    p_sts, p_ako = tmp_path / 'sts.csv', tmp_path / 'ako.csv'
    pd.DataFrame([dict(sport='PIŁKA NOŻNA', data_meczu='2026-10-09', godzina_meczu='20:00', gospodarz='RSC Anderlecht U23',
                       gosc='KAS Eupen', rynek='O2.5', kurs='1.45')]).to_csv(p_sts, index=False)
    pd.DataFrame([dict(bukmacher='LVBET', sport='PIŁKA NOŻNA', data_meczu='2026-10-09', godzina_meczu='20:00',
                       gospodarz='RSCA Futures', gosc='KAS Eupen', rynek='O2.5', kurs='1.45')]).to_csv(
        tmp_path / 'kursy_bukmacherow_2026-10-09_17-49.csv.gz', index=False)
    pd.DataFrame([dict(data='2026-10-09', godzina_uruchomienia='18:00', tag='AKON-1800', nr_kuponu='1', noga_nr='1',
                       zdarzenie='RSC Anderlecht U23 - KAS Eupen', rynek='O2.5', kurs='1.45')]).to_csv(p_ako, index=False)
    kursy3.main(['kupon', str(p_sts), str(tmp_path / 'kursy_bukmacherow_*.csv.gz'), '--ako', str(p_ako), '--data', '2026-10-09'])
    out = capsys.readouterr().out.splitlines()
    assert out[0] == 'kursy SUPERBET/LVBET: pobrane 2026-10-09 17:49'
    assert out[1] == 'LVBET: mecze STS dopasowane 1, brak 0, niejednoznaczne 0'
    assert out[2].startswith('AKON-1800#1 GRAJ U:')
