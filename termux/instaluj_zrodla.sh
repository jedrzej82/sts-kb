#!/data/data/com.termux/files/usr/bin/bash
# Jednorazowa instalacja dodatkowych zrodel (termux/zrodla.py) na telefonie — 03.10.2026.
#   curl -fsSL https://raw.githubusercontent.com/jedrzej82/sts-kb/main/termux/instaluj_zrodla.sh | bash
# Tworzy ~/zrodla.sh (pobiera najnowszy zrodla.py z main, uruchamia, wysyla wyniki na Dysk tym samym rclone co kursy)
# i dopisuje do crontaba uruchomienie 10 min po kursach (11:40, 14:40, 17:40, 20:40). Ponowne uruchomienie nic nie dubluje.
set -e
H=/data/data/com.termux/files/home
cat > "$H/zrodla.sh" <<'SKRYPT'
#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:/system/bin:$PATH
cd /data/data/com.termux/files/home
curl -fsSL https://raw.githubusercontent.com/jedrzej82/sts-kb/main/termux/zrodla.py -o zrodla.py
python zrodla.py "$@"
rclone move /sdcard/Download/ gdrive:zrodla/ --include "zrodla_*.zip"   # zapas, gdy zrodla.py nie wyslal sam
SKRYPT
chmod +x "$H/zrodla.sh"
LINIA="40 11,14,17,20 * * * PATH=/data/data/com.termux/files/usr/bin:/system/bin $H/zrodla.sh >> $H/zrodla.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'zrodla.sh' ; echo "$LINIA" ) | crontab -
echo "OK: ~/zrodla.sh gotowy, crontab:"; crontab -l
