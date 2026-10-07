"""07.10.2026 — Raport 07.10 12:00, usterka 3: „EOFError: Ran out of input” w tenis.state() przy 4 rownoleglych
tenis.py (jeden proces pisal plik stanu przez open(p, 'wb'), drugi czytal pusty, ale swiezy plik)."""
import multiprocessing as mp
import os
import pickle

import pamiec


def test_pusty_lub_uciety_plik_to_brak_cache(tmp_path):
    p = tmp_path / 'stan.pkl'
    p.write_bytes(b'')                                    # dokladnie stan z Raportu: plik otwarty do zapisu, jeszcze pusty
    assert pamiec.wczytaj(str(p)) is None
    p.write_bytes(pickle.dumps(list(range(1000)))[:50])   # uciety w polowie
    assert pamiec.wczytaj(str(p)) is None
    assert pamiec.wczytaj(str(tmp_path / 'brak.pkl')) is None


def test_zapis_atomowy_cel_nigdy_nie_jest_pusty(tmp_path, monkeypatch):
    p = str(tmp_path / 'stan.pkl')
    pamiec.zapisz(p, {'stary': 1})
    widziane = []
    prawdziwy = pickle.dump

    def dump(v, f):                                       # w trakcie zapisu ktos czyta plik docelowy
        widziane.append(pamiec.wczytaj(p))
        prawdziwy(v, f)
    monkeypatch.setattr(pickle, 'dump', dump)
    pamiec.zapisz(p, {'nowy': 2})
    assert widziane == [{'stary': 1}]                     # czytelnik widzi stara wersje, nie pusty plik
    assert pamiec.wczytaj(p) == {'nowy': 2}
    assert [f for f in os.listdir(tmp_path) if f.endswith('.tmp')] == []


def _pisz_czytaj(p, n, q):
    bledy = 0
    for i in range(n):
        pamiec.zapisz(p, list(range(20000 + i)))
        if pamiec.wczytaj(p) is None: bledy += 1
    q.put(bledy)


def test_cztery_procesy_naraz_bez_bledow(tmp_path):
    # jak przebieg (P128.3: do 4 procesow tenis.py naraz) — wczesniej: EOFError w czesci odczytow
    p = str(tmp_path / 'stan.pkl')
    q = mp.Queue()
    pr = [mp.Process(target=_pisz_czytaj, args=(p, 30, q)) for _ in range(4)]
    for x in pr: x.start()
    for x in pr: x.join(60)
    assert [q.get(timeout=5) for _ in pr] == [0, 0, 0, 0]


def test_moduly_nie_pisza_cache_przez_open_wb():
    # tenis.state, typuj.cached, ensemble.build_rows — zapis tylko przez pamiec.zapisz
    for m in ('tenis.py', 'typuj.py', 'ensemble.py'):
        s = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), m), encoding='utf-8').read()
        assert 'pickle.dump(' not in s and 'pamiec.zapisz(' in s, m
