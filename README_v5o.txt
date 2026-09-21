DODATEK v5o (20.09.2026) — koszykówka: zespół Elo + model marży punktowej. Bez kursów.
sporty.py (nadpisuje v5c/v5n): dla sportów z sporty_param.json (na razie koszykówka) P = Platt(0,1·logit P_Elo + 0,9·logit P_marży);
  wypisuje też przewidywaną różnicę punktów i odchylenie (13,7 pkt) — przydatne przy handicapach.
sporty_bt.py SPORT — test: uczenie 4 lata przed 07.2024, test 07.2024–09.2026 (NBA+WNBA, 3405 meczów):
  logloss obecny (Elo + mapa kalibracji) 0,6095 → zespół v5n 0,6053; P 75–80% → 78% trafień, 80–85% → 87%, 85–90% → 84%.
  Futbol amer. i baseball: poprawa pomijalna (0,6283→0,6279; 0,6871→0,6859) — NIE włączone.
tenis_bt.py — strojenie Elo tenisa (K, waga nawierzchni, gemy jako margines) + kalibracja Platta: wynik RÓWNY obecnemu modelowi
  z mapą kalibracji (logloss 0,6237 vs 0,6233 na 07.2025–09.2026) — tenis.py BEZ ZMIAN.
