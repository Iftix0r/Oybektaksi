import asyncio
import re
import json
import os
import logging
import html
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

# === SOZLAMALAR ===
BOT_TOKEN = "7954069564:AAESRHyiHwtu6HtNz-KFoQgOwrnwyJf4_y0"
ADMIN_ID = 5212570406           # Lichkadan kelgan zakazlar yuboriladigan admin
ORDER_GROUP_ID = -1002257821437 # Guruhdan kelgan zakazlar yuboriladigan guruh
USERS_FILE = "users.json"

# 1. LOGLARNI SOZLASH (Xatoliklarni ko'rish va kuzatish uchun)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# 2. XAVFSIZ FAYL BILAN ISHLASH (Lock)
user_lock = asyncio.Lock()

async def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            logger.error(f"Foydalanuvchilarni o'qishda xatolik: {e}")
            return set()
    return set()

async def save_user(user_id):
    async with user_lock:
        users = await load_users()
        if user_id not in users:
            users.add(user_id)
            try:
                with open(USERS_FILE, "w") as f:
                    json.dump(list(users), f)
            except Exception as e:
                logger.error(f"Foydalanuvchini saqlashda xatolik: {e}")

# Xabarni ma'lum vaqtdan so'ng o'chirish uchun orqa fon (background) vazifasi
async def delete_message_later(chat_id: int, message_id: int, delay: int = 10):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramAPIError:
        pass # Agar xabar allaqachon o'chirilgan bo'lsa xato bermasligi uchun

# LICHKA: /start komandasi
@dp.message(Command("start"), F.chat.type == "private")
async def start_handler(message: types.Message):
    await save_user(message.from_user.id)
    # 3. YAXSHILANGAN START XABARI
    welcome_text = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🚕 <i>Taksi buyurtma berish botiga xush kelibsiz!</i>\n\n"
        "📝 <b>Zakazingizni yozing:</b>\n"
        "📍 Qayerdan olasiz?\n"
        "🏁 Qayerga borasiz?\n"
        "📞 Telefon raqamingiz?"
    )
    await message.answer(welcome_text)

# LICHKA: Har qanday boshqa xabar (Zakaz sifatida qabul qilish)
@dp.message(F.chat.type == "private")
async def private_order_handler(message: types.Message):
    user_id = message.from_user.id
    users = await load_users()
    
    if user_id not in users:
        await message.answer("Iltimos, avval /start tugmasini bosing.")
        return
        
    # 4. XAVFSIZ HTML ESCAPE (Buziq belgilarni to'g'irlash)
    first_name = html.escape(message.from_user.first_name or "Mijoz")
    username = f"@{html.escape(message.from_user.username)}" if message.from_user.username else ""
    user_link = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
    
    text = html.escape(message.text or message.caption or "📎 Media fayl")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Bog'lanish", url=f"tg://user?id={user_id}")]
    ])
    
    order_text = (
        f"🆕 <b>YANGI ZAKAZ (Lichka)</b>\n\n"
        f"👤 {user_link} {username}\n"
        f"📱 <code>{user_id}</code>\n\n"
        f"📝 <b>Buyurtma:</b> {text}"
    )
    
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            photo_id = photos.photos[0][0].file_id
            await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=order_text, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=order_text, reply_markup=keyboard)
            
        reply_text = "✅ <b>Zakazingiz qabul qilindi!</b>\n\nTez orada haydovchilarimiz siz bilan bog'lanadi. 🚗"
        await message.answer(reply_text)
    except Exception as e:
        logger.error(f"Lichka zakazida xatolik: {e}")
        await message.answer("❌ Uzr, xatolik yuz berdi. Iltimos qayta urinib ko'ring.")

# GURUHLAR: Asosiy logikasi (Buyurtma guruhidan tashqari barcha guruhlar)
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def group_handler(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id == ORDER_GROUP_ID or message.from_user.is_bot:
        return

    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if bot_member.status not in ("administrator", "creator"):
            return 
            
        user_member = await bot.get_chat_member(chat_id, user_id)
        if user_member.status in ("administrator", "creator"):
            return 
    except TelegramAPIError as e:
        logger.warning(f"Guruh a'zolarini tekshirishda xato (chat_id: {chat_id}): {e}")
        return 

    text = message.text or message.caption or ""
    is_ad = False
    
    # 5. KUCHAYTIRILGAN REKLAMA TEKSHIRUVI
    emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]')
    link_pattern = re.compile(r'(http|https|www\.|t\.me|@)', re.IGNORECASE)
    # Qo'shimcha spam so'zlari
    ad_words = re.compile(r'\b(obuna|silka|kirish|qoshil|kanalga|obuna boling)\b', re.IGNORECASE)
    
    # Kengaytirilgan filtr
    if len(text) > 45 or emoji_pattern.search(text) or link_pattern.search(text) or ad_words.search(text) or message.sticker:
        is_ad = True
        
    if is_ad:
        try:
            await message.delete()
        except TelegramAPIError:
            pass
            
        ad_text = "⚠️ <b>Reklama berib ishlashmoqchi bo'lsangiz @FARSAJ_6363 bilan bog'laning!</b>"
        try:
            sent_msg = await message.answer(ad_text)
            asyncio.create_task(delete_message_later(chat_id, sent_msg.message_id, 10))
        except TelegramAPIError:
            pass
    
    else:
        # Xabar REKLAMA emas, zakaz sifatida qabul qilinadi
        first_name = html.escape(message.from_user.first_name or "Username yo'q")
        username = f"@{html.escape(message.from_user.username)}" if message.from_user.username else ""
        user_link = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        message_text = html.escape(text if text else "📎 Media fayl")
        
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
            await bot.send_message(chat_id=ORDER_GROUP_ID, text=order_text, reply_markup=keyboard)
            await message.delete()
            
            reply_text = f"✅ {user_link}, siz bilan tez orada haydovchilarimiz bog'lanadi!"
            sent_reply = await message.answer(reply_text)
            asyncio.create_task(delete_message_later(chat_id, sent_reply.message_id, 10))
            
        except Exception as e:
            logger.error(f"Guruh zakazida xatolik: {e}")

async def main():
    logger.info("Bot ishga tushdi...")
    try:
        # 6. Optimizatsiya qilingan polling (faqat kerakli update'larni oladi)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close() # Bot o'chganda session ni toza yopish

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi!")
