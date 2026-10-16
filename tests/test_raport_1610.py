"""Raporty 16.10 (12:00–21:00) — paczka wieczorna. Sprawdzone na bazie i paczce z 16.10 21:00 (przebieg OK, 420 931 meczow):

- nr 1 (21:00) Steaua Bukareszt -> „Steaua” (stary wpis Elo FCSB): NIEPEWNE DOPASOWANIE, noga MNIEJ. W Liga 2 gra CSA Steaua
  Bucuresti (32 mecze 2025–26, wspolna liga z FC Metaloglobus Bucharest). Po aliasie: oba kluby z Liga 2.
- nr 3 (21:00) Kyoto Sanga NIESWIEZA 1433 dni: rozbita historia — „Kyoto Sanga” (JAP2 do 13.11.2022) i „Kyoto” (J1 od
  02.2022, 165 meczow do 10.10.2026), daty sie nie nakladaja. SCAL_RECZNIE ('JAP2', 'Kyoto Sanga') -> Kyoto.
- (18:00) Wexford FC -> „Wexford” (IRL 2016): Wexford (football-data) = Wexford Youths (365, Division 1 od 2025).
- (18:00) Stade Lavallois -> None bez aliasy_auto.csv; w bazie Laval (F2).
- (18:00) sezon.py „Oviedo CB”: NIE ZNALEZIONO; arkusz ma „Oviedo Club Baloncesto”.
- (12:00–18:00) Regionalliga Ost NIESWIEZA (Favoritner AC, SG Traiskirchen, FC Marchfeld Donauauen, 329 dni): 365 do 11.2025
  pelnymi nazwami, FS od 09.2026 skrotami — 10 par z porownania list druzyn ligi.
- nr 8 (21:00) Rozliczenia: West Bromwich (x2) i Mardin Spor — NAZWA_NIEDOPASOWANA (w wynikach „West Brom”, „Mardin 1969”);
  po aliasach AKOBL-1800, AKOPD-1800 (13.10) i AKOP-1200-2 (15.10) rozliczone (TRAFIONY). Millonarios FC – CD Once Caldas
  (14.10): FS ma mecz BEZ wyniku, 365 nie ma go wcale — to zrodlo wynikow, nie nazwa: kod MECZ_BEZ_WYNIKU."""
import os

import pandas as pd
import pytest

import dzienniki
import kluby
import typuj

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = pd.Timestamp


@pytest.mark.parametrize('nazwa,pula,bylo,oczekiwane', [
    ('Steaua Bukareszt', {'Steaua', 'CSA Steaua Bucuresti', 'FC Metaloglobus Bucharest'}, 'Steaua', 'CSA Steaua Bucuresti'),
    ('Stade Lavallois', {'Laval', 'Clermont'}, None, 'Laval'),
    ('Wexford FC', {'Wexford', 'Wexford Youths', 'UC Dublin'}, 'Wexford', 'Wexford Youths'),
    ('West Bromwich', {'West Brom', 'West Brom U21', 'Wrexham'}, None, 'West Brom'),
    ('Mardin Spor', {'Mardin 1969', 'Fatih Karagümrük'}, None, 'Mardin 1969'),
])
def test_aliasy_1610(nazwa, pula, bylo, oczekiwane):
    assert typuj.resolve(nazwa, pula) == oczekiwane != bylo


def test_aliasy_csv_1610():
    a = pd.read_csv(os.path.join(KB, 'aliasy.csv'), dtype=str)
    m = {(r.modul, r.nazwa): r.cel for r in a.itertuples()}
    assert m[('sezon', 'Oviedo CB')] == 'Oviedo Club Baloncesto'
    assert m[('typuj', 'Steaua Bukareszt')] == 'CSA Steaua Bucuresti'


def test_sezon_oviedo():
    import sezon
    ark = [{'druzyna': n, 'liga': '1ª FEB', 'mecze': '5'} for n in ('Oviedo Club Baloncesto', 'Estudiantes Madrid')]
    assert (sezon.znajdz(ark, 'Oviedo CB', sport='koszykowka')[0] or {}).get('druzyna') == 'Oviedo Club Baloncesto'


def test_scal_recznie_1610():
    sr = kluby.SCAL_RECZNIE
    assert sr[('JAP2', 'Kyoto Sanga')] == 'Kyoto' and sr[('IRL', 'Wexford')] == 'Wexford Youths'
    ost = {k[1]: v for k, v in sr.items() if k[0] == 'Austria | Regionalliga East'}
    assert ost['Favoritner'] == 'Favoritner AC' and ost['Traiskirchen'] == 'SG Traiskirchen'
    assert ost['Marchfeld'] == 'FC Marchfeld Donauauen' and len(ost) == 10
    assert not {'Mattersburg SV 2020', 'SV Donau', 'Warth', 'Wienerberger'} & set(ost)   # beniaminki — bez pary


def _W(pilka=(), bez=()):
    k = ['d', 'h', 'a', 'g', 'ga', 'hg', 'ha', 'zr']
    return dict(pilka=pd.DataFrame(list(pilka), columns=k), pilka_bez=pd.DataFrame(list(bez), columns=k),
                tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']),
                inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']))


def test_mecz_bez_wyniku_w_zrodle():
    r = dict(sport='pilka', zdarzenie='Millonarios FC - CD Once Caldas', data='2026-10-13', rynek='1X',
             uwaga='mecz 2026-10-14 02:00')
    inne = [(T('2026-10-13'), 'Junior', 'Santa Fe', 1, 0, None, None, 'fs')]
    stan, wyn, uw = dzienniki.rozlicz_noge(r, _W(pilka=inne, bez=[(T('2026-10-14'), 'Millonarios', 'Once Caldas',
                                                                   None, None, None, None, 'fs')]))
    assert stan == 'BRAK WYNIKU' and wyn == '' and 'bez wyniku' in uw
    assert dzienniki.kod_anomalii(stan, uw) == 'MECZ_BEZ_WYNIKU'                  # przed: NAZWA_NIEDOPASOWANA
    stan, _, uw = dzienniki.rozlicz_noge(r, _W(pilka=inne))                       # bez wiersza w zrodle — jak dotad
    assert dzienniki.kod_anomalii(stan, uw) == 'NAZWA_NIEDOPASOWANA'


def test_wyniki_pilka_bez_wyniku(tmp_path):
    (tmp_path / 'zewn').mkdir()
    pd.DataFrame([dict(data='2026-10-14', gosp='Millonarios', gosc='Once Caldas', wg='', wa=''),
                  dict(data='2026-10-13', gosp='Wrexham', gosc='West Brom', wg='1', wa='2')]).to_csv(
        tmp_path / 'zewn' / 'wyniki_fs_pilka_2026-10.csv.gz', index=False)
    w, b = dzienniki.wyniki_pilka(str(tmp_path)), dzienniki.wyniki_pilka_bez_wyniku(str(tmp_path))
    assert list(w.h) == ['Wrexham'] and list(b.h) == ['Millonarios']


# P126.1: dopasuj.py auto 12–13 min. Na kursach 16.10 20:30 i bazie 16.10: 2 min 47 s, aliasy_auto.csv i log identyczne
# jak przed zmiana (to samo aliasy.csv). Pamiec norm() nie moze zmienic wyniku — takze dla nie-napisow.
@pytest.mark.parametrize('x,oczekiwane', [('Wisła Płock', 'wislaplock'), ('FC Köln', 'fckoln'), (None, 'none'),
                                          (float('nan'), 'nan'), (1969, '1969'), ('', '')])
def test_norm_z_pamiecia(x, oczekiwane):
    import sporty
    assert typuj.norm(x) == oczekiwane == typuj.norm(x)
    assert sporty.norm(x) == oczekiwane

