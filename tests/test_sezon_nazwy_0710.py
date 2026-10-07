"""sezon.py — dopasowanie nazw do arkuszy statystyk (07.10.2026).
Raport 24.09 21:00 nr 1: „Wang Xinyu” (STS) -> NIE ZNALEZIONO, arkusz tenisa ma „Xin-Yu Wang”.
Raport 27.09 21:00 nr 4: „Universidad de Chile” – „Everton” trafialo w Everton z Premier League,
a „Everton Vina del Mar” dawalo NIE ZNALEZIONO (arkusz: „Everton De Vina”, Primera CHI)."""
import sezon

# ---------------------------------------------------------------- tenis: czlony z lacznikiem
TENIS = [{'druzyna': n, 'mecze_ze_statami': '4'} for n in
         ('Xin-Yu Wang', 'Jiaqi Wang', 'Xinyu Gao', 'Pablo Carreno-Busta', 'Jan-Lennard Struff', 'Iga Swiatek')]


def _t(nazwa, arkusz=TENIS):
    w = sezon.znajdz(arkusz, nazwa, sport='tenis')[0]
    return w and w['druzyna']


def test_tenis_lacznik_sklejony_w_zapisie_sts():
    # przed: None (NIE ZNALEZIONO) — „xin yu” != „xinyu”
    assert _t('Wang Xinyu') == 'Xin-Yu Wang'
    assert _t('Xinyu Wang') == 'Xin-Yu Wang'
    assert _t('CarrenoBusta Pablo') == 'Pablo Carreno-Busta'
    # skrot STS: jedno imie z lacznikiem = jeden inicjal
    assert _t('Wang X.') == 'Xin-Yu Wang'
    assert _t('Struff J.') == 'Jan-Lennard Struff'


def test_tenis_lacznik_dotychczasowe_zapisy_bez_zmian():
    assert _t('Wang Xin-Yu') == 'Xin-Yu Wang'
    assert _t('Swiatek Iga') == 'Iga Swiatek'
    assert _t('Gao Xinyu') == 'Xinyu Gao'


def test_tenis_lacznik_nie_daje_falszywych_dopasowan():
    assert _t('Wang Xiyu') is None                 # inna zawodniczka (Xiyu Wang) — nie ma jej w arkuszu
    assert _t('Wang J.') == 'Jiaqi Wang'
    assert _t('Wang Yu') is None
    # dwa zapisy po sklejeniu: dokladny zapis wygrywa jak dotad (krok 3), a wariant z lacznikiem i skrot — nie zgaduja
    dwie = TENIS + [{'druzyna': 'Xinyu Wang', 'mecze_ze_statami': '2'}]
    assert _t('Wang Xinyu', dwie) == 'Xinyu Wang'
    assert _t('Wang X.', dwie) is None
    trzy = TENIS + [{'druzyna': 'Xi-Nyu Wang', 'mecze_ze_statami': '2'}]   # oba sklejone daja „xinyu”
    assert _t('Wang Xinyu', trzy) is None


# ---------------------------------------------------------------- pilka: rdzen nazwy + liga rywala
def _r(druzyna, liga, tid, mecze='23'):
    return {'druzyna': druzyna, 'liga': liga, 'team_id': tid, 'mecze': mecze,
            'dom_mecze': '10', 'dom_gz': '15', 'wyj_mecze': '10', 'wyj_gz': '12',
            'gole_na_mecz': '1.4', 'stracone_na_mecz': '1.2'}


PILKA = [
    _r('Universidad de Chile', 'Primera CHI', '8541'), _r('Everton De Vina', 'Primera CHI', '1230'),
    _r("O'Higgins", 'Primera CHI', '1240'), _r('Coquimbo Unido', 'Primera CHI', '1250'),
    _r('Universidad Catolica', 'Primera CHI', '1245'),
    _r('Everton', 'Premier League', '132', '5'), _r('Liverpool', 'Premier League', '108', '5'),
    _r('Liverpool', 'Liga Mistrzow', '108', '1'), _r('Real Madrid', 'Liga Mistrzow', '131', '1'),
    _r('Real Madrid', 'LaLiga', '131', '7'), _r('Racing Santander', 'LaLiga', '9001', '7'),
    _r('Athletic Bilbao', 'LaLiga', '9002', '7'),
    _r('Racing Club', 'Liga Profesional ARG', '9003', '29'), _r('Independiente', 'Liga Profesional ARG', '9004', '28'),
    _r('Universidad Catolica', 'LigaPro ECU', '10197', '32'), _r('Independiente del Valle', 'LigaPro ECU', '9005', '30'),
    _r('Bohemians Praha', 'Czech Liga', '1801', '8'), _r('Sparta Praha', 'Czech Liga', '1802', '8'),
    _r('Bohemians', 'Liga Konferencji', '836', '5'), _r('NK Varazdin', 'Liga Konferencji', '900', '2'),
]


def _pilka(monkeypatch, capsys, a, b, arkusz=PILKA):
    monkeypatch.setattr(sezon, 'wczytaj', lambda sport, plik=None: arkusz)
    try:
        sezon.pilka(a, b)
    except SystemExit as e:
        return 'EXIT ' + str(e)
    return next(l for l in capsys.readouterr().out.splitlines() if l.startswith('SEZON'))


def test_everton_vina_del_mar_wspolny_rdzen_i_miasto(monkeypatch, capsys):
    # przed: NIE ZNALEZIONO: „Everton Vina del Mar”
    p = sezon.para_po_lidze(PILKA, 'Universidad de Chile', 'Everton Vina del Mar')
    assert p and (p[0]['druzyna'], p[1]['druzyna']) == ('Universidad de Chile', 'Everton De Vina')
    assert 'Universidad de Chile – Everton De Vina  (Primera CHI' in \
        _pilka(monkeypatch, capsys, 'Universidad de Chile', 'Everton Vina del Mar')


def test_everton_z_ligi_gospodarza_zamiast_premier_league(monkeypatch, capsys):
    # przed: „Everton” z Premier League + UWAGA o roznych ligach
    assert 'Universidad de Chile – Everton De Vina  (Primera CHI' in \
        _pilka(monkeypatch, capsys, 'Universidad de Chile', 'Everton')
    assert "Everton De Vina – O'Higgins  (Primera CHI" in _pilka(monkeypatch, capsys, 'Everton', "O'Higgins")


def test_kilku_kandydatow_w_lidze_gospodarza_brak_dopasowania(monkeypatch, capsys):
    arkusz = PILKA + [_r('Everton Talcahuano', 'Primera CHI', '1260')]
    assert _pilka(monkeypatch, capsys, 'Universidad de Chile', 'Everton', arkusz).startswith('EXIT NIE ZNALEZIONO')


def test_bez_falszywych_dopasowan_po_rdzeniu(monkeypatch, capsys):
    # wspolna liga — nic sie nie zmienia
    assert 'Everton – Liverpool  (Premier League' in _pilka(monkeypatch, capsys, 'Everton', 'Liverpool')
    # „Racing Club” (ARG) to nie „Racing Santander” — mecz miedzyligowy jak dotad
    assert 'Racing Club – Athletic Bilbao  (Liga Profesional ARG' in \
        _pilka(monkeypatch, capsys, 'Racing Club', 'Athletic Bilbao')
    # „Bohemians Praha” (Czechy) to nie „Bohemians” (Dublin): jeden wspolny czlon to za malo
    assert 'Bohemians Praha – NK Varazdin  (Czech Liga' in _pilka(monkeypatch, capsys, 'Bohemians Praha', 'NK Varazdin')
    # rywal niejednoznaczny (dwa kluby „Universidad Catolica”, rozne team_id) nie jest kotwica
    assert 'Independiente – Universidad Catolica  (Liga Profesional ARG' in \
        _pilka(monkeypatch, capsys, 'Independiente', 'Universidad Catolica')
    # sam pierwszy czlon bez trafienia w caly klub — nie zgadujemy
    assert sezon.para_po_lidze(PILKA, 'Sparta', 'Bohemians Praha') is None
    assert sezon.para_po_lidze(PILKA, 'Universidad', 'Coquimbo Unido') is None


def test_rdzen_tylko_z_kotwica_nie_w_znajdz():
    # sam znajdz() bez rywala nie zgaduje — rdzen dziala wylacznie z kotwica ligowa
    assert sezon.znajdz(PILKA, 'Everton Vina del Mar')[0] is None
    assert sezon._rdzen_pasuje('Everton Vina del Mar', 'Everton De Vina')
    assert not sezon._rdzen_pasuje('Everton', 'Everton De Vina')                 # jeden czlon — tylko z kotwica (b)
    assert sezon._rdzen_pasuje('Everton', 'Everton De Vina', min_wspolne=1)
    assert not sezon._rdzen_pasuje('Bohemians Praha', 'Bohemians', min_wspolne=1)
    assert not sezon._rdzen_pasuje('Real Madrid Castilla', 'Real Madrid')
    assert not sezon._rdzen_pasuje('Chelsea (K)', 'Chelsea', min_wspolne=1)
