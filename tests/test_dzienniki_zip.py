"""30.09.2026 (Raport 18:00, usterka 1): dzienniki jako JEDEN dzienniki.zip (Apps Script dzienniki.gs) zamiast
62 pobran. Nazwy i manifest jak w dzienniki.gs; czas pliku = czas utworzenia na Dysku (pozniejszy wygrywa w scal)."""
import base64
import io
import os
import zipfile

import przebieg
import dzienniki

AKO = 'data,godzina_uruchomienia,tag,nr_kuponu,noga_nr,trafiona\n'
TYP = 'data,gosp,gość,rynek,trafiony\n'
PLIKI = [  # nazwa w zipie (jak dziennikiNazwa_), utworzony na Dysku, tresc
    ('ako_log 2026-09-24 21_00 (ręczne 21_39) __0001.csv', '2026-09-25T08:00:00.000Z', AKO + '2026-09-24,21:00,K1,1,1,0\n'),
    ('ako_log 2026-09-24 21_00 (ręczne 21_39) __0002.csv', '2026-09-24T20:17:26.000Z', AKO + '2026-09-24,21:00,K1,1,1,\n2026-09-24,21:00,K1,1,2,1\n'),
    ('typy_log PELNY 2026-09-29 21_00 __0003.csv', '2026-09-29T19:10:37.000Z', TYP + '2026-09-29,A,B,1,1\n'),
]


def _zip(bez_manifestu=False, bez_pliku=False):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for i, (n, _, t) in enumerate(PLIKI):
            if bez_pliku and i == 0: continue
            z.writestr(n, t)
        if not bez_manifestu:
            z.writestr('dzienniki_manifest.csv', 'plik,utworzony,id\n' + ''.join(f'"{n}",{c},id{i}\n' for i, (n, c, _) in enumerate(PLIKI)))
    return b.getvalue()


def test_rozpakuj_i_scal_pozniejszy_wygrywa(tmp_path):
    (tmp_path / 'dzienniki.zip').write_bytes(_zip())
    assert przebieg.rozpakuj_dzienniki(str(tmp_path)) == 3
    kat = tmp_path / 'dzienniki'
    assert sorted(os.listdir(kat)) == sorted(n for n, _, _ in PLIKI)
    w = dzienniki.scal(str(kat), cel=str(tmp_path))
    assert w['ako_log'] == (2, 3, 2) and w['typy_log'] == (1, 1, 1)
    ako = dzienniki._czytaj(str(tmp_path / 'ako_log.csv'))
    # noga 1: plik __0001 utworzony POZNIEJ (25.09) ma wynik 0 — wygrywa, choc jest pierwszy w zipie
    assert ako.set_index('noga_nr').loc['1', 'trafiona'] == '0'


def test_b64_z_konektora(tmp_path):
    t = '{"content": "' + base64.b64encode(_zip()).decode() + '", "id": "x", "mimeType": "application/zip", "title": "dzienniki.zip"}'
    (tmp_path / 'dzienniki.zip.b64').write_text(t)
    assert przebieg.rozpakuj_dzienniki(str(tmp_path)) == 3
    assert not (tmp_path / 'dzienniki.zip.b64').exists()


def test_bez_manifestu_albo_niepelny_blad(tmp_path, capsys):
    (tmp_path / 'dzienniki.zip').write_bytes(_zip(bez_manifestu=True))
    assert przebieg.rozpakuj_dzienniki(str(tmp_path)) is None
    (tmp_path / 'dzienniki.zip').write_bytes(_zip(bez_pliku=True))
    assert przebieg.rozpakuj_dzienniki(str(tmp_path)) is None
    (tmp_path / 'dzienniki.zip').write_bytes(b'to nie zip')
    assert przebieg.rozpakuj_dzienniki(str(tmp_path)) is None
    assert capsys.readouterr().out.count('BLAD') == 3


def test_brak_zipa(tmp_path):
    assert przebieg.rozpakuj_dzienniki(str(tmp_path)) is None


def test_gs_placeholder():
    t = open(os.path.join(os.path.dirname(przebieg.__file__), 'apps_script', 'dzienniki.gs'), encoding='utf-8').read()
    assert "DZIENNIKI_FOLDER_ID = 'WKLEJ_ID_FOLDERU_BAZA_WIEDZY'" in t and 'dzienniki_manifest.csv' in t
