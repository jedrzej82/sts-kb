"""30.09.2026 (Raport 15:00, usterka 4): arkusze statystyk jako spakowane CSV z Apps Script arkusze.gs."""
import base64, gzip, os, shutil, subprocess
import pandas as pd
import pytest

import przebieg

AS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'apps_script')


def _csv(godzina, wierszy):
    return pd.DataFrame({'druzyna': [f't{i}' for i in range(wierszy)], 'data_aktualizacji': [godzina] * wierszy}).to_csv(index=False)


def test_rozpakowanie_gz_i_b64(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    (tmp_path / 'statystyki_hokej.csv.gz').write_bytes(gzip.compress(_csv('2026-09-30 15:45', 120).encode()))
    (tmp_path / 'statystyki_reczna.csv.gz.b64').write_text(base64.b64encode(gzip.compress(_csv('2026-09-30 15:45', 60).encode())).decode())
    przebieg.rozpakuj_arkusze()
    assert len(pd.read_csv(tmp_path / 'statystyki_hokej.csv')) == 120
    assert len(pd.read_csv(tmp_path / 'statystyki_reczna.csv')) == 60
    assert not list(tmp_path.glob('*.gz')) and not list(tmp_path.glob('*.b64'))


def test_nowszy_csv_wygrywa(tmp_path, monkeypatch):
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    (tmp_path / 'statystyki_druzyn.csv').write_text(_csv('2026-09-30 16:45', 5))
    (tmp_path / 'statystyki_druzyn.csv.gz').write_bytes(gzip.compress(_csv('2026-09-30 15:45', 9).encode()))
    przebieg.rozpakuj_arkusze()
    assert len(pd.read_csv(tmp_path / 'statystyki_druzyn.csv')) == 5         # CSV nowszy — zostaje


def test_uszkodzony_gzip_nie_nadpisuje(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    (tmp_path / 'statystyki_tenis.csv').write_text(_csv('2026-09-30 10:00', 3))
    (tmp_path / 'statystyki_tenis.csv.gz').write_bytes(gzip.compress(_csv('2026-09-30 15:45', 9).encode())[:-20])
    przebieg.rozpakuj_arkusze()
    assert len(pd.read_csv(tmp_path / 'statystyki_tenis.csv')) == 3
    assert 'BLAD' in capsys.readouterr().out


def test_arkusze_gs():
    t = open(os.path.join(AS, 'arkusze.gs'), encoding='utf-8').read()
    assert "ARKUSZE_FOLDER_ID = 'WKLEJ_ID_FOLDERU_BAZA_WIEDZY'" in t          # bez prawdziwego id w repo
    c = t[t.index('function arkuszePracuj('):]
    assert c.index('folder.createFile(Utilities.gzip') < c.index('setTrashed(true); });') < c.index('P.setProperty(klucz, zm)')
    assert c.index('arkuszeDobry_(') < c.index('folder.createFile(Utilities.gzip')
    for a in przebieg.ARKUSZE + przebieg.ARKUSZE_OPCJ:
        assert f"'{a}'" in t
    if not shutil.which('node'):
        pytest.skip('brak node')
    i = t.index('function arkuszeDobry_('); j = t.index('\nfunction ', i + 1)
    js = t[i:j] + r'''
    console.log(JSON.stringify([arkuszeDobry_('statystyki_hokej', 'druzyna,data_aktualizacji\na,2026\n'),
      arkuszeDobry_('statystyki_hokej', 'druzyna,data_aktualizacji\n'), arkuszeDobry_('statystyki_hokej', 'a,b\n1,2\n'),
      arkuszeDobry_('absencje', 'a,b\n1,2\n'), arkuszeDobry_('statystyki_hokej', '')]));'''
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    ok, pusty, bez_kol, abs_, nic = __import__('json').loads(r.stdout)
    assert ok == '' and abs_ == '' and 'pusty' in pusty and 'data_aktualizacji' in bez_kol and 'pusty' in nic


def test_godzina_bez_zera(tmp_path, monkeypatch):
    """Arkusze pisza „2026-09-30 8:45” — napisowo „8:45” > „16:46”. Porownujemy daty."""
    f = tmp_path / 'x.csv'
    pd.DataFrame({'data_aktualizacji': ['2026-09-30 8:45']}).to_csv(f, index=False)
    assert przebieg._aktualizacja(f).hour == 8                                 # bez zera tez czytelne
    pd.DataFrame({'data_aktualizacji': ['2026-09-30 8:45', '2026-09-30 16:46']}).to_csv(f, index=False)
    assert przebieg._aktualizacja(f).hour == 16
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    (tmp_path / 'statystyki_tenis.csv').write_text(_csv('2026-09-30 8:45', 3))
    (tmp_path / 'statystyki_tenis.csv.gz').write_bytes(gzip.compress(_csv('2026-09-30 16:46', 9).encode()))
    przebieg.rozpakuj_arkusze()
    assert len(pd.read_csv(tmp_path / 'statystyki_tenis.csv')) == 9          # gz nowszy (16:46) wygrywa


def test_wiek_arkusza_z_godzina_bez_zera(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    t = przebieg.teraz_pl() - pd.Timedelta(hours=2)
    s = f'{t:%Y-%m-%d} {t.hour}:{t:%M}'                                        # godzina bez zera wiodacego
    for a in przebieg.ARKUSZE:
        pd.DataFrame({'data_aktualizacji': [s]}).to_csv(tmp_path / f'{a}.csv', index=False)
    assert przebieg.kontrola_arkuszy() == []
    assert '(2 h)' in capsys.readouterr().out


def test_archiwum_dnia_w_arkusze_gs():
    """01.10.2026: archiwum arkuszy dnia robi Apps Script (konektor nie przyjal 388 KB z przebiegu)."""
    t = open(os.path.join(AS, 'arkusze.gs'), encoding='utf-8').read()
    c = t[t.index('function arkuszePracuj('):]
    assert c.index('arkuszeArchiwum_(folder, log)') < c.index("getFilesByName('arkusze_log.txt')")
    if not shutil.which('node'):
        pytest.skip('brak node')
    i = t.index('function arkuszeArchiwumNazwa_('); j = t.index('\nfunction ', i + 1)
    js = t[i:j] + r'''
    var jest = function (n) { return n === 'arkusze_2026-10-01.zip'; };
    console.log(JSON.stringify([arkuszeArchiwumNazwa_('2026-10-02', '11', jest), arkuszeArchiwumNazwa_('2026-10-02', '12', jest),
      arkuszeArchiwumNazwa_('2026-10-01', '13', jest), arkuszeArchiwumNazwa_('2026-10-02', '23', jest)]));'''
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert __import__('json').loads(r.stdout) == ['', 'arkusze_2026-10-02.zip', '', 'arkusze_2026-10-02.zip']
