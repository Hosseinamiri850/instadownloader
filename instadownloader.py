from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import instaloader
import os
import uuid
import shutil
import requests
import re

# تنظیمات پراکسی
PROXY = "socks5://username:password@host:port"  # اگر پروکسی ندارید خالی بذارید ""

# ساخت session برای requests با پراکسی
session_requests = requests.Session()
if PROXY:
    session_requests.proxies = {
        "http": PROXY,
        "https": PROXY,
    }

def extract_video_url(instagram_url):
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    try:
        # استفاده از session با پراکسی
        response = session_requests.get(instagram_url, headers=headers)
        if response.status_code == 200:
            html = response.text
            video_url_match = re.search(r'"video_url":"([^"]+)"', html)
            if video_url_match:
                video_url = video_url_match.group(1).replace('\\u0026', '&').replace('\\', '')
                return video_url
    except Exception as e:
        print("Error extracting video:", e)
    return None

# ساخت شی instaloader و لود کردن سشن از فایل
L = instaloader.Instaloader()

# Load session from file for logged-in user
SESSION_FILE = "session-hosseininstadownloader"  # نام فایل سشن شما
try:
    L.load_session_from_file(username=None, filename=SESSION_FILE)
except FileNotFoundError:
    print("Session file not found, please login first.")
except Exception as e:
    print("Error loading session:", e)

# برای پراکسی در instaloader
if PROXY:
    L.context._session.proxies = {
        "http": PROXY,
        "https": PROXY,
    }

user_links = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک پست یا پروفایل اینستاگرام پابلیک رو بفرست 😊")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id

    if "instagram.com" not in url:
        await update.message.reply_text("این لینک اینستاگرام نیست!")
        return

    user_links[user_id] = url

    keyboard = []

    if "/p/" in url or "/reel/" in url:
        keyboard = [
            [InlineKeyboardButton("📷 دانلود کاور", callback_data='download_cover')],
            [InlineKeyboardButton("🎞️ دانلود ویدیو", callback_data='download_video')],
            [InlineKeyboardButton("🖼️ دانلود همه فایل‌ها", callback_data='download_all')]
        ]
    elif "instagram.com/" in url and url.count("/") == 4:
        keyboard = [[InlineKeyboardButton("👤 دانلود عکس پروفایل", callback_data='download_profile')]]
    else:
        await update.message.reply_text("نوع لینک نامعتبره یا پشتیبانی نمیشه!")
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("می‌خوای با این لینک چیکار کنی؟", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    url = user_links.get(user_id)

    if not url:
        await query.edit_message_text("لینکی ذخیره نشده 😕")
        return

    try:
        if query.data == "download_profile":
            username = url.split("instagram.com/")[1].strip("/").split("/")[0]
            profile = instaloader.Profile.from_username(L.context, username)
            photo_url = profile.profile_pic_url
            await query.message.reply_photo(photo_url, caption=f"عکس پروفایل @{username}")
            return

        shortcode = url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        temp_dir = f"temp_{uuid.uuid4()}"
        os.makedirs(temp_dir, exist_ok=True)
        L.download_post(post, target=temp_dir)

        files = sorted(os.listdir(temp_dir))

        if query.data == "download_cover":
            for f in files:
                if f.endswith(".jpg"):
                    with open(os.path.join(temp_dir, f), "rb") as file:
                        await query.message.reply_photo(file, caption="📷 کاور:")
                        break

        elif query.data == "download_video":
            video_url = extract_video_url(url)
            if video_url:
                video_data = session_requests.get(video_url, stream=True)
                if video_data.status_code == 200:
                    video_path = f"{temp_dir}/video.mp4"
                    with open(video_path, "wb") as f:
                        for chunk in video_data.iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)

                    with open(video_path, "rb") as f:
                        await query.message.reply_video(f, caption="🎞️ ویدیوی ریلز:")
                else:
                    await query.edit_message_text("نتونستم ویدیو رو دانلود کنم ❌")
            else:
                await query.edit_message_text("ویدیو پیدا نشد 😢")

        elif query.data == "download_all":
            for f in files:
                filepath = os.path.join(temp_dir, f)
                if f.endswith(".jpg"):
                    with open(filepath, "rb") as file:
                        await query.message.reply_photo(file)
                elif f.endswith(".mp4"):
                    with open(filepath, "rb") as file:
                        await query.message.reply_video(file)

        shutil.rmtree(temp_dir)

    except Exception as e:
        await query.edit_message_text(f"❌ خطا:\n{str(e)}")

app = ApplicationBuilder().token("8040441698:AAEY-hb6vLcicDRt3n_qO5LdZ15jMUHXqfw").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
app.add_handler(CallbackQueryHandler(button_handler))

app.run_polling()
