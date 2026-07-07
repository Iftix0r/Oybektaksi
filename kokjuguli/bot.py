import asyncio
import re
import json
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# === SOZLAMALAR ===
BOT_TOKEN = "7954069564:AAESRHyiHwtu6HtNz-KFoQgOwrnwyJf4_y0"
ADMIN_ID = 5212570406           # Lichkadan kelgan zakazlar yuboriladigan admin
ORDER_GROUP_ID = -1002257821437 # Guruhdan kelgan zakazlar yuboriladigan guruh
USERS_FILE = "users.json"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Foydalanuvchilarni saqlash tizimi
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, "w") as f:
            json.dump(list(users), f)

# Xabarni ma'lum vaqtdan so'ng o'chirish uchun orqa fon (background) vazifasi
async def delete_message_later(chat_id: int, message_id: int, delay: int = 10):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass # Agar xabar allaqachon o'chirilgan bo'lsa, xato bermasligi uchun

# 1. LICHKA: /start komandasi
@dp.message(Command("start"), F.chat.type == "private")
async def start_handler(message: types.Message):
    save_user(message.from_user.id)
    welcome_text = "👋 Assalomu alaykum!\n\n📝 Zakazingizni yozing (qayerga borasiz, telefon raqam va boshqa ma'lumotlar):"
    await message.answer(welcome_text)

# 2. LICHKA: Har qanday boshqa xabar (Zakaz sifatida qabul qilish)
@dp.message(F.chat.type == "private")
async def private_order_handler(message: types.Message):
    user_id = message.from_user.id
    users = load_users()
    
    # Agar start bosmagan bo'lsa, javob bermaymiz (yoki start bosishni so'rash mumkin)
    if user_id not in users:
        return
        
    first_name = message.from_user.first_name or "Mijoz"
    username = f"@{message.from_user.username}" if message.from_user.username else ""
    user_link = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
    
    text = message.text or message.caption or "📎 Media fayl"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Bog'lanish", url=f"tg://user?id={user_id}")]
    ])
    
    order_text = (
        f"🆕 <b>YANGI ZAKAZ (Lichka)</b>\n\n"
        f"👤 {user_link} {username}\n"
        f"📱 <code>{user_id}</code>\n\n"
        f"📝 {text}"
    )
    
    try:
        # Profil rasmini olishga harakat qilamiz
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            photo_id = photos.photos[0][0].file_id
            await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=order_text, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=order_text, reply_markup=keyboard)
    except Exception as e:
        # Agar adminni topolmasa yoki rasm yuborishda xatolik bo'lsa, matnli xabar yuborish
        await bot.send_message(chat_id=ADMIN_ID, text=order_text, reply_markup=keyboard)
        
    reply_text = "✅ Zakazingiz qabul qilindi! Tez orada shopirlar siz bilan bog'lanadi."
    await message.answer(reply_text)

# 3. GURUHLAR: Asosiy logikasi (Buyurtma guruhidan tashqari barcha guruhlar)
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def group_handler(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Buyurtmalar yig'iladigan guruhda hech narsa qilmaymiz
    if chat_id == ORDER_GROUP_ID:
        return
        
    # Bot o'z xabarlariga reaksiya qilmasligi uchun
    if message.from_user.is_bot:
        return

    try:
        # Bot guruhda adminmi yo'qmi tekshirish
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if bot_member.status not in ("administrator", "creator"):
            return # Bot admin bo'lmasa, xabarlarni o'chira olmaydi, shuning uchun to'xtaymiz
            
        # Foydalanuvchi guruhda adminmi yo'qmi tekshirish
        user_member = await bot.get_chat_member(chat_id, user_id)
        if user_member.status in ("administrator", "creator"):
            return # Adminlarga teginmaymiz
            
    except Exception:
        return # Xatolik yuz bersa (guruhdan chiqarilgan bo'lsa va hokazo) to'xtatish

    text = message.text or message.caption or ""
    
    # 4. REKLAMA TEKSHIRUVI
    is_ad = False
    
    emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]')
    link_pattern = re.compile(r'(http|https|www\.|t\.me|@)', re.IGNORECASE)
    
    if len(text) > 40 or emoji_pattern.search(text) or link_pattern.search(text) or message.sticker:
        is_ad = True
        
    if is_ad:
        try:
            await message.delete()
        except Exception:
            pass
            
        ad_text = "Reklama berib ishlashmoqchi bo'lsangiz @FARSAJ_6363 bilan bog'laning"
        sent_msg = await message.answer(ad_text)
        asyncio.create_task(delete_message_later(chat_id, sent_msg.message_id, 10))
    
    else:
        # Xabar REKLAMA emas, zakaz sifatida qabul qilinadi
        first_name = message.from_user.first_name or "Username yo'q"
        username = f"@{message.from_user.username}" if message.from_user.username else ""
        user_link = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        message_text = text if text else "📎 Media fayl"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Bog'lanish", url=f"tg://user?id={user_id}")]
        ])
        
        order_text = (
            f"🆕 <b>YANGI ZAKAZ (Guruh)</b>\n\n"
            f"👤 {user_link}\n"
            f"🔖 {username}\n"
            f"📱 <code>{user_id}</code>\n\n"
            f"📝 {message_text}"
        )
        
        try:
            # 1. Zakazni buyurtmalar guruhiga yuborish
            await bot.send_message(chat_id=ORDER_GROUP_ID, text=order_text, reply_markup=keyboard)
            
            # 2. Asl xabarni guruhdan o'chirish
            await message.delete()
            
            # 3. Javob yozish
            reply_text = f"{first_name}, siz bilan tez orada haydovchilarimiz bog'lanadi"
            sent_reply = await message.answer(reply_text)
            
            # 4. Javobni 10 soniyadan so'ng o'chirish
            asyncio.create_task(delete_message_later(chat_id, sent_reply.message_id, 10))
            
        except Exception as e:
            print(f"Xatolik: {e}")

async def main():
    print("Bot ishga tushdi...")
    # Pollingni boshlash (webhook o'rniga, tezkor va xavfsiz)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
