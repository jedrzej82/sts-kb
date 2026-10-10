"""Raport 10.10 12:00.
  1. Rozliczenie 09.10: AKOP-2100-2 Medvedev – Struff (Szanghaj, mecz 10.10 06:00) TRAFIONY „6-4 6-3” — to mecz z Pekinu 03.10;
     okno 8 dni wstecz (daty POCZATKU turnieju w tenis_hist) bralo stary turniej. Medvedev gral potem jeszcze 04.10 (QF),
     wiec mecz z 03.10 nie moze byc meczem z 10.10 -> BRAK WYNIKU. Sprawdzone na paczce 10.10: 09.10 zmienia sie tylko ta
     noga; 02.10, 03.10, 05.10, 07.10, 08.10 bez zmian.
  3. KUPON DNIA „brak” przy 58 nogach >= 83%: .drop_duplicates('mecz').head(15) zostawialo same O0.5 @1,01–1,04.
  4. sezon.py: „Cardiff City” — arkusz (Championship/PL) pisze skroty FBref (Cardiff, QPR, West Brom, Wolves...).
  5. NIESWIEZA: KV Kortrijk (B2 2025/26) = Kortrijk (B1); Polonia Warsawa (POL2, literowka zrodla) = Polonia Warszawa.
  6. Nazwy z oferty pod innym zapisem w bazie (Mesakhte Tkibuli, Iberia 1999, DAC 1904, FK Zalgiris, Kalju Nomme...)."""
import os

import pandas as pd

import dzienniki
import kluby
import kupon
import sezon
import typuj


def _W(tenis):
    t = pd.DataFrame([dict(d=pd.Timestamp(d), w=w, l=l, score=s) for d, w, l, s in tenis], columns=['d', 'w', 'l', 'score'])
    return dict(pilka=pd.DataFrame(columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha', 'zr']),
                inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']), tenis=t)


def test_tenis_okno_wstecz_nie_bierze_starego_turnieju():
    W = _W([('2026-10-02', 'Daniil Medvedev', 'Pablo Carreno Busta', '6-4 6-2'),
            ('2026-10-03', 'Daniil Medvedev', 'Jan Lennard Struff', '6-4 6-3'),
            ('2026-10-04', 'Daniil Medvedev', 'Francisco Cerundolo', '7-6(4) 6-3')])
    r = dict(sport='tenis', zdarzenie='Medvedev Daniil - Struff Jan-Lennard', rynek='Z1', data='2026-10-09',
             uwaga='mecz 2026-10-10 06:00 (Zwyciezca 1: Medvedev Daniil)')
    stan, wyn, uw = dzienniki.rozlicz_noge(r, W)
    assert (stan, wyn) == ('BRAK WYNIKU', '') and 'wczesniejszy turniej' in uw     # przed: TRAFIONY 6-4 6-3


def test_tenis_okno_wstecz_dla_daty_poczatku_turnieju_dalej_dziala():
    # tenis_hist z data poczatku turnieju (21.09) — wszystkie mecze turnieju pod ta sama data; noga z 23.09
    W = _W([('2026-09-21', 'Alycia Parks', 'Leylah Fernandez', '6-3 6-4'),
            ('2026-09-21', 'Alycia Parks', 'Anna Blinkova', '6-2 6-2')])
    r = dict(sport='tenis', zdarzenie='Parks Alycia - Fernandez Leylah', rynek='Z1', data='2026-09-23', uwaga='mecz 2026-09-23 14:00')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', 'Alycia Parks 6-3 6-4')


def test_kupon_dnia_siega_po_noge_z_kursem_z_tego_samego_meczu():
    nogi = [('La Louviere - Brugge', 'O0.5', .95, 1.02), ('La Louviere - Brugge', '12', .846, 1.18),
            ('Napoli - Frosinone', 'O0.5', .96, 1.01), ('Napoli - Frosinone', 'U4.5', .831, 1.30)]
    nogi += [(f'Mecz {i}', 'O0.5', .97 - i * .002, 1.01 + (i % 4) / 100) for i in range(20)]
    w = pd.DataFrame([dict(mecz=m, rynek=r, p=p, kurs=k, sport='pilka', szacunek=0, polski=0, marza=1.06) for m, r, p, k in nogi])
    o = kupon.kupon_dnia(w)
    assert o is not None and o['kurs'] >= kupon.DNIA_MIN_KURS                 # przed: None („brak”)
    assert len({w.at[i, 'mecz'] for i in o['nogi']}) == 2


def test_sezon_skroty_fbref():
    ark = [{'druzyna': n, 'liga': 'Championship', 'mecze': '8'} for n in
           ('Cardiff', 'Blackburn Rovers', 'QPR', 'West Brom', 'Wolves', 'Sheffield Utd', 'Preston', 'Stoke City', 'Bristol City')]
    z = lambda n: (sezon.znajdz(ark, n, sport='pilka')[0] or {}).get('druzyna')
    assert z('Cardiff City') == 'Cardiff'                                    # przed: NIE ZNALEZIONO
    assert z('Queens Park Rangers') == 'QPR' and z('West Bromwich Albion') == 'West Brom'
    assert z('Wolverhampton Wanderers') == 'Wolves' and z('Sheffield United') == 'Sheffield Utd'
    assert z('Preston North End') == 'Preston' and z('Stoke') == 'Stoke City'
    assert z('Bristol City') == 'Bristol City' and z('Bristol Rovers') is None and z('Sheffield Wednesday') is None


def test_kluby_i_aliasy_1010():
    sr = kluby.SCAL_RECZNIE
    assert sr[('B2', 'KV Kortrijk')] == 'Kortrijk' and sr[('POL2', 'Polonia Warsawa')] == 'Polonia Warszawa'
    assert typuj.ALIASES_KLUBY[typuj.norm('KV Kortrijk')] == 'Kortrijk'
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    m = {(r.modul, r.nazwa): r.cel for r in a.itertuples()}
    assert m[('typuj', 'Meshakhte Tkibuli')] == 'FC Mesakhte Tkibuli' and m[('typuj', 'Iberia Tbilisi')] == 'FC Iberia 1999'
    assert m[('typuj', 'DAC Dunajska Streda')] == 'DAC 1904' and m[('typuj', 'Żalgiris Wilno')] == 'FK Zalgiris'
    assert m[('typuj', 'Nomme Kalju')] == 'Kalju Nomme' and m[('typuj', 'Harju Laagri')] == 'Harju Jalgpallikool'
    assert m[('sezon', 'Cardiff City')] == 'Cardiff'
