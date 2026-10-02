"""02.10.2026: hokej — druzyna po awansie/spadku niesie Elo z innej ligi (Krefeld DEL2 -> DEL: model 76%, rynek 47%;
Dresdner Eislowen DEL -> DEL2). Do ZMIANA_LIGI_MIN meczow w nowej lidze WERDYKT = NIE NA KUPON. Dane syntetyczne."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sporty  # noqa: E402


def _mecze(liga, druzyny, od, n_kolejek):
    w, dz = [], pd.Timestamp(od)
    for k in range(n_kolejek):
        for i in range(0, len(druzyny) - 1, 2):
            a, b = druzyny[(i + k) % len(druzyny)], druzyny[(i + 1 + k) % len(druzyny)]
            w.append(dict(data=dz + pd.Timedelta(days=3 * k), sport='hokej', liga=liga, gosp=a, gosc=b, pg=3, pa=2, dogrywka=0))
    return w


def _baza():
    DEL = [f'D{i}' for i in range(8)]
    DEL2 = [f'Z{i}' for i in range(8)]
    w = _mecze('Germany | DEL', DEL + ['Dresden'], '2025-09-10', 20) + _mecze('Germany | DEL2', DEL2 + ['Krefeld'], '2025-09-10', 20)
    # sezon 2026/27: Krefeld awansowal, Dresden spadl; sparing i CHL nie sa liga
    w += _mecze('Germany | DEL', DEL[:7] + ['Krefeld'], '2026-09-15', 4) + _mecze('Germany | DEL2', DEL2[:7] + ['Dresden'], '2026-09-15', 4)
    w += [dict(data=pd.Timestamp('2026-09-01'), sport='hokej', liga='Germany | Club Friendlies', gosp='D0', gosc='Z0', pg=1, pa=0, dogrywka=0)]
    # zmiana NAZWY ligi: cala liga przechodzi razem
    L = [f'L{i}' for i in range(6)]
    w += _mecze('Latvia | LHL', L, '2025-09-10', 20) + _mecze('Latvia | Optibet', L, '2026-09-15', 4)
    return pd.DataFrame(w)


def test_awans_i_spadek_wykryte():
    d = _baza()
    assert sporty.zmiana_ligi(d, 'hokej', 'Krefeld') == ('Germany | DEL2', 'Germany | DEL', 4)
    assert sporty.zmiana_ligi(d, 'hokej', 'Dresden') == ('Germany | DEL', 'Germany | DEL2', 4)
    assert sporty.zmiana_ligi(d, 'hokej', 'D1') is None and sporty.zmiana_ligi(d, 'hokej', 'Z1') is None


def test_zmiana_nazwy_ligi_to_nie_awans_i_prog_meczow():
    d = _baza()
    assert sporty.zmiana_ligi(d, 'hokej', 'L1') is None
    # po ZMIANA_LIGI_MIN meczach w nowej lidze Elo juz sie dostosowalo
    extra = _mecze('Germany | DEL', ['D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'Krefeld'], '2026-10-10', sporty.ZMIANA_LIGI_MIN)
    assert sporty.zmiana_ligi(pd.concat([d, pd.DataFrame(extra)]), 'hokej', 'Krefeld') is None


def test_werdykt():
    p, powody = sporty.werdykt_meczu(True, 0.76, 50, (), [('Krefeld', 'Germany | DEL2', 'Germany | DEL', 4)])
    assert p is None and 'zmiana ligi: Krefeld' in powody[0]
    assert sporty.werdykt_meczu(True, 0.76, 50, ()) == (0.76, [])
    assert sporty.ZMIANA_LIGI_SPORTY == ('hokej',)          # koszykowka/siatkowka: backtest bez efektu
