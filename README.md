# sts-kb

Skrypty i pliki referencyjne systemu analizy zakladow STS.
Repozytorium **prywatne**. Zawiera wylacznie kod i kalibracje —
zadnych danych osobistych ani historii zakladow.

## Po co to istnieje

Do 21.09.2026 katalog `kb/` byl odtwarzany przy kazdym uruchomieniu
z **25 osobnych archiwow** na Dysku Google (`kb_skrypty v3` + 24
dodatki `v5b…v5q`), rozpakowywanych w kolejnosci `createdTime`.

Problemy tego podejscia, wszystkie zaobserwowane realnie:

* **Czas.** 21.09.2026 pobranie tych 25 plikow przez konektor Drive
  zajelo ~2 godziny i zjadlo cale uruchomienie 12:00. Budzet z KROKU 2b
  (20 min na baze) zostal przekroczony ~4-krotnie.
* **Cicha utrata danych.** Archiwum `v5b` bylo uszkodzone CRC
  **po stronie zrodla** — pobrane dwukrotnie, bajt w bajt identycznie
  zepsute. Odzyskano tylko `tabele_eu.csv`; reszta zawartosci przepadla
  bez zadnego komunikatu.
* **Wersjonowanie przez nazwe pliku.** „Ktora wersja jest najnowsza"
  bylo pytaniem rozstrzyganym po `createdTime` i kolejnosci rozpakowania.

`git clone --depth 1` tego repo: **~1,6 s**. Wersja = commit.

## Dlaczego GitHub, a nie Vercel / Netlify / Cloudflare

Sprawdzone empirycznie 21.09.2026 z sandboksa analizy:

| host | wynik |
|---|---|
| `raw.githubusercontent.com` | 200 |
| `github.com`, `codeload.github.com` | osiagalne |
| `vercel.com`, `*.vercel.app` | polaczenie odrzucone |
| `netlify.com`, `*.netlify.app` | polaczenie odrzucone |
| Cloudflare (Pages / R2) | polaczenie odrzucone |
| `gitlab.com`, `codeberg.org` | polaczenie odrzucone |
| `huggingface.co` | polaczenie odrzucone |

Bramka sieciowa srodowiska przepuszcza tylko GitHub i rejestry pakietow
(npm, PyPI, crates, Go). Nawet `nodejs.org` dostaje 403. GitHub nie jest
wiec wyborem estetycznym — jest jedynym dzialajacym hostem.

## Co tu JEST

* `*.py` — modele i narzedzia: `typuj.py`, `sezon.py`, `sporty.py`,
  `tenis.py`, `linie.py`, `ramki.py`, `specjalne.py`, `pi.py`,
  `ensemble.py`, `korekta_rynkow.py`, `build_kb.py`, `ucz.py`,
  `hist_import.py`, `uzupelnij_ligi.py`, `zewn.py`, `backtest.py`,
  `eksport.py`, `dodaj_tabele.py`, `test_ostatnie.py`
* kalibracje i parametry: `kalibracja_ligi_v5n.csv`,
  `korekta_rynkow_v5n.csv`, `linie_kalibracja.csv`, `linie_sigma.csv`,
  `ramki_kalibracja.csv`, `spec_kalibracja.csv`,
  `sporty_kalibracja_hist.csv`, `sporty_param.json`,
  `ensemble_wagi.json`, `tabele_eu.csv`
* `apps_script/` — zrodlo skryptu Google „wyniki STS"

## Co tu NIE JEST (i dlaczego)

| co | gdzie zostaje | powod |
|---|---|---|
| `kb.sqlite` | generowane | `build_kb.py` odtwarza z GitHuba w ~1 min |
| `tenis_hist.csv`, `sporty_hist.csv` | generowane | ~48 MB, `hist_import.py` ciagnie z GitHuba |
| `statystyki_*.csv`, `absencje.csv` | Dysk | Apps Script odswieza co godzine — repo byloby zawsze nieaktualne |
| `typy_log`, `ako_log`, `Bilans`, `kursy` | Dysk | historia zakladow, dane osobiste |
| PDF-y oferty | Dysk | wrzuca Termux 4x dziennie |

## Uzycie w KROKU 2b

Zamiast pobierania 25 archiwow:

```bash
git clone --depth 1 https://github.com/jedrzej82/sts-kb.git kb
cd kb
pip install --break-system-packages pandas scipy pyarrow tqdm pulp fsspec plotly pyreadr
pip install --break-system-packages --no-deps penaltyblog
python3 build_kb.py --refresh && python3 uzupelnij_ligi.py && python3 build_kb.py
python3 hist_import.py
```

Arkusze `statystyki_*` i `absencje.csv` nadal pobierane z Dysku do `kb/`.

**Uwaga o autoryzacji:** repo jest prywatne, wiec klon wymaga dostepu.
Najczystszy wariant to dodanie `jedrzej82/sts-kb` do repozytoriow
skonfigurowanych dla zadania w Claude — wtedy `git clone` dziala bez
zadnego tokenu trzymanego w plikach. Wariant zapasowy (PAT w pliku na
Dysku) dziala, ale wklada sekret tam, gdzie dotad zadnego nie bylo.

## Aktualizacja

Zmiana modelu = commit. Koniec z `kb_skrypty_dodatek v5r`.

```bash
git add -A && git commit -m "sezon.py: korekta xG dla lig bez statystyk" && git push
```

---
Pierwszy commit zlozony automatycznie 2026-09-21 ze stanu `kb/`
odtworzonego z archiwow v3 + v5b…v5q.
