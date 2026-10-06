"""06.10.2026 — kursy3: wiecej par STS <-> Superbet/LVBET (rezerwy „(R)”, tenis z godzina orientacyjna, deble, ZEA)."""
import pandas as pd

import kursy3
import nazwy


def _z(sport, *mecze):
    out = []
    for g, a, h in mecze:
        hh, mm = map(int, h.split(':'))
        out.append(dict(sport=sport, data_meczu='2026-10-06', godzina_meczu=h, gospodarz=g, gosc=a, t=hh * 60 + mm))
    return pd.DataFrame(out)


def test_rezerwy_R_i_Rezerwy():
    assert nazwy.znaczniki('CA River Plate (R)') == ('rezerwy',)
    assert nazwy.znaczniki('CA River Plate BA (Rezerwy)') == ('rezerwy',)
    assert nazwy.znaczniki('Bhosale R') == ()                         # inicjal bez nawiasu to nie rezerwy
    sts = _z('PIŁKA NOŻNA', ('Racing Club Avellaneda II', 'River Plate II', '20:00'))
    for buk in (('Racing Club (R)', 'CA River Plate (R)', '20:00'),
                ('Racing Club Avellaneda (Rezerwy)', 'CA River Plate BA (Rezerwy)', '20:00')):
        wyn, _ = kursy3.dopasuj_mecze(sts, _z('PIŁKA NOŻNA', buk))
        assert len(wyn) == 1
    # pierwsze druzyny o tej godzinie nie sa rezerwami
    wyn, _ = kursy3.dopasuj_mecze(sts, _z('PIŁKA NOŻNA', ('Racing Club', 'CA River Plate', '20:00')))
    assert not wyn


def test_tenis_godzina_orientacyjna_i_deble():
    # LVBET 06.10: „Kraus – Bartunkova” STS 11:40, LVBET 12:00; Superbet: debel z inicjalem „B” (bylo: znacznik rezerw)
    sts = _z('TENIS', ('Kraus Sinja', 'Bartunkova Nikola', '11:40'), ('Kicker N / Zeitune M', 'Arias B / Carou I', '15:00'),
             ('Bhosale R / Micic E', 'Falkowska W / Smith A', '09:00'))
    buk = _z('TENIS', ('Sinja Kraus', 'Nikola Bartunkova', '12:00'), ('N.Kicker/M.Zeitune', 'B.Arias/I.Carou', '15:00'),
             ('R.Bhosale/E.Micic', 'W.Falkowska/A.Smith', '14:00'))
    wyn, st = kursy3.dopasuj_mecze(sts, buk)
    assert st['jednoznaczne'] == 3


def test_tenis_bez_zgadywania():
    sts = _z('TENIS', ('Ivanov Mihail', 'Vasilev Alexander', '11:30'))
    # singiel nie paruje sie z deblem tych samych zawodnikow; dwa mecze tej pary w oknie = nie zgadujemy
    assert not kursy3.dopasuj_mecze(sts, _z('TENIS', ('M.Ivanov/X.Y', 'A.Vasilev/Z.W', '12:00')))[0]
    _, st = kursy3.dopasuj_mecze(sts, _z('TENIS', ('Mihail Ivanov', 'Alexander Vasilev', '11:37'),
                                         ('Mihail Ivanovic', 'Alexander Vasilevski', '18:00')))
    assert st['kilka'] == 1
    # tylko jedno nazwisko sie zgadza — to inny mecz
    assert not kursy3.dopasuj_mecze(sts, _z('TENIS', ('Mihail Ivanov', 'Jan Kowalski', '11:37')))[0]


def test_zea():
    wyn, _ = kursy3.dopasuj_mecze(_z('PIŁKA NOŻNA', ('Arabia Saudyjska', 'Zjednoczone Emiraty Arabskie', '20:00')),
                                  _z('PIŁKA NOŻNA', ('Arabia Saudyjska', 'ZEA', '20:00')))
    assert len(wyn) == 1
