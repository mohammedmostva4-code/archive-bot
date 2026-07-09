import telebot
from telebot import types
import sqlite3
import os
import json
from datetime import datetime
from template_handler import start_template_session, handle_template_photo, template_sessions

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

    if data == "login_admin":
        msg = bot.edit_message_text("🔐 أدخل رمز المشرف:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, verify_admin_password)
    elif data == "login_user":
        msg = bot.edit_message_text("🔐 أدخل رمز المستخدم:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, verify_user_password)
    elif data == "main_menu":
        if not is_authenticated(chat_id):
            bot.edit_message_text("❌ يرجى تسجيل الدخول أولاً عبر /start", chat_id, call.message.message_id)
            return
        user_sessions[chat_id] = {}
        bot.edit_message_text("الرجاء اختيار القسم المطلوب من القائمة أدناه:", chat_id, call.message.message_id, reply_markup=main_menu(chat_id))
    
    # --- تشغيل جلسة القالب ---
    elif data == "template_start":
        start_template_session(bot, chat_id, call.message.message_id)

    # --- مسارات الأرشفة والتقارير والإدارة (كما هي) ---
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
        act_index = int(parts[0]); sub_index = int(parts[1])
        current_activities = load_activities()
        act_keys = list(current_activities.keys())
        if act_index < len(act_keys):
            act_name = act_keys[act_index]
            subs = current_activities[act_name]
            user_sessions[chat_id]['sub_activity'] = subs[sub_index] if sub_index < len(subs) else "عام"
        goToUploadStage(chat_id, call.message.message_id)
    elif data == "view_stats":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📊 تقرير شهري", callback_data="stat_month_select"),
                   types.InlineKeyboardButton("📈 تقرير ربع سنوي", callback_data="stat_quarter"),
                   types.InlineKeyboardButton("📉 تقرير نصف سنوي", callback_data="stat_half"),
                   types.InlineKeyboardButton("🗓 تقرير سنوي", callback_data="stat_yearly"),
                   types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("📊 اختر نوع الإحصائية المطلوبة:", chat_id, call.message.message_id, reply_markup=markup)
    elif data == "stat_month_select":
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"runstat_{m}") for m in MONTHS]
        markup.add(*buttons); markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="view_stats"))
        bot.edit_message_text("اختر الشهر المراد توليد إحصائية له:", chat_id, call.message.message_id, reply_markup=markup)
    elif data.startswith("runstat_"):
        generate_statistics(chat_id, data.replace("runstat_", ""))
    elif data == "stat_quarter":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("الربع الأول (محرم - ربيع الأول)", callback_data="quarter_1"),
                   types.InlineKeyboardButton("الربع الثاني (ربيع الآخر - جمادى الآخرة)", callback_data="quarter_2"),
                   types.InlineKeyboardButton("الربع الثالث (رجب - رمضان)", callback_data="quarter_3"),
                   types.InlineKeyboardButton("الربع الرابع (شوال - ذو الحجة)", callback_data="quarter_4"),
                   types.InlineKeyboardButton("⬅️ العودة", callback_data="view_stats"))
        bot.edit_message_text("📈 اختر الربع السنوي:", chat_id, call.message.message_id, reply_markup=markup)
    elif data.startswith("quarter_"):
        q = int(data.replace("quarter_", ""))
        qs = {1: ["محرم", "صفر", "ربيع الأول"], 2: ["ربيع الآخر", "جمادى الأولى", "جمادى الآخرة"], 3: ["رجب", "شعبان", "رمضان"], 4: ["شوال", "ذو القعدة", "ذو الحجة"]}
        generate_period_statistics(chat_id, qs[q], f"الربع {q}")
    elif data == "stat_half":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("النصف الأول (محرم - جمادى الآخرة)", callback_data="half_1"),
                   types.InlineKeyboardButton("النصف الثاني (رجب - ذو الحجة)", callback_data="half_2"),
                   types.InlineKeyboardButton("⬅️ العودة", callback_data="view_stats"))
        bot.edit_message_text("📉 اختر النصف السنوي:", chat_id, call.message.message_id, reply_markup=markup)
    elif data.startswith("half_"):
        h = int(data.replace("half_", ""))
        hs = {1: MONTHS[:6], 2: MONTHS[6:]}
        generate_period_statistics(chat_id, hs[h], f"النصف {h}")
    elif data == "stat_yearly":
        generate_period_statistics(chat_id, MONTHS, "السنوي")
    elif data == "admin_panel":
        if not is_admin(chat_id): return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📥 سحب بيانات (شهر/أسبوع)", callback_data="admin_pull_select"),
                   types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("👑 لوحة تحكم المشرفين:", chat_id, call.message.message_id, reply_markup=markup)
    elif data == "admin_pull_select":
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(m, callback_data=f"pullmonth_{m}") for m in MONTHS]
        markup.add(*buttons); markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="admin_panel"))
        bot.edit_message_text("اختر الشهر لسحب بياناته:", chat_id, call.message.message_id, reply_markup=markup)
    elif data.startswith("pullmonth_"):
        user_sessions[chat_id]['pull_month'] = data.replace("pullmonth_", "")
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(w, callback_data=f"pullweek_{w}") for w in WEEKS]
        markup.add(*buttons); markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="admin_pull_select"))
        bot.edit_message_text(f"الشهر: {user_sessions[chat_id]['pull_month']}\nحدد الأسبوع:", chat_id, call.message.message_id, reply_markup=markup)
    elif data.startswith("pullweek_"):
        pull_data_for_admin(chat_id, user_sessions[chat_id]['pull_month'], data.replace("pullweek_", ""))
    elif data == "manage_activities":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة نشاط رئيسي", callback_data="add_main_act"),
                   types.InlineKeyboardButton("➕ إضافة تفريع لنشاط", callback_data="add_sub_act"),
                   types.InlineKeyboardButton("❌ حذف تفريع", callback_data="del_sub_act"),
                   types.InlineKeyboardButton("📝 تغيير اسم نشاط", callback_data="rename_act"),
                   types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("📝 إدارة الأنشطة:", chat_id, call.message.message_id, reply_markup=markup)
    elif data == "add_main_act":
        msg = bot.edit_message_text("✍️ أرسل اسم النشاط الرئيسي الجديد:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_add_main_activity)
    elif data == "add_sub_act":
        current_activities = load_activities()
        text = "اختر رقم النشاط المراد الإضافة إليه ثم أرسل (الرقم,اسم التفريع):\n\n"
        for i, act in enumerate(current_activities.keys()): text += f"{i+1}. {act}\n"
        msg = bot.edit_message_text(text, chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_add_sub_activity)
    elif data == "del_sub_act":
        msg = bot.edit_message_text("✍️ أرسل (اسم النشاط الرئيسي,اسم التفريع) لحذفه:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_delete_sub_activity)
    elif data == "rename_act":
        current_activities = load_activities()
        text = "اختر رقم النشاط المراد تعديله ثم أرسل (الرقم,الاسم الجديد):\n\n"
        for i, act in enumerate(current_activities.keys()): text += f"{i+1}. {act}\n"
        msg = bot.edit_message_text(text, chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_rename_activity)
    elif data == "change_passwords":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔑 تغيير رمز المشرف", callback_data="cp_admin"),
                   types.InlineKeyboardButton("🔑 تغيير رمز المستخدم", callback_data="cp_user"),
                   types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("🔑 اختر الرمز المراد تغييره:", chat_id, call.message.message_id, reply_markup=markup)
    elif data == "cp_admin":
        msg = bot.edit_message_text("✍️ أرسل رمز المشرف الجديد:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, lambda m: update_password(m, 'admin_password'))
    elif data == "cp_user":
        msg = bot.edit_message_text("✍️ أرسل رمز المستخدم الجديد:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, lambda m: update_password(m, 'user_password'))
    elif data == "hidden_section":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📝 إضافة ملاحظة سرية", callback_data="add_hidden_note"),
                   types.InlineKeyboardButton("📖 عرض الملاحظات", callback_data="view_hidden_notes"),
                   types.InlineKeyboardButton("⬅️ العودة", callback_data="main_menu"))
        bot.edit_message_text("🔒 الخانة المخفية (للمشرفين فقط):", chat_id, call.message.message_id, reply_markup=markup)
    elif data == "add_hidden_note":
        msg = bot.edit_message_text("✍️ أرسل الملاحظة السرية لحفظها:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, save_hidden_note)
    elif data == "view_hidden_notes":
        conn = sqlite3.connect('archive_bot.db'); cursor = conn.cursor()
        cursor.execute("SELECT note, timestamp FROM hidden_notes ORDER BY id DESC LIMIT 10")
        notes = cursor.fetchall(); conn.close()
        text = "📖 *آخر 10 ملاحظات سرية:*\n\n"
        for n, ts in notes: text += f"📍 {ts}\n📝 {n}\n\n"
        if not notes: text = "📭 لا توجد ملاحظات سرية بعد."
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ العودة", callback_data="hidden_section"))
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

def update_password(message, key):
    passwords = load_passwords(); passwords[key] = message.text.strip(); save_passwords(passwords)
    bot.send_message(message.chat.id, "✅ تم تحديث الرمز بنجاح!", reply_markup=main_menu(message.chat.id))

# --- معالجة الرسائل ---
@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    if handle_template_photo(bot, message): return
    if user_sessions.get(message.chat.id, {}).get('month'): process_archive_input(message)

@bot.message_handler(content_types=['text', 'video', 'document'])
def handle_all_messages(message):
    chat_id = message.chat.id
    if chat_id in template_sessions: return # يتم التعامل معه عبر register_next_step_handler
    if user_sessions.get(chat_id, {}).get('month'): process_archive_input(message)
    elif message.content_type == 'text' and not message.text.startswith('/'):
        bot.send_message(chat_id, "❌ يرجى البدء من القائمة الرئيسية أو تسجيل الدخول أولاً عبر /start")

# --- دوال الأرشفة والإحصاء والإدارة (كما هي) ---
def save_hidden_note(message):
    conn = sqlite3.connect('archive_bot.db'); cursor = conn.cursor()
    cursor.execute("INSERT INTO hidden_notes (admin_id, note, timestamp) VALUES (?, ?, ?)", (message.chat.id, message.text, str(datetime.now())))
    conn.commit(); conn.close(); bot.send_message(message.chat.id, "✅ تم حفظ الملاحظة السرية بنجاح!", reply_markup=main_menu(message.chat.id))

def process_add_main_activity(message):
    acts = load_activities()
    if message.text.strip() in acts: bot.send_message(message.chat.id, "❌ موجود بالفعل!", reply_markup=main_menu(message.chat.id))
    else: acts[message.text.strip()] = []; save_activities(acts); bot.send_message(message.chat.id, "✅ تم الإضافة", reply_markup=main_menu(message.chat.id))

def process_add_sub_activity(message):
    try:
        p = message.text.split(",", 1); n = int(p[0].strip())-1; s = p[1].strip(); acts = load_activities(); keys = list(acts.keys())
        if 0 <= n < len(keys): acts[keys[n]].append(s); save_activities(acts); bot.send_message(message.chat.id, "✅ تم الإضافة", reply_markup=main_menu(message.chat.id))
    except: bot.send_message(message.chat.id, "❌ خطأ في الصيغة")

def process_delete_sub_activity(message):
    try:
        p = message.text.split(",", 1); a = p[0].strip(); s = p[1].strip(); acts = load_activities()
        if a in acts and s in acts[a]: acts[a].remove(s); save_activities(acts); bot.send_message(message.chat.id, "✅ تم الحذف", reply_markup=main_menu(message.chat.id))
    except: bot.send_message(message.chat.id, "❌ خطأ في الصيغة")

def process_rename_activity(message):
    try:
        p = message.text.split(",", 1); n = int(p[0].strip())-1; new = p[1].strip(); acts = load_activities(); keys = list(acts.keys())
        if 0 <= n < len(keys): old = keys[n]; acts[new] = acts.pop(old); save_activities(acts); bot.send_message(message.chat.id, "✅ تم التغيير", reply_markup=main_menu(message.chat.id))
    except: bot.send_message(message.chat.id, "❌ خطأ في الصيغة")

def goToUploadStage(chat_id, message_id):
    s = user_sessions[chat_id]
    msg = bot.send_message(chat_id, f"⚙️ *جاهز للاستلام:*\n📅 {s['month']} | {s['week']}\n🗂 {s['activity']}\n✍️ أرسل المادة الآن.", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_archive_input)

def process_archive_input(message):
    s = user_sessions.get(message.chat.id, {})
    if not s or 'month' not in s: return
    c_type = "نص"; c_data = message.text; f_id = ""
    if message.content_type == 'photo': c_type = "صورة"; c_data = message.caption or ""; f_id = message.photo[-1].file_id
    elif message.content_type == 'video': c_type = "فيديو"; c_data = message.caption or ""; f_id = message.video.file_id
    elif message.content_type == 'document': c_type = "ملف"; c_data = message.caption or ""; f_id = message.document.file_id
    conn = sqlite3.connect('archive_bot.db'); cursor = conn.cursor()
    cursor.execute('INSERT INTO archive (user_id, username, month, week, activity, content_type, content_data, file_id, timestamp) VALUES (?,?,?,?,?,?,?,?,?)',
                   (message.chat.id, message.from_user.username, s['month'], s['week'], f"{s['activity']} - {s.get('sub_activity','')}", c_type, c_data, f_id, str(datetime.now())))
    conn.commit(); conn.close(); bot.send_message(message.chat.id, "✅ تم الحفظ", reply_markup=main_menu(message.chat.id))

def generate_statistics(chat_id, month):
    conn = sqlite3.connect('archive_bot.db'); cursor = conn.cursor()
    report = f"📊 *تقرير {month}:*\n"
    for w in WEEKS:
        cursor.execute("SELECT COUNT(*) FROM archive WHERE month=? AND week=?", (month, w))
        report += f"🔹 {w}: {cursor.fetchone()[0]} مادة\n"
    conn.close(); bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️", callback_data="main_menu")))

def generate_period_statistics(chat_id, months, name):
    conn = sqlite3.connect('archive_bot.db'); cursor = conn.cursor(); total = 0
    for m in months: cursor.execute("SELECT COUNT(*) FROM archive WHERE month=?", (m,)); total += cursor.fetchone()[0]
    conn.close(); bot.send_message(chat_id, f"📊 *تقرير {name}:* {total} مادة", parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️", callback_data="main_menu")))

def pull_data_for_admin(admin_id, month, week):
    conn = sqlite3.connect('archive_bot.db'); cursor = conn.cursor()
    cursor.execute("SELECT username, activity, content_type, content_data, file_id FROM archive WHERE month=? AND week=?", (month, week))
    rows = cursor.fetchall(); conn.close()
    if not rows: bot.send_message(admin_id, "📭 لا يوجد بيانات"); return
    for r in rows:
        u, a, t, d, f = r; cap = f"👤 @{u}\n🗂 {a}\n📝 {d}"
        if f == "": bot.send_message(admin_id, cap)
        elif t == "صورة": bot.send_photo(admin_id, f, caption=cap)
        elif t == "فيديو": bot.send_video(admin_id, f, caption=cap)
        elif t == "ملف": bot.send_document(admin_id, f, caption=cap)

if __name__ == '__main__':
    print("⚡ بوت الأرشفة يعمل الآن..."); bot.infinity_polling()
