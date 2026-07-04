import telebot
from telebot import types
import sqlite3
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# --- الإعدادات الأساسية ---
API_TOKEN = '8951535425:AAHUWdQgR36yjvIq-6NdUt1sIDrreYXGAuE'
bot = telebot.TeleBot(API_TOKEN)

ADMIN_IDS = [123456789, 987654321]  # ضع معرفات (User IDs) المشرفين هنا
TEMPLATE_PASSWORD = "secure_password123"  # كلمة مرور قسم القولبة

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    # جدول التوثيقات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            month TEXT,
            week TEXT,
            activity TEXT,
            content_type TEXT,
            content_data TEXT,
            file_id TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- بيانات القوائم الشجرية ---
MONTHS = ["محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة"]
WEEKS = ["الأسبوع الأول", "الأسبوع الثاني", "الأسبوع الثالث", "الأسبوع الرابع"]
ACTIVITIES = {
    "فعاليات وندوات للمناسبات": ["صور مع الخبر", "فيديو"],
    "اجتماعات ولقاءات": ["صورة مع الخبر"],
    "ورشات": [],
    "دورات": [],
    "نزول ميداني": [],
    "أنشطة الجانب الإعلامي": [],
    "أنشطة أخرى": []
}

# ذاكرة مؤقتة لتتبع خطوات المستخدم (Session State)
user_sessions = {}

# --- الدوال المساعدة للتأكد من المشرفين ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- القائمة الرئيسية ---
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_archive = types.InlineKeyboardButton("📁 البدء في الأرشفة والتصنيف", callback_data="start_archive")
    btn_stats = types.InlineKeyboardButton("📊 التقارير الإحصائية", callback_data="view_stats")
    btn_template = types.InlineKeyboardButton("🎨 نظام القولبة الذكي", callback_data="start_template")
    
    markup.add(btn_archive)
    markup.add(btn_stats, btn_template)
    
    if is_admin(user_id):
        btn_admin = types.InlineKeyboardButton("👑 لوحة تحكم المشرفين (سحب البيانات)", callback_data="admin_panel")
        markup.add(btn_admin)
        
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_sessions[message.chat.id] = {}
    bot.send_message(
        message.chat.id, 
        "👋 أهلاً بك في بوت المكتبة الإلكترونية لأرشفة التقارير والتوثيقات.\nالرجاء اختيار القسم المطلوب من القائمة أدناه:", 
        reply_markup=main_menu(message.chat.id)
    )

# --- معالجة الأزرار المضمنة (Callback Queries) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {}

    # العودة للقائمة الرئيسية
    if data == "main_menu":
        user_sessions[chat_id] = {}
        bot.edit_message_text("الرجاء اختيار القسم المطلوب من القائمة أدناه:", chat_id, call.message.message_id, reply_markup=main_menu(chat_id))
        
    # --- مسار الأرشفة ---
    elif data == "start_archive":
        # عرض الأشهر الهجرية
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"month_{m}") for m in MONTHS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("📅 الرجاء اختيار الشهر الهجري:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("month_"):
        user_sessions[chat_id]['month'] = data.replace("month_", "")
        # عرض الأسابيع
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(w, callback_data=f"week_{w}") for w in WEEKS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="start_archive"))
        bot.edit_message_text(f"📅 الشهر: {user_sessions[chat_id]['month']}\n📌 الآن حدد الأسبوع:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("week_"):
        user_sessions[chat_id]['week'] = data.replace("week_", "")
        # عرض الأنشطة
        markup = types.InlineKeyboardMarkup(row_width=1)
        for act in ACTIVITIES.keys():
            markup.add(types.InlineKeyboardButton(act, callback_data=f"act_{act}"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="start_archive"))
        bot.edit_message_text("🗂 اختر نوع النشاط المراد أرشفته:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("act_"):
        act_name = data.replace("act_", "")
        user_sessions[chat_id]['activity'] = act_name
        
        # التحقق من وجود تفريعات (مثل صور مع الخبر، فيديو)
        if act_name in ACTIVITIES and ACTIVITIES[act_name]:
            markup = types.InlineKeyboardMarkup(row_width=2)
            for sub in ACTIVITIES[act_name]:
                markup.add(types.InlineKeyboardButton(sub, callback_data=f"sub_{sub}"))
            markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="week_" + user_sessions[chat_id].get('week', '')))
            bot.edit_message_text(f"نشاط ({act_name}) يتطلب تحديد نوع التوثيق التفريعي:", chat_id, call.message.message_id, reply_markup=markup)
        else:
            user_sessions[chat_id]['sub_activity'] = "عام"
            goToUploadStage(chat_id, call.message.message_id)

    elif data.startswith("sub_"):
        user_sessions[chat_id]['sub_activity'] = data.replace("sub_", "")
        goToUploadStage(chat_id, call.message.message_id)

    # --- مسار التقارير الإحصائية ---
    elif data == "view_stats":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("📊 تقرير إحصائي شهري", callback_data="stat_month_select"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("اختر نوع الإحصائية المطلوبة:", chat_id, call.message.message_id, reply_markup=markup)

    elif data == "stat_month_select":
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"runstat_{m}") for m in MONTHS]
        markup.add(*buttons)
        bot.edit_message_text("اختر الشهر المراد توليد إحصائية له:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("runstat_"):
        selected_month = data.replace("runstat_", "")
        generate_statistics(chat_id, selected_month)

    # --- مسار المشرفين (سحب البيانات للتحميل) ---
    elif data == "admin_panel" and is_admin(chat_id):
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"pullm_{m}") for m in MONTHS]
        markup.add(*buttons)
        bot.edit_message_text("👑 لوحة سحب البيانات - اختر الشهر المطلوبة تقاريره:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("pullm_"):
        user_sessions[chat_id]['pull_month'] = data.replace("pullm_", "")
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(w, callback_data=f"pullw_{w}") for w in WEEKS]
        markup.add(*buttons)
        bot.edit_message_text("👑 اختر الأسبوع لسحب البيانات فورا:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("pullw_"):
        pull_week = data.replace("pullw_", "")
        pull_month = user_sessions[chat_id].get('pull_month', '')
        pull_data_for_admin(chat_id, pull_month, pull_week)

    # --- مسار القولبة ---
    elif data == "start_template":
        msg = bot.send_message(chat_id, "🔒 هذا القسم محمي. يرجى إدخال كلمة المرور الخاصة بنظام القولبة:")
        bot.register_next_step_handler(msg, check_template_password)

# --- الانتقال لمرحلة رفع المادة المؤرشفة ---
def goToUploadStage(chat_id, message_id):
    session = user_sessions[chat_id]
    text = f"⚙️ *جاهز لاستلام المواد للأرشفة:*\n\n📅 الشهر: {session['month']}\n📌 الأسبوع: {session['week']}\n🗂 النشاط: {session['activity']} ({session.get('sub_activity', '')})\n\n✍️ *فضلاً أرسل الآن نص الخبر أو التقرير، أو أرسل الصورة/الملف مباشرة.*"
    msg = bot.send_message(chat_id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_archive_input)

# --- معالجة المدخلات والأرشفة الفعلية ---
def process_archive_input(message):
    chat_id = message.chat.id
    session = user_sessions.get(chat_id, {})
    
    if not session or 'month' not in session:
        bot.send_message(chat_id, "❌ حدث خطأ في الجلسة، يرجى البدء من جديد عبر أمر /start")
        return

    content_type = ""
    content_data = ""
    file_id = ""

    if message.content_type == 'text':
        content_type = "نص / خبر"
        content_data = message.text
    elif message.content_type == 'photo':
        content_type = "صورة"
        content_data = message.caption if message.caption else "صورة بدون نص"
        file_id = message.photo[-1].file_id
    elif message.content_type == 'video':
        content_type = "فيديو"
        content_data = message.caption if message.caption else "فيديو بدون نص"
        file_id = message.video.file_id
    elif message.content_type == 'document':
        content_type = "ملف / PDF"
        content_data = message.caption if message.caption else "ملف بدون نص"
        file_id = message.document.file_id
    else:
        bot.send_message(chat_id, "❌ نوع الملف غير مدعوم حالياً، يرجى المحاولة بصيغة أخرى.")
        return

    # حفظ البيانات في الـ Database
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO archive (user_id, username, month, week, activity, content_type, content_data, file_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (chat_id, message.from_user.username, session['month'], session['week'], f"{session['activity']} - {session.get('sub_activity','')}", content_type, content_data, file_id, str(datetime.now())))
    conn.commit()
    conn.close()

    bot.send_message(chat_id, "✅ تم حفظ التوثيق وأرشدته في قاعدة البيانات بنجاح!", reply_markup=main_menu(chat_id))

    # إشعار فوري للمشرفين
    for admin_id in ADMIN_IDS:
        try:
            admin_msg = f"🔔 *إشعار أرشفة جديد:*\n👤 بواسطة: @{message.from_user.username}\n📅 الشهر: {session['month']} | {session['week']}\n🗂 النوع: {session['activity']}\n📄 طبيعة المادة: {content_type}"
            bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
        except Exception:
            pass

# --- نظام التقارير الإحصائية ---
def generate_statistics(chat_id, month):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    
    report = f"📊 *التقرير الإحصائي الشهري لشهر ({month}):*\n\n"
    
    for week in WEEKS:
        cursor.execute("SELECT COUNT(*) FROM archive WHERE month=? AND week=?", (month, week))
        total_week = cursor.fetchone()[0]
        report += f"🔹 *{week}:* إجمالي التوثيقات ({total_week} مادة)\n"
        
        # تفصيل حسب نوع النشاط
        cursor.execute("SELECT activity, COUNT(*) FROM archive WHERE month=? AND week=? GROUP BY activity", (month, week))
        activities_count = cursor.fetchall()
        for act, count in activities_count:
            report += f"  ◽️ {act}: {count}\n"
        report += "— — — — — — — — —\n"
        
    conn.close()
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ العودة للقائمة", callback_data="main_menu"))
    bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=markup)

# --- محرك سحب البيانات والتقارير للمشرفين ---
def pull_data_for_admin(admin_id, month, week):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, activity, content_type, content_data, file_id FROM archive WHERE month=? AND week=?", (month, week))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.send_message(admin_id, f"📭 لا توجد أي بيانات مؤرشفة لشهر {month} - {week}.", reply_markup=main_menu(admin_id))
        return

    bot.send_message(admin_id, f"📦 جاري سحب وتجميع البيانات لشهر *{month}* (*{week}*)... الرجاء الانتظار:", parse_mode="Markdown")
    
    for row in rows:
        username, activity, c_type, c_data, file_id = row
        caption_text = f"👤 الموثق: @{username}\n🗂 تصنيف النشاط: {activity}\n📝 المضمون/الخبر: {c_data}"
        
        if file_id == "":  # نص فقط
            bot.send_message(admin_id, f"📄 *[نص مؤرشف]*\n{caption_text}", parse_mode="Markdown")
        elif c_type == "صورة":
            bot.send_photo(admin_id, file_id, caption=caption_text)
        elif c_type == "فيديو":
            bot.send_video(admin_id, file_id, caption=caption_text)
        elif c_type == "ملف / PDF":
            bot.send_document(admin_id, file_id, caption=caption_text)

    bot.send_message(admin_id, "✨ تم سحب جميع ملفات وتقارير الفترة المحددة بنجاح.", reply_markup=main_menu(admin_id))

# --- نظام القولبة الذكي ---
def check_template_password(message):
    chat_id = message.chat.id
    if message.text == TEMPLATE_PASSWORD:
        msg = bot.send_message(chat_id, "🔓 تم التحقق بنجاح.\nالرجاء إرسال الصورة التي تريد دمجها بشعار الجهة والقولبة:")
        bot.register_next_step_handler(msg, process_template_image)
    else:
        bot.send_message(chat_id, "❌ كلمة المرور خاطئة! تم إلغاء العملية.", reply_markup=main_menu(chat_id))

def process_template_image(message):
    chat_id = message.chat.id
    if message.content_type != 'photo':
        bot.send_message(chat_id, "❌ عذراً، يجب إرسال صورة حصراً.")
        return

    # حفظ النص المصاحب للقولبة
    user_sessions[chat_id]['template_caption'] = message.caption if message.caption else ""
    
    # تحميل الصورة المرسلة من الخادم مؤقتاً
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    input_image_path = f"input_{chat_id}.jpg"
    output_image_path = f"output_{chat_id}.jpg"
    
    with open(input_image_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    bot.send_message(chat_id, "⏳ جاري دمج الشعار والقولبة وتوليد التصميم الفوري...")

    try:
        # معالجة الصورة عبر Pillow
        base_image = Image.open(input_image_path).convert("RGBA")
        
        # التأكد من وجود شعار باسم logo.png في نفس المجلد
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            # تغيير حجم الشعار ليتناسب تلقائياً مع حجم الصورة الأساسية (مثلاً 15% من العرض)
            w_percent = (base_image.size[0] * 0.15) / float(logo.size[0])
            h_size = int((float(logo.size[1]) * float(w_percent)))
            logo = logo.resize((int(base_image.size[0] * 0.15), h_size), Image.Resampling.LANCZOS)
            
            # وضع الشعار في الزاوية العلوية اليمنى
            position = (base_image.size[0] - logo.size[0] - 20, 20)
            
            # دمج الشعار مع الخلفية
            transparent = Image.new('RGBA', base_image.size, (0,0,0,0))
            transparent.paste(base_image, (0,0))
            transparent.paste(logo, position, mask=logo)
            final_image = transparent.convert("RGB")
        else:
            # في حال عدم وجود ملف شعار، يتم حفظ الصورة كما هي مع إشعار للمستخدم
            final_image = base_image.convert("RGB")
            bot.send_message(chat_id, "⚠️ تنبيه: ملف الشعار logo.png مفقود من السيرفر، تم إخراج الصورة بدون شعار.")

        final_image.save(output_image_path, "JPEG")

        # إعادة إرسال الصورة المقوْلبة للمستخدم مع نص الخبر الأصلي
        with open(output_image_path, 'rb') as img:
            bot.send_photo(chat_id, img, caption=f"✨ *الصورة المقوْلبة الجاهزة:*\n\n{user_sessions[chat_id]['template_caption']}", parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء معالجة الصورة: {str(e)}")
        
    finally:
        # تنظيف الملفات المؤقتة من السيرفر للحفاظ على المساحة
        if os.path.exists(input_image_path):
            os.remove(input_image_path)
        if os.path.exists(output_image_path):
            os.remove(output_image_path)

# --- تشغيل البوت المستمر ---
print("⚡️ البوت يعمل الآن بكفاءة...")
bot.infinity_polling()
