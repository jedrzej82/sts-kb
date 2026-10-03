"""03.10.2026 — termux/backfill_fsx.py: nadrabianie historii sportow druzynowych z Flashscore.

Pomiar, ktory uzasadnia ten skrypt (oferta 2026-10-03, okno 19:00-22:00, 70 zdarzen):
model mogl policzyc 32 (46%), brak danych 24 (34%), nazwa nierozpoznana 14 (20%).
Reczna: 8 policzalnych z 30; w bazie 964 druzyn recznej, tylko 109 (11%) z >= 10 meczami.
Przyczyna nie jest bledem pobierania (zrodla 853 meczow IX-X, baza 792), tylko data startu
kanalu Flashscore: 2026-09-22, dzien -1 i -2.

Testy sprawdzaja to, co moze cicho zepsuc dane: parsowanie kanalu i SCALANIE plikow.
Samego pobierania nie testujemy — wymaga sieci.
"""
import csv
import gzip
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'termux'))
import backfill_fsx as B  # noqa: E402

# Rekord w formacie kanalu Flashscore — separatory jak w apps_script/terminarz.gs
REK = ('ZA÷SPAIN: Liga Asobal¬ZY÷Spain~'
       'AA÷abc123¬AB÷3¬AD÷1759500000¬AE÷Bidasoa Irun'
       '¬AF÷Puente Genil¬AG÷31¬AH÷25¬ER÷Round 5'
       '¬BA÷15¬BB÷12¬BC÷16¬BD÷13~')


def test_parsuje_mecz_zakonczony():
    w = B.parsuj(REK, 'handball')
    assert len(w) == 1
    r = w[0]
    assert r[1] == 'handball'
    assert (r[2], r[3]) == ('SPAIN', 'Liga Asobal')      # kraj i turniej rozdzielone po ': '
    assert (r[5], r[6]) == ('Bidasoa Irun', 'Puente Genil')
    assert (r[7], r[8]) == ('31', '25')
    assert (r[9], r[10]) == ('15;16', '12;13')           # okresy sklejone srednikiem
    assert r[11] == 1                                    # zwyciezca: gospodarz


def test_pomija_mecz_w_trakcie():
    """AB != 3 = mecz niezakonczony. Wziecie go zatrulo by baze wynikiem z migawki."""
    assert B.parsuj(REK.replace('AB÷3', 'AB÷1'), 'handball') == []


def test_pomija_rekord_bez_wyniku():
    assert B.parsuj(REK.replace('AG÷31', 'AG÷'), 'handball') == []


def test_remis_ma_zwyciezce_zero():
    r = B.parsuj(REK.replace('AH÷25', 'AH÷31'), 'handball')[0]
    assert r[11] == 0


def test_turniej_bez_dwukropka_bierze_ZY():
    rek = REK.replace('ZA÷SPAIN: Liga Asobal', 'ZA÷Champions League')
    r = B.parsuj(rek, 'handball')[0]
    assert (r[2], r[3]) == ('Spain', 'Champions League')  # kraj z ZY


def test_naglowek_zgodny_z_apps_script():
    """Kolejnosc kolumn musi byc 1:1 z wynikiFsDruzynowe, inaczej zewn.py wczyta smieci."""
    assert B.NAGLOWEK == ['data', 'sport', 'kraj', 'turniej', 'runda', 'gosp', 'gosc',
                          'wg', 'wa', 'okresy_g', 'okresy_a', 'zwyciezca', 'nawierzchnia']


def test_klucz7_to_pierwsze_siedem_pol():
    """Klucz scalania identyczny jak _klucz7_ w terminarz.gs (data..gosc)."""
    w = B.parsuj(REK, 'handball')[0]
    assert B.klucz7(w) == '\u0001'.join(str(x) for x in w[:7])
    inny = list(w); inny[7] = '99'                       # inny wynik, ten sam mecz
    assert B.klucz7(inny) == B.klucz7(w)


def _plik(kat, miesiac, wiersze):
    s = os.path.join(kat, 'wyniki_fsx_inne_%s.csv.gz' % miesiac)
    with gzip.open(s, 'wt', encoding='utf-8', newline='') as fh:
        wr = csv.writer(fh, lineterminator='\n')
        wr.writerow(B.NAGLOWEK)
        for w in wiersze:
            wr.writerow(w)
    return s


def test_scalanie_nie_gubi_istniejacych(tmp_path):
    stary = ['2026-10-01', 'handball', 'SPAIN', 'Liga Asobal', '', 'A', 'B', '20', '19', '', '', 1, '']
    _plik(str(tmp_path), '2026-10', [stary])
    nowy = ['2026-10-02', 'handball', 'SPAIN', 'Liga Asobal', '', 'C', 'D', '30', '20', '', '', 1, '']
    nowych, razem = B.zapisz_miesiac(str(tmp_path), '2026-10', [nowy], False)
    assert (nowych, razem) == (1, 2)
    po = B.wczytaj_istniejace(os.path.join(str(tmp_path), 'wyniki_fsx_inne_2026-10.csv.gz'))
    assert B.klucz7(stary) in po and B.klucz7(nowy) in po


def test_ten_sam_mecz_nie_duplikuje_sie(tmp_path):
    w = ['2026-10-01', 'handball', 'SPAIN', 'Liga Asobal', '', 'A', 'B', '20', '19', '', '', 1, '']
    _plik(str(tmp_path), '2026-10', [w])
    nowych, razem = B.zapisz_miesiac(str(tmp_path), '2026-10', [w], False)
    assert (nowych, razem) == (0, 1)


def test_uszkodzony_plik_zostaje_nietkniety(tmp_path):
    """Lepiej nic nie zapisac niz nadpisac plik, ktorego nie umiemy odczytac."""
    s = os.path.join(str(tmp_path), 'wyniki_fsx_inne_2026-11.csv.gz')
    with open(s, 'wb') as fh:
        fh.write(b'to nie jest gzip')
    assert B.zapisz_miesiac(str(tmp_path), '2026-11', [['2026-11-01', 'handball', 'X', 'Y', '',
                                                        'A', 'B', '1', '0', '', '', 1, '']], False) == (0, 0)
    with open(s, 'rb') as fh:
        assert fh.read() == b'to nie jest gzip'


def test_obcy_naglowek_nie_zostaje_nadpisany(tmp_path):
    s = os.path.join(str(tmp_path), 'wyniki_fsx_inne_2026-12.csv.gz')
    with gzip.open(s, 'wt', encoding='utf-8', newline='') as fh:
        fh.write('cos,zupelnie,innego\n1,2,3\n')
    assert B.zapisz_miesiac(str(tmp_path), '2026-12', [['2026-12-01', 'handball', 'X', 'Y', '',
                                                        'A', 'B', '1', '0', '', '', 1, '']], False) == (0, 0)


def test_sucho_nic_nie_zapisuje(tmp_path):
    w = ['2026-10-01', 'handball', 'SPAIN', 'Liga Asobal', '', 'A', 'B', '20', '19', '', '', 1, '']
    nowych, razem = B.zapisz_miesiac(str(tmp_path), '2026-10', [w], True)
    assert (nowych, razem) == (1, 1)
    assert not os.path.exists(os.path.join(str(tmp_path), 'wyniki_fsx_inne_2026-10.csv.gz'))


def test_sporty_zgodne_z_apps_script():
    assert B.SPORTY == {'3': 'basketball', '7': 'handball', '12': 'volleyball'}


@pytest.mark.parametrize('pole', ['AE', 'FH'])
def test_nazwa_druzyny_z_AE_albo_FH(pole):
    """terminarz.gs bierze AE, a gdy puste — FH. Ta sama kolejnosc musi byc tutaj."""
    rek = REK.replace('AE÷Bidasoa Irun', '%s÷Bidasoa Irun' % pole)
    r = B.parsuj(rek, 'handball')
    assert r and r[0][5] == 'Bidasoa Irun'
