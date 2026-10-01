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


def test_puchar_krajowy_skroty_z_czlonami_ogolnymi():
    """01.10.2026 (Raport 12:00, USTERKA 4): QSL Cup (Katar) — kluby z dwoch poziomow ligi nie maja wspolnej ligi."""
    typuj._SKROTY.clear(); typuj._SKROTY_OGOLNE.clear()
    pula = {'Al Gharafa', 'Mesaimeer SC', 'Independiente', 'Qatar SC'}
    assert typuj._skrot_albo_nic('Al-Gharafa SC', 'Al Gharafa', pula) == 'Al Gharafa'
    assert typuj._skrot_albo_nic('Al-Mesaimeer SC', 'Mesaimeer SC', pula) == 'Mesaimeer SC'    # „Al-” odpada, rdzen jednoznaczny
    assert typuj._skrot_albo_nic('Independiente Yumbo', 'Independiente', pula) == 'Independiente'  # przypadek (c)
    assert typuj._SKROTY_OGOLNE == {'Al-Gharafa SC', 'Al-Mesaimeer SC'}
    # „Al-” przy rdzeniu, ktory maja tez inne kluby — dalej ODRZUCONE (przypadek (b)), nie skrot
    assert typuj._skrot_albo_nic('Al Hilal', 'Hilal', {'Hilal', 'Hilal Omdurman'}) is None
    puchar = {'kraj': 'QATAR', 'turniej': 'QSL Cup'}
    ok = [('Al-Gharafa SC', 'Al Gharafa'), ('Al-Mesaimeer SC', 'Mesaimeer SC')]
    assert typuj.skrot_w_pucharze_ok(ok, puchar, ('qatar', 'qatar'))
    # liga, nie puchar — wspolna liga dalej wymagana
    assert not typuj.skrot_w_pucharze_ok(ok, {'kraj': 'QATAR', 'turniej': 'Stars League'}, ('qatar', 'qatar'))
    # brak meczu w terminarzu albo kraj inny niz lig klubow — dalej noga MNIEJ
    assert not typuj.skrot_w_pucharze_ok(ok, None, ('qatar', 'qatar'))
    assert not typuj.skrot_w_pucharze_ok(ok, puchar, ('qatar', 'saudi arabia'))
    assert not typuj.skrot_w_pucharze_ok(ok, puchar, ('qatar', None))
    # zgubiony czlon rozrozniajacy — w pucharze tez stop
    assert not typuj.skrot_w_pucharze_ok([('Independiente Yumbo', 'Independiente')],
                                         {'kraj': 'COLOMBIA', 'turniej': 'Copa Colombia'}, ('colombia', 'colombia'))
