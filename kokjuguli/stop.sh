#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ -f "bot.pid" ]; then
    PID=$(cat bot.pid)
    if ps -p $PID > /dev/null; then
        echo "Bot to'xtatilmoqda... (PID: $PID)"
        kill $PID
        rm bot.pid
        echo "Bot to'xtatildi."
    else
        echo "Bot ishlamayapti (PID fayl eskirgan)."
        rm bot.pid
    fi
else
    echo "bot.pid fayli topilmadi."
    echo "Shunday bo'lsa-da, jarayon nomidan izlab to'xtatishga urinib ko'ramiz..."
    pkill -f "python3 bot.py"
    if [ $? -eq 0 ]; then
        echo "Bot jarayoni topildi va to'xtatildi."
    else
        echo "Bot jarayoni topilmadi, bot hozir ishlamayapti."
    fi
fi
