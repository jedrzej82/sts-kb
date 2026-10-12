"""Decyzja uzytkownika 12.10 („B”, P182.7): KUPON DNIA (tag KD) tylko papierowy od 11.10. Przebieg wpisywal w RAZEM
„stawka 5 zl”, a dzienniki.py liczyly KD do Bilansu jako 5 zl postawione."""
import pandas as pd

import dzienniki
import kupon
from tests.test_dzienniki import AKO_KOL


def _ako(data, tag, status='DO GRY'):
    w = [dict(data=data, godzina_uruchomienia='12:00', tag=tag, nr_kuponu='1', noga_nr='1', sport='pilka', zdarzenie='Legia - Lech',
              rynek='12', P='90.0', kurs='1.20', uwaga=f'mecz {data} 18:00'),
         dict(data=data, godzina_uruchomienia='12:00', tag=tag, nr_kuponu='1', noga_nr='RAZEM', P='90.0', status=status,
              kurs='1.20', uwaga='stawka 5 zl')]
    return pd.DataFrame(w).reindex(columns=AKO_KOL).fillna('')


def _W(data):
    d = pd.Timestamp(data)
    return dict(pilka=pd.DataFrame({'d': [d], 'h': ['Legia'], 'a': ['Lech'], 'g': [2], 'ga': [0], 'hg': [None], 'ha': [None]}),
                inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']), tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))


def test_kd_od_11_10_papierowy():
    roz, bil = dzienniki.rozlicz_dzien('2026-10-12', _ako('2026-10-12', 'KD'), _W('2026-10-12'))
    assert bil['postawione'] == 0 and bil['pien'] == 0 and bil['pap_liczba'] == 1 and bil['pap_traf'] == 1
    assert 'tylko papierowy' in roz.loc[roz.tag == 'RAZEM_KD_1', 'uwaga'].iloc[0]


def test_kd_przed_11_10_i_inne_tagi_bez_zmian():
    _, bil = dzienniki.rozlicz_dzien('2026-10-09', _ako('2026-10-09', 'KD'), _W('2026-10-09'))
    assert bil['postawione'] == 5 and bil['pien'] == 1            # historia sprzed decyzji nie zmienia sie
    _, bil = dzienniki.rozlicz_dzien('2026-10-12', _ako('2026-10-12', 'K5'), _W('2026-10-12'))
    assert bil['postawione'] == 5 and bil['pien'] == 1


def test_linia_kuponu_dnia_mowi_papierowy():
    w = pd.DataFrame([dict(mecz='A - B', rynek='12', p=0.95, kurs=1.10, szacunek=0, polski=0, marza=1.05, sport='pilka'),
                      dict(mecz='C - D', rynek='1X', p=0.95, kurs=1.12, szacunek=0, polski=0, marza=1.05, sport='pilka')])
    t = '\n'.join(kupon.linie_dnia(w))
    assert 'TYLKO PAPIEROWY' in t and 'decyzja uzytkownika 08.10' not in t


def test_tag_kd_z_godzina_i_status_nie_do_gry():
    # prawdziwy zapis ako_log 11.10: tag „KD-1200”, status „NIE DO GRY”, uwaga „... stawka 5 zl tylko decyzja uzytkownika”
    roz, bil = dzienniki.rozlicz_dzien('2026-10-12', _ako('2026-10-12', 'KD-1200'), _W('2026-10-12'))
    assert bil['postawione'] == 0 and bil['pap_liczba'] == 1
    _, bil = dzienniki.rozlicz_dzien('2026-10-10', _ako('2026-10-10', 'K5', 'NIE DO GRY'), _W('2026-10-10'))
    assert bil['postawione'] == 0 and bil['pap_liczba'] == 1
    assert dzienniki.kupon_pieniezny(pd.Series(dict(status='NIE DO GRY', uwaga='stawka 5 zl'))) == (5.0, False)
    assert dzienniki.kupon_pieniezny(pd.Series(dict(status='DO GRY', uwaga='stawka 5 zl'))) == (5.0, True)
