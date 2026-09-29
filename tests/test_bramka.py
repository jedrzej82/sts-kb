"""Bramka drugiego zrodla (Poprawka 48) i arytmetyka EV po podatku."""
import pytest

import typuj


def _mecze(druzyna, wyniki, rywal='R'):
    """Lista (data, gosp, gosc, gole_g, gole_a) z perspektywy gospodarza."""
    return [(i, druzyna, f'{rywal}{i}', g, a) for i, (g, a) in enumerate(wyniki)]


def test_brak_drugiego_zrodla_przy_malej_probie(capsys):
    w = _mecze('H', [(1, 0)] * 5) + _mecze('A', [(0, 1)] * 10)
    assert typuj.drugie_zrodlo(w, 'H', 'A', [('1', 0.8, 0.8)]) == {}
    assert 'BRAK DRUGIEGO ZRODLA' in capsys.readouterr().out


def test_zgodne_daje_p_modelu():
    # Poprawka 58: zgodnosc obowiazkowa, ale P do kuponu = P modelu (nie min) — docs/BACKTEST_P48.md.
    # H wygrywa 8/10, A przegrywa 8/10 -> forma '1' = (9/12 + 9/12)/2 = 0.75, model 0.80 -> zgodne (5 pp)
    w = _mecze('H', [(2, 0)] * 8 + [(0, 1)] * 2) + _mecze('A', [(0, 1)] * 8 + [(1, 0)] * 2)
    wynik = typuj.drugie_zrodlo(w, 'H', 'A', [('1', 0.80, 0.80)])
    assert wynik['1'] == pytest.approx(0.80)


def test_rozbiezne_to_none():
    w = _mecze('H', [(0, 1)] * 10) + _mecze('A', [(1, 0)] * 10)
    assert typuj.drugie_zrodlo(w, 'H', 'A', [('1', 0.80, 0.80)])['1'] is None


@pytest.mark.parametrize('dz, k, oczekiwane', [
    (None, '1X', (None, 'drugie zrodlo nie liczone')),
    ({}, '1X', (None, 'BRAK DRUGIEGO ZRODLA')),
    ({'1': 0.7}, '1X', (None, 'rynek bez drugiego zrodla')),
    ({'1X': None}, '1X', (None, 'ROZBIEZNE zrodla')),
    ({'1X': 0.8}, '1X', (0.8, None)),
])
def test_werdykt_nogi(dz, k, oczekiwane):
    assert typuj.werdykt_nogi(k, dz) == oczekiwane


def test_ev_po_podatku():
    ev, kelly = typuj.ev_kelly(0.80, 1.40)
    assert ev == pytest.approx(0.80 * 1.40 * 0.88 - 1)
    assert kelly == 0.0                      # EV < 0 -> brak stawki
    assert typuj.ev_kelly(0.5, 1.10)[1] == 0.0   # kurs po podatku < 1


def test_value_liczy_ev_z_p_po_bramce(capsys):
    # P modelu 82% daje EV > 0, ale P do kuponu 80% juz nie — noga ma odpasc
    typuj.value([('1X', 0.80, 0.82)], {'1X': 1.40}, {'1X': 0.80})
    out = capsys.readouterr().out
    assert '✔ wartość' in out and 'NIE NA KUPON: EV ≤ 0 po bramce' in out


@pytest.mark.parametrize('k, p, dopuszczona', [('U2.5', 0.72, False), ('BTTS_nie', 0.80, False), ('2', 0.71, False),
                                               ('U2.5', 0.65, True), ('U3.5', 0.75, True), ('1', 0.75, True)])
def test_rynki_zawyzone_przy_p70(k, p, dopuszczona):
    # Poprawka 58.5: U2.5/BTTS/2 przy P >= 70% mocno zawyzone w backtescie (docs/BACKTEST_P48.md)
    pk, powod = typuj.werdykt_nogi(k, {k: p})
    assert (pk is not None) == dopuszczona
    if not dopuszczona: assert 'ZAWYZONY' in powod


def test_nogi_dopuszczone_trafiaja_do_pliku(tmp_path, monkeypatch):
    import pandas as pd
    f = tmp_path / 'nogi.csv'
    monkeypatch.setattr(typuj, 'NOGI_PLIK', str(f))
    typuj.value([('1X', 0.85, 0.85), ('O1.5', 0.80, 0.80)], {'1X': 1.40, 'O1.5': 1.10},
                {'1X': 0.85, 'O1.5': 0.80}, mecz='A - B', szacunek=False, polski=True)
    d = pd.read_csv(f)
    assert list(d.rynek) == ['1X']                      # O1.5 @1.10: EV <= 0 — nie trafia
    assert d.polski.iloc[0] == 1 and d.kryteria.isna().all()


def test_para_z_siatki_nie_iloczyn():
    # Poprawka 59 / A5 pkt 1: "1" + "U2.5" sa ujemnie skorelowane — laczne P z siatki < iloczyn
    from model import p_pary, markets
    mk = markets(1.6, 0.9)
    pj = p_pary(1.6, 0.9, -0.05, '1', 'U2.5')
    assert pj < mk['1'] * mk['U2.5'] - 0.03
    assert p_pary(1.6, 0.9, -0.05, 'O2.5', 'U2.5') == 0.0
    assert p_pary(1.6, 0.9, -0.05, '1', 'gosp_O0.5') == pytest.approx(mk['1'])   # "1" zawiera gola gospodarza
    assert p_pary(1.6, 0.9, -0.05, 'DNB_1', 'O1.5') is None and p_pary(1.6, 0.9, -0.05, 'HT_1', 'O1.5') is None


def _rows(lam=(1.8, 0.8)):
    from model import markets
    mk = markets(*lam)
    return [(k, mk[k], mk[k]) for k in typuj.KEY_MARKETS]


@pytest.mark.parametrize('kurs, dopuszczona', [(None, False), (1.05, False), (3.0, True)])
def test_para_wymaga_kursu_buildera_i_ev(kurs, dopuszczona, capsys, tmp_path, monkeypatch):
    rows = _rows(); d = {k: pc for k, p, pc in rows}
    f = tmp_path / 'nogi.csv'; monkeypatch.setattr(typuj, 'NOGI_PLIK', str(f))
    typuj.para(rows, (1.8, 0.8), -0.05, '1X', 'O1.5', kurs, {'1X': d['1X'], 'O1.5': d['O1.5']}, mecz='A - B')
    out = capsys.readouterr().out
    assert ('PARA DOPUSZCZONA' in out) == dopuszczona and f.exists() == dopuszczona
    if dopuszczona:
        import pandas as pd
        r = pd.read_csv(f).iloc[0]
        assert r.rynek == '1X+O1.5' and r.p <= min(d['1X'], d['O1.5'])


def test_para_odpada_gdy_noga_odpada(capsys):
    rows = _rows(); d = {k: pc for k, p, pc in rows}
    typuj.para(rows, (1.8, 0.8), -0.05, '1X', 'O1.5', 9.0, {'1X': None, 'O1.5': d['O1.5']})   # 1X rozbiezne
    assert 'NIE NA KUPON' in capsys.readouterr().out
