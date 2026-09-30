"""30.09.2026 (Raport 18:00): paczka.zip (Apps Script paczka.gs) — wszystkie dane przebiegu jednym pobraniem;
hist_import.fetch rownolegle. Paczka bledna = nic nie rozpakowane (przebieg pobiera pliki pojedynczo)."""
import gzip
import io
import os
import zipfile

import przebieg


def _dz():
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('ako_log X __0001.csv', 'data,godzina_uruchomienia,tag,nr_kuponu,noga_nr,trafiona\n2026-09-30,18:00,K3,1,1,\n')
        z.writestr('dzienniki_manifest.csv', 'plik,utworzony,id\n"ako_log X __0001.csv",2026-09-30T17:55:36.000Z,a\n')
    return b.getvalue()


def _paczka(pliki, zly_rozmiar=None):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        man = 'plik,zmieniony,bajty\n'
        for n, t in pliki.items():
            z.writestr(n, t)
            man += f'{n},2026-09-30T17:47:42.000Z,{len(t) + (1 if n == zly_rozmiar else 0)}\n'
        z.writestr('paczka_manifest.csv', man)
    return b.getvalue()


PLIKI = {'zewn/wyniki_365_pilka_2026-09.csv.gz': gzip.compress(b'data,gosp\n2026-09-30,A\n'),
         'zewn/terminarz_fs.csv.gz': gzip.compress(b'data,sport\n2026-09-30,football\n'),
         'statystyki_druzyn.csv.gz': gzip.compress(b'druzyna,data_aktualizacji\nA,2026-09-30 19:45\n'),
         'dzienniki.zip': _dz()}


def test_rozpakuj_na_miejsca_i_dzienniki(tmp_path):
    (tmp_path / 'paczka.zip').write_bytes(_paczka(PLIKI))
    assert przebieg.rozpakuj_paczke(str(tmp_path)) == 4
    assert (tmp_path / 'zewn' / 'wyniki_365_pilka_2026-09.csv.gz').read_bytes() == PLIKI['zewn/wyniki_365_pilka_2026-09.csv.gz']
    assert (tmp_path / 'statystyki_druzyn.csv.gz').exists() and not (tmp_path / 'paczka.zip').exists()
    assert (tmp_path / 'ako_log.csv').exists()   # dzienniki z paczki od razu scalone
    t = os.path.getmtime(tmp_path / 'zewn' / 'terminarz_fs.csv.gz')
    assert abs(t - 1790790462) < 2   # czas zmiany z manifestu (2026-09-30T17:47:42Z)


def test_bledna_paczka_nic_nie_rozpakowuje(tmp_path, capsys):
    for zle in (dict(PLIKI, **{'zewn/wyniki_fs_inne_2026-09.csv.gz': b'BRAK'}),   # nie gzip
                dict(PLIKI, **{'../przebieg.py': b'x'}),                          # sciezka poza wzorcami
                dict(PLIKI, **{'typuj.py': b'x'})):                               # kod repo
        (tmp_path / 'paczka.zip').write_bytes(_paczka(zle))
        assert przebieg.rozpakuj_paczke(str(tmp_path)) is None
    (tmp_path / 'paczka.zip').write_bytes(_paczka(PLIKI, zly_rozmiar='zewn/terminarz_fs.csv.gz'))
    assert przebieg.rozpakuj_paczke(str(tmp_path)) is None
    assert not (tmp_path / 'zewn').exists() and not (tmp_path / 'typuj.py').exists()
    assert capsys.readouterr().out.count('BLAD: paczka.zip niepoprawna') == 4


def test_brak_paczki(tmp_path):
    assert przebieg.rozpakuj_paczke(str(tmp_path)) is None


def test_fetch_te_same_pobrania_rownolegle(monkeypatch):
    import hist_import
    wywolania = []
    monkeypatch.setattr(hist_import, 'get', lambda url, path, force=False: wywolania.append((url, path, bool(force))) or True)
    monkeypatch.setattr(hist_import, '_repo', lambda d, repo, pat: wywolania.append((repo, d, None)))
    monkeypatch.setattr(hist_import.os, 'makedirs', lambda *a, **k: None)
    hist_import.fetch()
    Y = hist_import.YEAR
    oczek = len(hist_import.REPOS) + 1 + 3 * (Y + 2 - 2002) + 2 * (Y + 1 - 1968)
    assert len(wywolania) == oczek == len(set(wywolania))
    assert ('https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
            os.path.join(hist_import.RAW, 'nfl_games.csv'), True) in wywolania


def test_gs_placeholder():
    t = open(os.path.join(os.path.dirname(przebieg.__file__), 'apps_script', 'paczka.gs'), encoding='utf-8').read()
    assert "PACZKA_FOLDER_ID = 'WKLEJ_ID_FOLDERU_BAZA_WIEDZY'" in t and 'paczka_manifest.csv' in t
