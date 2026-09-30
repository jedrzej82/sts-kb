# sts-kb — zasady pracy (dla każdej sesji)

## Zasada nadrzędna użytkownika (29.09.2026)
**Wszystko ma działać poprawnie.** Usterkę znalezioną w raporcie przebiegu, w danych albo w kodzie naprawiamy
od razu — nie odkładamy „do najbliższego wydania”, nie zostawiamy obejść. Każda poprawka:
1. jest sprawdzona na prawdziwych danych (albo wprost napisane, czego nie dało się sprawdzić i dlaczego),
2. ma test w `tests/` i przechodzi CI (`python -m pytest -q tests`, pyflakes),
3. trafia do `main` PR-em, a zmiana zachowania przebiegu — do POPRAWEK na Dysku dopiero PO scaleniu kodu
   (reguły nigdy nie wyprzedzają kodu), publikacja tylko między przebiegami (12/15/18/21 PL), z odczytem kontrolnym.

## Czego nie wolno
- Wpisywać do repo danych osobistych i historii zakładów: logów, Bilansu, kursów, Dziennika, Raportu, PDF, e-maili,
  id folderów Dysku (w `apps_script/` zostaje placeholder `WKLEJ_ID_FOLDERU_BAZA_WIEDZY`).
- Luzować CZĘŚCI A (stawki, limity, budżet 300 zł) bez decyzji opartej na backteście.
- Zgadywać nazw drużyn: brak jednoznacznego dopasowania = noga MNIEJ / „BRAK WYNIKU”.
- Usuwać zadania cyklicznego `trig_01LXhx9anABLZ7aaWYpxUcUA`.

## Czas
Użytkownik liczy w czasie polskim (UTC+2 latem): 10:00 UTC = 12:00 PL. Przebiegi: 12:00, 15:00, 18:00, 21:00 PL.

## Mapa
- Reguły: Dysk, folder baza-wiedzy — „INSTRUKCJA STS v7” + „POPRAWKI DO INSTRUKCJI v7 — wyd. N” (każde nowsze niż v7).
  Projekt v7: `docs/INSTRUKCJA_v7_projekt.md`; strategia: `docs/STRATEGIA.md`; backtest P48/P58: `docs/BACKTEST_P48.md`.
- Przebieg: `przebieg.py` (build_kb → uzupelnij_ligi → build_kb → hist_import → swiezosc + kontrole plików).
- Typowanie: `typuj.py` (piłka), `sporty.py` (inne sporty, linia WERDYKT), `tenis.py`, `sezon.py` (arkusze).
- Kupony: `kupon.py`; rozliczenia i dzienniki: `dzienniki.py`; CLV: `clv.py`.
- Nazwy: `nazwy.py` (wspólne znaczniki), `aliasy.csv` (aliasy jako dane; działają tylko, gdy cel jest w puli).
- Apps Script (wkleja użytkownik): `apps_script/terminarz.gs`, `apps_script/ligapro.gs`, `apps_script/arkusze.gs` (arkusze statystyk jako .csv.gz), `apps_script/dzienniki.gs` (wszystkie dzienniki w jednym dzienniki.zip; `python3 przebieg.py --dzienniki`).
