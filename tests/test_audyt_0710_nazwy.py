"""07.10.2026 — audyt usterek ze wszystkich raportow: otwarte dopasowania nazw (sprawdzone na bazie z 06.10)."""
import contextlib
import io

import pandas as pd

import build_kb
import sporty
import typuj


def _scal(w, monkeypatch):
    monkeypatch.setattr(build_kb, '_elo_nazwy', lambda: {})
    m = pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'])
    out = build_kb.scal_zapis_nazw(m)
    return out[0] if isinstance(out, tuple) else out


def test_leczna_i_mes_kerman_jeden_wpis(monkeypatch):
    # Raport 04.10 15:00 nr 4 (Gornik Leczna: POL2 do 05.2026, II liga 2026/27 jako „Leczna”), 05.10 12:00 nr 1 (Mes Kerman)
    out = _scal([('POL2', '2026-05-24', 'LKS Lodz', 'Gornik Leczna', 1, 0),
                 ('Poland | Division 2', '2026-10-04', 'Leczna', 'Chojniczanka', 2, 1),
                 ('IRN', '2023-05-18', 'Sanat Mes Kerman', 'Esteghlal', 0, 2),
                 ('Iran | Azadegan League', '2026-09-28', 'Mes Kerman', 'Shahrdari', 1, 1)], monkeypatch)
    n = set(out.HomeTeam) | set(out.AwayTeam)
    assert 'Leczna' not in n and 'Gornik Leczna' in n
    assert 'Sanat Mes Kerman' not in n and 'Mes Kerman' in n


def _r(nazwa, pula):
    with contextlib.redirect_stdout(io.StringIO()):
        return typuj.resolve(nazwa, pula)


def test_aliasy_z_audytu():
    pula = {'Salisbury', 'Salisbury City', 'Algeciras', 'Algeciras CF', 'Maccabi Kiryat Gat', 'Beitar Ironi Kiryat Gat',
            'MS Kfar Kassem', 'Hapoel Kfar Kassem'}
    assert _r('Salisbury FC', pula) == 'Salisbury City'
    assert _r('CF Algeciras', pula) == 'Algeciras CF'
    assert _r('Maccabi Ironi Kiryat Gat', pula) == 'Maccabi Kiryat Gat'
    assert _r('MS Kafr Qasim', pula) == 'MS Kfar Kassem'
    with contextlib.redirect_stdout(io.StringIO()):
        assert sporty.resolve('Bnei Herzliya', {'Bnei Hertzliya', 'Maccabi Ironi Raanana'}, 'koszykówka') == 'Bnei Hertzliya'


def test_rezerwy_ii_jak_res():
    # Raporty 23.09 19:06 U2 i 21:00 nr 3: „CA Banfield II”, „Atletico Lanus II” -> None, choc w bazie „Banfield Res.”, „Lanus Res.”
    pula = {'Banfield', 'Banfield Res.', 'Banfield (W)', 'Lanus', 'Lanus Res.', 'Gimnasia La Plata Res.', 'Gimnasia Mendoza Res.'}
    assert _r('CA Banfield II', pula) == 'Banfield Res.'
    assert _r('Atletico Lanus II', pula) == 'Lanus Res.'
    assert _r('Gimnasia La Plata II', pula) == 'Gimnasia La Plata Res.'
    assert _r('Gimnasia II', pula) is None                         # dwoch kandydatow — nie zgadujemy
    assert _r('CA Banfield', pula) == 'Banfield'                   # pierwsza druzyna bez zmian


def test_reprezentacje_elo_niezbiezne_blokuje_noge():
    # Raport 23.09 20:00 nr 7: Wlochy (1693, 34 m.) – Finlandia (1707, 25 m.) dostawalo NOGA DOPUSZCZONA
    p, pow_ = sporty.werdykt_meczu(True, 0.54, 25, reprezentacje=True)
    assert p is None and any('reprezentacje' in x for x in pow_)
    assert sporty.werdykt_meczu(True, 0.54, 25)[0] == 0.54                      # kluby jak dotad
    assert sporty.werdykt_meczu(True, 0.54, sporty.REPREZENTACJE_MIN_MECZOW, reprezentacje=True)[0] == 0.54
    assert sporty._kraj('Italy') and sporty._kraj('Finland') and not sporty._kraj('Trefl Gdansk')


def test_pojedynczy_znak_to_inna_druzyna():
    # Raport 01.10 (audyt): „Odense Q” (kobiety, Kvindeligaen) -> „Odense” (mezczyzni, DEN)
    pula = {'Odense', 'Chievo', 'Wisla Plock'}
    assert _r('Odense Q', pula) is None
    assert _r('Chievo Verona', pula) == 'Chievo'                  # czlon wieloliterowy — jak dotad (z ostrzezeniem)
