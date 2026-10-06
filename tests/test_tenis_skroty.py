"""06.10.2026 — tenis: zapis Flashscore ITF „Nazwisko I.” sklejany z pelna nazwa (Raport 05.10 21:00, Ruzic – Dudeney)."""
import pandas as pd

import tenis


def _hist(tmp_path, monkeypatch, mecze):
    w = [dict(date=d, tour=t, turniej='X', poziom='C', nawierzchnia='Hard', runda='R32', best_of=3,
              zwyciezca=z, przegrany=p, score='6-4 6-4') for d, t, z, p in mecze]
    pd.DataFrame(w).to_csv(tmp_path / 'h.csv', index=False)
    monkeypatch.setattr(tenis, 'HIST', str(tmp_path / 'h.csv'))
    monkeypatch.setattr(tenis, 'DELTA', str(tmp_path / 'brak.csv'))
    tenis.ALIASY.clear()
    d = tenis.load()
    return set(d.winner_name) | set(d.loser_name), d


def test_skrot_flashscore_sklejony_z_pelna_nazwa(tmp_path, monkeypatch):
    # tenis_hist: „Alicia Dudeney” (WTA do 29.06) i „Dudeney A.” (ITF-W 01-02.10) — dotad dwie osoby,
    # tenis.py: „ostatni w bazie 2026-06-29”, „dane nieaktualne”
    n, d = _hist(tmp_path, monkeypatch, [
        ('2026-06-15', 'WTA', 'Dayana Yastremska', 'Alicia Dudeney'),
        ('2026-06-29', 'WTA', 'Alycia Parks', 'Alicia Dudeney'),
        ('2026-10-01', 'ITF-W', 'Dudeney A.', 'Linda Klimovicova'),
        ('2026-10-02', 'ITF-W', 'Katie Swan', 'Dudeney A.'),
        ('2026-10-01', 'ITF-W', 'Amariei I. D.', 'Katie Swan'),     # drugie imie pominiete w pelnej nazwie — wolno
        ('2026-08-01', 'WTA', 'Ilinca Amariei', 'Alycia Parks')])
    assert 'Dudeney A.' not in n and 'Amariei I. D.' not in n
    assert d[(d.winner_name == 'Alicia Dudeney') | (d.loser_name == 'Alicia Dudeney')].date.max() == pd.Timestamp('2026-10-02')
    assert tenis.ALIASY['Dudeney A.'] == 'Alicia Dudeney'


def test_skrot_niejednoznaczny_albo_z_dodatkowym_imieniem_zostaje(tmp_path, monkeypatch):
    n, _ = _hist(tmp_path, monkeypatch, [
        ('2026-09-01', 'ITF', 'Cristian Felipe Sanchez Rojas', 'Jan Nowak'),
        ('2026-10-01', 'ITF', 'Rojas C.', 'Piotr Kowal'),          # Flashscore podalby „Sanchez Rojas C. F.”
        ('2026-09-01', 'ITF', 'Oliver Brown', 'Jan Nowak'),
        ('2026-09-02', 'ITF', 'Owen Brown', 'Piotr Kowal'),
        ('2026-10-01', 'ITF', 'Brown O.', 'Adam Lis'),             # dwoch kandydatow — nie zgadujemy
        ('2026-09-01', 'ITF', 'Marek Zalewski', 'Jan Nowak'),
        ('2026-10-01', 'ITF', 'Zalewski M.', 'Marek Zalewski'),    # grali ze soba — dwie osoby
        ('2026-09-01', 'ITF-W', 'Anna Lis', 'Ewa Nowak'),
        ('2026-10-01', 'ITF', 'Lis A.', 'Jan Nowak')])             # inna plec rozgrywek
    assert {'Rojas C.', 'Brown O.', 'Zalewski M.', 'Lis A.'} <= n
