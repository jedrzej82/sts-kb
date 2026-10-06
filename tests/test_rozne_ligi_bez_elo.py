"""06.10.2026 — Raport 15:00 usterka 2: „ROZNE LIGI BEZ ELO … nie buduj nogi kuponu” musi blokowac noge (Raufoss – IK Start)."""
import typuj


def test_rozne_ligi_bez_elo_blokuje_noge(monkeypatch):
    monkeypatch.setattr(typuj, 'LIGA_BEZ_TESTU', None)
    monkeypatch.setattr(typuj, 'KONTEKST_MECZU', {})
    dz = {'gosp_O0.5': 0.715}                                      # drugie zrodlo ZGODNE, EV +0,7% przy 1,60
    assert typuj.werdykt_nogi('gosp_O0.5', dz) == (0.715, None)
    typuj.KONTEKST_MECZU['zakaz_nogi'] = 'ROZNE LIGI BEZ ELO — P nieporownywalne, z tego meczu nie budujemy nogi kuponu'
    p, powod = typuj.werdykt_nogi('gosp_O0.5', dz)
    assert p is None and 'ROZNE LIGI BEZ ELO' in powod


def test_blokada_ustawiana_z_komunikatu():
    # komunikat i blokada w jednym miejscu kodu: zmiana tekstu komunikatu nie moze cicho wylaczyc blokady
    src = open(typuj.__file__, encoding='utf-8').read()
    assert "msg = (f'ROZNE LIGI BEZ ELO:" in src and "o.startswith('ROZNE LIGI BEZ ELO')" in src
