# PROJEKT — Poprawka 56 (do zatwierdzenia przez uzytkownika)

Ten plik NIE jest czytany przez przebiegi. Po zatwierdzeniu uzytkownik publikuje tresc jako nowe wydanie
POPRAWEK na Dysku — dopiero wtedy obowiazuje. Zakladamy, ze PR z tym plikiem jest juz scalony do `main`.

---

## Poprawka 56 (od 2026-09-29)

### 56.1 Werdykt nogi z typuj.py jest wiazacy
`typuj.py` z `--kurs` wypisuje pod kazdym rynkiem linie `→`:
- `→ P do kuponu X%: EV=…  ✔ NOGA DOPUSZCZONA` — tylko taka noga moze wejsc na kupon za pieniadze;
  EV i ¼ Kelly bierz z TEJ linii, nie z linii powyzej (ta liczy z P modelu).
- `→ NIE NA KUPON: …` — noga odpada, takze gdy linia powyzej pokazuje „✔ wartość”.
Nie przeliczaj P recznie i nie odejmuj niczego drugi raz.

KONTROLA W REPO: `grep -c "def werdykt_nogi" kb/typuj.py` → 1. Wynik 0 = obowiazuja stare zasady P48.

### 56.2 Rozliczenie w kazdym przebiegu
Na poczatku KROKU 5 sprawdz, czy istnieje plik „Rozliczenie <dzisiejsza data>”. Jezeli NIE — wykonaj
KROK 5 w tym przebiegu, niezaleznie od godziny. Jezeli brakuje rozliczen z wczesniejszych dni, rozlicz je
najpierw, od najstarszego (stan na 29.09: brak od 25.09).

### 56.3 Kurs zamkniecia (CLV)
Dla KAZDEJ nogi (za pieniadze i papierowej) zapisz w typy_log kurs z chwili typu. W rozliczeniu dopisz
kurs z ostatniego PDF oferty przed poczatkiem meczu i `CLV = kurs_typu / kurs_zamkniecia − 1`.
Brak kursu zamkniecia = puste pole, nie zero. W Bilansie: srednie CLV i liczba nog z CLV.

### 56.4 Foldery
Raport, Dziennik, PULS i Rozliczenie — wylacznie do folderu powiadomien `1mQruedkXbBHlEciIzBNNAeTZQwOgr7hx`.
(24–28.09 cztery raporty trafily do folderu bazy wiedzy.)

### 56.5 Zmiana dopasowania nazw w sezon.py
`sezon.py` przestal ucinac poczatki slow (Schalke, Hearts Scotland, Sporting Achaia, Śląsk). Czesc druzyn,
ktore dotad dawaly NIE ZNALEZIONO, teraz sie znajdzie. Przez 3 dni wypisuj w USTERKACH kazde NOWE
dopasowanie z sezon.py, ktore budzi watpliwosc (inny kraj, inna liga, rezerwy).
