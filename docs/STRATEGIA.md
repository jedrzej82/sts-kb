# Strategia systemu STS — po Poprawce 55 (29.09.2026)

Zrodla: trzy audyty z 29.09.2026 — kod (commit `98cd911`), reguly (INSTRUKCJA v6e + POPRAWKI do wyd. 33),
wyniki przebiegow 21–28.09.

## 1. Diagnoza

| Obszar | Stan | Dowod |
|---|---|---|
| Niezawodnosc | **8 z 32** przebiegow bez raportu; od 25.09 brak rozliczen | 26.09 caly dzien, 27.09 12/15, 28.09 12; rozliczenie tylko o 12:00 |
| Pomiar | brak CLV, brak porownania z rynkiem | nigdzie w kodzie ani w Bilansie |
| Wynik | 5 kuponow, 14 zl, **−4,43 zl (ROI −31,6%)** | Bilans 2026-09-25 — proba za mala na jakikolwiek wniosek |
| Nazwy | ~20 tabel aliasow (~1300 wpisow), 8 roznych `norm()` | Poprawki 42–55 prawie wylacznie aliasy |
| Bramki | reguly egzekwowane tylko przez LLM czytajacy tekst | `drugie_zrodlo()` — wynik wyrzucany (naprawione w tym PR dla typuj.py) |
| Kalibracja | wszystkie pliki z 21.09, sprzed naprawy 19 392 dat (P47) | `git log` plikow `*_kalibracja*`, `ensemble_wagi.json` |
| Reguly | ~130 tys. znakow prozy na przebieg, sprzecznosci v6e vs P48 | audyt regul |

## 2. Problem strategiczny

Kupony AKO/K5 skladane z nog po 1,10–1,46 przy podatku 12% nie moga miec EV > 0:

| kurs | wymagane P |
|---|---|
| 1,20 | 94,7% |
| 1,30 | 87,4% |
| 1,46 | 77,8% |

Przy marzy 104–110% to niemal niemozliwe — dlatego wszystkie AKO wychodza z EV od −4% do −48%.
**Cel „kupon ~80%” jest sprzeczny z celem „wykazac przewage do 15.11”.** Decyzja: kupony wysokiego
prawdopodobienstwa zostaja wylacznie papierowe (pomiar kalibracji), a pieniadze ida tylko na nogi
z EV > 0 po bramce, glownie pojedyncze (K3), gdzie przewaga ma szanse przetrwac podatek.

## 3. Decyzje

1. **Kod przed proza.** Kazda regula liczbowa (EV, Kelly, progi, limity, bramki) trafia do kodu z testem.
   Proza opisuje tylko to, czego kod nie moze (weryfikacja kursu w aplikacji, nieobecnosci).
2. **Nazwy: stop kolejnym aliasom w kodzie.** Nowe pary tylko do jednego rejestru danych (faza 2);
   do tego czasu kazda nowa para = przypadek w `tests/test_nazwy.py`.
3. **Pomiar przed skalowaniem.** Zadnego podnoszenia stawek, dopoki nie ma CLV z ≥100 nog (juz w CZESCI A pkt 4).
4. **Rozliczenie nie moze zalezec od jednego przebiegu.**
5. **Zmiany w regulach na Drive publikuje uzytkownik** — kazdy przebieg je czyta, a w grze sa pieniadze.

## 4. Plan

### Faza 1 — fundament (ten PR)
- [x] `sezon.norm`: formy prawne tylko jako cale czlony, ł/ø/ß (Schalke, Hearts Scotland, Śląsk)
- [x] `typuj.py`: wynik bramki P48 uzyty — EV i Kelly do kuponu z P po bramce, jawne NIE NA KUPON
- [x] cichy `except` w `sezon._alias` -> ostrzezenie
- [x] pyflakes: niezdefiniowane `dni` (uzupelnij_ligi), `last_div` (eksport), nieuzywane importy
- [x] `tests/` — zloty zestaw nazw + bramka; znane defekty jako `xfail(strict)`
- [x] CI (GitHub Actions): pyflakes, kompilacja, pytest
- [x] `sporty.py`: jedna linia WERDYKT laczaca bramki (wspolna skala, drugie zrodlo, dane rywala)
- [ ] Poprawka 56 na Drive — projekt w `docs/POPRAWKA_56_projekt.md`, do zatwierdzenia

### Faza 2 — niezawodnosc i czas (1 tydzien)
- `kb.sqlite` budowany raz na dobe w GitHub Actions i publikowany jako release; przebieg tylko pobiera
  (~20 min mniej na przebieg — glowna przyczyna przekroczen czasu). Wymaga ustalenia, skad Actions
  bierze pliki `zewn/` i arkusze (dzis przez Drive).
- `build_kb.norm`: przestac usuwac lata z nazw (Metalist 1925 != Metalist) i dodac ł/ø — **tylko razem
  z porownaniem sklejen przed/po** na pelnej przebudowie bazy.
- Przeliczyc `ensemble.py` i `korekta_rynkow.py` na poprawionej bazie; `przebieg.py` ostrzega, gdy
  kalibracja starsza niz 7 dni.

### Faza 3 — tozsamosc druzyn (2 tygodnie)
- Rejestr encji: `entity(id, sport, rodzaj, kraj, nazwa, rok_zal, plec, poziom)` + `alias(entity_id, zrodlo, nazwa, liga)`.
  Migracja ~20 tabel do danych; jedna funkcja `normalize()`.
- Dopasowanie oferty **po meczu**: liga + data ±1 dzien + obie druzyny naraz; akceptacja tylko przy
  jednoznacznym trafieniu. Usuwa klase bledow Independiente Yumbo / CD Inca / Athletic Club.
- Zdjecie `xfail` z dwoch testow znanych defektow.

### Faza 4 — model i przewaga (do 15.11)
- CLV: kurs w chwili typu i kurs zamkniecia dla kazdej nogi (takze papierowej).
- Backtest bramki P48; zastapienie `min(P)` mieszanka w logit z waga z backtestu + kalibracja na holdoucie.
- `kupon.py`: skladanie kuponow w kodzie (JSON), LLM tylko prezentuje i weryfikuje kursy.
- Instrukcja v7: poprawki 1–56 scalone, sprzecznosci usuniete, cel < 30 tys. znakow.

## 5. Kryteria sukcesu na 15.11

- ≥ 95% przebiegow z raportem, rozliczenie kazdego dnia.
- ≥ 100 rozliczonych nog z CLV; decyzja o przewadze wg CZESCI A (CLV, p < 0,05, 2 tygodnie).
- Blad kalibracji ≤ 5 pp w kazdym koszyku P z n ≥ 30.
- Zero nowych aliasow w kodzie od fazy 3.
