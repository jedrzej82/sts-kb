"""30.09.2026 (przeglad typuj.py): liczba modeli w zespole i kontrola wspolnej ligi dla skrotow nazw."""
import typuj

W = (0.4, 0.0, 0.6)          # ensemble_wagi.json: Elo ma wage 0


def test_jeden_model_gdy_elo_ma_wage_zero():
    dc, el, pi = (1.3, 1.0), (1.4, 1.1), (1.2, 0.9)
    assert len(typuj.skladniki_zespolu(W, dc, el, pi)) == 2               # DC + pi
    # beniaminek (bez DC): Elo jest, ale nie wchodzi — liczy sie z samego pi, to JEDEN model
    assert typuj.skladniki_zespolu(W, None, el, pi) == [(0.6, pi)]
    # rozne ligi: pi pominiete w club(), zostaje samo Elo z waga 1
    assert typuj.skladniki_zespolu(W, None, el, None) == [(1.0, el)]
    assert typuj.skladniki_zespolu(W, None, None, None) == []


def test_krotsza_nazwa_i_czlony_ogolne_ida_do_kontroli_wspolnej_ligi():
    typuj._SKROTY.clear()
    pula = {'Crystal Palace', 'Olympic', 'Arsenal'}
    assert typuj._skrot_albo_nic('Crystal', 'Crystal Palace', pula) == 'Crystal Palace'
    assert typuj._skrot_albo_nic('BK Olympic', 'Olympic', pula) == 'Olympic'
    assert typuj._SKROTY == {'Crystal': 'Crystal Palace', 'BK Olympic': 'Olympic'}


def test_skrot_po_zamianie_nazwy_miasta_pod_nazwa_z_oferty():
    typuj._SKROTY.clear()
    r = typuj._przez_egzonim('Atletico Turyn', {'Torino', 'Bari'})
    assert r == 'Torino' and typuj._SKROTY.get('Atletico Turyn') == 'Torino'
