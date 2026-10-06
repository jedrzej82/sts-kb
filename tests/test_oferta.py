"""oferta.py (01.10.2026): kursy z PDF oferty STS w kodzie + kurs_zamkniecia dla ako_log.
Uklad stron odtworzony z prawdziwych PDF z 30.09 (oferta-dzisiaj-auto 17-30 i 20-30, oferta-jutro-auto 20-30):
syntetyczne znaki w tych samych polozeniach — PDF oferty nie trafia do repo."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dzienniki  # noqa: E402
import oferta  # noqa: E402


def slowo(x, y, tekst, rozm=7.2):
    """Znaki jednego slowa: (x0, x1, y_od_gory, rozmiar, znak); szerokosc znaku jak w PDF (ok. 0,45 rozmiaru)."""
    w, z = rozm * 0.45, []
    for i, c in enumerate(tekst):
        z.append((x + i * w, x + (i + 1) * w, y, rozm, c))
    return z


def wiersz(x_lewy, y, nr, nazwa, kursy, godz, rozm_nazwy=7.2, rozm_kursow=7.2):
    """Wiersz zdarzenia: numer (8.2, 1 pt wyzej), nazwa, kursy w podanych x (wzgledem krawedzi szpalty), godzina."""
    z = slowo(x_lewy, y - 1, nr, 8.2) + slowo(x_lewy + 28, y, nazwa, rozm_nazwy)
    for x, k in kursy:
        z += slowo(x_lewy + x, y, k, rozm_kursow)
    return z + slowo(x_lewy + 251, y, godz)


def strona():
    L, P = 26.0, 300.0
    z = slowo(L, 17, 'OFERTA KURSOWA', 12.0)
    z += slowo(95, 109, 'ŚRODA 2026-09-30', 17.0)
    z += slowo(118, 137, 'PIŁKA NOŻNA', 15.0)
    z += slowo(38, 164, 'MŁODZIEŻOWE - MISTRZOSTWA EUROPY U21 -', 13.0) + slowo(121, 181, 'KWALIFIKACJE', 13.0)
    # „Mecz” z etykietami 1 X 2 1X X2 12 w tej samej linii
    z += slowo(L + 27, 199, 'Mecz', 9.5)
    for x, e in ((148, '1'), (166, 'X'), (184, '2'), (200, '1X'), (219, 'X2'), (237, '12')):
        z += slowo(L + x, 199, e, 8.5)
    z += wiersz(L, 213, '3919', 'Szkocja U21 - Azerbejdżan U21',
                [(143, '1.17'), (162, '7.10'), (178, '13.00'), (198, '1.04'), (217, '4.40'), (235, '1.08')], '20:30')
    # sklejone slowa „22.0040.0021:00” i tylko 1 X 2
    z += slowo(L + 28, 225, 'Mecz', 9.5)
    for x, e in ((201, '1'), (220, 'X'), (239, '2')):
        z += slowo(L + x, 225, e, 8.5)
    z += slowo(L, 238, '3922', 8.2) + slowo(L + 28, 239, 'Portugalia U21 - Gibraltar U21') + \
        slowo(L + 197, 239, '1.01') + slowo(L + 214, 239, '22.0040.0021:00')
    # Liczba goli - + : linia w nawiasie; waska twarda spacja w nazwie
    z += slowo(L + 28, 251, 'Liczba goli', 9.5) + slowo(L + 220, 251, '-', 8.5) + slowo(L + 239, 251, '+', 8.5)
    z += wiersz(L, 265, '17463', 'Szkocja U21 - Azerbejdżan U21 (1.5)', [(215, '6.10'), (234, '1.09')], '20:30')
    # dlugi tytul pomniejszony (8.4) i etykiety 5.2 zaczynajace sie < 140 pt od krawedzi
    z += slowo(P + 30, 300, '1. połowa / wynik końcowy', 8.4)
    for i, e in enumerate(('1/1', '1/X', '1/2', 'X/1', 'X/X', 'X/2', '2/1', '2/X', '2/2')):
        z += slowo(P + 126 + 14.3 * i, 302, e, 5.2)
    # kursy z 1 miejscem po kropce i bez kropki
    z += wiersz(P, 316, '59662', 'Tatran Presov - Bergischer HC',
                [(123 + 14.3 * i, k) for i, k in enumerate(('13.50', '32.0', '6.50', '50.0', '50', '11.0', '27.0', '28.0', '1.25'))],
                '20:45', rozm_nazwy=5.2, rozm_kursow=5.2)   # jak w PDF: 9 kursow pomniejszonych do 5.2
    # podnaglowek rynku zawodnikow
    z += slowo(P + 29, 340, 'Zawodnik - liczba goli', 9.5) + slowo(P + 221, 341, '-', 8.5) + slowo(P + 240, 341, '+', 8.5)
    z += slowo(P + 29, 354, 'SC Magdeburg - THW Kiel') + slowo(P + 251, 354, '19:00')
    z += wiersz(P, 366, '35128', 'Kristjansson Gisli (4.5)', [(216, '2.00'), (235, '1.70')], '19:00')
    z += slowo(31, 817, '2026-09-30 17:25', 12.0) + slowo(508, 817, 'Strona ', 12.0) + slowo(542, 815, '1', 14.4)
    return z


def test_czytaj_uklad(monkeypatch):
    monkeypatch.setattr(oferta, '_znaki', lambda pdf: iter([strona()]))
    d, ostrz = oferta.czytaj('x.pdf')
    assert ostrz == []
    k = {(r.zdarzenie, r.linia, r.rynek): r.kurs for r in d.fillna('').itertuples()}
    assert k[('Szkocja U21 - Azerbejdżan U21', '', '1')] == '1.17'
    assert k[('Szkocja U21 - Azerbejdżan U21', '', '12')] == '1.08'
    assert k[('Portugalia U21 - Gibraltar U21', '', 'X')] == '22.00'
    assert k[('Portugalia U21 - Gibraltar U21', '', '2')] == '40.00'
    assert k[('Szkocja U21 - Azerbejdżan U21', '1.5', 'O1.5')] == '1.09'
    assert k[('Szkocja U21 - Azerbejdżan U21', '1.5', 'U1.5')] == '6.10'
    assert k[('Tatran Presov - Bergischer HC', '', '1. połowa / wynik końcowy|1/1')] == '13.50'
    assert k[('Tatran Presov - Bergischer HC', '', '1. połowa / wynik końcowy|1/X')] == '32.00'
    assert k[('Tatran Presov - Bergischer HC', '', '1. połowa / wynik końcowy|X/X')] == '50.00'
    assert k[('Tatran Presov - Bergischer HC', '', '1. połowa / wynik końcowy|2/2')] == '1.25'
    assert k[('Kristjansson Gisli', '4.5', 'Zawodnik - liczba goli (SC Magdeburg - THW Kiel)|+')] == '1.70'
    w = d[d.zdarzenie == 'Szkocja U21 - Azerbejdżan U21'].iloc[0]
    assert (w.data_meczu, w.godzina_meczu, w.sport, w.gospodarz, w.gosc) == \
        ('2026-09-30', '20:30', 'PIŁKA NOŻNA', 'Szkocja U21', 'Azerbejdżan U21')
    assert w.liga == 'MŁODZIEŻOWE - MISTRZOSTWA EUROPY U21 - KWALIFIKACJE'
    assert set(d.godzina_pobrania) == {'2026-09-30 17:25'}       # ze stopki PDF
    assert w.marza_1x2 == round(1 / 1.17 + 1 / 7.10 + 1 / 13.00, 4)
    assert len(d) == 6 + 3 + 2 + 9 + 2


def test_kurs_nie_trafia_w_etykiete_to_ostrzezenie(monkeypatch):
    z = slowo(53, 199, 'Mecz', 9.5) + slowo(174, 199, '1', 8.5) + slowo(192, 199, 'X', 8.5) + slowo(210, 199, '2', 8.5)
    z += wiersz(26, 213, '3919', 'A - B', [(143, '1.17'), (60 + 143, '7.10')], '20:30')   # drugi kurs 30 pt obok
    monkeypatch.setattr(oferta, '_znaki', lambda pdf: iter([z]))
    d, ostrz = oferta.czytaj('x.pdf')
    assert len(d) == 1 and any('nie trafia' in o for o in ostrz)


def test_pusty_pdf_to_ostrzezenie(monkeypatch):
    monkeypatch.setattr(oferta, '_znaki', lambda pdf: iter([[]]))
    d, ostrz = oferta.czytaj('x.pdf')
    assert len(d) == 0 and ostrz


def _kursy(*w):
    return pd.DataFrame([dict(data_meczu=d, godzina_meczu=g, sport=s, gospodarz=h, gosc=a, rynek=r, kurs=k,
                              godzina_pobrania=p) for d, g, s, h, a, r, k, p in w])


AKO_KOL = ['data', 'godzina_uruchomienia', 'tag', 'nr_kuponu', 'noga_nr', 'sport', 'zdarzenie', 'rynek', 'kurs',
           'trafiona', 'uwaga', 'kurs_zamkniecia']


def _ako(*w):
    return pd.DataFrame([dict(zip(AKO_KOL, x)) for x in w], columns=AKO_KOL)


def test_zamkniecia_ostatni_pdf_przed_meczem():
    k = _kursy(('2026-09-30', '18:00', 'PIŁKA NOŻNA', 'Litwa', 'Andora', '12', '1.27', '2026-09-30 17:30'),
               ('2026-09-30', '18:00', 'PIŁKA NOŻNA', 'Litwa', 'Andora', '12', '1.30', '2026-09-30 20:30'),   # po starcie
               ('2026-09-30', '18:00', 'PIŁKA NOŻNA', 'Litwa', 'Andora', '12', '1.25', '2026-09-30 14:30'),
               ('2026-09-30', '19:30', 'PIŁKA NOŻNA', 'Zjednoczone Emiraty Arabskie', 'Katar', 'O1.5', '1.28', '2026-09-30 17:30'),
               ('2026-09-30', '19:30', 'HOKEJ NA LODZIE', 'Litwa', 'Andora', '12', '9.99', '2026-09-30 17:30'))
    a = _ako(('2026-09-30', '15:00', 'K5c', '1', '1', 'pilka', 'Litwa - Andora', '12', '1.26', '', 'mecz 2026-09-30 18:00', ''),
             ('2026-09-30', '15:00', 'K5c', '1', '2', 'pilka', 'Zjednoczone Emiraty Arabskie - Katar', 'powyzej 1.5 gola',
              '1.30', '', 'mecz 2026-09-30 19:30', ''),
             ('2026-09-30', '15:00', 'K5c', '1', '3', 'pilka', 'Litwa - Andora', 'X2', '1.50', '', '', ''),   # rynku brak w PDF
             ('2026-09-30', '15:00', 'K5c', '1', 'RAZEM', '', '', '', '2.10', '', 'stawka 0 zl', ''))
    z, info = oferta.zamkniecia(k, a)
    assert list(z.noga_nr) == ['1', '2'] and list(z.kurs_zamkniecia) == ['1.27', '1.28']
    assert list(z.kurs) == ['1.26', '1.30']       # reszta wiersza bez zmian
    assert len(info) == 2


def test_zamkniecia_bez_zgadywania_nazw_i_dnia():
    k = _kursy(('2026-09-30', '18:00', 'PIŁKA NOŻNA', 'Litwa', 'Andora', '12', '1.27', '2026-09-30 17:30'),
               ('2026-10-05', '18:00', 'PIŁKA NOŻNA', 'Kuba', 'Bonaire', '1', '1.50', '2026-10-05 08:30'))
    a = _ako(('2026-09-30', '15:00', 'K5c', '1', '1', 'pilka', 'Litwa U21 - Andora', '12', '1.26', '', '', ''),  # inna nazwa
             ('2026-09-30', '15:00', 'K5c', '1', '2', 'pilka', 'Kuba - Bonaire', '1', '1.40', '', '', ''),       # inny dzien
             ('2026-09-30', '15:00', 'K5c', '1', '3', 'tenis', 'Litwa - Andora', '12', '1.26', '', '', ''))      # nie pilka
    z, info = oferta.zamkniecia(k, a)
    assert len(z) == 0 and info == []


def test_scal_najpozniejszy_kurs_zamkniecia(tmp_path):
    kol = 'data,godzina_uruchomienia,tag,nr_kuponu,noga_nr,zdarzenie,kurs,trafiona,kurs_zamkniecia\n'
    pliki = [('ako_log 2026-09-30 15_00.csv', '2026-09-30,15:00,K5c,1,1,Litwa - Andora,1.26,,\n'),
             ('ako_log zamkniecia 2026-09-30 14-30.csv', '2026-09-30,15:00,K5c,1,1,Litwa - Andora,1.26,,1.25\n'),
             ('ako_log zamkniecia 2026-09-30 17-30.csv', '2026-09-30,15:00,K5c,1,1,Litwa - Andora,1.26,,1.27\n'),
             # rozliczenie z wynikiem — bez kursu zamkniecia; wynik wygrywa, kurs zamkniecia zostaje z delty 17-30
             ('ako_log 2026-10-01 12_00.csv', '2026-09-30,15:00,K5c,1,1,Litwa - Andora,1.26,TAK,\n')]
    for i, (n, w) in enumerate(pliki):
        p = tmp_path / n
        p.write_text(kol + w, encoding='utf-8')
        os.utime(p, (1_000_000 + i, 1_000_000 + i))
    dzienniki.scal(str(tmp_path), cel=str(tmp_path))
    d = dzienniki._czytaj(tmp_path / 'ako_log.csv')
    assert len(d) == 1
    assert d.iloc[0].trafiona == 'TAK' and d.iloc[0].kurs_zamkniecia == '1.27'


def test_zapis_gz_z_odczytem_kontrolnym(monkeypatch, tmp_path):
    monkeypatch.setattr(oferta, '_znaki', lambda pdf: iter([strona()]))
    wyj = tmp_path / 'kursy_2026-09-30_17-30.csv.gz'
    oferta.main([str(tmp_path / 'oferta-dzisiaj-auto 2026-09-30 17-30.pdf'), '--wyjscie', str(wyj)])
    d = pd.read_csv(wyj, dtype=str)
    # 06.10.2026: plik ma tez kolumne „kontrola” (KONTROLA PDF) — poprawna strona: pusta w kazdym wierszu
    assert list(d.columns) == oferta.KOLUMNY + ['kontrola'] and len(d) == 22
    assert d.kontrola.isna().all()
    assert set(d.godzina_pobrania) == {'2026-09-30 17:25'}        # stopka ma pierwszenstwo przed nazwa pliku


def test_pobrano_z_nazwy_gdy_brak_stopki(monkeypatch):
    monkeypatch.setattr(oferta, '_znaki', lambda pdf: iter([[z for z in strona() if z[2] < 800]]))
    d, _ = oferta.czytaj('oferta-jutro-auto 2026-09-30 20-30.pdf')
    assert set(d.godzina_pobrania) == {'2026-09-30 20:30'}


def test_kilka_pdf_zostaje_najnowszy_kurs(monkeypatch, tmp_path):
    stary = strona()                                    # stopka 17:25, Szkocja-Azerbejdzan „1” = 1.17
    nowy = [z for z in strona() if z[2] < 800 and not (z[2] == 213 and 169 <= z[0] < 186)] \
        + slowo(26 + 143, 213, '1.19') + slowo(31, 817, '2026-09-30 20:25', 12.0)
    strony = {'nowy.pdf': nowy, 'stary.pdf': stary}
    monkeypatch.setattr(oferta, '_znaki', lambda pdf: iter([strony[os.path.basename(pdf)]]))
    wyj = tmp_path / 'k.csv'
    oferta.main([str(tmp_path / 'nowy.pdf'), str(tmp_path / 'stary.pdf'), '--wyjscie', str(wyj)])
    d = pd.read_csv(wyj, dtype=str)
    w = d[(d.zdarzenie == 'Szkocja U21 - Azerbejdżan U21') & (d.rynek == '1')]
    assert list(w.kurs) == ['1.19'] and list(w.godzina_pobrania) == ['2026-09-30 20:25']


def test_mecz_podglad(monkeypatch, capsys):
    monkeypatch.setattr(oferta, '_znaki', lambda pdf: iter([strona()]))
    oferta.main(['x.pdf', '--mecz', 'szkocja', 'azerbejdzan'])
    out = capsys.readouterr().out
    assert 'pasujacych' not in out                       # jedno zdarzenie
    assert '1.17' in out and 'O1.5' in out and 'Portugalia' not in out


def test_zamkniecia_polskie_znaki_i_godzina_w_nazwie():
    k = _kursy(('2026-09-25', '20:45', 'PIŁKA NOŻNA', 'Węgry', 'Ukraina', '12', '1.30', '2026-09-25 20:25'),
               ('2026-09-25', '20:45', 'PIŁKA NOŻNA', 'Irlandia Północna', 'Gruzja', '12', '1.33', '2026-09-25 18:25'))   # PDF po przebiegu 18:00 (P115.5)
    a = _ako(('2026-09-25', '18:00', 'K5', '1', '1', 'pilka', 'Wegry - Ukraina (20:45)', '12', '1.28', '', '', ''),
             ('2026-09-25', '18:00', 'K5', '1', '2', 'pilka', 'Irlandia Polnocna - Gruzja', '12', '1.35', '', '', ''),
             ('2026-09-25', '18:00', 'K5', '1', '3', 'pilka', 'Wegry B - Ukraina', '12', '1.28', '', '', ''))   # inny klub
    z, _ = oferta.zamkniecia(k, a)
    assert list(z.noga_nr) == ['1', '2'] and list(z.kurs_zamkniecia) == ['1.30', '1.33']


def test_zamkniecia_mecz_przed_zapisem_nogi_odpada():
    k = _kursy(('2026-09-25', '12:00', 'PIŁKA NOŻNA', 'Australia', 'Brazylia', 'U3.5', '1.67', '2026-09-25 11:25'),
               ('2026-09-26', '12:00', 'PIŁKA NOŻNA', 'Australia', 'Brazylia', 'U3.5', '1.55', '2026-09-26 11:25'))
    a = _ako(('2026-09-25', '21:00', 'AKOP', '1', '1', 'pilka', 'Australia - Brazylia', 'U3.5', '1.54', '', '', ''))
    z, _ = oferta.zamkniecia(k, a)
    assert list(z.kurs_zamkniecia) == ['1.55']          # mecz z 26.09, nie rozegrany 25.09 12:00


def test_plik_zamkniecia_nie_nadpisuje_nogi(tmp_path):
    """Noga bez wyniku + plik zamkniec z samym kluczem i kursem: zostaje wiersz nogi (status, uwaga), dochodzi kurs."""
    kol = 'data,godzina_uruchomienia,tag,nr_kuponu,noga_nr,zdarzenie,rynek,kurs,status,trafiona,uwaga\n'
    (tmp_path / 'ako_log DELTA 2026-10-01 12:00.csv').write_text(
        kol + '2026-10-01,12:00,K5,1,1,Walia - Norwegia,U3.5,1.62,DO GRY,,stawka 2 zl\n', encoding='utf-8')
    (tmp_path / 'ako_log zamkniecia 2026-10-01 20-30.csv').write_text(
        'data,godzina_uruchomienia,tag,nr_kuponu,noga_nr,zdarzenie,rynek,kurs,kurs_zamkniecia\n'
        '2026-10-01,12:00,K5,1,1,Walia - Norwegia,U3.5,1.62,1.58\n'
        '2026-10-01,12:00,K9,1,1,Nie ma - Takiej nogi,1,1.50,1.40\n', encoding='utf-8')
    os.utime(tmp_path / 'ako_log DELTA 2026-10-01 12:00.csv', (1_000_000, 1_000_000))
    dzienniki.scal(str(tmp_path), cel=str(tmp_path))
    d = dzienniki._czytaj(tmp_path / 'ako_log.csv')
    assert len(d) == 1                                   # klucz tylko z pliku zamkniec nie tworzy nogi
    r = d.iloc[0]
    assert (r.status, r.uwaga, r.kurs_zamkniecia) == ('DO GRY', 'stawka 2 zl', '1.58')


def test_zamkniecia_kolumny_wyniku():
    k = _kursy(('2026-09-30', '18:00', 'PIŁKA NOŻNA', 'Litwa', 'Andora', '12', '1.27', '2026-09-30 17:30'))
    a = _ako(('2026-09-30', '15:00', 'K5c', '1', '1', 'pilka', 'Litwa - Andora', '12', '1.26', '', '', ''))
    z, _ = oferta.zamkniecia(k, a)
    assert list(z.columns) == oferta.KLUCZ_AKO + ['zdarzenie', 'rynek', 'kurs', 'kurs_zamkniecia']
    assert list(oferta.KLUCZ_AKO) == dzienniki.RODZAJE['ako_log'][0]
    z, _ = oferta.zamkniecia(k, a.assign(zdarzenie='Inny - Mecz'))
    assert len(z) == 0 and 'kurs_zamkniecia' in z.columns
