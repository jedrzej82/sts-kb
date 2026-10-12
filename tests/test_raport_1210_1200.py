"""Raport 12.10 12:00.
  3. Liga Mistrzow AFC (--kontynentalny): 5 z 6 meczow „NIEPEWNE DOPASOWANIE … nie graly w jednej lidze”. Krotsza nazwa
     NIE moze byc przyjeta bez aliasu — bez niego „Al-Qadisiyah FC” trafialo w libijskie Al Qadisiyah, a „Al-Ain FC”
     w saudyjskie Al-Ain (sprawdzone na bazie 07.10). Aliasy potwierdzone terminarzem 365/FS z 12.10.
  4. „Fortaleza CE” (BRA2; Fortaleza FC to klub kolumbijski), „Future FC” = Modern Sport FC (Egipt, terminarz: – ENPPI).
  5. kosz Serbia: „Kolubara Lazarevac” / „Dynamic Belgrad” — w statystykach „Kolubara La 2003” / „KK Dynamic BG”.
  7. rozliczenie 11.10: „Aris Saloniki – Volos NPS”, „RFS Riga – FK Jelgava” konczyly „nie dopasowano” (wyniki: Aris
     Salonica/Aris – Volos NFC/Volos 3:2, Rigas FS – FK Jelgava 4:2)."""
import pandas as pd

import dzienniki
import sporty
import typuj

T = pd.Timestamp


def test_afc_aliasy_wskazuja_wlasciwy_kraj():
    pula = {'Al Wasl', 'Al Ahli Jeddah', 'Pakhtakor', 'Qadisiya', 'Qadisiya Kuwait', 'Al Qadisiyah', 'Tractor FC', 'Al Shamal',
            'Al Shamal Future', 'Al Gharafa', 'Etihad Al Gharafa', 'Quwa Al Jawiya', 'Al Ain', 'Al-Ain', 'Esteghlal FC Tehran'}
    ocz = {'Al-Wasl FC': 'Al Wasl', 'Al-Qadisiyah FC': 'Qadisiya', 'Pakhtakor Tashkent': 'Pakhtakor',
           'Tractor Sazi Tebriz': 'Tractor FC', 'Al-Shamal SC': 'Al Shamal', 'Al-Gharafa SC': 'Al Gharafa',
           'Al-Quwa Al-Jawiya': 'Quwa Al Jawiya', 'Al-Ain FC': 'Al Ain'}
    for n, c in ocz.items():
        assert typuj.resolve(n, pula) == c, n


def test_nazwy_pkt_4_i_rozliczenie():
    pula = {'Fortaleza', 'Fortaleza FC', 'CRB', 'Modern Sport FC', 'ENPPI', 'Aris', 'Aris Limasol', 'Volos NFC', 'Rigas FS',
            'Riga', 'FK Jelgava'}
    for n, c in {'Fortaleza CE': 'Fortaleza', 'Future FC': 'Modern Sport FC', 'Aris Saloniki': 'Aris',
                 'Volos NPS': 'Volos NFC', 'RFS Riga': 'Rigas FS'}.items():
        assert typuj.resolve(n, pula) == c, n


def test_kosz_serbia():
    pula = {'Kolubara La 2003', 'KK Dynamic BG', 'OKK Belgrad', 'KK Radnicki'}
    assert sporty.resolve('Kolubara Lazarevac', pula, 'koszykowka') == 'Kolubara La 2003'
    assert sporty.resolve('Dynamic Belgrad', pula, 'koszykowka') == 'KK Dynamic BG'


def test_rozliczenie_1110_aris_i_rfs():
    # zapis jak w wynikach 12.10: 365 i Flashscore (FS ma tez cypryjskiego „Aris” tego samego dnia)
    p = pd.DataFrame([(T('2026-10-11'), 'Aris Salonica', 'Volos NFC', 3, 2, None, None, '365'),
                      (T('2026-10-11'), 'Aris', 'Volos', 3, 2, None, None, 'fs'),
                      (T('2026-10-11'), 'Ol. Nicosia', 'Aris', 1, 2, None, None, 'fs'),
                      (T('2026-10-11'), 'Rigas FS', 'FK Jelgava', 4, 2, None, None, '365')],
                     columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha', 'zr'])
    W = dict(pilka=p, inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']),
             tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))
    r = lambda z, ry: dzienniki.rozlicz_noge(dict(zdarzenie=z, rynek=ry, sport='piłka nożna', data='2026-10-11', uwaga=''), W)
    assert r('Aris Saloniki - Volos NPS', 'O0.5')[:2] == ('TRAFIONY', '3:2')
    assert r('RFS Riga - FK Jelgava', '12')[:2] == ('TRAFIONY', '4:2')
    assert r('Aris Saloniki - Volos NPS', '2')[:2] == ('PRZEGRANY', '3:2')
