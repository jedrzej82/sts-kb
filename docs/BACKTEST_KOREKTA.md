# Backtest korekty rynków (korekta_rynkow_v5n) — 30.09.2026

**Decyzja: zostaje obecna korekta `(trafność − P) · n/(n+300)`, tylko w dół.** Mocniejsze warianty pogarszają wynik poza próbą.

## Pytanie
Tabela `korekta_rynkow_v5n.csv` w kilku komórkach odejmuje ułamek widocznego zawyżenia
(np. rynek „1” przy P ≥ 90%: model 93,9%, trafność 77,2%, korekta −1,8 pp; „12” ≥ 90%: 93,3% vs 85,2%, korekta −1,7 pp).
Czy należy korygować mocniej?

## Metoda
- Wiersze walk-forward z `ensemble.build_rows()` (2025-08-01 … 2026-09-30, 82 738 meczów, 392 484 nogi z P ≥ 70%),
  wagi z `ensemble_wagi.json`.
- Tabela korekty liczona **wyłącznie na danych przed datą cięcia**, oceniana na danych po niej
  (5 cięć: 2025-12-01, 2026-01-01, 2026-03-01, 2026-05-01, 2026-07-01). Reguła „poniżej −4 pp” w obu wariantach.
- Warianty:
  - **stara**: `min(0, (T − P) · n/(n+300))`, wagi czasowe z półokresem 180 dni;
  - **CI**: mocniejsza z (stara, górna granica 80% przedziału ufności luki), `n_eff` Kisha ≥ 20;
  - **z < −2 / z < −3**: jak CI, ale tylko w komórkach, gdzie luka w danych uczących jest istotna (z < −2 albo z < −3).

## Wynik (Brier / log loss na danych po cięciu)

| cięcie | stara | CI | z < −2 | z < −3 |
|---|---|---|---|---|
| 2025-12-01 | 0.149673 / 0.469931 | — | 0.149950 / 0.470449 | 0.149949 / 0.470447 |
| 2026-01-01 | 0.14926 / 0.46881 | 0.14950 / 0.46930 | 0.149499 / 0.469296 | 0.149499 / 0.469307 |
| 2026-03-01 | 0.14939 / 0.46905 | 0.14943 / 0.46907 | 0.149431 / 0.469065 | 0.149434 / 0.469094 |
| 2026-05-01 | 0.14881 / 0.46737 | 0.14888 / 0.46747 | 0.148882 / 0.467468 | 0.148886 / 0.467503 |
| 2026-07-01 | 0.148651 / 0.466382 | — | 0.148708 / 0.466540 | 0.148708 / 0.466539 |

Każdy mocniejszy wariant jest gorszy przy **każdym** cięciu. Średnio model piłkarski przy P ≥ 70% jest raczej
*niedoszacowany* (P − trafność ≈ −1,1 pp), więc dodatkowe obniżanie P w komórkach, które w danych uczących wyglądały
na zawyżone, nie przenosi się na późniejsze mecze.

## Co zostaje zabezpieczone inaczej
Komórki trwale zawyżone są wyłączone z kuponów regułą `RYNKI_ZAWYZONE_P70` w `typuj.py`
(U2.5, BTTS_nie, BTTS_tak, „2” przy P ≥ 70% — Poprawka 58.5). Rynki P ≥ 90% mają kursy ok. 1,05–1,10 i praktycznie nie
dają EV > 0 po podatku.

## Kiedy wrócić do tematu
Po zebraniu ≥ 30 rozliczonych **własnych** nóg w danej komórce (rynek × przedział P) — wtedy `korekta_wlasna.csv`
(uczenie na rozliczonych typach) jest właściwym narzędziem, a nie backtest całej bazy.

# pi-ratings: średnia ligi ściągana do globalnej (pi.K_LIGA = 50) — 30.09.2026

**Usterka:** `fit_pi_glm` mnożył λ przez średnią goli ligi liczoną z samych jej meczów. Liga z kilkoma meczami
(np. same 0:0) dawała współczynnik 0 → λ = 0 → zdegenerowane rynki w zespole (214 meczów w backteście 2025/26;
w `ensemble.comb` log(0) = −∞).

**Poprawka:** średnia ligi = (suma goli + K · średnia globalna) / (liczba meczów + K).

**Backtest** (pi dopasowane na 4 latach przed cięciem, test: 3 miesiące po cięciu, log loss Poissona obu drużyn):

| cięcie | meczów | K = 0 (było) | przypadków λ = 0 | K = 5 | K = 10 | K = 20 | K = 50 |
|---|---|---|---|---|---|---|---|
| 2025-10-01 | 11 966 | 3.15894 | 42 | 3.02383 | 3.01257 | 3.00737 | **3.00658** |
| 2026-01-01 | 15 520 | 2.93516 | 15 | 2.91636 | 2.91346 | 2.91140 | **2.91118** |
| 2026-04-01 | 16 083 | 3.03608 | 94 | 2.96839 | 2.96534 | 2.96304 | **2.96230** |
| 2026-07-01 | 13 359 | 2.98779 | 0 | 2.98637 | 2.98545 | 2.98436 | **2.98334** |

Każde K > 0 jest lepsze od stanu poprzedniego przy każdym cięciu; K = 50 najlepsze z badanych. Przy K = 50 nie ma już λ = 0.

# Hokej: kalibracja `sporty.p_gospodarza` — 30.09.2026

**Decyzja: bez korekty.** Wrzesień 2026 wyglądał na zawyżony (P 0,626 vs trafność 0,579, n = 558, ok. 2σ),
ale na całym sezonie model hokejowy jest skalibrowany, a korekta nie przenosi się poza próbę.

**Metoda:** pi/Elo z `sporty.elo` dopasowane na danych sprzed każdego tygodnia, P z `p_gospodarza` (produkcja),
mecze z ≥ 10 meczami obu drużyn, bez remisów; 2025-10-01 … 2026-09-28, 8 704 mecze.

| przedział P (faworyt) | n | P | trafność |
|---|---|---|---|
| 0,5–0,6 | 4 543 | 0,555 | 0,553 |
| 0,6–0,7 | 1 454 | 0,638 | 0,627 |
| 0,7–0,8 | 2 444 | 0,742 | 0,756 |
| 0,8–0,9 | 263 | 0,807 | 0,867 |

Platt (a·logit P + b) i sama skala uczone przed cięciem, log loss po cięciu (bez korekty / Platt / skala):

| cięcie | a | log loss |
|---|---|---|
| 2025-12-01 | 1,019 | 0,63316 / 0,63320 / 0,63306 |
| 2026-01-01 | 1,039 | 0,63138 / 0,63108 / 0,63127 |
| 2026-02-01 | 1,045 | 0,63277 / 0,63251 / 0,63263 |
| 2026-03-01 | 1,072 | 0,64179 / 0,64160 / 0,64187 |
| 2026-04-01 | 1,080 | 0,65039 / 0,65042 / 0,65071 |
| 2026-09-01 | 1,097 | 0,67423 / 0,67682 / 0,67673 |

Wyuczone a > 1 (model raczej *niedoszacowany*), zyski ≤ 0,0003, a na wrześniu 2026 korekta wyraźnie szkodzi.
Początek sezonu nie jest systematycznie zawyżony: wrzesień 2025 P 0,600 vs trafność 0,646 (n = 364).
Obniżanie P w hokeju nie ma oparcia w danych; wrócić po ≥ 30 rozliczonych własnych nogach hokejowych.

## Koszykówka i piłka ręczna — ta sama metoda (30.09.2026)

**Decyzja: bez korekty (nie podnosimy P).** Na całym sezonie oba sporty wyglądają na mocno *niedoszacowane*
(kosz: P 0,645 vs trafność 0,738 w przedziale 0,6–0,7; ręczna: 0,652 vs 0,772), Platt uczy a ≈ 2.
Przyczyna to krótka historia w bazie: ligi spoza NBA/NHL są w niej dopiero od lipca 2025, więc jesienią 2025 oceny
drużyn były ściągnięte do średniej. Z każdym miesiącem średnie P rośnie (kosz: 0,592 w 10.2025 → 0,659 w 09.2026),
a trafność stoi (~0,68). We wrześniu 2026 koszykówka jest skalibrowana (P 0,659 vs 0,662, n = 619), a korekta
uczona na wcześniejszych danych psuje wynik: log loss 0,61740 → 0,65169 (Platt) / 0,65146 (skala).
Ręczna we wrześniu 2026: P 0,713 vs 0,776, ale n = 143 — za mało, by luzować limity (CZĘŚĆ A).
Wrócić w styczniu 2027 (sezon z pełną roczną historią) albo po ≥ 30 rozliczonych własnych nogach.
