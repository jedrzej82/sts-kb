"""30.09.2026 (przeglad Apps Script): skryptow nie da sie uruchomic w CI — pilnujemy kolejnosci krokow w kodzie
i klucza scalania (ten ostatni: node, jesli jest)."""
import os
import re
import shutil
import subprocess

import pytest

AS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'apps_script')


def _txt(n):
    return open(os.path.join(AS, n), encoding='utf-8').read()


def _cialo(txt, funkcja):
    i = txt.index(f'function {funkcja}(')
    j = txt.find('\nfunction ', i + 1)
    return txt[i:j if j > 0 else None]


def test_ligapro_postep_po_zapisie_plikow():
    c = _cialo(_txt('ligapro.gs'), 'ligaproPracuj')
    assert c.index('ligaproZapisz(nowe)') < c.index("P.setProperty('ligapro_hist'")


def test_terminarz_bez_pilki_nie_nadpisuje():
    t = _txt('terminarz.gs')
    for f in ('terminarzFs',):
        c = _cialo(t, f)
        assert 'brakPilki' in c and c.index('brakPilki.length') < c.index("folder.createFile(Utilities.gzip")
    c = t[t.index('var wiersze = [], nazwySportow = {}, brakPilki = []'):t.index('// Flashscore: identyfikator sportu')]
    assert c.index('if (brakPilki.length)') < c.index('folder.createFile(Utilities.gzip')


def test_historia_niepelny_dzien_nie_jest_gotowy():
    c = _cialo(_txt('terminarz.gs'), 'wyniki365Historia')
    assert c.index('if (niepelny)') < c.index('gotowe[d] = 1')


def test_klucz_scalania_z_pol_csv():
    t = _txt('terminarz.gs')
    assert not re.search(r"split\(','\)\.slice\(0, 7\)", t)
    if not shutil.which('node'):
        pytest.skip('brak node')
    csv = _cialo(t, 'terminarzCsv'); kl = _cialo(t, '_klucz7_')
    js = csv + '\n' + kl + r'''
    // Utilities.parseCsv — prosty parser RFC 4180 (tylko do testu)
    var Utilities = {parseCsv: function (s) { var o = [], f = '', q = false;
      for (var i = 0; i < s.length; i++) { var ch = s[i];
        if (q) { if (ch === '"' && s[i + 1] === '"') { f += '"'; i++; } else if (ch === '"') q = false; else f += ch; }
        else if (ch === '"') q = true; else if (ch === ',') { o.push(f); f = ''; } else f += ch; }
      o.push(f); return [o]; }};
    var a = terminarzCsv(['2026-09-28', 'handball', 'Europe', 'EHF, Group A', '', 'Kielce', 'Veszprem', 30, 28]);
    var b = terminarzCsv(['2026-09-28', 'handball', 'Europe', 'EHF, Group A', '', 'Kielce', 'Szeged', 27, 27]);
    var stary = function (w) { return w.split(',').slice(0, 7).join(','); };
    console.log(JSON.stringify([stary(a) === stary(b), _klucz7_(a) === _klucz7_(b), _klucz7_(a).split('\u0001')[6]]));
    '''
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip()
    assert out == '[true,false,"Veszprem"]'                  # stary klucz: kolizja; nowy: rozne mecze
