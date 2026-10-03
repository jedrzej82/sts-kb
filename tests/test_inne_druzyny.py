"""03.10.2026 („nic nie moze sie gubic”): rozgrywki kobiet/mlodziezy/rezerw/amatorow i male ligi wchodza do bazy jako OSOBNE
druzyny i ligi, ale ich nogi nie ida na kupon (typuj.LIGA_BEZ_TESTU)."""
import pandas as pd

import typuj
import zewn


def test_znacznik_rozgrywek_i_nazwy():
    assert zewn.znacznik_rozgrywek('Liga Profesional - Reserva') == 'Res.'
    assert zewn.znacznik_rozgrywek("Women's Super League") == '(W)'
    assert zewn.znacznik_rozgrywek('Liga MX U19') == 'U19'
    assert zewn.znacznik_rozgrywek('Torneo Regional Federal Amateur') == ''
    assert zewn.z_znacznikiem('Racing Club Res.', 'Res.') == 'Racing Club Res.'        # juz ma znacznik rezerw
    assert zewn.z_znacznikiem('Atlético de Rafaela (Reserves)', 'Res.') == 'Atlético de Rafaela (Reserves)'
    assert zewn.z_znacznikiem('Hammarby', '(W)') == 'Hammarby (W)'                       # bez znacznika — nie zleje sie z mezczyznami
    assert zewn.z_znacznikiem('Hacken (W)', '(W)') == 'Hacken (W)'
    # rezerwy Argentyny NIE moga trafic do kodu pierwszej ligi (sofa_div mapowal je na ARG)
    assert zewn.sofa_div('Argentina', 'Liga Profesional - Reserva') == 'ARG'
    assert zewn.INNE_DRUZYNY.search('Liga Profesional - Reserva') and not zewn.PUCHAR_WLASCIWY.search('Liga Profesional - Reserva')
    assert zewn.PUCHAR_WLASCIWY.search('Copa Argentina') and zewn.MIN_MECZOW_LIGI == 10


def test_liga_bez_testu():
    m = pd.DataFrame({'Division': ['POL'] * 70 + ['Poland | III Liga - Group I'] * 15 + ['Argentina | Liga Profesional - Reserva'] * 800})
    assert typuj.liga_bez_testu(m, {'POL'}) is None
    assert 'za malo historii' in typuj.liga_bez_testu(m, {'POL', 'Poland | III Liga - Group I'})
    assert 'bez testu wstecznego' in typuj.liga_bez_testu(m, {'Argentina | Liga Profesional - Reserva'})
    stare = typuj.LIGA_BEZ_TESTU
    try:
        typuj.LIGA_BEZ_TESTU = 'liga X'
        assert typuj.werdykt_nogi('1X', {'1X': 0.8}) == (None, 'LIGA BEZ TESTU — liga X')
        typuj.LIGA_BEZ_TESTU = None
        assert typuj.werdykt_nogi('1X', {'1X': 0.8}) == (0.8, None)
    finally:
        typuj.LIGA_BEZ_TESTU = stare


def test_formy_prawne_nie_blokuja():
    # 03.10: po dolaczeniu malych lig „Young Boys Reutlingen” (2 mecze) blokowal „BSC Young Boys” -> Young Boys
    assert typuj.resolve('BSC Young Boys', {'Young Boys', 'Young Boys Reutlingen'}) == 'Young Boys'


def _fs(tmp_path, monkeypatch, s365, fs):
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    kol = ['data', 'sport', 'kraj', 'turniej', 'runda', 'gosp', 'gosc', 'wg', 'wa', 'okresy_g', 'okresy_a', 'zwyciezca', 'nawierzchnia']
    d = lambda r: dict(zip(kol, list(r) + [''] * (len(kol) - len(r))))
    pd.DataFrame([d(r) for r in fs], columns=kol).to_csv(tmp_path / 'wyniki_fs_pilka_2026-09.csv.gz', index=False)
    s = pd.DataFrame([d(r) for r in s365], columns=kol).astype(str)
    return zewn._pilka_fs(s).iloc[len(s):]


def test_fs_kobiety_rezerwy_wchodza_bez_dubli(tmp_path, monkeypatch):
    # 03.10: FS odrzucal WSZYSTKIE mecze kobiet/mlodziezy/rezerw (ok. 2000 z 8300), a regex lapal tez „Serie B”/„Group B”
    s365 = [('2026-09-20', 'football', 'England', "Women's Super League", '', 'Arsenal', 'Chelsea', '2', '1')]
    fs = [('2026-09-20', 'football', 'ENGLAND', 'WSL', '', 'Arsenal W', 'Chelsea W', '2', '1'),             # dubel z 365
          ('2026-09-20', 'football', 'ENGLAND', 'WSL 2', '', 'Durham W', 'Sunderland W', '0', '0'),         # nowy
          ('2026-09-20', 'football', 'BRAZIL', 'Serie B', '', 'Goias', 'Coritiba', '1', '1'),               # „B” w lidze seniorow
          ('2026-09-20', 'football', 'SPAIN', 'Primera RFEF - Group 1', '', 'Real Madrid B', 'Lugo', '1', '0'),
          ('2026-09-20', 'football', 'WORLD', 'Club Friendly', '', 'Ajax', 'PSV', '3', '3')]                # sparing — odpada
    out = _fs(tmp_path, monkeypatch, s365, fs)
    pary = set(zip(out.gosp, out.gosc))
    assert pary == {('Durham W', 'Sunderland W'), ('Goias', 'Coritiba'), ('Real Madrid B', 'Lugo')}


def test_fs_dubel_po_wyniku(tmp_path, monkeypatch):
    # 03.10, dane 23.09: Liga Alef (FS) = Division 3 (365) — inne zapisy nazw, ten sam kraj, dzien i wynik
    s365 = [('2026-09-23', 'football', 'Israel', 'Division 3', '', 'SC Tzeirei Tamra', "Hapoel Beit She'an Mesilot", '1', '0')]
    fs = [('2026-09-23', 'football', 'ISRAEL', 'Liga Alef North', '', 'Tzeirey Tamra', 'Beit Shean', '1', '0'),
          ('2026-09-23', 'football', 'ISRAEL', 'Liga Alef North', '', 'Tzeirey Tamra', 'Beit Shean', '2', '0')]   # inny wynik
    out = _fs(tmp_path, monkeypatch, s365, fs)
    assert list(zip(out.wg, out.wa)) == [('2', '0')]
    assert zewn._podobna_druzyna('Hapoel Herzliya', 'Hapoel Hertzliya') and not zewn._podobna_druzyna('Hapoel Azor', 'Maccabi Haifa')


def test_skrot_innego_klubu_i_egzonim():
    # 03.10: po dolaczeniu Prazsky prebor „Dukla Praga” trafiala w „Praga”; „Wisła II Płock” w „Wisla II” (rezerwy Wisly Krakow)
    pula = {'Dukla Prague', 'Praga', 'Wisla Plock', 'Wisla Krakow', 'Wisla II', 'Firpo', 'CD Luis Angel Firpo (W)'}
    assert (typuj.resolve('Dukla Praga', pula) or typuj._przez_egzonim('Dukla Praga', pula)) == 'Dukla Prague'
    assert typuj.resolve('Wisła II Płock', pula) is None
    assert typuj.resolve('Luis Angel Firpo', pula) == 'Firpo'           # wariant kobiet nie blokuje klubu mezczyzn


def test_liga_kobiet_bez_slowa_w_nazwie():
    m = pd.DataFrame({'Division': ['Japan | WE League'] * 80 + ['Spain | Primera RFEF - Group 1'] * 80,
                      'HomeTeam': ['Urawa W'] * 80 + ['Real Madrid B'] * 10 + ['Lugo'] * 70})
    assert 'kobiet' in typuj.liga_bez_testu(m, {'Japan | WE League'})
    assert typuj.liga_bez_testu(m, {'Spain | Primera RFEF - Group 1'}) is None       # rezerwy w lidze seniorow — liga zwykla
