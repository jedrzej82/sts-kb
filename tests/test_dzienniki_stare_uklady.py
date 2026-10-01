"""01.10.2026 (Raport 12:00, USTERKA 7): pliki dziennikow z 20-24.09 mialy inne uklady kolumn i wypadaly ze scalania
(dni na zawsze poza kalibracja i CLV); 24-25.09 P zapisywano w procentach („37.8”) — w ucz.py/sporty.py takie wiersze
wypadaly z przedzialow albo psuly srednie („srednie P 2945%”). Uklady odtworzone z prawdziwych plikow."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dzienniki  # noqa: E402


def _zapisz(kat, nazwa, tresc, i):
    p = kat / nazwa
    p.write_text(tresc, encoding='utf-8')
    os.utime(p, (1_000_000 + i, 1_000_000 + i))


def test_stare_uklady_typy_log(tmp_path):
    _zapisz(tmp_path, 'typy_log 2026-09-19.csv', 'data,gosp,gość,rynek,p,trafiony,kurs_typu,pieniadze\n'
            '2026-09-19,Istra 1961,HNK Gorica,1,0.477,,,\n', 0)
    # 20.09: gospodarz/gosc, godzina „jutro 02:30”, przecinek bez cudzyslowu w ostatniej kolumnie, inny sport
    _zapisz(tmp_path, 'typy_log 2026-09-20 21_00 (okno).csv',
            'data,godzina_uruchomienia,sport,liga,gospodarz,gosc,godzina_meczu,rynek,P,zrodlo_P,status\n'
            '2026-09-20,21:00,piłka,ARG,Platense,Newell\'s Old Boys,22:00,1,0.429,sezon,bez kontroli\n'
            '2026-09-20,21:00,piłka,ARG,Velez Sarsfield,Tigre,jutro 02:30,1X,0.760,sezon,bez kontroli (jutro, -2pp)\n'
            '2026-09-20,21:00,koszykowka,WNBA,Indiana Fever,Washington Mystics,22:00,1,0.597,sezon,N=8\n', 1)
    # 23.09: zdarzenie „A - B”
    _zapisz(tmp_path, 'typy_log 2026-09-23 12_00.csv', 'data,sport,liga,zdarzenie,godzina,rynek,P,zrodlo_P,status\n'
            '2026-09-23,pilka,USL,Birmingham Legion FC - Brooklyn FC,18:00,12,0.783,typuj.py,ok\n', 2)
    # 23.09 21:00: data_meczu, P w procentach, kurs
    _zapisz(tmp_path, 'typy_log 2026-09-23 21_00 (delta).csv',
            'data_meczu,godzina,liga,gospodarz,gosc,rynek,P,zrodlo_P,status,kurs,marza,tag\n'
            '2026-09-23,22:00,PER,ADT Tarma,Cienciano,1X,65.0,sezon,OK,1.75,107.7,AKOP_K5d\n', 3)
    dzienniki.scal(str(tmp_path), cel=str(tmp_path))
    d = dzienniki._czytaj(tmp_path / 'typy_log.csv')
    assert list(d.columns) == dzienniki.KOLUMNY_LOGU['typy_log']
    w = {(r.data, r.gosp, r['gość'], r.rynek): (r.p, r.kurs_typu) for _, r in d.iterrows()}
    assert w == {('2026-09-19', 'Istra 1961', 'HNK Gorica', '1'): ('0.477', ''),
                 ('2026-09-20', 'Platense', "Newell's Old Boys", '1'): ('0.429', ''),
                 ('2026-09-21', 'Velez Sarsfield', 'Tigre', '1X'): ('0.760', ''),          # „jutro” = dzien pozniej
                 ('2026-09-23', 'Birmingham Legion FC', 'Brooklyn FC', '12'): ('0.783', ''),
                 ('2026-09-23', 'ADT Tarma', 'Cienciano', '1X'): ('0.65', '1.75')}        # 65.0 -> 0.65


def test_stare_uklady_sporty_typy(tmp_path):
    _zapisz(tmp_path, 'sporty_typy 2026-09-23 12_00.csv', 'data,sport,liga,zdarzenie,godzina,rynek,P,zrodlo_P,status\n'
            '2026-09-23,tenis,ATP,Royer Valentin - Walton Adam,13:30,zwyciezca: Valentin Royer,0.547,tenis.py,OK\n'
            '2026-09-23,tenis,ITF,Bulgaru Miriam Bianca - Ebeling Koning Loes,13:04,zwyciezca: Ebeling Koning L.,0.8,t,s\n'
            '2026-09-23,siatkowka,X,Kamerun - Algieria,18:00,-,-,x,y\n', 0)
    _zapisz(tmp_path, 'sporty_typy 2026-09-23 21_00 (delta).csv',
            'data_meczu,godzina,sport,turniej,zawodnik_a,zawodnik_b,rynek,P,zrodlo_P,status,kurs,tag\n'
            '2026-09-23,23:30,tenis,CH,Francisco Comesana,Joaquin Aguilar Cardozo,2,50.8,tenis.py,OK,2.60,\n', 1)
    _zapisz(tmp_path, 'sporty_typy 2026-09-24 12_00.csv', 'data,sport,zdarzenie,rynek,P_model,P_sezon,N,status,kurs,marza,tag\n'
            '2026-09-24,tenis,Cerundolo Juan Manuel - Zhou Yi,1,79.8,56.5,3,mala proba,1.45,106.0,AKOP_\n', 2)
    dzienniki.scal(str(tmp_path), cel=str(tmp_path))
    d = dzienniki._czytaj(tmp_path / 'sporty_typy.csv')
    assert list(d.columns) == dzienniki.KOLUMNY_LOGU['sporty_typy']
    w = {(r.gosp, r.gosc): (r.rynek, r.p, r.kurs_typu) for _, r in d.iterrows()}
    assert w == {('Royer Valentin', 'Walton Adam'): ('1', '0.547', ''),         # te same slowa, inna kolejnosc
                 ('Bulgaru Miriam Bianca', 'Ebeling Koning Loes'): ('zwyciezca: Ebeling Koning L.', '0.8', ''),  # skrot — bez zgadywania
                 ('Francisco Comesana', 'Joaquin Aguilar Cardozo'): ('2', '0.508', '2.60'),
                 ('Cerundolo Juan Manuel', 'Zhou Yi'): ('1', '0.798', '1.45')}
    # wiersz bez liczbowego P (Kamerun - Algieria „-”) pominiety; kolumna p cala liczbowa
    assert pd.read_csv(tmp_path / 'sporty_typy.csv').p.dtype == float


def test_obecny_uklad_bez_zmian(tmp_path):
    tresc = 'data,gosp,gość,rynek,p,trafiony,kurs_typu,pieniadze\n2026-09-30,A,B,1X,0.81,1,1.30,1\n'
    _zapisz(tmp_path, 'typy_log 2026-09-30.csv', tresc, 0)
    dzienniki.scal(str(tmp_path), cel=str(tmp_path))
    assert (tmp_path / 'typy_log.csv').read_text(encoding='utf-8') == tresc
