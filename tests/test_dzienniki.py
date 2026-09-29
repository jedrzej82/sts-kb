"""dzienniki.py: scalanie delt i rozliczanie kuponow z ako_log (dane sztuczne)."""
import os

import pandas as pd
import pytest

import dzienniki

DZIS = pd.Timestamp.today().normalize()
D = DZIS.strftime('%Y-%m-%d')
AKO_KOL = ['data', 'godzina_uruchomienia', 'tag', 'nr_kuponu', 'noga_nr', 'sport', 'liga', 'zdarzenie', 'rynek', 'typ_rynku',
           'P', 'zrodlo_P', 'status', 'kurs', 'kurs_poranny', 'kurs_zamkniecia', 'wynik_nogi', 'trafiona', 'kategoria_diagnozy', 'uwaga']


def _ako(tag, nr, nogi, kurs, status, uwaga_razem):
    w = [dict(data=D, godzina_uruchomienia='12:00', tag=tag, nr_kuponu=nr, noga_nr=str(i + 1), sport=s, zdarzenie=z, rynek=r,
              P='80.0', kurs=k, kurs_zamkniecia=kz, uwaga=f'mecz {D} 18:00') for i, (s, z, r, k, kz) in enumerate(nogi)]
    w.append(dict(data=D, godzina_uruchomienia='12:00', tag=tag, nr_kuponu=nr, noga_nr='RAZEM', P='50.0', status=status,
                  kurs=kurs, uwaga=uwaga_razem))
    return pd.DataFrame(w).reindex(columns=AKO_KOL).fillna('')


@pytest.fixture
def W():
    pilka = pd.DataFrame({'d': [DZIS, DZIS, DZIS], 'h': ['Ethiopia', 'Bulgaria', 'Legia Warsaw'],
                          'a': ['Senegal', 'Estonia', 'Lech Poznan'], 'g': [0, 1, 1], 'ga': [2, 1, 3], 'hg': [None] * 3, 'ha': [None] * 3})
    inne = pd.DataFrame({'d': [DZIS, DZIS], 'sport': ['koszykówka', 'hokej'], 'h': ['Real Madrid', 'Tappara'],
                         'a': ['Barcelona', 'Ilves'], 'pg': [80, 3], 'pa': [70, 2], 'ot': [0, 1]})
    tenis = pd.DataFrame({'d': [DZIS], 'w': ['Hubert Hurkacz'], 'l': ['Alejandro Davidovich Fokina'], 'score': ['6-4 6-4']})
    return dict(pilka=pilka, inne=inne, tenis=tenis)


def test_rynki_pilka():
    assert dzienniki.rynek_pilka('powyzej 1.5') == 'O1.5' and dzienniki.rynek_pilka('ponizej 3,5') == 'U3.5'
    assert dzienniki.rynek_pilka('1X') == '1X' and dzienniki.rynek_pilka('obie strzelą tak') == 'BTTS_tak'


def test_noga_reprezentacja_i_klub(W):
    r = dict(sport='pilka', zdarzenie='Etiopia - Senegal', rynek='12', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', '0:2')
    r = dict(sport='pilka', zdarzenie='Bułgaria - Estonia', rynek='powyzej 2.5', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[0] == 'PRZEGRANY'
    r = dict(sport='pilka', zdarzenie='Estonia - Bułgaria', rynek='X', data=D, uwaga='')   # odwrocone strony
    assert dzienniki.rozlicz_noge(r, W)[0] == 'TRAFIONY'
    r = dict(sport='pilka', zdarzenie='Kongo - Kamerun', rynek='12', data=D, uwaga='')      # brak meczu -> nie zgadujemy
    assert dzienniki.rozlicz_noge(r, W)[0] == 'BRAK WYNIKU'


def test_noga_inne_sporty_i_tenis(W):
    assert dzienniki.rozlicz_noge(dict(sport='koszykowka', zdarzenie='Real Madryt - Barcelona', rynek='1', data=D), W)[0] == 'TRAFIONY'
    # hokej: '1' w czasie regulaminowym, mecz rozstrzygniety w dogrywce -> PRZEGRANY; '1 z dogrywka' -> TRAFIONY
    assert dzienniki.rozlicz_noge(dict(sport='hokej', zdarzenie='Tappara - Ilves', rynek='1', data=D), W)[0] == 'PRZEGRANY'
    assert dzienniki.rozlicz_noge(dict(sport='hokej', zdarzenie='Tappara - Ilves', rynek='1 z dogrywka', data=D), W)[0] == 'TRAFIONY'
    r = dict(sport='tenis', zdarzenie='Hurkacz - Davidovich Fokina', rynek='Zwyciezca Hurkacz', data=D)
    assert dzienniki.rozlicz_noge(r, W)[0] == 'TRAFIONY'


def test_rozlicz_dzien_kupony_i_bilans(W):
    ako = pd.concat([
        _ako('K5', '1', [('pilka', 'Etiopia - Senegal', '12', '1.18', '1.10'), ('pilka', 'Bułgaria - Estonia', 'X', '3.40', '')],
             '4.012', 'ZAGRANY', 'stawka 2 zl'),
        _ako('AKOP-1200-1', '1', [('pilka', 'Etiopia - Senegal', '12', '1.18', ''), ('pilka', 'Bułgaria - Estonia', '1', '1.50', '')],
             '1.770', 'PAPIEROWY', 'EV -5%'),
        _ako('AKOP-1200-2', '2', [('pilka', 'Kongo - Kamerun', '12', '1.27', '')], '1.270', 'PAPIEROWY', ''),
    ], ignore_index=True)
    roz, bil = dzienniki.rozlicz_dzien(D, ako, W)
    razem = dict(zip(roz.tag, roz.TRAFIONY_PRZEGRANY))
    assert razem['RAZEM_K5_1'] == 'TRAFIONY 2/2' and razem['RAZEM_AKOP-1200-1_1'] == 'PRZEGRANY 1/2'
    assert razem['RAZEM_AKOP-1200-2_2'].startswith('NIEROZLICZONY')
    assert bil['postawione'] == 2 and bil['wyplacone'] == pytest.approx(2 * 4.012 * 0.88, abs=0.01)
    assert bil['pap_liczba'] == 2 and bil['pap_traf'] == 0 and bil['pap_nierozl'] == 1
    assert roz.loc[roz.zdarzenie == 'Etiopia - Senegal', 'CLV'].iloc[0] == '+7.3%'   # 1,18 / 1,10 - 1


def test_scal_bez_duplikatow_wynik_wygrywa(tmp_path):
    k = tmp_path / 'delty'; k.mkdir()
    pd.DataFrame([dict(data=D, gosp='A', **{'gość': 'B'}, rynek='1X', p='0.8', trafiony='')]).to_csv(k / 'typy_log 12:00', index=False)
    pd.DataFrame([dict(data=D, gosp='A', **{'gość': 'B'}, rynek='1X', p='0.8', trafiony='1'),
                  dict(data=D, gosp='C', **{'gość': 'D'}, rynek='O1.5', p='0.7', trafiony='')]).to_csv(k / 'typy_log DELTA 15:00.csv', index=False)
    wyn = dzienniki.scal(str(k), cel=str(tmp_path))
    d = pd.read_csv(tmp_path / 'typy_log.csv', dtype=str, keep_default_na=False)
    assert wyn['typy_log'] == (2, 3, 2) and d.loc[d.gosp == 'A', 'trafiony'].iloc[0] == '1'
    assert not os.path.exists(tmp_path / 'ako_log.csv')
