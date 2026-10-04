"""Paczka 04.10.2026 — usterki z Raportow 15:00 i 18:00. Kazdy test to przypadek z prawdziwego przebiegu
(wejscie, wynik przed poprawka, oczekiwany wynik — w komentarzu)."""
import pandas as pd

import kursy3
import rynek
import sezon
import sporty
import typuj


# ---------- sezon.py: przedrostki klubow tylko z kotwica ligowa (Raport 18:00 usterka 1, 15:00 usterka 2) ----------
ARKUSZ = [
    {'druzyna': 'Huracan', 'liga': 'Liga Profesional ARG', 'mecze': '28'},
    {'druzyna': 'Aldosivi', 'liga': 'Liga Profesional ARG', 'mecze': '26'},
    {'druzyna': 'Mallorca', 'liga': 'LaLiga 2', 'mecze': '7'},
    {'druzyna': 'Girona', 'liga': 'LaLiga 2', 'mecze': '7'},
    {'druzyna': 'Castellon', 'liga': 'LaLiga 2', 'mecze': '7'},
    {'druzyna': 'AD Ceuta FC', 'liga': 'LaLiga 2', 'mecze': '7'},
    {'druzyna': 'CS San Lorenzo', 'liga': 'Primera PAR', 'mecze': '35'},
    {'druzyna': 'Olimpia', 'liga': 'Primera PAR', 'mecze': '35'},
]


def _para(a, b):
    p = sezon.para_po_lidze(ARKUSZ, a, b)
    return p and (p[0]['druzyna'], p[1]['druzyna'])


def test_sezon_przedrostki_z_kotwica_ligowa():
    # przed: NIE ZNALEZIONO „CA Huracan” / „RCD Mallorca” / „CD Castellon”
    assert _para('CA Huracan', 'CA Aldosivi') == ('Huracan', 'Aldosivi')
    assert _para('Girona FC', 'RCD Mallorca') == ('Girona', 'Mallorca')
    assert _para('CD Castellon', 'AD Ceuta') == ('Castellon', 'AD Ceuta FC')


def test_sezon_przedrostek_bez_wspolnej_ligi_nie_zgaduje():
    # „San Lorenzo” (ARG) z oferty nie moze trafic w „CS San Lorenzo” (PAR) tylko dlatego, ze CS odpada
    assert _para('CA Huracan', 'Girona FC') is None
    assert _para('San Lorenzo', 'Huracan') is None
    assert sezon.znajdz(ARKUSZ, 'CA Huracan')[0] is None          # sama nazwa, bez rywala — jak dotad nic


# ---------- typuj.py: skrot trafiony w inny klub, terminarz wskazuje wlasciwy (Raport 18:00 usterka 2) ----------
def _m(w):
    return pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam']).assign(
        MatchDate=lambda x: pd.to_datetime(x.MatchDate))


def test_chacarita_terminarz_rozstrzyga_skrot():
    # przed: "CA Chacarita Juniors" -> „CA Chacarita Juniors (Aimogasta)” (amatorzy) -> NIEPEWNE DOPASOWANIE, noga MNIEJ
    m = _m([('Argentina | Primera Nacional', '2026-09-20', 'Chacarita Juniors', 'Patronato'),
            ('Argentina | Torneo Regional Federal Amateur', '2025-11-24', 'CA Chacarita Juniors (Aimogasta)', 'Andino')])
    pool = {'Chacarita Juniors', 'Patronato', 'CA Chacarita Juniors (Aimogasta)', 'Andino'}
    mt = {'gosp': 'Chacarita Juniors', 'gosc': 'Patronato', 'kraj': 'ARGENTINA', 'turniej': 'Primera Nacional'}
    wyn = typuj.skrot_z_terminarza('CA Chacarita Juniors', 'CA Chacarita Juniors (Aimogasta)', 'Patronato',
                                   [('CA Chacarita Juniors', 'CA Chacarita Juniors (Aimogasta)')], mt, pool, m)
    assert wyn == ('Chacarita Juniors', 'Patronato')


def test_terminarz_bez_wspolnej_ligi_nie_zmienia_klubu():
    m = _m([('ARG2', '2026-09-20', 'Chacarita Juniors', 'X'), ('ARG3', '2026-09-20', 'Patronato', 'Y')])
    pool = {'Chacarita Juniors', 'Patronato', 'CA Chacarita Juniors (Aimogasta)', 'X', 'Y'}
    mt = {'gosp': 'Chacarita Juniors', 'gosc': 'Patronato', 'kraj': 'ARGENTINA', 'turniej': 'Primera Nacional'}
    assert typuj.skrot_z_terminarza('CA Chacarita Juniors', 'CA Chacarita Juniors (Aimogasta)', 'Patronato',
                                    [('CA Chacarita Juniors', 'CA Chacarita Juniors (Aimogasta)')], mt, pool, m) is None


def test_cerrito_jeden_klub_dwie_nazwy():
    # przed: „CS Cerrito” -> stary zapis „Cerrito” (URU do 2022), a mecze 2025/26 pod „Club Sportivo Cerrito”
    import kluby
    assert kluby.SCAL_RECZNIE[('Uruguay | Segunda Division', 'Club Sportivo Cerrito')] == 'Cerrito'


# ---------- typuj.py --intl: polskie nazwy reprezentacji (Raport 18:00 usterka 3) ----------
INTL = {'Bahamas', 'Turks and Caicos Islands', 'Saint Vincent and the Grenadines', 'Solomon Islands', 'Timor-Leste',
        'Aruba', 'Haiti'}


def test_reprezentacje_concacaf_po_polsku():
    # przed: NIE ZNALEZIONO reprezentacji 'Bahamy' / 'Turks i Caicos' (Liga Narodow CONCACAF 04.10)
    assert typuj.resolve('Bahamy', INTL) == 'Bahamas'
    assert typuj.resolve('Turks i Caicos', INTL) == 'Turks and Caicos Islands'
    assert typuj.resolve('Saint Vincent i Grenadyny', INTL) == 'Saint Vincent and the Grenadines'
    assert typuj.resolve('Wyspy Salomona', INTL) == 'Solomon Islands'
    assert typuj.resolve('Aruba', INTL) == 'Aruba'                 # ta sama nazwa po polsku — bez wpisu


# ---------- sporty.py reczna: aliasy jako dane (Raport 18:00 usterka 4) ----------
def test_reczna_islandia_aliasy():
    # przed: "UMF Stjarnan" -> ODRZUCONO (gubi czlon), "HK Kopavogs" -> BRAK W BAZIE
    pula = {'Kopavogur', 'Stjarnan', 'Fram', 'IBV Vestmannaeyjar'}
    assert sporty.resolve('HK Kopavogs', pula, 'piłka ręczna') == 'Kopavogur'
    assert sporty.resolve('UMF Stjarnan', pula, 'piłka ręczna') == 'Stjarnan'


# ---------- kursy3.py: Z1/Z2 i rynki druzyn (Raport 15:00 usterka 6, 18:00 usterka 5) ----------
def test_kod_ako_zwyciezca_meczu():
    assert kursy3.kod_ako('Z1', 'hokej') == 'Zwyciezca 1'
    assert kursy3.kod_ako('Z2', 'koszykowka') == 'Zwyciezca 2'
    assert kursy3.kod_ako('1', 'hokej') == '1'                    # 1/X/2 w hokeju zostaje czasem regulaminowym


def test_kursy_innych_bukmacherow_dla_z1_i_gola_druzyny():
    sts = pd.DataFrame([
        dict(sport='HOKEJ NA LODZIE', data_meczu='2026-10-04', godzina_meczu='18:30', gospodarz='Dynamo Pardubice',
             gosc='Sparta Praga', rynek='Zwycięzca meczu|1', kurs='1.52', linia=''),
        dict(sport='PIŁKA NOŻNA', data_meczu='2026-10-04', godzina_meczu='20:45', gospodarz='Portugalia',
             gosc='Norwegia', rynek='1. drużyna - strzeli gola|TAK', kurs='1.09', linia=''),
        dict(sport='PIŁKA NOŻNA', data_meczu='2026-10-04', godzina_meczu='20:45', gospodarz='Portugalia',
             gosc='Norwegia', rynek='Zakład bez remisu|1', kurs='1.33', linia='')])
    buk = pd.DataFrame([
        dict(bukmacher='SUPERBET', sport='HOKEJ NA LODZIE', data_meczu='2026-10-04', godzina_meczu='18:30',
             gospodarz='Dynamo Pardubice', gosc='Sparta Praga', rynek='Zwyciezca 1', kurs=1.49),
        dict(bukmacher='SUPERBET', sport='PIŁKA NOŻNA', data_meczu='2026-10-04', godzina_meczu='20:45',
             gospodarz='Portugalia', gosc='Norwegia', rynek='gosp_O0.5', kurs=1.07),
        dict(bukmacher='SUPERBET', sport='PIŁKA NOŻNA', data_meczu='2026-10-04', godzina_meczu='20:45',
             gospodarz='Portugalia', gosc='Norwegia', rynek='DNB_1', kurs=1.30)])
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    out, _ = kursy3.kupon(tab, [('Dynamo Pardubice - Sparta Praga', 'Z1', '1.52', 'hokej'),
                                ('Portugalia - Norwegia', 'gosp_O0.5', '1.09', 'pilka'),
                                ('Portugalia - Norwegia', 'DNB_1', '1.33', 'pilka')])
    # przed: tylko STS („SUPERBET nan | LVBET nan”)
    assert [w.get('SUPERBET') for _, _, w in out] == [1.49, 1.07, 1.30]


# ---------- rynek.py: filtr 6.4 bez kursu dopelnienia (Raport 18:00 usterka 7) ----------
def test_filtr_dziala_bez_kursu_dopelnienia():
    # Portugalia – Norwegia U3.5 @1.82, P 69.4%: z O3.5 odrzucona (+17.3 pp), bez O3.5 bylo ✔ EV +11.2%
    kursy = {'1': 1.70, 'X': 4.40, '2': 4.50, 'U3.5': 1.82}
    assert rynek.p_rynku('U3.5', kursy) is None
    pow_ = rynek.filtr_model_rynek('U3.5', 0.694, kursy)
    assert pow_ and 'rynku glownego' in pow_
    assert rynek.filtr_model_rynek('U3.5', 0.55, kursy) is None        # zgodne z rynkiem — przechodzi
    assert rynek.filtr_model_rynek('U3.5', 0.694, {'U3.5': 1.82}) is None   # brak czegokolwiek — bez filtra, jak dotad
    # pelna para O/U dalej ma pierwszenstwo przed szacunkiem z 1X2
    assert 'po zdjeciu marzy —' in rynek.filtr_model_rynek('U3.5', 0.694, dict(kursy, **{'O3.5': 1.98}))


# ---------- zdarzenia.py / dopasuj.py: sporty osobowe graja kilka meczow dziennie (Raport 15:00 usterka 7) ----------
def test_setka_rozegrany_mecz_z_kims_innym_to_nie_konflikt():
    # przed: CONFLICT [RYWAL_INNY:Melnyk Valerii~Reznychenko Roman] dla Melnyk – Pysmennyi (oba mecze tego samego dnia)
    import zdarzenia
    d = pd.Timestamp('2026-10-04')
    ev = pd.DataFrame([dict(S='tenis stołowy', d=d, t=pd.Timestamp('2026-10-04 15:40'), dni=frozenset({d}),
                            A='Melnyk Valerii', B='Pysmennyi Yevhen')])
    z = pd.DataFrame([dict(S='tenis stołowy', d=d, t=pd.Timestamp('2026-10-04 11:00'), gosp='Melnyk Valerii',
                           gosc='Reznychenko Roman', zrodlo='wyniki_setka_inne_2026-10')])
    pula = {'tenis stołowy': {'Melnyk Valerii', 'Pysmennyi Yevhen', 'Reznychenko Roman'}}
    ligi = {('tenis stołowy', n): {'UKRAINE | Setka Cup'} for n in pula['tenis stołowy']}
    k = zdarzenia.klasyfikuj(ev, z, lambda S, n: None, pula, ligi, set())
    assert k.stan.tolist() == ['MATCH'] and 'RYWAL_INNY' not in k.dowody[0]
    # w pilce ta sama sytuacja dalej jest konfliktem (jeden mecz dziennie)
    k2 = zdarzenia.klasyfikuj(ev.assign(S='pilka'), z.assign(S='pilka'), lambda S, n: None,
                              {'pilka': pula['tenis stołowy']}, {}, set())
    assert k2.stan.tolist() == ['CONFLICT']


def test_setka_brak_kotwicy_w_nauce_aliasow():
    # przed: „KONFLIKT z resolverem: Cherevko Roman -> kod Cherevko Roman, zrodlo Pysmennyi Yevhen” (Dukhovenko zagral
    # wczesniej z Pysmennym, mecz z oferty z Cherevko jeszcze sie nie odbyl)
    import dopasuj
    k = pd.DataFrame([('TENIS STOŁOWY', '2026-10-04', '15:40', 'Dukhovenko Oleksandr', 'Cherevko Roman')],
                     columns=['sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc'])
    ev = dopasuj.zdarzenia_sts(k)
    z = pd.DataFrame([(ev.S.iloc[0], pd.Timestamp('2026-10-04'), pd.NaT, 'Dukhovenko Oleksandr', 'Pysmennyi Yevhen', 'setka')],
                     columns=['S', 'd', 't', 'gosp', 'gosc', 'zrodlo'])
    pula = {ev.S.iloc[0]: {'Dukhovenko Oleksandr', 'Pysmennyi Yevhen', 'Cherevko Roman'}}
    a, kon, _ = dopasuj.ucz(ev, z, lambda S, n: n if n in pula[S] else None, pula)
    assert a.empty and kon.empty


# ---------- oferta.py: kurs 1.00 = rynek wstrzymany (Raport 15:00 usterka 8) ----------
def test_kurs_jeden_to_rynek_wstrzymany():
    import oferta
    d = pd.DataFrame([dict(zdarzenie='Unia Oświęcim - Podhale Nowy Targ', rynek=r, kurs=k)
                      for r, k in (('1', '1.00'), ('X', '15.00'), ('2', '150.00'), ('U9.5', '1.85'))])
    ostrz = []
    out = oferta.bez_wstrzymanych(d, ostrz)
    assert out.rynek.tolist() == ['X', '2', 'U9.5'] and len(ostrz) == 1 and 'wstrzymany' in ostrz[0]


def test_aliasy_koszykowki_z_raportu_1500():
    pula = {'Wbc Raiffeisen Wels', 'Post Südstadt Karlsruhe', 'USC Heidelberg', 'Orangeacademy', 'Traiskirchen'}
    assert sporty.resolve('Flyers Wels', pula, 'koszykówka') == 'Wbc Raiffeisen Wels'
    assert sporty.resolve('PS Karlsruhe Lions', pula, 'koszykówka') == 'Post Südstadt Karlsruhe'
    assert sporty.resolve('MLP Heidelberg', pula, 'koszykówka') == 'USC Heidelberg'
    assert sporty.resolve('Orange Academy', pula, 'koszykówka') == 'Orangeacademy'
