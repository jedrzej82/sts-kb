"""07.10.2026 (paczka wieczorna): tozsamosc klubow — rezerwy, TP-47/TPV, zmiany zapisu Serie D, Atletico Mineiro.

Zmierzone w uzupelnij_ligi.canon() na danych 07.10 18:00 (przed -> po):
  - „Atlantis FC” -> „Atlantis 2” (pierwsza druzyna sklejona z rezerwami, Kakkonen) — znika;
  - „Atlético Mineiro” (Campeonato Mineiro) -> „Atletico-MG” — dochodzi;
  - „Terrassa FC” -> „Terrassa” w „Spain | Segunda RFEF ” (spacja na koncu nazwy ligi z 365) — dochodzi;
  - „K. Beerschot V.A.”/„Beerschot VA” i „Inverness CT”/„Inverness C” — dalej sklejone (inicjaly to nie znaczniki).
"""
import pandas as pd

import build_kb
import kluby
import uzupelnij_ligi as u
import zewn


# --- rezerwy nigdy nie trafiaja automatem w pierwsza druzyne -------------------------------------------------------
def test_rezerwy_nie_trafiaja_w_pierwsza_druzyne():
    assert u.match_one('San Sebastian Reyes B', ['San Sebastian Reyes', 'Numancia'], 'Spain | Segunda RFEF ') is None
    assert u.match_one('San Sebastian Reyes B', ['San Sebastian De Los Reyes'], 'Spain | Tercera RFEF - Group 7') is None
    assert u.match_one('San Sebastian Reyes', ['San Sebastian Reyes B'], 'X') is None
    assert u.match_one('Atlantis FC', ['Atlantis 2', 'HPS'], 'Finland | Kakkonen') is None   # norm(): oba „atlantis”
    assert u.match_one('Valladolid B', ['Valladolid'], 'X') is None
    assert u.match_one('Jong Ajax', ['Ajax'], 'X') is None


def test_ta_sama_druzyna_dalej_sie_dopasowuje():
    assert u.match_one('Celta Vigo B', ['Celta B', 'Celta Vigo'], 'X') == 'Celta B'
    assert u.match_one('Shamrock', ['Shamrock Rovers', 'Bohemians'], 'X') == 'Shamrock Rovers'
    # inicjal / skrot czlonu to nie znacznik rezerw/kobiet/zespolu C
    assert u.match_one('K. Beerschot V.A.', ['Beerschot VA'], 'B1') == 'Beerschot VA'
    assert u.match_one('Inverness CT', ['Inverness C'], 'SC1') == 'Inverness C'


def test_canon_nie_skleja_rezerw_z_historia_pierwszej_druzyny():
    kb = pd.DataFrame(dict(Division=['Spain | Segunda RFEF '] * 2, MatchDate=pd.to_datetime(['2025-09-06', '2025-09-14']),
                           HomeTeam=['San Sebastian Reyes', 'Fuenlabrada'], AwayTeam=['RSD Alcala', 'San Sebastian Reyes']))
    df = pd.DataFrame(dict(Division=['Spain | Segunda RFEF '], MatchDate=pd.to_datetime(['2026-10-04']),
                           HomeTeam=['San Sebastian Reyes B'], AwayTeam=['Real Aranjuez'], FTHome=[3], FTAway=[5], src=['sofa']))
    out, mapping = u.canon(df, kb)
    assert out.HomeTeam.iloc[0] == 'San Sebastian Reyes B'


# --- TP-47 (Tornio) i TPV (Tampere) ---------------------------------------------------------------------------------
def test_tp47_to_nie_tpv():
    # norm() zdejmuje cyfry: „tp” ~ „tpv” (0,8) — teraz rozne liczby w nazwach blokuja dopasowanie po podobienstwie
    assert u.match_one('TP-47', ['TPV', 'JJK'], 'Finland | Ykkonen') is None
    assert u.match_one('TP-47', ['TPV', 'TP-47 Tornio'], 'Finland | Kakkonen') == 'TP-47 Tornio'
    for div in ('Finland | Kakkonen', 'Finland | Ykkonen'):
        assert kluby.zakazane(div, 'TP-47', 'TPV') and kluby.zakazane(div, 'TPV', 'TP-47 Tornio')
    assert kluby.zakazane('Spain | Segunda RFEF', 'San Sebastian Reyes B', 'San Sebastian Reyes')


def test_nie_sklejaj_dziala_tez_dla_ligi_ze_spacja_na_koncu():
    # 365scores: „Segunda RFEF ” — canon() dostaje Division ze spacja; wpis UD Ourense/Ourense CF dotad nie dzialal
    assert kluby.zakazane('Spain | Segunda RFEF ', 'UD Ourense', 'Ourense CF')
    assert u.match_one('Terrassa FC', ['Terrassa', 'Europa'], 'Spain | Segunda RFEF ') == 'Terrassa'


# --- Serie D 2026/27 (FS) pod nowym zapisem: mecze nie odpadaja, wchodza pod nazwa z historii -----------------------
def test_scal_recznie_serie_d_i_mineiro():
    for nowy, stary in [('Siracusa', 'US Siracusa'), ('Sanremese', 'Sanremo'), ('USD Casatese', 'Casatese Merate'),
                        ('USD Ragusa', 'Asd Ragusa Calcio'), ('Union Clodiense', 'ASD Clodiense'),
                        ('Ciserano-Bergamo', 'Virtus Bergamo')]:
        assert kluby.SCAL_RECZNIE[('Italy | Serie D', nowy)] == stary
    assert kluby.SCAL_RECZNIE[('Brazil | Mineiro', 'Atlético Mineiro')] == 'Atletico-MG'


def _mecz(d, kraj, t, a, b, wg='1', wa='0'):
    return dict(data=f'{d} 15:00', sport='football', kraj=kraj, turniej=t, gosp=a, gosc=b, wg=wg, wa=wa)


def test_zewn_fs_nowy_zapis_klubu_trafia_w_nazwe_z_365(monkeypatch):
    s = pd.DataFrame([_mecz('2025-10-04', 'Italy', 'Serie D', 'Luparense', 'ASD Clodiense'),
                      _mecz('2025-10-12', 'Italy', 'Serie D', 'Treviso', 'Este'),
                      _mecz('2025-10-19', 'Italy', 'Serie D', 'Adriese', 'Portogruaro')])
    fs = pd.DataFrame([_mecz('2026-09-27', 'ITALY', 'Serie D - Group C', 'Luparense', 'Union Clodiense', '3', '0'),
                       _mecz('2026-09-28', 'ITALY', 'Serie D - Group C', 'Treviso', 'Adriese', '2', '2'),
                       _mecz('2026-09-29', 'ITALY', 'Serie D - Group C', 'Este', 'Portogruaro', '0', '1')])
    monkeypatch.setattr(zewn, 'czytaj', lambda wzor, bez=None: fs if 'pilka' in wzor else pd.DataFrame())
    out = zewn._pilka_fs(s)
    nowe = out[out.data >= '2026-09']
    assert len(nowe) == 3 and set(nowe.turniej) == {'Serie D'}
    assert 'ASD Clodiense' in set(nowe.gosc) and 'Union Clodiense' not in set(nowe.gosc)


def test_zewn_cyfra_to_znacznik_rezerw():
    assert zewn._znaczniki_fs('Atlantis 2') != zewn._znaczniki_fs('Atlantis')
    assert zewn._znaczniki_fs('Inter Turku 2') == zewn._znaczniki_fs('Fc Inter Turku 2')


def test_build_kb_atletico_mineiro_ze_stanowki_to_atletico_mg(monkeypatch):
    monkeypatch.setitem(build_kb._ELO_CACHE, 'e', {})
    w = [('BRA', '2026-04-01', 'Atletico-MG', 'Cruzeiro', 1, 0),
         ('BRA', '2026-09-20', 'Flamengo', 'Atletico-MG', 2, 2),
         ('Brazil | Mineiro', '2026-01-11', 'Atlético Mineiro', 'Tombense', 2, 0),
         ('Brazil | Mineiro', '2026-03-08', 'Cruzeiro', 'Atlético Mineiro', 0, 1)]
    out = build_kb.scal_zapis_nazw(pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway']))
    druz = set(out.HomeTeam) | set(out.AwayTeam)
    assert 'Atlético Mineiro' not in druz
    assert ((out.HomeTeam == 'Atletico-MG') | (out.AwayTeam == 'Atletico-MG')).sum() == 4
