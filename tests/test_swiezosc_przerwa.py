"""swiezosc.py: przerwa reprezentacyjna nie jest „dniem niepelnym” (dane sztuczne)."""
import datetime as dt

import pandas as pd

import swiezosc


def _plik(katalog, wiersze):
    pd.DataFrame(wiersze, columns=['data', 'kraj', 'turniej']).to_csv(katalog / 'wyniki_365_pilka_2026-09.csv.gz', index=False)


def test_przerwa_liczy_tylko_seniorskie_reprezentacje(tmp_path):
    w = ([('2026-09-26', 'Europe', 'UEFA Nations League')] * 20
         + [('2026-09-27', 'Africa', 'Africa Cup of Nations Qualification')] * 15
         + [('2026-09-27', 'International', 'U19 Friendly International')] * 50       # mlodziez — nie liczy sie
         + [('2026-09-27', 'Europe', 'UEFA Champions League Qualification')] * 50     # kluby — nie licza sie
         + [('2026-09-27', 'Poland', 'Ekstraklasa')] * 50)
    _plik(tmp_path, w)
    r = swiezosc.mecze_reprezentacji(str(tmp_path))
    assert len(r) == 35
    assert swiezosc.przerwa_reprezentacyjna(dt.date(2026, 9, 28), r) == 35 >= swiezosc.PROG_PRZERWY
    assert swiezosc.przerwa_reprezentacyjna(dt.date(2026, 9, 14), r) == 0


def test_brak_plikow_to_zwykly_tydzien(tmp_path):
    r = swiezosc.mecze_reprezentacji(str(tmp_path / 'nie_ma'))
    assert swiezosc.przerwa_reprezentacyjna(dt.date(2026, 9, 28), r) == 0


def _wyniki(katalog, nazwa, daty):
    pd.DataFrame({'data': daty}).to_csv(katalog / nazwa, index=False)


def test_brak_bazy_to_blad_a_1_dnia_miesiaca_licza_sie_pliki_poprzedniego(tmp_path, monkeypatch, capsys):
    # 30.09.2026 (przeglad): wiersz „BRAK” (kb.sqlite, sporty_hist, pliki miesiaca) nie podnosil kodu wyjscia —
    # przebieg szedl dalej z „Wszystkie bazy w normie”. 1. dnia miesiaca plikow nowego miesiaca jeszcze nie ma.
    zd = tmp_path / 'zewn'; zd.mkdir()
    for z in ('365_pilka', '365_inne', 'fs_inne'):
        _wyniki(zd, f'wyniki_{z}_2026-09.csv.gz', ['2026-09-29', '2026-09-30'])
    monkeypatch.setattr(swiezosc, 'HERE', str(tmp_path))
    monkeypatch.setattr(swiezosc, 'DZIS', dt.date(2026, 10, 1))
    assert swiezosc.main() == 2                                 # brak kb.sqlite i sporty_hist.csv = BRAK DANYCH
    out = capsys.readouterr().out
    wiersz = [l for l in out.splitlines() if l.startswith('pliki zewn/')][0]
    assert '2026-09-30' in wiersz and ' ok' in wiersz          # wrzesniowe pliki licza sie 1.10
    assert [l for l in out.splitlines() if l.startswith('kb.sqlite')][0].rstrip().endswith('BRAK DANYCH nie zbudowano bazy')


def test_zrodlo_ze_starym_plikiem_to_waskie_gardlo_takze_1_dnia(tmp_path, monkeypatch, capsys):
    zd = tmp_path / 'zewn'; zd.mkdir()
    _wyniki(zd, 'wyniki_365_pilka_2026-09.csv.gz', ['2026-09-30'])
    _wyniki(zd, 'wyniki_365_pilka_2026-10.csv.gz', ['2026-10-01'])
    _wyniki(zd, 'wyniki_fs_inne_2026-09.csv.gz', ['2026-09-20'])    # stara kopia z repo
    monkeypatch.setattr(swiezosc, 'HERE', str(tmp_path))
    monkeypatch.setattr(swiezosc, 'DZIS', dt.date(2026, 10, 1))
    swiezosc.main()
    wiersz = [l for l in capsys.readouterr().out.splitlines() if l.startswith('pliki zewn/')][0]
    assert '2026-09-20' in wiersz and 'PRZETERMINOWANE' in wiersz


def test_dzien_bez_zadnego_wyniku_jest_niepelny(monkeypatch):
    # 30.09.2026 (przeglad): petla szla po dniach OBECNYCH w danych — dzien z zerem wynikow znikal z kontroli
    monkeypatch.setattr(swiezosc, 'DZIS', dt.date(2026, 9, 30))
    dni = [dt.date(2026, 9, 29) - dt.timedelta(days=k) for k in range(35)]
    daty = [str(d) for d in dni if d != dt.date(2026, 9, 28) for _ in range(100)]
    z = swiezosc.kompletnosc(daty, 'test')
    assert [(x[0], x[1]) for x in z] == [(dt.date(2026, 9, 28), 0)]
    assert swiezosc.kompletnosc([str(d) for d in dni for _ in range(100)], 'test') == []
