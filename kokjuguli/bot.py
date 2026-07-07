import asyncio
import re
import json
import os
import logging
import html
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

# === SOZLAMALAR ===
BOT_TOKEN = "7954069564:AAESRHyiHwtu6HtNz-KFoQgOwrnwyJf4_y0"
ADMIN_ID = 5212570406           # Lichkadan kelgan zakazlar yuboriladigan admin
ORDER_GROUP_ID = -1002257821437 # Guruhdan kelgan zakazlar yuboriladigan guruh
USERS_FILE = "users.json"
CONTACTS_FILE = "contacts.json" # Raqamlarni saqlash uchun

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_lock = asyncio.Lock()
contacts_lock = asyncio.Lock()

async def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
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
            except Exception:
                pass

async def load_contacts():
    if os.path.exists(CONTACTS_FILE):
        try:
            with open(CONTACTS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

async def save_contact(user_id, phone_number, first_name):
    async with contacts_lock:
        contacts = await load_contacts()
        contacts[str(user_id)] = {
            "phone": phone_number,
            "name": first_name
        }
        try:
            with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
                json.dump(contacts, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

async def delete_message_later(chat_id: int, message_id: int, delay: int = 10):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramAPIError:
        pass

# LICHKA: /start komandasi
@dp.message(Command("start"), F.chat.type == "private")
async def start_handler(message: types.Message):
    await save_user(message.from_user.id)
    
    # PASTDAGI TUGMALAR (Raqam va Lokatsiya so'rash)
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True),
                KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )
    
    welcome_text = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🚕 <i>Taksi buyurtma berish botiga xush kelibsiz!</i>\n\n"
        "📝 <b>Zakazingizni yozing:</b>\n"
        "📍 Qayerdan olasiz?\n"
        "🏁 Qayerga borasiz?\n\n"
        "👇 <i>Pastdagi tugmalar orqali tezkor raqamingiz va manzilingizni yuborishingiz mumkin!</i>"
    )
    await message.answer(welcome_text, reply_markup=markup)

# Adminning Reply orqali mijozga javob yozishi
@dp.message(F.reply_to_message)
async def admin_reply_to_user(message: types.Message):
    if message.chat.id not in (ADMIN_ID, ORDER_GROUP_ID):
        return

    if message.reply_to_message.from_user.id != bot.id:
        return

    original_text = message.reply_to_message.text or message.reply_to_message.caption
    if not original_text:
        return

    match = re.search(r"📱 (\d+)", original_text)
    if not match:
        return

    customer_id = int(match.group(1))
    
    if message.text:
        admin_reply_text = html.escape(message.text)
        reply_to_customer = (
            f"👨‍💻 <b>Admindan / Haydovchidan javob:</b>\n\n"
            f"💬 <i>{admin_reply_text}</i>"
        )
        try:
            await bot.send_message(chat_id=customer_id, text=reply_to_customer)
            await message.answer("✅ Javobingiz mijozga yuborildi!")
        except Exception as e:
            logger.error(f"Mijozga javob yuborishda xato: {e}")
            await message.answer("❌ Mijozga xabar yuborib bo'lmadi (bloklagan bo'lishi mumkin).")
    else:
        try:
            caption = message.caption or ""
            formatted_caption = (
                f"👨‍💻 <b>Admindan / Haydovchidan javob:</b>\n\n"
                f"💬 <i>{html.escape(caption)}</i>"
            ) if caption else "👨‍💻 <b>Admindan / Haydovchidan javob</b>"
            
            await message.copy_to(chat_id=customer_id, caption=formatted_caption, parse_mode=ParseMode.HTML)
            await message.answer("✅ Faylli javobingiz mijozga yuborildi!")
        except Exception as e:
            await message.answer("❌ Mijozga fayl yuborib bo'lmadi.")

# LICHKA: Zakazlarni qabul qilish
@dp.message(F.chat.type == "private")
async def private_order_handler(message: types.Message):
    user_id = message.from_user.id
    users = await load_users()
    
    if user_id not in users:
        await message.answer("Iltimos, avval /start tugmasini bosing.")
        return
        
    first_name = html.escape(message.from_user.first_name or "Mijoz")
    username = f"@{html.escape(message.from_user.username)}" if message.from_user.username else ""
    user_link = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
    
    # Raqam yoki lokatsiya yuborilganda maxsus tekst yaratish
    text = ""
    if message.contact:
        phone = message.contact.phone_number
        await save_contact(user_id, phone, message.from_user.first_name)
        text = f"☎️ <b>Kontakt yuborildi:</b> {phone}"
    elif message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        text = f"📍 <b>Lokatsiya yuborildi:</b>\n<a href='https://maps.google.com/?q={lat},{lon}'>Xaritada ko'rish</a>"
    else:
        text = html.escape(message.text or message.caption or "📎 Media fayl")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Bog'lanish", url=f"tg://user?id={user_id}")]
    ])
    
    # Agar ma'lumotlar bazasida saqlangan raqam bo'lsa uni qo'shish
    contacts = await load_contacts()
    saved_phone = contacts.get(str(user_id), {}).get("phone", "")
    phone_info = f"\n📞 <b>Bazadagi raqami:</b> {saved_phone}" if saved_phone else ""
    
    order_text = (
        f"🆕 <b>YANGI ZAKAZ (Lichka)</b>\n\n"
        f"👤 {user_link} {username}\n"
        f"📱 <code>{user_id}</code>{phone_info}\n\n"
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
        
        admin_btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 Admin bilan bog'lanish", url="https://t.me/FARSAJ_6363")]
        ])
        
        await message.answer(reply_text, reply_markup=admin_btn)
    except Exception as e:
        await message.answer("❌ Uzr, xatolik yuz berdi. Iltimos qayta urinib ko'ring.")

# GURUHLAR: Zakaz qabul qilish
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
    except TelegramAPIError:
        return 

    text = message.text or message.caption or ""
    is_ad = False
    
    emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]')
    link_pattern = re.compile(r'(http|https|www\.|t\.me|@)', re.IGNORECASE)
    ad_words = re.compile(r'\b(obuna|silka|kirish|qoshil|kanalga|obuna boling)\b', re.IGNORECASE)
    
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
            
            reply_text = f"✅ {first_name}, buyurtmangiz qabul qilindi. Siz bilan tez orada haydovchilarimiz bog'lanadi!"
            
            admin_btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👨‍💻 Admin bilan bog'lanish", url="https://t.me/FARSAJ_6363")]
            ])
            
            sent_reply = await message.answer(reply_text, reply_markup=admin_btn)
            asyncio.create_task(delete_message_later(chat_id, sent_reply.message_id, 10))
            
        except Exception:
            pass

async def main():
    logger.info("Bot ishga tushdi...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi!")
