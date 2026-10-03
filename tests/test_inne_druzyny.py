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
