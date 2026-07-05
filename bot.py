import telebot
from telebot import types
import sqlite3
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# --- الإعدادات الأساسية ---
API_TOKEN = '8951535425:AAHUWdQgR36yjvIq-6NdUt1sIDrreYXGAuE'
bot = telebot.TeleBot(API_TOKEN)

TEMPLATE_PASSWORD = "secure_password123"  # كلمة مرور قسم القولبة
ADMIN_PASSWORD = "admin2024"  # كلمة مرور تسجيل الدخول كمشرف رئيسي

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
    # جدول المشرفين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            role TEXT DEFAULT 'admin',
            added_by INTEGER,
            added_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- دوال إدارة المشرفين ---
def is_admin(user_id):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def is_super_admin(user_id):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE user_id=? AND role='super_admin'", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_admin(user_id, username, role='admin', added_by=0):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO admins (user_id, username, role, added_by, added_at) VALUES (?, ?, ?, ?, ?)",
                       (user_id, username, role, added_by, str(datetime.now())))
        conn.commit()
    except:
        pass
    conn.close()

def remove_admin(user_id):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id=? AND role != 'super_admin'", (user_id,))
    conn.commit()
    conn.close()

def get_all_admins():
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, role FROM admins")
    rows = cursor.fetchall()
    conn.close()
    return rows

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

# --- القائمة الرئيسية ---
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_archive = types.InlineKeyboardButton("📁 البدء في الأرشفة والتصنيف", callback_data="start_archive")
    btn_stats = types.InlineKeyboardButton("📊 التقارير الإحصائية", callback_data="view_stats")
    btn_template = types.InlineKeyboardButton("🎨 نظام القولبة الذكي", callback_data="start_template")
    
    markup.add(btn_archive)
    markup.add(btn_stats, btn_template)
    
    if is_admin(user_id):
        btn_admin = types.InlineKeyboardButton("👑 لوحة تحكم المشرفين", callback_data="admin_panel")
        markup.add(btn_admin)
    else:
        btn_login = types.InlineKeyboardButton("🔐 تسجيل دخول كمشرف", callback_data="admin_login")
        markup.add(btn_login)
        
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
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"month_{m}") for m in MONTHS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("📅 الرجاء اختيار الشهر الهجري:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("month_"):
        user_sessions[chat_id]['month'] = data.replace("month_", "")
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(w, callback_data=f"week_{w}") for w in WEEKS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="start_archive"))
        bot.edit_message_text(f"📅 الشهر: {user_sessions[chat_id]['month']}\n📌 الآن حدد الأسبوع:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("week_"):
        user_sessions[chat_id]['week'] = data.replace("week_", "")
        markup = types.InlineKeyboardMarkup(row_width=1)
        for act in ACTIVITIES.keys():
            markup.add(types.InlineKeyboardButton(act, callback_data=f"act_{act}"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="start_archive"))
        bot.edit_message_text("🗂 اختر نوع النشاط المراد أرشفته:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("act_"):
        act_name = data.replace("act_", "")
        user_sessions[chat_id]['activity'] = act_name
        
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

    # --- تسجيل دخول المشرف ---
    elif data == "admin_login":
        msg = bot.send_message(chat_id, "🔐 أدخل كلمة مرور المشرف الرئيسي:")
        bot.register_next_step_handler(msg, process_admin_login)

    # --- لوحة تحكم المشرفين ---
    elif data == "admin_panel" and is_admin(chat_id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📦 سحب بيانات الأرشيف", callback_data="pull_data"))
        markup.add(types.InlineKeyboardButton("👥 إدارة المشرفين", callback_data="manage_admins"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة للرئيسية", callback_data="main_menu"))
        bot.edit_message_text("👑 *لوحة تحكم المشرفين*\nاختر العملية المطلوبة:", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # --- سحب البيانات ---
    elif data == "pull_data" and is_admin(chat_id):
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"pullm_{m}") for m in MONTHS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="admin_panel"))
        bot.edit_message_text("👑 اختر الشهر المطلوب سحب تقاريره:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("pullm_") and is_admin(chat_id):
        user_sessions[chat_id]['pull_month'] = data.replace("pullm_", "")
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(w, callback_data=f"pullw_{w}") for w in WEEKS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="pull_data"))
        bot.edit_message_text("👑 اختر الأسبوع لسحب البيانات:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("pullw_") and is_admin(chat_id):
        pull_week = data.replace("pullw_", "")
        pull_month = user_sessions[chat_id].get('pull_month', '')
        pull_data_for_admin(chat_id, pull_month, pull_week)

    # --- إدارة المشرفين ---
    elif data == "manage_admins" and is_super_admin(chat_id):
        admins = get_all_admins()
        text = "👥 *قائمة المشرفين الحاليين:*\n\n"
        for uid, uname, role in admins:
            role_text = "مشرف رئيسي 👑" if role == "super_admin" else "مشرف"
            text += f"• @{uname or 'بدون اسم'} (ID: {uid}) - {role_text}\n"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة مشرف جديد", callback_data="add_admin"))
        markup.add(types.InlineKeyboardButton("➖ حذف مشرف", callback_data="remove_admin"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="admin_panel"))
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "manage_admins" and is_admin(chat_id) and not is_super_admin(chat_id):
        bot.answer_callback_query(call.id, "⚠️ هذه الصلاحية متاحة للمشرف الرئيسي فقط.", show_alert=True)

    elif data == "add_admin" and is_super_admin(chat_id):
        msg = bot.send_message(chat_id, "➕ أرسل الآن معرف (User ID) الشخص المراد إضافته كمشرف:\n\n💡 يمكن للشخص معرفة الـ ID الخاص به عبر بوت @userinfobot")
        bot.register_next_step_handler(msg, process_add_admin)

    elif data == "remove_admin" and is_super_admin(chat_id):
        admins = get_all_admins()
        markup = types.InlineKeyboardMarkup(row_width=1)
        for uid, uname, role in admins:
            if role != "super_admin":
                markup.add(types.InlineKeyboardButton(f"❌ @{uname or uid} (ID: {uid})", callback_data=f"deladmin_{uid}"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="manage_admins"))
        bot.edit_message_text("➖ اختر المشرف المراد حذفه:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("deladmin_") and is_super_admin(chat_id):
        del_id = int(data.replace("deladmin_", ""))
        remove_admin(del_id)
        bot.answer_callback_query(call.id, "✅ تم حذف المشرف بنجاح.", show_alert=True)
        # إعادة عرض قائمة المشرفين
        admins = get_all_admins()
        text = "👥 *قائمة المشرفين الحاليين:*\n\n"
        for uid, uname, role in admins:
            role_text = "مشرف رئيسي 👑" if role == "super_admin" else "مشرف"
            text += f"• @{uname or 'بدون اسم'} (ID: {uid}) - {role_text}\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة مشرف جديد", callback_data="add_admin"))
        markup.add(types.InlineKeyboardButton("➖ حذف مشرف", callback_data="remove_admin"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="admin_panel"))
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # --- مسار القولبة ---
    elif data == "start_template":
        msg = bot.send_message(chat_id, "🔒 هذا القسم محمي. يرجى إدخال كلمة المرور الخاصة بنظام القولبة:")
        bot.register_next_step_handler(msg, check_template_password)

# --- تسجيل دخول المشرف ---
def process_admin_login(message):
    chat_id = message.chat.id
    if message.text == ADMIN_PASSWORD:
        # أول مشرف يسجل يصبح مشرف رئيسي
        admins = get_all_admins()
        if not admins:
            add_admin(chat_id, message.from_user.username, role='super_admin')
            bot.send_message(chat_id, "✅ تم تسجيلك كمشرف رئيسي بنجاح! 👑\nيمكنك الآن إدارة المشرفين وسحب البيانات.", reply_markup=main_menu(chat_id))
        else:
            # إذا كان هناك مشرفين بالفعل، يُضاف كمشرف عادي
            add_admin(chat_id, message.from_user.username, role='admin')
            bot.send_message(chat_id, "✅ تم تسجيلك كمشرف بنجاح!", reply_markup=main_menu(chat_id))
    else:
        bot.send_message(chat_id, "❌ كلمة المرور خاطئة!", reply_markup=main_menu(chat_id))

# --- إضافة مشرف جديد ---
def process_add_admin(message):
    chat_id = message.chat.id
    try:
        new_admin_id = int(message.text.strip())
        add_admin(new_admin_id, "", role='admin', added_by=chat_id)
        bot.send_message(chat_id, f"✅ تم إضافة المشرف الجديد (ID: {new_admin_id}) بنجاح!", reply_markup=main_menu(chat_id))
        # إشعار المشرف الجديد
        try:
            bot.send_message(new_admin_id, "🎉 تم تعيينك كمشرف في بوت الأرشفة! أرسل /start للبدء.")
        except:
            pass
    except ValueError:
        bot.send_message(chat_id, "❌ يرجى إدخال رقم صحيح (User ID).", reply_markup=main_menu(chat_id))

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

    bot.send_message(chat_id, "✅ تم حفظ التوثيق وأرشفته في قاعدة البيانات بنجاح!", reply_markup=main_menu(chat_id))

    # إشعار فوري للمشرفين
    admins = get_all_admins()
    for admin_id, _, _ in admins:
        if admin_id != chat_id:
            try:
                admin_msg = f"🔔 *إشعار أرشفة جديد:*\n👤 بواسطة: @{message.from_user.username}\n📅 الشهر: {session['month']} | {session['week']}\n🗂 النوع: {session['activity']}\n📄 طبيعة المادة: {content_type}"
                bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
            except:
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
        
        if file_id == "":
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

    user_sessions[chat_id]['template_caption'] = message.caption if message.caption else ""
    
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    input_image_path = f"input_{chat_id}.jpg"
    output_image_path = f"output_{chat_id}.jpg"
    
    with open(input_image_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    bot.send_message(chat_id, "⏳ جاري دمج الشعار والقولبة وتوليد التصميم الفوري...")

    try:
        base_image = Image.open(input_image_path).convert("RGBA")
        
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            w_percent = (base_image.size[0] * 0.15) / float(logo.size[0])
            h_size = int((float(logo.size[1]) * float(w_percent)))
            logo = logo.resize((int(base_image.size[0] * 0.15), h_size), Image.Resampling.LANCZOS)
            
            position = (base_image.size[0] - logo.size[0] - 20, 20)
            
            transparent = Image.new('RGBA', base_image.size, (0,0,0,0))
            transparent.paste(base_image, (0,0))
            transparent.paste(logo, position, mask=logo)
            final_image = transparent.convert("RGB")
        else:
            final_image = base_image.convert("RGB")
            bot.send_message(chat_id, "⚠️ تنبيه: ملف الشعار logo.png مفقود من السيرفر، تم إخراج الصورة بدون شعار.")

        final_image.save(output_image_path, "JPEG")

        with open(output_image_path, 'rb') as img:
            bot.send_photo(chat_id, img, caption=f"✨ *الصورة المقوْلبة الجاهزة:*\n\n{user_sessions[chat_id]['template_caption']}", parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء معالجة الصورة: {str(e)}")
        
    finally:
        if os.path.exists(input_image_path):
            os.remove(input_image_path)
        if os.path.exists(output_image_path):
            os.remove(output_image_path)

# --- تشغيل البوت المستمر ---
print("⚡️ البوت يعمل الآن بكفاءة...")
bot.infinity_polling()
