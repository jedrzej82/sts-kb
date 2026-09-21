# Zadanie: wyniki meczów ligowych z Wikipedii (angielskiej) → CSV

Narzędzia: WebFetch (tylko en.wikipedia.org; strona może się nie załadować — spróbuj wariantu URL z %E2%80%93 zamiast "–",
albo polskiej/niemieckiej/lokalnej Wikipedii). NIE używaj narzędzi jina (płatne). Shell nie ma dostępu do internetu poza GitHubem.

Dla każdej przydzielonej ligi/sezonu:
1. WebFetch strony sezonu, prompt w stylu: "Output the full RESULTS MATRIX (home team rows × away team columns) verbatim
   as CSV: first line = column team names in order, each next line = home team name followed by the scores, using
   'x' for the diagonal and '' for not yet played. Also output the league TABLE as CSV: team,P,W,D,L,GF,GA."
   Jeśli liga ma kilka faz (np. runda zasadnicza + championship/relegation round, Apertura/Clausura) — pobierz matryce
   WSZYSTKICH faz (osobne sekcje lub osobne strony). Jeśli strona ma listę meczów z datami — tym lepiej, weź daty.
   Duże matryce (18–20 drużyn) poproś w dwóch częściach (pierwsza i druga połowa wierszy), bo odpowiedź może się uciąć.
2. Zamień na mecze i ZAPISZ do /home/claude/kb/eu/wiki/<KOD>_<sezon>.csv z kolumnami:
   div,season,phase,date,home,away,fh,fa
   (div = kod z przydziału; date = YYYY-MM-DD jeśli znana, inaczej puste; phase np. 'regular','championship','relegation').
3. WALIDACJA (obowiązkowa, w Pythonie): z meczów policz dla każdej drużyny P,W,D,L,GF,GA (suma ze wszystkich faz)
   i porównaj z tabelą ligi z tej samej strony. Plik zostaje TYLKO jeśli wszystko się zgadza (dopuszczalne różnice
   wyłącznie przy odjętych punktach / walkowerach — opisz je). Jeśli się nie zgadza — pobierz ponownie fragment,
   popraw; jeśli nie da się — usuń plik i zgłoś.
4. Na koniec krótki raport: plik, liczba meczów, stan sezonu (do której kolejki / data aktualizacji strony),
   wynik walidacji. Bez zmyślania — jeśli czegoś nie ma, napisz że nie ma.
