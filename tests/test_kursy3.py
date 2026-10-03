"""02.10.2026: porownanie kursow STS / SUPERBET / LVBET (kursy3.py). Dane syntetyczne — prawdziwe kursy tylko na Dysku."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kursy3  # noqa: E402

D = '2026-10-02'


def _sts(*w):
    return pd.DataFrame([dict(sport=s, data_meczu=D, godzina_meczu=g, gospodarz=a, gosc=b, rynek=r, kurs=k)
                         for s, g, a, b, r, k in w])


def _buk(*w):
    return pd.DataFrame([dict(bukmacher=bk, sport=s, data_meczu=D, godzina_meczu=g, gospodarz=a, gosc=b, rynek=r, kurs=k)
                         for bk, s, g, a, b, r, k in w])


P = 'PIŁKA NOŻNA'


def test_u21_o_tej_samej_godzinie_nie_jest_niejednoznaczne():
    sts = _sts((P, '18:00', 'Słowenia U21', 'Holandia U21', '1', '3.10'), (P, '18:00', 'Austria U21', 'Dania U21', '1', '2.00'))
    buk = _buk(('SUPERBET', P, '18:00', 'Słowenia U21', 'Holandia U21', '1', '3.20'),
               ('SUPERBET', P, '18:00', 'Austria U21', 'Dania U21', '1', '2.05'),
               ('SUPERBET', P, '18:00', 'Ukraina U21', 'Chorwacja U21', '1', '1.90'))
    tab, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['SUPERBET'] == {'jednoznaczne': 2, 'brak': 0, 'kilka': 0}
    assert list(tab.SUPERBET) == [3.20, 2.05]


def test_znaczniki_musza_sie_zgadzac_i_godzina_5_min():
    sts = _sts((P, '18:00', 'Barcelona', 'Sevilla', '1', '1.50'), (P, '20:00', 'Legia Warszawa', 'Lech Poznań', 'X', '3.40'))
    buk = _buk(('LVBET', P, '18:00', 'Barcelona (Wom)', 'Sevilla (Wom)', '1', '1.20'),   # kobiety -> inny mecz
               ('LVBET', P, '20:04', 'Legia Warszawa', 'Lech Poznań', 'X', '3.50'))
    tab, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['LVBET'] == {'jednoznaczne': 1, 'brak': 1, 'kilka': 0}
    assert pd.isna(tab.LVBET.iloc[0]) and tab.LVBET.iloc[1] == 3.50
    buk = _buk(('LVBET', P, '20:06', 'Legia Warszawa', 'Lech Poznań', 'X', '3.50'))
    _, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['LVBET']['jednoznaczne'] == 0


def test_dwa_mozliwe_mecze_to_brak_dopasowania_i_podejrzany_kurs_odrzucony():
    sts = _sts((P, '18:00', 'Dinamo', 'Spartak', '1', '2.00'), (P, '19:00', 'Wisła Kraków', 'Cracovia', '1', '2.00'))
    buk = _buk(('SUPERBET', P, '18:00', 'Dinamo Moskwa', 'Spartak Moskwa', '1', '2.10'),
               ('SUPERBET', P, '18:00', 'Dinamo Mińsk', 'Spartak Trnava', '1', '1.90'),
               ('SUPERBET', P, '19:00', 'Wisła Kraków', 'Cracovia', '1', '3.50'))           # +75% -> podejrzany
    tab, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['SUPERBET'] == {'jednoznaczne': 1, 'brak': 0, 'kilka': 1}
    assert tab.SUPERBET.isna().all() and bool(tab.SUPERBET_podejrzany.iloc[1])


def test_kupon_kurs_laczny_tylko_gdy_kazda_noga_ma_kurs():
    sts = _sts((P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.60'), (P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.50'))
    buk = _buk(('LVBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.65'), ('LVBET', P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.55'),
               ('SUPERBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.70'))
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    nogi, laczne = kursy3.kupon(tab, [('Walia - Norwegia', 'U3.5'), ('Anglia - Łotwa', 'U3.5')])
    assert set(laczne) == {'STS', 'LVBET'} and round(laczne['LVBET'], 4) == round(1.65 * 1.55, 4)
    assert kursy3.najlepszy(nogi[0][2]) == ('SUPERBET', 1.70)


def test_graj_u_zawsze_jest():
    """02.10.2026: Telegram (POWIADOMIENIE / AKO DNIA) zawsze pokazuje, u ktorego bukmachera grac kupon."""
    sts = _sts((P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.60'), (P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.50'))
    nogi = [('Walia - Norwegia', 'U3.5', '1.60'), ('Anglia - Łotwa', 'U3.5', '1.50')]
    # brak pliku z telefonu -> STS
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow([]))
    assert kursy3.gdzie_grac(*kursy3.kupon(tab, nogi)).startswith('GRAJ U: STS @2.400')
    # LVBET ma wszystkie nogi i lepszy kurs laczny; SUPERBET bez nogi 2
    buk = _buk(('LVBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.65'), ('LVBET', P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.55'),
               ('SUPERBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.90'))
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert kursy3.gdzie_grac(*kursy3.kupon(tab, nogi)) == ('GRAJ U: LVBET @2.558 (STS 2.400 | SUPERBET nie znaleziono nogi 2)'
                                                     ' — POROWNANIE NIEPELNE, sprawdz w aplikacji: SUPERBET (lepszy o 15%'
                                                     ' na nogach, ktore ma; noga 2 nieznaleziona w pliku)')
    # remis kursow -> STS
    buk = _buk(('LVBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.60'), ('LVBET', P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.50'))
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert kursy3.gdzie_grac(*kursy3.kupon(tab, nogi)).startswith('GRAJ U: STS @2.400')
    # noga spoza oferty STS: kurs STS z ako_log
    tab, _ = kursy3.tabela(sts.iloc[:1], kursy3.wczytaj_bukmacherow([]))
    assert kursy3.gdzie_grac(*kursy3.kupon(tab, nogi)).startswith('GRAJ U: STS @2.400')


def test_cli_kupon_kazdy_kupon_ma_linie(tmp_path, capsys):
    p_sts = tmp_path / 'kursy_sts.csv'
    _sts((P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.60')).to_csv(p_sts, index=False)
    p_ako = tmp_path / 'ako_log.csv'
    pd.DataFrame([dict(data=D, godzina_uruchomienia='12:00', tag=t, nr_kuponu='1', noga_nr=n, zdarzenie=z, rynek='U3.5', kurs='1.60')
                  for t in ('K5', 'AKOP-1200-1') for n, z in (('1', 'Walia - Norwegia'), ('RAZEM', ''))]).to_csv(p_ako, index=False)
    kursy3.main(['kupon', str(p_sts), str(tmp_path / 'kursy_bukmacherow_*.csv.gz'), '--ako', str(p_ako), '--data', D, '--godzina', '12:00'])
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith('kursy SUPERBET/LVBET: BRAK pliku')
    assert [x.split(' GRAJ U: ')[0] for x in out if 'GRAJ U:' in x] == ['K5#1', 'AKOP-1200-1#1']


# ---- 02.10.2026 (2): koszykowka / tenis / reczna, zapis rynkow w ako_log, pisownia nazw ----
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'termux'))
import kursy_bukmacherow as kb  # noqa: E402


def test_kody_rynkow_bukmacherow_dwudrogowe_i_z_remisem():
    k = lambda r, w, sp, l='': kb.kod_rynku(r, w, l, 'A', 'B', sp)
    assert k('Zwycięzca (z dogrywką)', '1', 'KOSZYKÓWKA') == 'Zwyciezca 1'
    assert k('Zwycięzca', '2', 'TENIS') == 'Zwyciezca 2'
    assert k('Zwycięzca meczu', 'B', 'KOSZYKÓWKA') == 'Zwyciezca 2'                  # LVBET bez dopisku = z dogrywka
    assert k('Zwycięzca meczu (regulaminowy czas)', 'Remis', 'KOSZYKÓWKA') == 'X'     # czas regulaminowy = 1/X/2
    assert k('Zwycięzca meczu', 'A', 'PIŁKA NOŻNA') == '1'                            # pilka: 1/X/2 jak dotad
    assert k('Zwycięzca meczu', 'Remis', 'PIŁKA RĘCZNA') == 'X'
    assert k('Liczba goli', 'poniżej 63.5', 'PIŁKA RĘCZNA', '63.5') == 'U63.5'
    assert k('Liczba goli', 'powyżej 5.5', 'HOKEJ NA LODZIE', '5.5') == ''           # hokej O/U nadal bez kodu
    assert k('Liczba punktów (z dogrywką)', 'powyżej', 'KOSZYKÓWKA', '157.5') == 'O157.5'
    assert k('Liczba punktów', 'powyżej', 'KOSZYKÓWKA', '157.5') == ''               # bez „z dogrywką” — nie zgadujemy


def test_kod_sts_i_porownanie_koszykowki():
    sts = pd.DataFrame([dict(sport='KOSZYKÓWKA', data_meczu=D, godzina_meczu='20:00', gospodarz='Bayern Monachium',
                             gosc='Partizan Belgrad', rynek=r, linia=l, kurs=k)
                        for r, l, k in (('Zwycięzca meczu|1', '', '1.70'), ('Zwycięzca meczu|2', '', '2.10'), ('1', '', '1.80'),
                                        ('Liczba punktów (z dogrywką)|-', '157.5', '1.90'))])
    buk = _buk(('SUPERBET', 'KOSZYKÓWKA', '20:00', 'Bayern Munchen', 'Partizan Belgrad', 'Zwyciezca 1', '1.75'),
               ('SUPERBET', 'KOSZYKÓWKA', '20:00', 'Bayern Munchen', 'Partizan Belgrad', 'U157.5', '1.85'))
    tab, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['SUPERBET']['jednoznaczne'] == 1                                       # Monachium = Munchen
    t = dict(zip(tab.rynek, tab.SUPERBET))
    assert t['Zwyciezca 1'] == 1.75 and t['U157.5'] == 1.85 and pd.isna(t['1'])     # 1 (czas regulaminowy) != Zwyciezca
    out, laczne = kursy3.kupon(tab, [('Bayern Monachium - Partizan Belgrad', '1', '1.70', 'koszykowka')])
    assert out[0][1] == 'Zwyciezca 1' and laczne == {'STS': 1.70, 'SUPERBET': 1.75}


def test_kod_ako_rozne_zapisy():
    k = kursy3.kod_ako
    assert k('Liczba goli ponizej 3.5', 'pilka') == 'U3.5' and k('poniżej 3,5 gola', 'piłka') == 'U3.5'
    assert k('powyzej 1.5 gola', 'pilka') == 'O1.5' and k('Podwojna szansa 12', 'pilka') == '12'
    assert k('Zwyciezca - Fenerbahce', 'koszykowka', 'Fenerbahce SK', 'BC Dubai') == 'Zwyciezca 1'
    assert k('zwyciezca_1', 'tenis') == 'Zwyciezca 1' and k('1', 'koszykowka') == 'Zwyciezca 1'
    assert k('1', 'hokej') == '1' and k('1 (60 min)', 'reczna') == '1' and k('1', '') == '1'
    assert k('zwyciezca', 'koszykowka', 'A', 'B') == 'zwyciezca'                       # bez strony — bez kursu


def test_pisownia_nazw():
    sts = _sts((P, '19:00', 'Naestved BK', 'Nykoebing FC', '1', '2.0'), (P, '13:00', 'SC Poltava', 'FC Chernigiv', '1', '2.0'),
               (P, '15:00', 'Al-Ain FC', 'Ajman SC', '1', '1.5'))
    buk = _buk(('LVBET', P, '19:00', 'Naestved BK', 'Nykobing FC', '1', '2.1'), ('LVBET', P, '13:00', 'SC Poltava', 'FC Chernihiv', '1', '2.1'),
               ('LVBET', P, '15:00', 'Al Ain Abu Dhabi', 'Ajman Club', '1', '1.5'))
    _, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['LVBET'] == {'jednoznaczne': 3, 'brak': 0, 'kilka': 0}
    assert kursy3._pisownia('Koelner') == 'kolner' and kursy3._pisownia('M.Gonzalez/A.Molteni') == 'm.gonzalez/a.molteni'


def test_lvbet_sporty_i_rynek_trojdrogowy():
    assert {3: 'KOSZYKÓWKA', 4: 'TENIS', 29: 'PIŁKA RĘCZNA'}.items() <= kb.LV_SPORT.items() and 6 not in kb.LV_SPORT
    # „Zwycięzca meczu” z wyborem „Remis” w koszykowce = czas regulaminowy, nie Zwyciezca z dogrywka
    assert kb.kod_rynku('Zwycięzca meczu', 'A', '', 'A', 'B', 'KOSZYKÓWKA', z_remisem=True) == '1'
    assert kb.kod_rynku('Zwycięzca meczu', 'A', '', 'A', 'B', 'KOSZYKÓWKA') == 'Zwyciezca 1'
    assert kb.kod_rynku('Zwycięzca meczu', 'Remis', '', 'A', 'B', 'PIŁKA RĘCZNA', z_remisem=True) == 'X'
    assert kb.kod_rynku('Suma goli', 'Powyżej (55.5)', 55.5, 'A', 'B', 'PIŁKA RĘCZNA') == 'O55.5'


def test_lvbet_reczna_zwyciezca_bez_remisu_bez_kodu():
    """02.10 08:26 (plik z telefonu): LVBET reczna „Zwycięzca meczu” tylko 1 i 2 — kursy ~10% nizsze niz 1/2 STS
    (inny rynek). Bez „Remis” w rynku = brak kodu; z „Remis” = 1/X/2."""
    assert kb.kod_rynku('Zwycięzca meczu', 'A', '', 'A', 'B', 'PIŁKA RĘCZNA', z_remisem=False) == ''
    assert kb.kod_rynku('Zwycięzca meczu', 'A', '', 'A', 'B', 'PIŁKA NOŻNA', z_remisem=True) == '1'
    assert kb.kod_rynku('Mecz', '1', '', 'A', 'B', 'PIŁKA RĘCZNA') == '1'          # Superbet bez zmian


def test_raport_0210_1200_dr_kongo_i_porownanie_niepelne():
    """Reprodukcja (Raport 02.10 12:00, uzupelnienie 3): K5 = DR Kongo - Uganda O1.5 (STS 1,44) + Deportivo - Porto X2
    (STS 1,52). Superbet pisze „DR Konga” (15:00), LVBET „Demokratyczna Republika Konga” o 17:00 (zla godzina u LVBET)
    i X2 po 1,60. Bylo: „GRAJ U: STS @2.189 (SUPERBET brak nogi 1 | LVBET brak nogi 1)” — wyglada jak odpowiedz,
    a LVBET dawal 2,35. Oczekiwane: Superbet dopasowany (odmiana), LVBET bez nogi 1 = POROWNANIE NIEPELNE."""
    sts = _sts((P, '15:00', 'DR Kongo', 'Uganda', 'O1.5', '1.44'), (P, '19:00', 'Deportivo A Coruna', 'FC Porto', 'X2', '1.52'))
    buk = _buk(('SUPERBET', P, '15:00', 'DR Konga', 'Uganda', 'O1.5', '1.43'),
               ('SUPERBET', P, '19:00', 'Deportivo de A Coruna', 'Porto', 'X2', '1.50'),
               ('LVBET', P, '17:00', 'Demokratyczna Republika Konga', 'Uganda', 'O1.5', '1.47'),
               ('LVBET', P, '19:00', 'Deportivo de A Coruna', 'Porto', 'X2', '1.60'))
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    linia = kursy3.gdzie_grac(*kursy3.kupon(tab, [('DR Kongo - Uganda', 'O1.5', '1.44', 'pilka'),
                                                  ('Deportivo A Coruna - FC Porto', 'X2', '1.52', 'pilka')]))
    assert linia.startswith('GRAJ U: STS @2.189 (SUPERBET 2.145 | LVBET nie znaleziono nogi 1)')
    assert 'POROWNANIE NIEPELNE' in linia and 'LVBET (lepszy o 5%' in linia
    # komplet u wszystkich -> bez ostrzezenia
    pelne = [('A - B', 'U3.5', {'STS': 1.6, 'SUPERBET': 1.5, 'LVBET': 1.55})]
    assert 'NIEPELNE' not in kursy3.gdzie_grac(pelne, {'STS': 1.6, 'SUPERBET': 1.5, 'LVBET': 1.55})
    # bukmacher bez nogi, ale gorszy na pozostalych -> bez ostrzezenia
    gorszy = [('A - B', 'U3.5', {'STS': 1.6, 'LVBET': 1.5}), ('C - D', 'O1.5', {'STS': 1.3})]
    assert 'NIEPELNE' not in kursy3.gdzie_grac(gorszy, {'STS': 2.08})


def test_obciete_nazwy_pdf_i_cale_nazwy():
    # 03.10 (oferta 03.10 vs LVBET/Superbet 02.10 20:43): PDF STS ucina nazwy — „W...” bylo znacznikiem kobiet,
    # z „Podravka Kopri...” znikal [K]; Superbet pisze „WKS” zamiast „Wybrzeże Kości Słoniowej”
    import kursy3 as k
    assert k._obciete('Polonia Lidzbark W...') == (True, 'Polonia Lidzbark')
    assert k._obciete('Sokół Aleksandrów Ł…') == (True, 'Sokół Aleksandrów')
    assert k._obciete('Lech Poznań') == (False, 'Lech Poznań')
    assert k._zn('Polonia Lidzbark W...') is None and k._zn('Medyk Konin [K]') == ('kobiety',)
    assert k._podobne('Polonia Lidzbark W...', 'MKS Polonia Lidzbark Warminski')
    assert k._podobne('Wybrzeże Kości Słoniowej', 'WKS') and not k._podobne('WKS Śląsk Wrocław', 'Wybrzeże Kości Słoniowej')
    sts = k.pd.DataFrame([('PIŁKA RĘCZNA', '2026-10-03', '16:00', 'HSG Blomberg-Lippe [K]', 'Podravka Kopri...'),
                          ('PIŁKA NOŻNA', '2026-10-03', '15:00', 'Lechia Tomaszów Mazowiecki', 'Polonia Lidzbark W...'),
                          ('PIŁKA NOŻNA', '2026-10-03', '21:00', 'Wybrzeże Kości Słoniowej', 'Kamerun')],
                         columns=['sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc'])
    buk = k.pd.DataFrame([('PIŁKA RĘCZNA', '2026-10-03', '16:00', 'HSG Blomberg-Lippe (Kobiety)', 'ZRK Podravka Vegeta (Kobiety)'),
                          ('PIŁKA RĘCZNA', '2026-10-03', '16:00', 'HSG Blomberg-Lippe', 'Podravka Vegeta'),   # mezczyzni — nie
                          ('PIŁKA NOŻNA', '2026-10-03', '15:00', 'Lechia Tomaszów Mazowiecki', 'MKS Polonia Lidzbark Warminski'),
                          ('PIŁKA NOŻNA', '2026-10-03', '21:00', 'WKS', 'Kamerun')],
                         columns=['sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc'])
    m, st = k.dopasuj_mecze(k.zdarzenia(sts), k.zdarzenia(buk))
    assert st == {'jednoznaczne': 3, 'brak': 0, 'kilka': 0}
    assert m[('PIŁKA RĘCZNA', '2026-10-03', 'HSG Blomberg-Lippe [K]', 'Podravka Kopri...')] == \
        ('HSG Blomberg-Lippe (Kobiety)', 'ZRK Podravka Vegeta (Kobiety)')
    # obie strony uciete = znaczniki nieznane -> nie laczymy (mogloby trafic w mecz kobiet albo mezczyzn)
    s2 = sts.iloc[:1].assign(gospodarz='HSG Blomberg-Li...')
    assert k.dopasuj_mecze(k.zdarzenia(s2), k.zdarzenia(buk))[1]['jednoznaczne'] == 0
