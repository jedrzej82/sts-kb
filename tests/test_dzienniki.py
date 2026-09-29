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


def test_kotwica_gdy_zrodla_pisza_mecz_inaczej():
    # 365: „Maccabi Bnei Reineh – Hapoel Raanana”, Flashscore: „Maccabi Bnei Raina – H. Raanana” (28.09.2026)
    pilka = pd.DataFrame({'d': [DZIS, DZIS], 'h': ['Maccabi Bnei Reineh', 'Maccabi Bnei Raina'], 'a': ['Hapoel Raanana', 'H. Raanana'],
                          'g': [1, 1], 'ga': [2, 2], 'hg': [None] * 2, 'ha': [None] * 2})
    W = dict(pilka=pilka, inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']), tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))
    st, wyn, uw = dzienniki.rozlicz_noge(dict(sport='pilka', zdarzenie='Maccabi Bnei Reina - Hapoel Raanana', rynek='powyzej 1.5', data=D, uwaga=''), W)
    assert (st, wyn) == ('TRAFIONY', '1:2') and 'dopasowano po jednej druzynie' in uw


def test_kotwica_sprzeczne_wyniki_nie_rozstrzyga():
    # dwa wiersze z ta sama kotwica i pasujacym rywalem, ale roznym wynikiem -> nie zgadujemy
    okno = pd.DataFrame({'d': [DZIS, DZIS + pd.Timedelta(days=1)], 'h': ['Maccabi Bnei Reineh', 'Hapoel Raanana'],
                         'a': ['Hapoel Raanana', 'Maccabi Bnei Reineh'], 'g': [1, 0], 'ga': [2, 0]})
    args = (okno, None, 'Hapoel Raanana', 'Maccabi Bnei Reina', 'Hapoel Raanana', dzienniki._rozwiaz_pilka, 'h', 'a')
    assert dzienniki._po_kotwicy(*args) is None
    okno.loc[1, ['g', 'ga']] = [2, 1]                     # ten sam wynik (odwrocone strony) -> rozstrzyga
    s_, odwr = dzienniki._po_kotwicy(*args)
    assert (s_.g, s_.ga, odwr) == (1, 2, False)


def test_rozlicz_ako_z_katalogu(tmp_path, monkeypatch, W):
    k = tmp_path / 'delty'; k.mkdir()
    _ako('AKOP-1200-1', '1', [('pilka', 'Etiopia - Senegal', '12', '1.18', '')], '1.18', 'PAPIEROWY', '').to_csv(k / 'ako_log 12:00', index=False)
    monkeypatch.setattr(dzienniki, 'HERE', str(tmp_path))
    monkeypatch.setattr(dzienniki, 'wyniki_pilka', lambda *a: W['pilka'])
    monkeypatch.setattr(dzienniki, 'wyniki_inne', lambda *a: W['inne'])
    monkeypatch.setattr(dzienniki, 'wyniki_tenis', lambda *a: W['tenis'])
    dzienniki.main(['rozlicz', D, '--ako', str(k), '--wyjscie', str(tmp_path / 'r.csv')])
    r = pd.read_csv(tmp_path / 'r.csv', dtype=str)
    assert r.loc[r.tag == 'RAZEM_AKOP-1200-1_1', 'TRAFIONY_PRZEGRANY'].iloc[0] == 'TRAFIONY 1/1'


def test_tenis_para_rozstrzyga_kandydatow():
    # 29.09.2026: „Hurkacz” = Hubert albo Nika — rozstrzyga para, ktora grala; obca osoba z inicjalami odpada
    t = pd.DataFrame({'d': [DZIS, DZIS, DZIS], 'w': ['Hubert Hurkacz', 'Nika Hurkacz', 'Cinalli L. M.'],
                      'l': ['Denis Shapovalov', 'Anna Nowak', 'Jan Kowalski'], 'score': ['6-3 6-3', '6-1 6-1', '6-0 6-0']})
    W = dict(tenis=t, pilka=None, inne=None)
    st, wyn, uw = dzienniki.rozlicz_noge(dict(sport='tenis', zdarzenie='Hurkacz - Shapovalov', rynek='Zwyciezca Hurkacz', data=D), W)
    assert st == 'TRAFIONY' and wyn.startswith('Hubert Hurkacz') and 'jedyna pasujaca para' in uw
    assert dzienniki._kandydaci_tenis('Linette M.', set(t.w) | set(t.l)) == set()


# 29.09.2026 — przeglad dzienniki.py (bledy potwierdzone przykladem)
def _W_inne(rows):
    return dict(pilka=pd.DataFrame(columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha']), tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']),
                inne=pd.DataFrame(rows, columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']))


def test_remis_to_nie_wygrana_goscia():
    T = pd.Timestamp
    w = _W_inne([(T('2026-09-28'), 'futsal', 'Alpha Team', 'Beta Club', 3, 3, 0)])
    for ry in ('1', '2'):
        assert dzienniki.rozlicz_noge(dict(sport='futsal', zdarzenie='Alpha Team - Beta Club', rynek=ry, data='2026-09-28'), w)[0] == 'PRZEGRANY'
    w = _W_inne([(T('2026-09-28'), 'hokej na trawie', 'Alpha Team', 'Beta Club', 2, 2, 0)])   # sport bez DRAW_PRIOR
    assert dzienniki.rozlicz_noge(dict(sport='hokej na trawie', zdarzenie='Alpha Team - Beta Club', rynek='2', data='2026-09-28'), w)[0] == 'BRAK WYNIKU'


def test_ta_sama_para_dwa_dni_z_rzedu():
    T = pd.Timestamp
    w = _W_inne([(T('2026-09-28'), 'baseball', 'New York Yankees', 'Boston Red Sox', 5, 2, 0),
                 (T('2026-09-29'), 'baseball', 'New York Yankees', 'Boston Red Sox', 1, 4, 0)])
    z = dict(sport='baseball', zdarzenie='New York Yankees - Boston Red Sox', rynek='1')
    assert dzienniki.rozlicz_noge(dict(z, data='2026-09-28'), w)[:2] == ('TRAFIONY', '5:2')
    assert dzienniki.rozlicz_noge(dict(z, data='2026-09-29'), w)[:2] == ('PRZEGRANY', '1:4')
    w2 = _W_inne([(T('2026-09-27'), 'baseball', 'New York Yankees', 'Boston Red Sox', 5, 2, 0),
                  (T('2026-09-29'), 'baseball', 'New York Yankees', 'Boston Red Sox', 1, 4, 0)])
    assert dzienniki.rozlicz_noge(dict(z, data='2026-09-28'), w2)[0] == 'BRAK WYNIKU'    # 27 i 29 w oknie — nie zgadujemy


def _ako_pilka(kurs_razem, uw, status='ZAGRANY'):
    base = dict(data='2026-09-28', godzina_uruchomienia='12:00', tag='K1', nr_kuponu='1', sport='pilka', P='80', status=status, kurs_zamkniecia='')
    return pd.DataFrame([dict(base, noga_nr='1', zdarzenie='Legia Warszawa - Lech Poznan', rynek='1', kurs='1.60', uwaga=''),
                         dict(base, noga_nr='RAZEM', zdarzenie='', rynek='', kurs=kurs_razem, uwaga=uw)])


def test_kurs_i_stawka_kuponu():
    T = pd.Timestamp
    W = dict(pilka=pd.DataFrame([(T('2026-09-28'), 'Legia Warszawa', 'Lech Poznan', 2, 0, None, None)], columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha']),
             tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']), inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']))
    for k, u in (('1.60', 'stawka 5 zl'), ('', 'stawka 5 zl'), ('1.60', 'stawka: 5 zł')):
        _, b = dzienniki.rozlicz_dzien('2026-09-28', _ako_pilka(k, u), W)
        assert (b['postawione'], b['wyplacone'], b['pien'], b['pap_liczba']) == (5.0, 7.04, 1, 0)
    r, b = dzienniki.rozlicz_dzien('2026-09-28', _ako_pilka('1.60', 'bez kwoty'), W)
    assert b['postawione'] == 0 and b['pap_liczba'] == 0 and 'bez stawki' in r.iloc[1].TRAFIONY_PRZEGRANY
