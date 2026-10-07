"""07.10.2026 — decyzja uzytkownika („od razu”): tenis.py wypisuje WERDYKT i z --nogi dopisuje noge do nogi.csv.
P do kuponu = P_skalibr − 3 pp (model zawyzal: 66,6% wobec 63,4% na 82 rozliczonych typach), noga od 70%, do pliku
tylko z kursem i EV > 0 po podatku."""
import csv

import tenis


def _w(tmp_path, monkeypatch, pc, kurs=None, nmin=50, stale=(), nogi=True):
    cal = tmp_path / 'cal.csv'
    cal.write_text('p_model,p_kalibr\n0.5,0.5\n1,1\n')
    monkeypatch.setattr(tenis, 'CAL', str(cal))
    plik = tmp_path / 'nogi.csv'
    a = ['Swiatek Iga', 'Kasatkina Daria'] + (['--kurs', f'Z1={kurs}'] if kurs else []) + (['--nogi', str(plik)] if nogi else [])
    pk = tenis.werdykt(['Swiatek Iga', 'Kasatkina Daria'], 'Iga Swiatek', 'Daria Kasatkina', 'Iga Swiatek', pc, nmin, list(stale), a)
    return pk, (list(csv.DictReader(open(plik, encoding='utf-8'))) if plik.exists() else [])


def test_noga_z_ev_dodatnim_trafia_do_nogi_csv(tmp_path, monkeypatch, capsys):
    pk, w = _w(tmp_path, monkeypatch, 0.839, kurs=1.45)
    assert abs(pk - 0.809) < 1e-9
    assert 'WERDYKT: NOGA DOPUSZCZONA' in capsys.readouterr().out
    assert len(w) == 1 and w[0]['rynek'] == 'Z1' and w[0]['sport'] == 'tenis' and w[0]['ev_dodatni'] == '1'
    assert w[0]['mecz'] == 'Swiatek Iga - Kasatkina Daria' and w[0]['p'] == '0.8090'


def test_ev_ujemne_i_progi(tmp_path, monkeypatch, capsys):
    assert _w(tmp_path, monkeypatch, 0.766, kurs=1.24)[1] == []                         # EV < 0 — tylko werdykt
    assert _w(tmp_path, monkeypatch, 0.72, kurs=2.0)[0] is None                         # 72% − 3 pp < 70%
    assert _w(tmp_path, monkeypatch, 0.90, kurs=1.5, nmin=3)[0] is None                 # brak danych rywala
    assert _w(tmp_path, monkeypatch, 0.90, kurs=1.5, stale=['Daria Kasatkina'])[0] is None
    out = capsys.readouterr().out
    assert out.count('WERDYKT: NIE NA KUPON') == 3


def test_opcje_nie_sa_nazwiskami():
    assert tenis._kursy(['A', 'B', '--kurs', 'Z2=2,90', '--kurs', '1=1.4', '--kurs', 'X=3']) == {'2': 2.9, '1': 1.4}
