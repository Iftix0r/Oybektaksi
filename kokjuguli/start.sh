#!/bin/bash

# Hozirgi papkaga o'tish (qayerdan ishga tushirilsa ham to'g'ri ishlashi uchun)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ -f "bot.pid" ]; then
    PID=$(cat bot.pid)
    if ps -p $PID > /dev/null; then
        echo "Bot allaqachon ishlayapti. PID: $PID"
        exit 1
    else
        echo "Eski PID fayli topildi, o'chirilmoqda..."
        rm bot.pid
    fi
fi

echo "Bot ishga tushirilmoqda..."
# Botni orqa fonda (background) ishga tushirish va loglarni bot.log ga yozish
nohup python3 bot.py > bot.log 2>&1 &
PID=$!
echo $PID > bot.pid

echo "Bot muvaffaqiyatli ishga tushdi! Orqa fonda ishlamoqda."
echo "Jarayon (Process) ID: $PID"
echo "Loglarni ko'rish uchun: tail -f bot.log"
