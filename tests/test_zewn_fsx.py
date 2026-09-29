"""zewn: wyniki koszykowki/recznej/siatkowki z Flashscore (wyniki_fsx_inne_*) — bez dubli z 365, nazwy do zapisu 365."""
import pandas as pd

import zewn

KOL = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'.split(',')


def _w(sport, kraj, tur, g, a, wg, wa):
    return ['2026-09-28', sport, kraj, tur, '', g, a, wg, wa, '', '', 1 if wg > wa else 2, '']


def test_fsx_dubel_i_nazwy(tmp_path, monkeypatch):
    s365 = pd.DataFrame([_w('handball', 'Europe', 'EHF Champions League', 'Füchse Berlin', 'Kielce', 30, 28),
                         _w('handball', 'Germany', 'Bundesliga', 'SC Magdeburg', 'THW Kiel', 31, 29)], columns=KOL)
    fsx = pd.DataFrame([_w('handball', 'EUROPE', 'Champions League', 'Fuchse Berlin', 'Kielce', 30, 28),      # dubel 365
                        _w('handball', 'EUROPE', 'European League', 'THW Kiel', 'Benfica', 33, 30),              # nowy
                        _w('handball', 'EUROPE', 'European League', 'Magdeburg', 'Porto', 35, 30)], columns=KOL)  # nazwa -> 365
    s365.to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    fsx.to_csv(tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    assert len(x) == 4                                           # 2 z 365 + 2 z Flashscore (dubel odrzucony)
    el = x[x.liga.str.contains('European League')]
    assert sorted(el.gosp) == ['SC Magdeburg', 'THW Kiel'] and el.liga.iloc[0].startswith('Europe |')


def test_fsx_dubel_po_wyniku_i_nauczona_nazwa(tmp_path, monkeypatch):
    # „Hamburg” (FS) = „HSV Handball” (365): ten sam dzien, ten sam wynik, rywal pasuje -> dubel; nazwa przechodzi
    # na inny mecz Hamburga (Liga Europejska), ktorego 365 nie ma. 3x3 wypada (inna dyscyplina).
    s365 = pd.DataFrame([_w('handball', 'Germany', 'Bundesliga', 'HSV Handball', 'HSG Wetzlar', 37, 32)], columns=KOL)
    fsx = pd.DataFrame([_w('handball', 'GERMANY', 'Bundesliga', 'Hamburg', 'HSG Wetzlar', 37, 32),
                        _w('handball', 'EUROPE', 'European League', 'Benfica', 'Hamburg', 30, 31),
                        _w('basketball', 'WORLD', 'World Tour 3x3', 'Riga', 'Ub', 21, 18)], columns=KOL)
    s365.to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    fsx.to_csv(tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    assert len(x) == 2 and 'HSV Handball' in set(x.gosc) and '3x3' not in ' '.join(x.liga)


def test_fsx_nazwa_365_dla_kilku_klubow_fs_nie_zgadujemy(tmp_path, monkeypatch):
    # 29.09: „Wybicki Kielce” i „ZPRP Kielce” (nizsze ligi) nie moga dostac nazwy „Kielce” (Industria);
    # „China 3x3 W” nie moze zostac reprezentacja w koszykowce 5x5.
    s365 = pd.DataFrame([_w('handball', 'Poland', 'Superliga', 'Kielce', 'Slask Wroclaw', 35, 25),
                         _w('handball', 'Germany', 'Bundesliga', 'THW Kiel', 'HSG Wetzlar', 31, 29),
                         _w('basketball', 'Asia', 'Asian Games Women', 'China (W)', 'Japan (W)', 80, 70)], columns=KOL)
    fsx = pd.DataFrame([_w('handball', 'POLAND', 'I Liga', 'Wybicki Kielce', 'Opole', 30, 28),
                        _w('handball', 'POLAND', 'Central League', 'ZPRP Kielce', 'Kalisz', 25, 27),
                        _w('handball', 'EUROPE', 'European League', 'Kiel', 'Benfica', 33, 30),
                        _w('basketball', 'ASIA', 'Asian Games 3x3 Women', 'China 3x3 W', 'Japan 3x3 W', 21, 15)], columns=KOL)
    s365.to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    fsx.to_csv(tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    nazwy = set(x.gosp) | set(x.gosc)
    assert {'Wybicki Kielce', 'ZPRP Kielce', 'THW Kiel'} <= nazwy          # Kiel -> THW Kiel nadal (jednoznaczne)
    assert (x.gosp == 'Kielce').sum() == 1                                 # tylko mecz Industrii z 365
    assert not x.liga.str.contains('3x3').any() and len(x) == 6


def test_fsx_nazwa_tylko_w_tym_samym_kraju(tmp_path, monkeypatch):
    # 29.09: „Zamora” (Hiszpania, Division de Honor Plata) nie jest „SAG Lomas de Zamora” (Argentyna)
    s365 = pd.DataFrame([_w('handball', 'Argentina', 'Liga de Honor Oro', 'SAG Lomas de Zamora', 'River Plate', 30, 25),
                         _w('handball', 'Europe', 'Champions League', 'FC Porto', 'Veszprem', 28, 30)], columns=KOL)
    fsx = pd.DataFrame([_w('handball', 'SPAIN', 'Division de Honor Plata', 'Zamora', 'Oviedo', 26, 26),
                        _w('handball', 'EUROPE', 'European League', 'Porto', 'Benfica', 31, 29)], columns=KOL)
    s365.to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    fsx.to_csv(tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    nazwy = set(x.gosp) | set(x.gosc)
    assert 'Zamora' in nazwy and 'FC Porto' in set(x[x.liga.str.contains('European League')].gosp)


def test_fsx_kraj_w_nawiasie_i_rowna_nazwa(tmp_path, monkeypatch):
    # „Seoul Knights” (KBL) i „Seoul Knights (Kor)” (puchar) to jeden klub = „SK Knights” z 365;
    # „China W” to „China (W)”, nie „China Univ. (W)” (jedyna nazwa o tych samych czlonach)
    s365 = pd.DataFrame([_w('basketball', 'South Korea', 'KBL', 'SK Knights', 'KCC Egis', 80, 75),
                         _w('volleyball', 'Asia', 'Asian Championship Women', 'China (W)', 'Japan (W)', 3, 1),
                         _w('volleyball', 'Asia', 'Universiade Women', 'China Univ. (W)', 'Japan Univ. (W)', 3, 2)], columns=KOL)
    fsx = pd.DataFrame([_w('basketball', 'SOUTH KOREA', 'KBL Cup', 'Seoul Knights', 'Anyang', 70, 65),
                        _w('basketball', 'WORLD', 'Intercontinental Cup', 'Seoul Knights (Kor)', 'Tenerife', 60, 70),
                        _w('volleyball', 'ASIA', 'Asian Games Women', 'China W', 'Thailand W', 3, 0)], columns=KOL)
    s365.to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    fsx.to_csv(tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    assert (x.gosp == 'SK Knights').sum() == 3
    assert 'China (W)' in set(x[x.liga.str.contains('Asian Games')].gosp)


def test_fsx_alias_z_aliasy_csv(tmp_path, monkeypatch):
    # 29.09: „St. Raphael” (FS) i „Saint Raphaël” (365) byly w bazie dwoma klubami — alias z aliasy.csv je laczy
    s365 = pd.DataFrame([_w('handball', 'France', 'Starligue', 'Saint Raphaël', 'USAM Nimes', 30, 28)], columns=KOL)
    fsx = pd.DataFrame([_w('handball', 'EUROPE', 'European League', 'St. Raphael', 'Nexe', 31, 29)], columns=KOL)
    s365.to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    fsx.to_csv(tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    assert (x.gosp == 'Saint Raphaël').sum() == 2 and 'St. Raphael' not in set(x.gosp)


def test_hist_jeden_zapis_nazwy():
    import hist_import
    assert hist_import._jeden_zapis('William O&#039;Connor') == "William O'Connor"
    assert hist_import._jeden_zapis('William O’Connor') == "William O'Connor"
    assert hist_import._jeden_zapis(None) is None
