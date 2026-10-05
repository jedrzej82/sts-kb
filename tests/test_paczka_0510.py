"""Paczka 05.10.2026 — usterki z Raportu 04.10 21:00 (tozsamosc klubow i dopasowanie po terminarzu)."""
import pandas as pd

import build_kb
import typuj


def _m(w):
    return pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam']).assign(
        MatchDate=lambda x: pd.to_datetime(x.MatchDate))


def test_oba_skroty_terminarz_potwierdza_jeden_i_poprawia_drugi():
    # przed: Godoy Cruz – CA Los Andes -> NIEPEWNE DOPASOWANIE (terminarz potwierdzal Godoy Cruz, a funkcja sie poddawala)
    m = _m([('Argentina | Primera Nacional', '2026-09-27', 'Godoy Cruz', 'Los Andes'),
            ('Argentina | Torneo Regional Federal Amateur', '2025-12-07', 'CA Los Andes (Los Sarmientos)', 'X')])
    pool = {'Godoy Cruz', 'Los Andes', 'CA Los Andes (Los Sarmientos)', 'X'}
    mt = {'gosp': 'Godoy Cruz', 'gosc': 'Los Andes', 'kraj': 'ARGENTINA', 'turniej': 'Primera Nacional'}
    wyn = typuj.skrot_z_terminarza('CD Godoy Cruz', 'Godoy Cruz', 'CA Los Andes (Los Sarmientos)',
                                   [('CD Godoy Cruz', 'Godoy Cruz'), ('CA Los Andes', 'CA Los Andes (Los Sarmientos)')],
                                   mt, pool, m)
    assert wyn == ('Godoy Cruz', 'Los Andes')


def test_terminarz_tylko_potwierdza_to_nie_zmiana():
    m = _m([('ARG2', '2026-09-27', 'Godoy Cruz', 'Y')])
    mt = {'gosp': 'Godoy Cruz', 'gosc': 'Los Andes', 'kraj': 'ARGENTINA', 'turniej': 'Primera Nacional'}
    assert typuj.skrot_z_terminarza('CD Godoy Cruz', 'Godoy Cruz', 'Z', [('CD Godoy Cruz', 'Godoy Cruz')],
                                    mt, {'Godoy Cruz', 'Y', 'Z'}, m) is None


def _scal(w, monkeypatch):
    monkeypatch.setattr(build_kb, '_elo_nazwy', lambda: {})
    m = pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'])
    out = build_kb.scal_zapis_nazw(m)
    out = out[0] if isinstance(out, tuple) else out
    return set(out.HomeTeam) | set(out.AwayTeam)


def test_sparing_i_liga_to_ten_sam_klub(monkeypatch):
    # przed: "Argentinos Juniors" -> wpis z JEDNEGO sparingu (ROZNE LIGI BEZ ELO, NIESWIEZA 263 dni)
    nazwy = _scal([('ARG', '2026-09-20', 'Argentinos Jrs', 'Tigre', 1, 0),
                   ('Argentina | Amistosos de Verano', '2026-01-14', 'Argentinos Juniors', 'Boca Juniors', 0, 0),
                   ('Argentina | Amistosos de Verano', '2026-01-17', 'Instituto AC Cordoba', 'Talleres', 1, 1),
                   ('ARG', '2026-10-02', 'Instituto', 'Tigre', 2, 1)], monkeypatch)
    assert 'Argentinos Juniors' not in nazwy and 'Argentinos Jrs' in nazwy
    assert 'Instituto AC Cordoba' not in nazwy and 'Instituto' in nazwy


def test_spadek_zmienia_zapis_nazwy(monkeypatch):
    # przed: Unión Española NIESWIEZA (302 dni) — po spadku 365scores pisze „U. Española”
    nazwy = _scal([('CHI', '2025-12-06', 'Unión Española', 'Colo Colo', 1, 2),
                   ('Chile | First Division B', '2026-09-15', 'U. Española', 'San Luis de Quillota', 0, 0),
                   ('URU', '2023-12-07', 'La Luz FC', 'Nacional', 0, 1),
                   ('Uruguay | Segunda Division', '2026-09-27', 'La Luz', 'CA River Plate', 1, 1)], monkeypatch)
    assert 'U. Española' not in nazwy and 'Unión Española' in nazwy
    assert 'La Luz' not in nazwy and 'La Luz FC' in nazwy


def test_aliasy_klubow_z_raportu_2100():
    pool = {'CA River Plate', 'River Plate', 'Tigres', 'U.A.N.L.- Tigres'}
    assert typuj.resolve('River Plate Montevideo', pool) == 'CA River Plate'
    assert typuj.resolve('Tigres FC Bogota', pool) == 'Tigres'
