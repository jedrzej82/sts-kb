"""18.10.2026: wspolny zapis kursu (kursy_rekord.py, TRYB OBSERWACJI) i nowe kolumny pliku z telefonu
(termux/kursy_bukmacherow.py). Dane syntetyczne — prawdziwe kursy tylko na Dysku. Bez sieci: odpowiedzi API podstawione."""
import datetime as dt
import gzip
import os
import sys

import pandas as pd
import pytest

KAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KAT)
sys.path.insert(0, os.path.join(KAT, 'termux'))
import kursy3  # noqa: E402
import kursy_bukmacherow as kb  # noqa: E402
import kursy_rekord as kr  # noqa: E402

UTC = dt.timezone.utc
T = dt.datetime(2026, 10, 18, 18, 0, tzinfo=UTC)
P = 'PIŁKA NOŻNA'


def _ev(g, a, m=0):
    return dict(gospodarz=g, gosc=a, t=T + dt.timedelta(minutes=m))


def _stan(g, a, kandydaci):
    return [(s, p) for _, s, _, p in kr.paruj([_ev(g, a)], [_ev(*k) for k in kandydaci])][0]


# ---------------- adapter Superbet / LVBET (telefon) ----------------

SB_STRUCT = {'data': {'tournaments': [{'id': 77, 'localNames': {'pl-PL': 'Polska - Ekstraklasa'}}, {'id': 78, 'name': 'Liga X'}]}}
SB_LISTA = {'data': [{'eventId': 9001, 'matchName': 'Legia Warszawa·Lech Poznań', 'utcDate': '2026-10-18T16:00:00Z',
                      'sportId': 5, 'tournamentId': 77, 'odds': []},
                     {'eventId': 9002, 'matchName': 'Alfa·Beta', 'utcDate': '2026-10-18T18:30:00Z', 'sportId': 5,
                      'tournamentId': 999, 'odds': []}]}
SB_DETAL = {'data': [{'odds': [{'status': 'active', 'marketName': '1X2', 'name': '1', 'price': 2.1, 'marketId': 1},
                               {'status': 'active', 'marketName': '1X2', 'name': 'X', 'price': 3.4, 'marketId': 1},
                               {'status': 'suspended', 'marketName': '1X2', 'name': '2', 'price': 3.0, 'marketId': 1}]}]}


def _sb_get(struct_ok=True):
    def get(url, naglowki=None, proby=3):
        if url.endswith('/struct'):
            if not struct_ok: raise OSError('503')
            return SB_STRUCT
        if '/events/by-date' in url: return SB_LISTA
        if '/events/' in url: return SB_DETAL
        raise AssertionError(url)
    return get


def test_superbet_zapisuje_id_lige_start_i_czas_pobrania(monkeypatch):
    monkeypatch.setattr(kb, 'get', _sb_get())
    w = []
    kb.superbet(dt.datetime(2026, 10, 18, 10), dt.datetime(2026, 10, 19, 16), w)
    assert len(w) == 4                                                        # 2 mecze x 2 aktywne kursy
    r = w[0]
    assert (r['event_id'], r['liga'], r['start_utc']) == ('9001', 'Polska - Ekstraklasa', '2026-10-18T16:00:00Z')
    assert (r['data_meczu'], r['godzina_meczu']) == ('2026-10-18', '18:00')   # czas polski bez zmian (lato UTC+2)
    assert kr.utc(r['pobrano_utc']) is not None and r['rynek'] == '1'
    assert w[2]['liga'] == ''                                                 # turniej spoza /struct -> pusto, nie zgadujemy


def test_superbet_bez_struct_dalej_pobiera_kursy(monkeypatch, capsys):
    monkeypatch.setattr(kb, 'get', _sb_get(struct_ok=False))
    w = []
    kb.superbet(dt.datetime(2026, 10, 18, 10), dt.datetime(2026, 10, 19, 16), w)
    assert len(w) == 4 and {r['liga'] for r in w} == {''}
    assert 'brak nazw lig' in capsys.readouterr().out


def test_lvbet_id_i_start_utc_ze_strefy(monkeypatch):
    lista = [{'match_id': 'lv1', 'sports_groups_ids': [1], 'state': {'is_pre': True, 'status': 'open'},
              'home': ['Legia Warszawa'], 'away': ['Lech Poznań'], 'date': '2026-10-18T18:00:00+02:00'}]
    rynki = [{'name': '1X2', 'state': {'status': 'open'}, 'line': None,
              'selections': [{'name': '1', 'status': 'open', 'rate': {'decimal': 2.05}}]}]
    monkeypatch.setattr(kb, 'get', lambda url, h=None, proby=3: rynki if '/markets/' in url else lista)
    w = []
    kb.lvbet(dt.datetime(2026, 10, 18, 10), dt.datetime(2026, 10, 19, 16), w)
    assert len(w) == 1 and (w[0]['event_id'], w[0]['start_utc'], w[0]['liga']) == ('lv1', '2026-10-18T16:00:00Z', '')


def test_plik_z_telefonu_ma_nowe_kolumny_na_koncu(monkeypatch, tmp_path):
    monkeypatch.setattr(kb, 'get', _sb_get())
    plik = kb.main(['--bez-lvbet', '--katalog', str(tmp_path)])
    df = pd.read_csv(plik, dtype=str, keep_default_na=False)
    assert list(df.columns[:11]) == kb.KOLUMNY[:11]                          # stary uklad nienaruszony
    assert list(df.columns[11:]) == ['event_id', 'liga', 'start_utc', 'pobrano_utc']


def test_kursy3_czyta_stary_i_nowy_plik_tak_samo():
    stary = pd.DataFrame([dict(bukmacher='SUPERBET', sport=P, data_meczu='2026-10-18', godzina_meczu='18:00',
                               gospodarz='Legia Warszawa', gosc='Lech Poznań', rynek_oryg='1X2', wybor_oryg='1', linia='',
                               rynek='1', kurs='2.10')])
    nowy = stary.assign(event_id='9001', liga='Polska - Ekstraklasa', start_utc='2026-10-18T16:00:00Z',
                        pobrano_utc='2026-10-18T09:30:00Z')
    sts = pd.DataFrame([dict(sport=P, data_meczu='2026-10-18', godzina_meczu='18:00', gospodarz='Legia Warszawa',
                             gosc='Lech Poznań', rynek='1', kurs='2.00')])
    a, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(stary))
    b, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(nowy))
    assert a.SUPERBET.tolist() == b.SUPERBET.tolist() == [2.10]


# ---------------- rekordy i walidacja ----------------

def test_stary_plik_czas_pobrania_z_nazwy_wedlug_strefy():
    df = pd.DataFrame([dict(bukmacher='SUPERBET', sport=P, data_meczu='2026-10-26', godzina_meczu='20:00', gospodarz='A',
                            gosc='B', rynek='1', kurs='2.0')])
    lato = kr.z_telefonu(df.assign(data_meczu='2026-10-18'), 'x/kursy_bukmacherow_2026-10-18_11-30.csv.gz')[0]
    zima = kr.z_telefonu(df, 'kursy_bukmacherow_2026-10-26_11-30.csv.gz')[0]
    assert (lato['pobrano_utc'], lato['start_utc']) == ('2026-10-18T09:30:00Z', '2026-10-18T18:00:00Z')
    assert (zima['pobrano_utc'], zima['start_utc']) == ('2026-10-26T10:30:00Z', '2026-10-26T19:00:00Z')
    assert lato['id_zdarzenia'] == '' and lato['zrodlo'] == 'TELEFON'


def _rek(kurs='2.0', pob='2026-10-18T16:00:00Z', start='2026-10-18T18:00:00Z', g='A', a='B'):
    return dict(bukmacher='SUPERBET', gospodarz=g, gosc=a, rynek='1', kurs=kurs, pobrano_utc=pob, start_utc=start)


@pytest.mark.parametrize('teraz,stan', [('2026-10-18T17:29:00Z', 'OK'), ('2026-10-18T17:31:00Z', 'NIEAKTUALNY')])
def test_wiek_kursu_prog_90_min(teraz, stan):
    assert kr.waliduj(_rek(), kr.utc(teraz))[0] == stan


def test_wiek_ponad_6_h_tylko_papierowo_i_bez_teraz_bez_kontroli():
    s, p = kr.waliduj(_rek(pob='2026-10-18T05:00:00Z', start='2026-10-18T20:00:00Z'), kr.utc('2026-10-18T11:30:00Z'))
    assert s == 'NIEAKTUALNY' and 'tylko papierowo' in p
    assert kr.waliduj(_rek(pob='2026-10-01T05:00:00Z'))[0] == 'OK'
    assert kr.waliduj(_rek(pob='2026-10-18T17:50:00Z'), kr.utc('2026-10-18T18:01:00Z'))[0] == 'NIEAKTUALNY'   # mecz trwa


@pytest.mark.parametrize('rek,stan', [
    (_rek(pob='2026-10-18T18:00:00Z'), 'PO_STARCIE'), (_rek(pob='2026-10-18T18:20:00Z'), 'PO_STARCIE'),
    (_rek(kurs='1.0'), 'BRAK_DANYCH'), (_rek(kurs=''), 'BRAK_DANYCH'), (_rek(kurs='abc'), 'BRAK_DANYCH'),
    (_rek(g=''), 'BRAK_DANYCH'), (_rek(start=''), 'BRAK_DANYCH'), (_rek(pob='wczoraj'), 'BRAK_DANYCH'),
    (_rek(kurs='2,15'), 'OK')])
def test_statusy_walidacji(rek, stan):
    assert kr.waliduj(rek)[0] == stan


# ---------------- dopasowanie zdarzen (zero falszywych par) ----------------

@pytest.mark.parametrize('g,a,kand,stan', [
    ('Legia Warszawa', 'Lech Poznań', [('Legia', 'Lech Poznan')], 'MATCH'),
    ('Real Madrid', 'Inter', [('Real Sociedad', 'Inter Turku')], 'UNKNOWN'),
    ('San Felice Gladiator', 'Real Agro Aversa', [('ASD Santangelo', 'ASD Tropical Coriano')], 'UNKNOWN'),   # 3 litery to nie skrot
    ('Aer Afantou', 'Proodeftiki', [('Casatese Merate', 'Aurora Pro Patria')], 'UNKNOWN'),
    ('Dinamo Moskwa', 'Spartak Moskwa', [('Dinamo Mińsk', 'Spartak Trnava')], 'UNKNOWN'),
    ('Legia Warszawa', 'Lech Poznań', [('Lech Poznań', 'Legia Warszawa')], 'UNKNOWN'),
    ('Barcelona', 'Sevilla', [('Barcelona (Wom)', 'Sevilla (Wom)')], 'UNKNOWN'),
    ('Słowenia U21', 'Holandia U21', [('Austria U21', 'Dania U21'), ('Słowenia U21', 'Holandia U21')], 'MATCH'),
    ('Dinamo', 'Spartak', [('Dinamo Moskwa', 'Spartak Moskwa'), ('Dinamo Mińsk', 'Spartak Mińsk')], 'UNKNOWN'),
    ('Cleethorpes Town', 'Hyde United', [('Alfreton Town', 'United of Manchester')], 'UNKNOWN'),
    ('Polonia Lidzbark W...', 'Stomil', [('Polonia Lidzbark Warminski', 'Stomil')], 'UNKNOWN'),   # nazwa ucieta w PDF
])
def test_paruj(g, a, kand, stan):
    assert _stan(g, a, kand)[0] == stan


def test_paruj_godzina_5_min_tak_6_min_nie():
    x = [_ev('Legia Warszawa', 'Lech Poznań')]
    assert kr.paruj(x, [_ev('Legia Warszawa', 'Lech Poznań', 5)])[0][1] == 'MATCH'
    assert kr.paruj(x, [_ev('Legia Warszawa', 'Lech Poznań', -6)])[0][1] == 'UNKNOWN'


def test_conflict_gdy_mecz_bukmachera_ma_juz_pewna_pare():
    # o 18:00 u bukmachera tylko Legia - Lech; w ofercie Legia - Lech ORAZ Legia - Wisla (ta sama Legia w dwoch meczach)
    out = kr.paruj([_ev('Legia Warszawa', 'Lech Poznań'), _ev('Legia Warszawa', 'Wisła Kraków')], [_ev('Legia', 'Lech Poznan')])
    assert [(s, p) for _, s, _, p in out] == [('MATCH', 'OBIE_STRONY+GODZINA'), ('CONFLICT', 'DRUZYNA_W_INNEJ_PARZE')]
    # inna pisownia jednej strony (18.10, plik z telefonu: Paris FC - Rennes / Paris FC - Stade Rennais) -> UNKNOWN, nie CONFLICT
    assert _stan('Paris FC', 'Lille', [('Paris FC', 'LOSC')]) == ('UNKNOWN', 'JEDNA_STRONA')
    # ... chyba ze para nazw ma alias z dowodem z kursow (aliasy_bukmacherow.csv: Rennes = Stade Rennais)
    assert _stan('Paris FC', 'Rennes', [('Paris FC', 'Stade Rennais')])[0] == 'MATCH'


def test_paruj_niejednoznaczne_wstecz():
    # dwa mecze z oferty pasuja do jednego meczu bukmachera -> zaden nie jest MATCH
    a = [_ev('Dinamo', 'Spartak'), _ev('Dinamo Moskwa', 'Spartak Moskwa')]
    out = kr.paruj(a, [_ev('Dinamo Moskwa', 'Spartak Moskwa')])
    assert [s for _, s, _, _ in out] == ['UNKNOWN', 'UNKNOWN']


def test_zloty_zbior_pary_nowe_dopasowanie_bez_wyjatkow():
    z = pd.read_csv(os.path.join(KAT, 'tests', 'fixtures', 'zloty_rynki.csv'), dtype=str, keep_default_na=False)
    z = z[(z.rodzaj == 'para_meczu') & (z.stan != 'OBSERVATION')]
    assert len(z) >= 8
    for w in z.itertuples():
        stan = _stan(w.gosp, w.gosc, [tuple(w.rynek.split('|'))])[0]
        assert ('PARA' if stan == 'MATCH' else 'BRAK') == w.oczekiwane, (w.gosp, w.gosc, w.rynek, stan)


# ---------------- PODEJRZANY i calosc ----------------

def test_podejrzany_tylko_dla_pary_match_i_tego_samego_rynku():
    pob, st = '2026-10-18T16:00:00Z', '2026-10-18T18:00:00Z'
    r = [dict(bukmacher='SUPERBET', gospodarz='Legia Warszawa', gosc='Lech Poznań', rynek='1', kurs='3.50', pobrano_utc=pob, start_utc=st),
         dict(bukmacher='LVBET', gospodarz='Legia', gosc='Lech Poznan', rynek='1', kurs='2.00', pobrano_utc=pob, start_utc=st),
         dict(bukmacher='SUPERBET', gospodarz='Legia Warszawa', gosc='Lech Poznań', rynek='X', kurs='3.40', pobrano_utc=pob, start_utc=st),
         dict(bukmacher='LVBET', gospodarz='Legia', gosc='Lech Poznan', rynek='X', kurs='3.30', pobrano_utc=pob, start_utc=st),
         # wysoki kurs: 10 / 15 to +50%, ale tylko 3,3 pp prawdopodobienstwa — zwykly rozrzut, nie PODEJRZANY
         dict(bukmacher='SUPERBET', gospodarz='Legia Warszawa', gosc='Lech Poznań', rynek='2', kurs='10', pobrano_utc=pob, start_utc=st),
         dict(bukmacher='LVBET', gospodarz='Legia', gosc='Lech Poznan', rynek='2', kurs='15', pobrano_utc=pob, start_utc=st),
         # inny mecz o tej godzinie (Real ~ Real) — kursy rozne, ale to nie para: bez oznaczenia
         dict(bukmacher='SUPERBET', gospodarz='Real Madrid', gosc='Inter', rynek='1', kurs='1.50', pobrano_utc=pob, start_utc=st),
         dict(bukmacher='LVBET', gospodarz='Real Sociedad', gosc='Inter Turku', rynek='1', kurs='4.00', pobrano_utc=pob, start_utc=st)]
    kr.rekordy(r)
    assert [x['status_walidacji'] for x in r] == ['PODEJRZANY', 'PODEJRZANY'] + ['OK'] * 6
    assert 'LVBET 2' in r[0]['powod']


def test_import_autoryzowany_brak_kolumn_i_poprawny(tmp_path):
    with pytest.raises(ValueError, match='brak kolumn pobrano_utc'):
        kr.z_importu(pd.DataFrame([dict(bukmacher='PINNACLE', gospodarz='A', gosc='B', start_utc='2026-10-18T18:00:00Z',
                                        rynek='1', kurs='2.0')]), 'DOSTAWCA')
    p = tmp_path / 'import.csv'
    pd.DataFrame([dict(bukmacher='PINNACLE', gospodarz='Legia Warszawa', gosc='Lech Poznań', start_utc='2026-10-18T18:00:00+02:00',
                       rynek='1', kurs='2.0', pobrano_utc='2026-10-18 15:00', id_zdarzenia='P1')]).to_csv(p, index=False)
    df = kr.main(['--import', str(p), '--zrodlo', 'DOSTAWCA', '--teraz', '2026-10-18T15:30:00Z'])
    assert df.iloc[0][['zrodlo', 'start_utc', 'status_walidacji']].tolist() == ['DOSTAWCA', '2026-10-18T16:00:00Z', 'OK']


def test_integracja_plik_z_telefonu_do_rekordow(tmp_path, capsys):
    w = [dict(bukmacher='SUPERBET', sport=P, data_meczu='2026-10-18', godzina_meczu='20:00', gospodarz='Legia Warszawa',
              gosc='Lech Poznań', rynek_oryg='1X2', wybor_oryg='1', linia='', rynek='1', kurs='2.10', event_id='9001',
              liga='Ekstraklasa', start_utc='2026-10-18T18:00:00Z', pobrano_utc='2026-10-18T09:30:00Z'),
         dict(bukmacher='SUPERBET', sport=P, data_meczu='2026-10-18', godzina_meczu='12:00', gospodarz='Alfa', gosc='Beta',
              rynek_oryg='1X2', wybor_oryg='1', linia='', rynek='1', kurs='1.90', event_id='9002', liga='',
              start_utc='2026-10-18T10:00:00Z', pobrano_utc='2026-10-18T09:30:00Z'),
         dict(bukmacher='SUPERBET', sport=P, data_meczu='2026-10-18', godzina_meczu='20:00', gospodarz='Legia Warszawa',
              gosc='Lech Poznań', rynek_oryg='Inny', wybor_oryg='?', linia='', rynek='', kurs='5.0', event_id='9001',
              liga='', start_utc='2026-10-18T18:00:00Z', pobrano_utc='2026-10-18T09:30:00Z')]
    p = tmp_path / 'kursy_bukmacherow_2026-10-18_11-30.csv.gz'
    with gzip.open(p, 'wt', encoding='utf-8') as fh: pd.DataFrame(w).to_csv(fh, index=False)
    out = tmp_path / 'rek.csv'
    df = kr.main([str(p), '--teraz', '2026-10-18T10:30:00Z', '--csv', str(out)])
    assert len(df) == 2 and list(df.columns) == kr.POLA                       # rynek bez kodu pominiety
    assert df.status_walidacji.tolist() == ['OK', 'NIEAKTUALNY'] and 'rozpoczety' in df.powod.iloc[1] and df.id_zdarzenia.tolist() == ['9001', '9002']
    assert 'SUPERBET OK: 1' in capsys.readouterr().out and out.exists()
