"""07.10.2026: rynek_model.py (TRYB OBSERWACJI) — normalizacja marzy, laczenie P modelu z kursem, regresja z wiadomym b.
Dane syntetyczne (bez danych uzytkownika)."""
import gzip

import numpy as np
import pandas as pd
import pytest

import rynek_model as R


def test_normalizacja_marzy_1x2_dc_ou():
    p, m = R.normalizuj([1.90, 3.50, 4.00])
    assert sum(p) == pytest.approx(1.0) and m == pytest.approx(1 / 1.9 + 1 / 3.5 + 1 / 4.0)
    assert p[0] > p[1] > p[2]
    p, m = R.normalizuj([1.25, 1.30, 1.40], suma=2.0)          # podwojna szansa: P sumuja sie do 2
    assert sum(p) == pytest.approx(2.0) and m == pytest.approx((1 / 1.25 + 1 / 1.3 + 1 / 1.4) / 2)
    p, _ = R.normalizuj([1.80, 2.00])
    assert sum(p) == pytest.approx(1.0)


def test_grupy_rynkow():
    assert [R.grupa_rynku(r) for r in ['1', 'X', '2', '1X', '12', 'O2.5', 'U0.5', 'BTTS_tak', 'gosp_O0.5', 'O2']] == \
        ['1X2', '1X2', '1X2', 'DC', 'DC', 'OU2.5', 'OU0.5', None, None, None]


def _kursy(tmp_path, wiersze, nazwa='k.csv.gz'):
    kol = ['data_meczu', 'godzina_meczu', 'sport', 'liga', 'gospodarz', 'gosc', 'rynek', 'kurs', 'godzina_pobrania']
    f = tmp_path / nazwa
    with gzip.open(f, 'wt', encoding='utf-8') as g:
        pd.DataFrame(wiersze, columns=kol).to_csv(g, index=False)
    return str(f)


def _mecz(d, h, a, pobr, k1, kx, k2, ko=None, ku=None, godz='20:00', liga='POLSKA - EKSTRAKLASA'):
    w = [(d, godz, 'PIŁKA NOŻNA', liga, h, a, r, k, pobr) for r, k in (('1', k1), ('X', kx), ('2', k2)) if k]
    if ko: w += [(d, godz, 'PIŁKA NOŻNA', liga, h, a, 'O2.5', ko, pobr), (d, godz, 'PIŁKA NOŻNA', liga, h, a, 'U2.5', ku, pobr)]
    return w


def test_niepelna_grupa_odrzucona_i_migawki(tmp_path):
    w = (_mecz('2026-10-05', 'Lech Poznań', 'Legia Warszawa', '2026-10-04 11:30', '2.10', '3.40', '3.30', '1.90', '1.90')
         + _mecz('2026-10-05', 'Lech Poznań', 'Legia Warszawa', '2026-10-05 17:30', '1.80', '3.60', '4.20')
         + _mecz('2026-10-05', 'Lech Poznań', 'Legia Warszawa', '2026-10-05 20:30', '1.50', '4.00', '6.00')   # po starcie
         + _mecz('2026-10-05', 'Rakow', 'Pogon', '2026-10-05 11:30', '1.70', None, '4.00'))                  # brak X
    k = R.wczytaj_kursy([_kursy(tmp_path, w), str(tmp_path / 'brak.csv')])
    assert not (k.pobrano == '2026-10-05 20:30').any()          # kurs pobrany po rozpoczeciu meczu nie wchodzi
    m = R.migawki(k)
    assert set(m.gospodarz) == {'Lech Poznań'}                  # Rakow bez X: grupa 1X2 niepelna -> brak P rynku
    r1 = m[m.rynek == '1'].iloc[0]
    assert r1.kurs == 2.10 and r1.pobrano == '2026-10-04 11:30'                 # najwczesniejszy
    assert r1.kurs_zamk == 1.80 and r1.pobrano_zamk == '2026-10-05 17:30'       # najpozniejszy sprzed meczu
    assert m[m.grupa == '1X2'].p_rynku.sum() == pytest.approx(1.0)
    assert m[m.grupa == 'OU2.5'].p_rynku.tolist() == pytest.approx([0.5, 0.5])
    ou = m[m.rynek == 'O2.5'].iloc[0]
    assert ou.kurs_zamk == 1.90                                 # O/U byla tylko w pierwszej migawce


def test_plik_bez_kolumn_oferty_pominiety(tmp_path, capsys):
    f = tmp_path / 'stary.csv'
    pd.DataFrame({'mecz': ['A - B'], 'k1': ['1.5']}).to_csv(f, index=False)
    assert len(R.wczytaj_kursy([str(f)])) == 0
    assert 'POMINIETO' in capsys.readouterr().out


MAPA = {'Lech Poznań': ('Lech Poznan', 'klub'), 'Legia Warszawa': ('Legia', 'klub'), 'Legia': ('Legia', 'klub'),
        'Cypr': ('Cyprus', 'intl'), 'Łotwa': ('Latvia', 'intl'), 'Wisła': ('Wisla Plock', 'klub'),
        'Wisła Płock': ('Wisla Plock', 'klub'), 'Polonia': ('Polonia', 'klub'), 'Latvia FC': ('Latvia', 'klub')}


def _rozw(n, liga):
    return MAPA.get(n)


def _mig(*mecze):
    w = []
    for d, h, a in mecze:
        for r, p in (('1', 0.5), ('X', 0.3), ('2', 0.2)):
            w.append(dict(data=d, godzina='20:00', liga='L', gospodarz=h, gosc=a, grupa='1X2', rynek=r, kurs=1 / p / 1.05,
                          pobrano='2026-10-05 11:30', marza=1.05, p_rynku=p, kurs_zamk=np.nan, pobrano_zamk='', p_rynku_zamk=np.nan))
    return pd.DataFrame(w)


def _typy(*wiersze):
    return pd.DataFrame(wiersze, columns=['data', 'gosp_baza', 'gosc_baza', 'rynek', 'p'])


def test_laczenie_po_dacie_i_parze_z_bazy():
    mig = _mig(('2026-10-05', 'Lech Poznań', 'Legia Warszawa'), ('2026-10-05', 'Cypr', 'Łotwa'),
               ('2026-10-05', 'Nieznani', 'Legia Warszawa'))
    typy = _typy(('2026-10-05', 'Lech Poznan', 'Legia', '1', 0.55), ('2026-10-05', 'Cyprus', 'Latvia', 'X', 0.25),
                 ('2026-10-06', 'Lech Poznan', 'Legia', '2', 0.20),        # inny dzien — nie laczy
                 ('2026-10-05', 'Legia', 'Lech Poznan', '2', 0.30))        # odwrocona para — nie laczy
    z = R.polacz(mig, typy, R.wczytaj_p_sts([]), _rozw)
    assert sorted(zip(z.gospodarz, z.rynek, z.p_model, z.druzyny)) == [
        ('Cypr', 'X', 0.25, 'reprezentacje'), ('Lech Poznań', '1', 0.55, 'kluby')]
    assert set(z.zrodlo_p) == {'typy_log'}


def test_niejednoznaczne_zdarzenia_odrzucone():
    # dwa zdarzenia oferty wskazujace te sama pare bazy w dniu -> zadne nie dostaje P (nie zgadujemy, ktore to)
    mig = _mig(('2026-10-05', 'Wisła', 'Legia'), ('2026-10-05', 'Wisła Płock', 'Legia Warszawa'),
               ('2026-10-05', 'Legia', 'Legia Warszawa'),          # ta sama druzyna po obu stronach
               ('2026-10-05', 'Polonia', 'Łotwa'))                 # klub z reprezentacja — rozne rodzaje
    typy = _typy(('2026-10-05', 'Wisla Plock', 'Legia', '1', 0.4), ('2026-10-05', 'Polonia', 'Latvia', '1', 0.4))
    assert len(R.polacz(mig, typy, R.wczytaj_p_sts([]), _rozw)) == 0


def test_p_sts_uzupelnia_typy_log(tmp_path):
    mig = _mig(('2026-10-05', 'Lech Poznań', 'Legia Warszawa'), ('2026-10-05', 'Cypr', 'Łotwa'))
    typy = _typy(('2026-10-05', 'Lech Poznan', 'Legia', '1', 0.55))
    f = tmp_path / 'model_p.csv'
    pd.DataFrame([('2026-10-05', 'Lech Poznań', 'Legia Warszawa', '1', 0.99, False),     # typy_log wygrywa
                  ('2026-10-05', 'Lech Poznań', 'Legia Warszawa', 'X', 0.21, False),
                  ('2026-10-05', 'Cypr', 'Łotwa', '2', 0.15, True)],
                 columns=['dzien', 'gospodarz', 'gosc', 'rynek', 'p_model', 'intl']).to_csv(f, index=False)
    z = R.polacz(mig, typy, R.wczytaj_p_sts([str(f)]), _rozw)
    got = {(r.gospodarz, r.rynek): (r.p_model, r.zrodlo_p, r.druzyny) for r in z.itertuples()}
    assert got == {('Lech Poznań', '1'): (0.55, 'typy_log', 'kluby'), ('Lech Poznań', 'X'): (0.21, 'wsad', 'kluby'),
                   ('Cypr', '2'): (0.15, 'wsad', 'reprezentacje')}


def test_typy_log_pierwszy_zapis_wygrywa(tmp_path):
    f = tmp_path / 't.csv'
    pd.DataFrame([('2026-10-05', 'A', 'B', '1', '0.6', '', '', ''), ('2026-10-05', 'A', 'B', '1', '0.7', '', '', ''),
                  ('2026-10-05', 'A', 'B', 'BTTS_tak', '0.5', '', '', '')],
                 columns=['data', 'gosp', 'gość', 'rynek', 'p', 'trafiony', 'kurs_typu', 'pieniadze']).to_csv(f, index=False)
    t = R.wczytaj_typy([str(f)])
    assert t.p.tolist() == [0.6] and t.rynek.tolist() == ['1']


def test_dopisz_bez_dubli_i_uzupelnia_wynik():
    def w(rynek, p, wynik):
        return {**{c: '' for c in R.KOL_ZBIOR}, 'data': '2026-10-05', 'gospodarz': 'A', 'gosc': 'B', 'rynek': rynek,
                'p_model': p, 'wynik': wynik, 'stan': 'TRAFIONY' if wynik == '1' else ''}
    stary = pd.DataFrame([w('1', '0.5', ''), w('X', '0.3', '0')])
    nowy = pd.DataFrame([w('1', '0.9', '1'), w('X', '0.9', '1'), w('2', '0.2', '0')])
    out = R.dopisz(stary, nowy)
    assert len(out) == 3
    got = {r.rynek: (r.p_model, r.wynik) for r in out.itertuples()}
    assert got == {'1': ('0.5', '1'), 'X': ('0.3', '0'), '2': ('0.2', '0')}   # P zamrozone, wynik tylko uzupelniony


def _syntetyczne(b, n_mecze=3000, nogi=3, ziarno=1):
    rng = np.random.default_rng(ziarno)
    n = n_mecze * nogi
    lr = rng.normal(-0.3, 1.2, n)
    d = rng.normal(0, 0.6, n)                  # roznica logitow model - rynek
    y = (rng.random(n) < R.sigm(lr + b * d)).astype(float)
    return pd.DataFrame(dict(p_rynku=R.sigm(lr), p_model=R.sigm(lr + d), wynik=y,
                             dzien=[f'2026-10-{1 + (i // nogi) % 6:02d}' for i in range(n)],
                             mecz=[f'm{i // nogi}' for i in range(n)]))


def test_regresja_odzyskuje_znane_b():
    for b in (0.0, 0.5, 1.0):
        x = _syntetyczne(b)
        bh, _ = R.dopasuj_b(R.logit(x.p_rynku), R.logit(x.p_model) - R.logit(x.p_rynku), x.wynik.to_numpy())
        assert bh == pytest.approx(b, abs=0.12)


def test_ocena_segmentu_istotnosc():
    r = R.ocen_segment(_syntetyczne(0.6), boot=200)
    assert r['b_lo'] > 0 and r['istotne'] and r['cv_ll_rez'] < r['cv_ll_rynek']
    r0 = R.ocen_segment(_syntetyczne(0.0, ziarno=3), boot=200)
    assert r0['b_lo'] < 0 < r0['b_hi'] and not r0['istotne']
    # gdy model jest szumem (b=0), sam model ma gorszy log-loss niz rynek
    assert r0['ll_model'] > r0['ll_rynek']


def test_raport_segmenty():
    x = _syntetyczne(0.0, n_mecze=200)
    x = x.assign(grupa='1X2', druzyny='kluby', zrodlo_p='typy_log', data=x.dzien, gospodarz=x.mecz, gosc='B',
                 rynek='1', p_rynku_zamk=np.nan)
    z = R.przygotuj(x.astype(str))
    linie, wiersze = R.raport(z, boot=50)
    seg = {w['segment'] for w in wiersze}
    assert 'WSZYSTKIE: wszystkie' in seg and 'rynek: 1X2' in seg and 'druzyny: kluby' in seg
    assert linie[-1].startswith('b>0 istotnie')


def test_typy_log_z_nazwami_oferty_laczy_sie_wprost():
    # 07.10.2026: w typy_log czesc wierszy ma nazwy z oferty („Cypr”, „Łotwa”), nie z bazy — laczymy po dokladnej nazwie
    mig = _mig(('2026-10-05', 'Cypr', 'Łotwa'), ('2026-10-05', 'Nieznani FC', 'Inni FC'))
    typy = _typy(('2026-10-05', 'Cypr', 'Łotwa', '1', 0.6), ('2026-10-05', 'Nieznani FC', 'Inni FC', '2', 0.3),
                 ('2026-10-05', 'Cyprus', 'Latvia', '1', 0.9))       # ten sam mecz po resolve — wygrywa zapis po resolve
    z = R.polacz(mig, typy, R.wczytaj_p_sts([]), _rozw)
    got = sorted((r.gospodarz, r.rynek, r.p_model, r.druzyny) for r in z.itertuples())
    assert got == [('Cypr', '1', 0.9, 'reprezentacje'), ('Nieznani FC', '2', 0.3, 'kluby')]
