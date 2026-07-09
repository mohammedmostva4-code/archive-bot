import telebot
from telebot import types
import sqlite3
import os
import json
from datetime import datetime
from image_processor import process_template

# --- الإعدادات الأساسية ---
API_TOKEN = '8951535425:AAHUWdQgR36yjvIq-6NdUt1sIDrreYXGAuE'
bot = telebot.TeleBot(API_TOKEN)

# --- ملف حفظ الرموز ---
PASSWORDS_FILE = 'passwords.json'

def load_passwords():
    if os.path.exists(PASSWORDS_FILE):
        with open(PASSWORDS_FILE, 'r') as f:
            return json.load(f)
    return {"admin_password": "admin123", "user_password": "user123"}

def save_passwords(passwords):
    with open(PASSWORDS_FILE, 'w') as f:
        json.dump(passwords, f)

# تهيئة الرموز
passwords = load_passwords()
save_passwords(passwords)

# --- ملف حفظ الأنشطة الديناميكية ---
ACTIVITIES_FILE = 'activities.json'

def load_activities():
    if os.path.exists(ACTIVITIES_FILE):
        with open(ACTIVITIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return get_default_activities()

def save_activities(activities):
    with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(activities, f, ensure_ascii=False, indent=2)

def get_default_activities():
    return {
        "فعاليات وندوات للمناسبات": ["صور مع الخبر", "فيديو"],
        "اجتماعات ولقاءات": ["صورة مع الخبر"],
        "ورشات": [],
        "دورات": [],
        "النزول الميداني + الزيارات": [],
        "أنشطة الإعلام": [
            "الإعلام الإذاعي (حلقة الأسبوع، برنامج الأمن والمجتمع، لقاءات إذاعية، مداخلات)",
            "تحرير أخباري",
            "رصد الشائعات",
            "ردود على الشائعات",
            "تنسيق مع القنوات الإعلامية",
            "نشر منشورات توعوية أمنية",
            "فلاشات/ريلز توعوية أمنية",
            "الإعلام الصحفي (عدد الإصدار)",
            "إنتاج فلاشات",
            "إنتاج أفلام",
            "إنتاج جرافيكس",
            "إنتاج ريلزات",
            "تقارير"
        ],
        "أنشطة أخرى": [
            "ملفات مستند ورش",
            "ملفات مستند اليوم الثقافي",
            "ملفات مستند الجانب الإعلامي",
            "ملفات مستند أنشطة أخرى"
        ],
        "الأنشطة مع التعبئة العامة": []
    }

# تحميل الأنشطة
ACTIVITIES = load_activities()
save_activities(ACTIVITIES)

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hidden_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            note TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- بيانات القوائم الشجرية ---
MONTHS = ["محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة"]
WEEKS = ["الأسبوع الأول", "الأسبوع الثاني", "الأسبوع الثالث", "الأسبوع الرابع"]

# ذاكرة مؤقتة لتتبع خطوات المستخدم
user_sessions = {}
authenticated_users = {}  # لتتبع المستخدمين المصادق عليهم ودورهم

# --- الدوال المساعدة ---
def is_admin(user_id):
    return authenticated_users.get(user_id) == "admin"

def is_authenticated(user_id):
    return user_id in authenticated_users

# --- القائمة الرئيسية ---
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_archive = types.InlineKeyboardButton("📁 البدء في الأرشفة والتصنيف", callback_data="start_archive")
    btn_stats = types.InlineKeyboardButton("📊 التقارير الإحصائية", callback_data="view_stats")
    btn_template = types.InlineKeyboardButton("🖼 قالب وجد أثر العمل", callback_data="template_start")
    
    markup.add(btn_archive)
    markup.add(btn_stats)
    markup.add(btn_template)
    
    if is_admin(user_id):
        btn_admin = types.InlineKeyboardButton("👑 لوحة تحكم المشرفين", callback_data="admin_panel")
        btn_change_pass = types.InlineKeyboardButton("🔑 تغيير الرموز", callback_data="change_passwords")
        btn_hidden = types.InlineKeyboardButton("🔒 الخانة المخفية", callback_data="hidden_section")
        btn_manage_acts = types.InlineKeyboardButton("📝 إدارة الأنشطة", callback_data="manage_activities")
        markup.add(btn_admin)
        markup.add(btn_change_pass, btn_hidden)
        markup.add(btn_manage_acts)
        
    return markup

# --- شاشة تسجيل الدخول ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_sessions[message.chat.id] = {}
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_admin_login = types.InlineKeyboardButton("👑 دخول كمشرف", callback_data="login_admin")
    btn_user_login = types.InlineKeyboardButton("👤 دخول كمستخدم", callback_data="login_user")
    markup.add(btn_admin_login, btn_user_login)
    
    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في بوت المكتبة الإلكترونية لأرشفة التقارير والتوثيقات.\n\n🔐 الرجاء اختيار نوع الدخول:",
        reply_markup=markup
    )

# --- التحقق من رمز المشرف ---
def verify_admin_password(message):
    chat_id = message.chat.id
    passwords = load_passwords()
    
    if message.text == passwords['admin_password']:
        authenticated_users[chat_id] = "admin"
        bot.send_message(chat_id, "✅ تم التحقق بنجاح! مرحباً بك كمشرف.", reply_markup=main_menu(chat_id))
    else:
        bot.send_message(chat_id, "❌ الرمز غير صحيح! يرجى المحاولة مرة أخرى عبر /start")

# --- التحقق من رمز المستخدم ---
def verify_user_password(message):
    chat_id = message.chat.id
    passwords = load_passwords()
    
    if message.text == passwords['user_password']:
        authenticated_users[chat_id] = "user"
        bot.send_message(chat_id, "✅ تم التحقق بنجاح! مرحباً بك.", reply_markup=main_menu(chat_id))
    else:
        bot.send_message(chat_id, "❌ الرمز غير صحيح! يرجى المحاولة مرة أخرى عبر /start")

# --- معالجة الأزرار المضمنة ---
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {}

    # --- تسجيل الدخول ---
    if data == "login_admin":
        msg = bot.edit_message_text("🔐 أدخل رمز المشرف:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, verify_admin_password)
        
    elif data == "login_user":
        msg = bot.edit_message_text("🔐 أدخل رمز المستخدم:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, verify_user_password)

    # العودة للقائمة الرئيسية
    elif data == "main_menu":
        if not is_authenticated(chat_id):
            bot.edit_message_text("❌ يرجى تسجيل الدخول أولاً عبر /start", chat_id, call.message.message_id)
            return
        user_sessions[chat_id] = {}
        bot.edit_message_text("الرجاء اختيار القسم المطلوب من القائمة أدناه:", chat_id, call.message.message_id, reply_markup=main_menu(chat_id))
        
    # --- مسار القالب الجديد (وجد أثر العمل) ---
    elif data == "template_start":
        user_sessions[chat_id] = {'mode': 'template', 'images': [], 'title': '', 'details': ''}
        bot.edit_message_text("🖼 *مرحباً بك في خدمة قالب وجد أثر العمل*\n\n📸 فضلاً أرسل الآن 4 صور للنشاط (واحدة تلو الأخرى أو دفعة واحدة).", chat_id, call.message.message_id, parse_mode="Markdown")

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
        current_activities = load_activities()
        markup = types.InlineKeyboardMarkup(row_width=1)
        act_keys = list(current_activities.keys())
        for i, act in enumerate(act_keys):
            markup.add(types.InlineKeyboardButton(act, callback_data=f"act_{i}"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="start_archive"))
        bot.edit_message_text("🗂 اختر نوع النشاط المراد أرشفته:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("act_"):
        act_index = int(data.replace("act_", ""))
        current_activities = load_activities()
        act_keys = list(current_activities.keys())
        
        if act_index < len(act_keys):
            act_name = act_keys[act_index]
            user_sessions[chat_id]['activity'] = act_name
            
            if current_activities[act_name]:
                markup = types.InlineKeyboardMarkup(row_width=1)
                for j, sub in enumerate(current_activities[act_name]):
                    markup.add(types.InlineKeyboardButton(sub, callback_data=f"sub_{act_index}_{j}"))
                markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="week_" + user_sessions[chat_id].get('week', '')))
                bot.edit_message_text(f"📂 نشاط ({act_name})\nاختر التفريع:", chat_id, call.message.message_id, reply_markup=markup)
            else:
                user_sessions[chat_id]['sub_activity'] = "عام"
                goToUploadStage(chat_id, call.message.message_id)

    elif data.startswith("sub_"):
        parts = data.replace("sub_", "").split("_")
        act_index = int(parts[0])
        sub_index = int(parts[1])
        current_activities = load_activities()
        act_keys = list(current_activities.keys())
        
        if act_index < len(act_keys):
            act_name = act_keys[act_index]
            subs = current_activities[act_name]
            if sub_index < len(subs):
                user_sessions[chat_id]['sub_activity'] = subs[sub_index]
            else:
                user_sessions[chat_id]['sub_activity'] = "عام"
        else:
            user_sessions[chat_id]['sub_activity'] = "عام"
        goToUploadStage(chat_id, call.message.message_id)

    # --- مسار التقارير الإحصائية ---
    elif data == "view_stats":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📊 تقرير شهري", callback_data="stat_month_select"))
        markup.add(types.InlineKeyboardButton("📈 تقرير ربع سنوي", callback_data="stat_quarter"))
        markup.add(types.InlineKeyboardButton("📉 تقرير نصف سنوي", callback_data="stat_half"))
        markup.add(types.InlineKeyboardButton("🗓 تقرير سنوي", callback_data="stat_yearly"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("📊 اختر نوع الإحصائية المطلوبة:", chat_id, call.message.message_id, reply_markup=markup)

    elif data == "stat_month_select":
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"runstat_{m}") for m in MONTHS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="view_stats"))
        bot.edit_message_text("اختر الشهر المراد توليد إحصائية له:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("runstat_"):
        selected_month = data.replace("runstat_", "")
        generate_statistics(chat_id, selected_month)

    elif data == "stat_quarter":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("الربع الأول (محرم - ربيع الأول)", callback_data="quarter_1"))
        markup.add(types.InlineKeyboardButton("الربع الثاني (ربيع الآخر - جمادى الآخرة)", callback_data="quarter_2"))
        markup.add(types.InlineKeyboardButton("الربع الثالث (رجب - رمضان)", callback_data="quarter_3"))
        markup.add(types.InlineKeyboardButton("الربع الرابع (شوال - ذو الحجة)", callback_data="quarter_4"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="view_stats"))
        bot.edit_message_text("📈 اختر الربع السنوي:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("quarter_"):
        quarter_num = int(data.replace("quarter_", ""))
        quarters = {
            1: ["محرم", "صفر", "ربيع الأول"],
            2: ["ربيع الآخر", "جمادى الأولى", "جمادى الآخرة"],
            3: ["رجب", "شعبان", "رمضان"],
            4: ["شوال", "ذو القعدة", "ذو الحجة"]
        }
        generate_period_statistics(chat_id, quarters[quarter_num], f"الربع {quarter_num}")

    elif data == "stat_half":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("النصف الأول (محرم - جمادى الآخرة)", callback_data="half_1"))
        markup.add(types.InlineKeyboardButton("النصف الثاني (رجب - ذو الحجة)", callback_data="half_2"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="view_stats"))
        bot.edit_message_text("📉 اختر النصف السنوي:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("half_"):
        half_num = int(data.replace("half_", ""))
        halves = {
            1: ["محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة"],
            2: ["رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة"]
        }
        generate_period_statistics(chat_id, halves[half_num], f"النصف {half_num}")

    elif data == "stat_yearly":
        generate_period_statistics(chat_id, MONTHS, "السنوي")

    # --- لوحة تحكم المشرفين ---
    elif data == "admin_panel":
        if not is_admin(chat_id): return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📥 سحب بيانات (شهر/أسبوع)", callback_data="admin_pull_select"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("👑 لوحة تحكم المشرفين:", chat_id, call.message.message_id, reply_markup=markup)

    elif data == "admin_pull_select":
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"pullmonth_{m}") for m in MONTHS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="admin_panel"))
        bot.edit_message_text("اختر الشهر لسحب بياناته:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("pullmonth_"):
        user_sessions[chat_id]['pull_month'] = data.replace("pullmonth_", "")
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(w, callback_data=f"pullweek_{w}") for w in WEEKS]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="admin_pull_select"))
        bot.edit_message_text(f"الشهر: {user_sessions[chat_id]['pull_month']}\nحدد الأسبوع:", chat_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("pullweek_"):
        week = data.replace("pullweek_", "")
        pull_data_for_admin(chat_id, user_sessions[chat_id]['pull_month'], week)

    # --- إدارة الأنشطة ---
    elif data == "manage_activities":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة نشاط رئيسي", callback_data="add_main_act"))
        markup.add(types.InlineKeyboardButton("➕ إضافة تفريع لنشاط", callback_data="add_sub_act"))
        markup.add(types.InlineKeyboardButton("❌ حذف تفريع", callback_data="del_sub_act"))
        markup.add(types.InlineKeyboardButton("📝 تغيير اسم نشاط", callback_data="rename_act"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("📝 إدارة الأنشطة:", chat_id, call.message.message_id, reply_markup=markup)

    elif data == "add_main_act":
        msg = bot.edit_message_text("✍️ أرسل اسم النشاط الرئيسي الجديد:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_add_main_activity)

    elif data == "add_sub_act":
        current_activities = load_activities()
        text = "اختر رقم النشاط المراد الإضافة إليه ثم أرسل (الرقم,اسم التفريع):\n\n"
        for i, act in enumerate(current_activities.keys()):
            text += f"{i+1}. {act}\n"
        msg = bot.edit_message_text(text, chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_add_sub_activity)

    elif data == "del_sub_act":
        msg = bot.edit_message_text("✍️ أرسل (اسم النشاط الرئيسي,اسم التفريع) لحذفه:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_delete_sub_activity)

    elif data == "rename_act":
        current_activities = load_activities()
        text = "اختر رقم النشاط المراد تعديله ثم أرسل (الرقم,الاسم الجديد):\n\n"
        for i, act in enumerate(current_activities.keys()):
            text += f"{i+1}. {act}\n"
        msg = bot.edit_message_text(text, chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_rename_activity)

    # --- تغيير الرموز ---
    elif data == "change_passwords":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔑 تغيير رمز المشرف", callback_data="cp_admin"))
        markup.add(types.InlineKeyboardButton("🔑 تغيير رمز المستخدم", callback_data="cp_user"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("🔑 اختر الرمز المراد تغييره:", chat_id, call.message.message_id, reply_markup=markup)

    elif data == "cp_admin":
        msg = bot.edit_message_text("✍️ أرسل رمز المشرف الجديد:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, lambda m: update_password(m, 'admin_password'))

    elif data == "cp_user":
        msg = bot.edit_message_text("✍️ أرسل رمز المستخدم الجديد:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, lambda m: update_password(m, 'user_password'))

    # --- الخانة المخفية ---
    elif data == "hidden_section":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📝 إضافة ملاحظة سرية", callback_data="add_hidden_note"))
        markup.add(types.InlineKeyboardButton("📖 عرض الملاحظات", callback_data="view_hidden_notes"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("🔒 الخانة المخفية (للمشرفين فقط):", chat_id, call.message.message_id, reply_markup=markup)

    elif data == "add_hidden_note":
        msg = bot.edit_message_text("✍️ أرسل الملاحظة السرية لحفظها:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, save_hidden_note)

    elif data == "view_hidden_notes":
        conn = sqlite3.connect('archive_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT note, timestamp FROM hidden_notes ORDER BY id DESC LIMIT 10")
        notes = cursor.fetchall()
        conn.close()
        
        text = "📖 *آخر 10 ملاحظات سرية:*\n\n"
        for n, ts in notes:
            text += f"📍 {ts}\n📝 {n}\n\n"
        
        if not notes: text = "📭 لا توجد ملاحظات سرية بعد."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="hidden_section"))
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

def update_password(message, key):
    passwords = load_passwords()
    passwords[key] = message.text.strip()
    save_passwords(passwords)
    bot.send_message(message.chat.id, "✅ تم تحديث الرمز بنجاح!", reply_markup=main_menu(message.chat.id))

# --- معالجة الصور والرسائل لوضع القالب ---
@bot.message_handler(content_types=['photo', 'text', 'video', 'document'])
def handle_all_messages(message):
    chat_id = message.chat.id
    session = user_sessions.get(chat_id, {})
    
    # التحقق من وضع القالب
    if session.get('mode') == 'template':
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # حفظ الصورة مؤقتاً
            if not os.path.exists('/home/ubuntu/archive-bot/temp'):
                os.makedirs('/home/ubuntu/archive-bot/temp')
            
            img_path = f'/home/ubuntu/archive-bot/temp/{chat_id}_{len(session["images"])}.jpg'
            with open(img_path, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            session['images'].append(img_path)
            
            if len(session['images']) < 4:
                bot.send_message(chat_id, f"✅ تم استلام الصورة ({len(session['images'])}/4). أرسل الصورة التالية.")
            else:
                msg = bot.send_message(chat_id, "✅ اكتمل استلام الصور الأربع.\n\n✍️ الآن أرسل *عنوان النشاط*:", parse_mode="Markdown")
                bot.register_next_step_handler(msg, process_template_title)
            return

    # إذا لم يكن في وضع القالب، ننتقل لمعالجة الأرشفة العادية
    if session.get('month'):
        process_archive_input(message)
    else:
        # إذا لم يكن هناك جلسة نشطة، نطلب منه البدء
        if message.content_type == 'text' and not message.text.startswith('/'):
            bot.send_message(chat_id, "❌ يرجى البدء من القائمة الرئيسية أو تسجيل الدخول أولاً عبر /start")

def process_template_title(message):
    chat_id = message.chat.id
    if message.content_type != 'text':
        msg = bot.send_message(chat_id, "❌ يرجى إرسال نص للعنوان:")
        bot.register_next_step_handler(msg, process_template_title)
        return
    
    user_sessions[chat_id]['title'] = message.text
    msg = bot.send_message(chat_id, "✍️ رائع، الآن أرسل *تفاصيل النشاط* (التاريخ، الجهة، المكان):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_template_details)

def process_template_details(message):
    chat_id = message.chat.id
    if message.content_type != 'text':
        msg = bot.send_message(chat_id, "❌ يرجى إرسال نص للتفاصيل:")
        bot.register_next_step_handler(msg, process_template_details)
        return
    
    session = user_sessions[chat_id]
    session['details'] = message.text
    
    bot.send_message(chat_id, "⏳ جاري معالجة الصور وتوليد القالب، يرجى الانتظار...")
    
    try:
        output_path = f'/home/ubuntu/archive-bot/temp/result_{chat_id}.png'
        process_template(session['images'], session['title'], session['details'], output_path)
        
        with open(output_path, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption="✨ تم تجهيز قالب (وجد أثر العمل) بنجاح!")
            
        # تنظيف الملفات المؤقتة
        for img in session['images']:
            if os.path.exists(img): os.remove(img)
        if os.path.exists(output_path): os.remove(output_path)
        
        # العودة للقائمة الرئيسية
        user_sessions[chat_id] = {}
        bot.send_message(chat_id, "الرجاء اختيار القسم المطلوب من القائمة أدناه:", reply_markup=main_menu(chat_id))
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء معالجة الصورة: {str(e)}")
        user_sessions[chat_id] = {}

# --- دوال الخانة المخفية ---
def save_hidden_note(message):
    chat_id = message.chat.id
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO hidden_notes (admin_id, note, timestamp) VALUES (?, ?, ?)",
                   (chat_id, message.text, str(datetime.now())))
    conn.commit()
    conn.close()
    bot.send_message(chat_id, "✅ تم حفظ الملاحظة السرية بنجاح!", reply_markup=main_menu(chat_id))

# --- دوال إدارة الأنشطة ---
def process_add_main_activity(message):
    chat_id = message.chat.id
    new_activity = message.text.strip()
    current_activities = load_activities()
    
    if new_activity in current_activities:
        bot.send_message(chat_id, "❌ هذا النشاط موجود بالفعل!", reply_markup=main_menu(chat_id))
    else:
        current_activities[new_activity] = []
        save_activities(current_activities)
        bot.send_message(chat_id, f"✅ تم إضافة النشاط الرئيسي: {new_activity}", reply_markup=main_menu(chat_id))

def process_add_sub_activity(message):
    chat_id = message.chat.id
    try:
        parts = message.text.split(",", 1)
        act_num = int(parts[0].strip()) - 1
        sub_name = parts[1].strip()
        
        current_activities = load_activities()
        act_keys = list(current_activities.keys())
        
        if 0 <= act_num < len(act_keys):
            current_activities[act_keys[act_num]].append(sub_name)
            save_activities(current_activities)
            bot.send_message(chat_id, f"✅ تم إضافة التفريع '{sub_name}' إلى '{act_keys[act_num]}'", reply_markup=main_menu(chat_id))
        else:
            bot.send_message(chat_id, "❌ رقم النشاط غير صحيح!", reply_markup=main_menu(chat_id))
    except:
        bot.send_message(chat_id, "❌ صيغة غير صحيحة! استخدم: رقم,اسم التفريع", reply_markup=main_menu(chat_id))

def process_delete_sub_activity(message):
    chat_id = message.chat.id
    try:
        parts = message.text.split(",", 1)
        act_name = parts[0].strip()
        sub_name = parts[1].strip()
        
        current_activities = load_activities()
        
        if act_name in current_activities and sub_name in current_activities[act_name]:
            current_activities[act_name].remove(sub_name)
            save_activities(current_activities)
            bot.send_message(chat_id, f"✅ تم حذف التفريع '{sub_name}' من '{act_name}'", reply_markup=main_menu(chat_id))
        else:
            bot.send_message(chat_id, "❌ لم يتم العثور على النشاط أو التفريع!", reply_markup=main_menu(chat_id))
    except:
        bot.send_message(chat_id, "❌ صيغة غير صحيحة! استخدم: اسم النشاط,اسم التفريع", reply_markup=main_menu(chat_id))

def process_rename_activity(message):
    chat_id = message.chat.id
    try:
        parts = message.text.split(",", 1)
        act_num = int(parts[0].strip()) - 1
        new_name = parts[1].strip()
        
        current_activities = load_activities()
        act_keys = list(current_activities.keys())
        
        if 0 <= act_num < len(act_keys):
            old_name = act_keys[act_num]
            current_activities[new_name] = current_activities.pop(old_name)
            save_activities(current_activities)
            bot.send_message(chat_id, f"✅ تم تغيير اسم النشاط من '{old_name}' إلى '{new_name}'", reply_markup=main_menu(chat_id))
        else:
            bot.send_message(chat_id, "❌ رقم النشاط غير صحيح!", reply_markup=main_menu(chat_id))
    except:
        bot.send_message(chat_id, "❌ صيغة غير صحيحة! استخدم: رقم,الاسم الجديد", reply_markup=main_menu(chat_id))

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
        content_type = "ملف / مستند"
        content_data = message.caption if message.caption else "ملف بدون نص"
        file_id = message.document.file_id
    else:
        bot.send_message(chat_id, "❌ نوع الملف غير مدعوم حالياً.")
        return

    # حفظ في قاعدة البيانات
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO archive (user_id, username, month, week, activity, content_type, content_data, file_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (chat_id, message.from_user.username, session['month'], session['week'],
          f"{session['activity']} - {session.get('sub_activity','')}", content_type, content_data, file_id, str(datetime.now())))
    conn.commit()
    conn.close()

    bot.send_message(chat_id, "✅ تم حفظ التوثيق وأرشفته بنجاح!", reply_markup=main_menu(chat_id))

    # إشعار فوري للمشرفين
    for uid, role in authenticated_users.items():
        if role == "admin" and uid != chat_id:
            try:
                admin_msg = f"🔔 *إشعار أرشفة جديد:*\n👤 بواسطة: @{message.from_user.username}\n📅 الشهر: {session['month']} | {session['week']}\n🗂 النوع: {session['activity']}\n📄 المادة: {content_type}"
                bot.send_message(uid, admin_msg, parse_mode="Markdown")
            except Exception:
                pass

# --- نظام التقارير الإحصائية الشهرية ---
def generate_statistics(chat_id, month):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    
    report = f"📊 *التقرير الإحصائي الشهري لشهر ({month}):*\n\n"
    total_month = 0
    
    for week in WEEKS:
        cursor.execute("SELECT COUNT(*) FROM archive WHERE month=? AND week=?", (month, week))
        total_week = cursor.fetchone()[0]
        total_month += total_week
        report += f"🔹 *{week}:* إجمالي التوثيقات ({total_week} مادة)\n"
        
        cursor.execute("SELECT activity, COUNT(*) FROM archive WHERE month=? AND week=? GROUP BY activity", (month, week))
        activities_count = cursor.fetchall()
        for act, count in activities_count:
            report += f"  ◽️ {act}: {count}\n"
        report += "— — — — — — — — —\n"
    
    report += f"\n📌 *إجمالي الشهر:* {total_month} مادة مؤرشفة"
    conn.close()
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ العودة للقائمة", callback_data="main_menu"))
    bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=markup)

# --- تقارير الفترات (ربع سنوي / نصف سنوي / سنوي) ---
def generate_period_statistics(chat_id, months_list, period_name):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    
    report = f"📊 *تقرير {period_name}:*\n\n"
    grand_total = 0
    
    for month in months_list:
        cursor.execute("SELECT COUNT(*) FROM archive WHERE month=?", (month,))
        total = cursor.fetchone()[0]
        grand_total += total
        report += f"🔹 {month}: {total} مادة\n"
    
    report += f"\n📌 *الإجمالي الكلي:* {grand_total} مادة مؤرشفة"
    conn.close()
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ العودة للقائمة", callback_data="main_menu"))
    bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=markup)

# --- محرك سحب البيانات للمشرفين ---
def pull_data_for_admin(admin_id, month, week):
    conn = sqlite3.connect('archive_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, activity, content_type, content_data, file_id FROM archive WHERE month=? AND week=?", (month, week))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.send_message(admin_id, f"📭 لا توجد أي بيانات مؤرشفة لشهر {month} - {week}.", reply_markup=main_menu(admin_id))
        return

    bot.send_message(admin_id, f"📦 جاري سحب البيانات لشهر *{month}* (*{week}*)...", parse_mode="Markdown")
    
    for row in rows:
        username, activity, c_type, c_data, file_id = row
        caption_text = f"👤 الموثق: @{username}\n🗂 النشاط: {activity}\n📝 المضمون: {c_data}"
        
        if file_id == "":
            bot.send_message(admin_id, f"📄 *[نص مؤرشف]*\n{caption_text}", parse_mode="Markdown")
        elif c_type == "صورة":
            bot.send_photo(admin_id, file_id, caption=caption_text)
        elif c_type == "فيديو":
            bot.send_video(admin_id, file_id, caption=caption_text)
        elif c_type == "ملف / مستند":
            bot.send_document(admin_id, file_id, caption=caption_text)

    bot.send_message(admin_id, "✨ تم سحب جميع البيانات بنجاح.", reply_markup=main_menu(admin_id))

# --- تشغيل البوت ---
if __name__ == '__main__':
    print("⚡ بوت الأرشفة يعمل الآن...")
    bot.infinity_polling()
