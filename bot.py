import telebot
from telebot import types
import sqlite3
import os
import json
from datetime import datetime
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# --- الإعدادات والرموز الافتراضية الثنائية ---
TOKEN = '8951535425:AAHUWdQgR36yjvIq-6NdUt1sIDrreYXGAuE'
bot = telebot.TeleBot(TOKEN)

# أرقام افتراضية للرموز السرية (تتغير ديناميكياً من لوحة التحكم)
DEFAULT_OWNER_PASS = "owner2026"
DEFAULT_USER_PASS = "user2026"

# --- إدارة قاعدة البيانات (SQLite) ---
def init_db():
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    
    # جدول الإعدادات العامة (الرموز الحالية)
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY, value TEXT)''')
    
    # جدول المشرفين والأعضاء وصلاحياتهم
    cursor.execute('''CREATE TABLE IF NOT EXISTS members (
                        user_id INTEGER PRIMARY KEY, 
                        username TEXT, 
                        role TEXT, 
                        status TEXT DEFAULT 'active')''')
    
    # جدول قائمة الأنشطة والأقسام الديناميكية
    cursor.execute('''CREATE TABLE IF NOT EXISTS activity_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        category TEXT, 
                        sub_category TEXT)''')
    
    # جدول الأرشيف العام للمواد
    cursor.execute('''CREATE TABLE IF NOT EXISTS archive_master (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        username TEXT,
                        hijri_month TEXT,
                        hijri_week TEXT,
                        main_category TEXT,
                        sub_category TEXT,
                        content_type TEXT,
                        content_data TEXT,
                        file_id TEXT,
                        actual_date TEXT,
                        timestamp TEXT)''')
    
    # إدخال القيم الافتراضية إذا كانت فارغة
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('owner_pass', ?)", (DEFAULT_OWNER_PASS,))
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('user_pass', ?)", (DEFAULT_USER_PASS,))
    
    # التحقق من وجود الأنشطة الافتراضية بحسب الوثيقة
    cursor.execute("SELECT COUNT(*) FROM activity_types")
    if cursor.fetchone()[0] == 0:
        default_activities = [
            ("النزول الميداني والزيارات", "عام"),
            ("أنشطة الإعلام", "الإعلام الإذاعي"),
            ("أنشطة الإعلام", "التحرير الإخباري"),
            ("أنشطة الإعلام", "رصد الشائعات | الردود على الشائعات"),
            ("أنشطة الإعلام", "التنسيق مع القنوات الإعلامية"),
            ("أنشطة الإعلام", "نشر منشورات توعوية أمنية"),
            ("أنشطة الإعلام", "فلاشات وريلز توعوية أمنية"),
            ("أنشطة الإعلام", "الإعلام الصحفي"),
            ("أنشطة الإعلام", "الإنتاج الفني"),
            ("أنشطة الإعلام", "تقارير إعلامية"),
            ("أنشطة الإعلام", "الأنشطة مع التعبئة العامة"),
            ("أنشطة أخرى", "ملفات مستند ورش"),
            ("أنشطة أخرى", "ملفات مستند اليوم الثقافي"),
            ("أنشطة أخرى", "ملفات مستند الجانب الإعلامي"),
            ("أنشطة أخرى", "ملفات مستند أنشطة أخرى")
        ]
        cursor.executemany("INSERT INTO activity_types (category, sub_category) VALUES (?, ?)", default_activities)
        
    conn.commit()
    conn.close()

init_db()

# --- دالات جلب وفحص الصلاحيات والرموز ---
def get_setting(key, default):
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else default

def set_setting(key, value):
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_user_role(user_id):
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    cursor.execute("SELECT role, status FROM members WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    if res:
        if res[1] == 'banned': return 'banned'
        return res[0]
    return None

# ذاكرة الجلسات النشطة لتتبع تدفق مدخلات كل مستخدم (State Management)
user_sessions = {}

# --- لوحات المفاتيح والأزرار الذكية ---
def build_main_menu(user_id):
    role = get_user_role(user_id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if role == 'banned':
        return None
        
    # أزرار واجهة المستخدم الأساسية
    btn_archive = types.InlineKeyboardButton("📂 البدء في الأرشفة والتصنيف", callback_data="ui_archive")
    btn_stats = types.InlineKeyboardButton("📊 التقارير الإحصائية والاسترجاع", callback_data="ui_stats")
    btn_template = types.InlineKeyboardButton("🎨 نظام القولبة الذكي", callback_data="ui_template")
    markup.add(btn_archive)
    markup.add(btn_stats, btn_template)
    
    # إضافة زر التحكم الإضافي للمشرفين والمالك
    if role in ['owner', 'admin']:
        btn_admin = types.InlineKeyboardButton("⚙️ لوحة التحكم الإدارية للمشرفين", callback_data="admin_main")
        markup.add(btn_admin)
        
    return markup

# --- استقبال أمر البدء /start ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    role = get_user_role(user_id)
    
    if role == 'banned':
        bot.send_message(user_id, "❌ عذراً، لقد تم حظر حسابك من قبل المشرف العام.")
        return

    # إذا كان مسجلاً مسبقاً، تفتح القائمة الرئيسية مباشرة
    if role in ['owner', 'admin', 'user']:
        bot.send_message(user_id, "📲 مرحباً بك مجدداً في منظومة الأرشفة الإلكترونية. اختر من القائمة التالية:", reply_markup=build_main_menu(user_id))
    else:
        user_sessions[user_id] = {"step": "wait_auth_code"}
        bot.send_message(user_id, "🔒 *مرحباً بك في منظومة الأرشفة المحمية.*\n\nالرجاء إدخال الرمز السري المخصص لك لتفعيل صلاحيات الوصول الخاصة برتبتك:", parse_mode="Markdown")

# --- دالة الاستماع والتحقق من الرموز والمدخلات النصية العامة ---
@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'document', 'video'])
def global_message_handler(message):
    user_id = message.chat.id
    role = get_user_role(user_id)
    
    if role == 'banned': return
    
    session = user_sessions.get(user_id, {})
    step = session.get("step")
    
    # 1. مرحلة التحقق من رمز الدخول لأول مرة
    if step == "wait_auth_code" and message.content_type == 'text':
        entered_code = message.text.strip()
        owner_pass = get_setting('owner_pass', DEFAULT_OWNER_PASS)
        user_pass = get_setting('user_pass', DEFAULT_USER_PASS)
        
        conn = sqlite3.connect('library_archive.db')
        cursor = conn.cursor()
        
        # فحص إذا كان هناك مالك للنظام أم لا لتحديد الرتبة
        cursor.execute("SELECT COUNT(*) FROM members WHERE role='owner'")
        has_owner = cursor.fetchone()[0] > 0
        
        if entered_code == owner_pass:
            if not has_owner:
                cursor.execute("INSERT OR REPLACE INTO members VALUES (?, ?, 'owner', 'active')", (user_id, message.from_user.username))
                bot.send_message(user_id, "👑 تم اعتمادك بنجاح بصفتك *المشرف الرئيسي والمالك العام* للمنظومة بالصلاحيات المطلقة.", parse_mode="Markdown")
            else:
                cursor.execute("INSERT OR REPLACE INTO members VALUES (?, ?, 'admin', 'active')", (user_id, message.from_user.username))
                bot.send_message(user_id, "⚙️ تم التحقق بنجاح وتفعيل صلاحياتك كـ *مشرف عادي*.", parse_mode="Markdown")
            conn.commit()
            user_sessions[user_id] = {}
            bot.send_message(user_id, "الرجاء اختيار أحد الخيارات لتشغيل النظام:", reply_markup=build_main_menu(user_id))
            
        elif entered_code == user_pass:
            cursor.execute("INSERT OR REPLACE INTO members VALUES (?, ?, 'user', 'active')", (user_id, message.from_user.username))
            conn.commit()
            user_sessions[user_id] = {}
            bot.send_message(user_id, "✅ تم التحقق بنجاح. تم تفعيل حسابك بصفتك *مستخدم/عضو* مخول برفع التقارير والأرشفة.", parse_mode="Markdown")
            bot.send_message(user_id, "الرجاء اختيار أحد الخيارات:", reply_markup=build_main_menu(user_id))
        else:
            bot.send_message(user_id, "❌ الرمز السري غير صحيح. يرجى مراجعة الإدارة وإعادة إدخال الرمز بدقة:")
        conn.close()
        return

    # 2. خطوة إرسال نص التقرير اليدوي بعد استلام الملف في مسار الأرشفة
    elif step == "wait_archive_file":
        session['msg_content'] = message
        user_sessions[user_id] = session
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📅 أرشفة بتاريخ اليوم الحالي تلقائياً", callback_data="time_auto"))
        markup.add(types.InlineKeyboardButton("✏️ إدخال تاريخ يوم محدد يدوياً", callback_data="time_manual"))
        bot.send_message(user_id, "⏳ تم استلام المادة التوثيقية بنجاح. حدد الآن آلية التثبيت الزمني للتقرير:", reply_markup=markup)
        return

    # 3. إدخال تاريخ يدوي
    elif step == "wait_manual_date" and message.content_type == 'text':
        session['actual_date'] = message.text.strip()
        user_sessions[user_id] = session
        execute_final_archiving(user_id)
        return

    # 4. مسار استقبال صور القولبة الذكية
    elif step == "wait_template_photos" and message.content_type == 'photo':
        if 'template_photos' not in session:
            session['template_photos'] = []
        session['template_photos'].append(message.photo[-1].file_id)
        user_sessions[user_id] = session
        
        current_count = len(session['template_photos'])
        target_count = session['target_photos_count']
        
        if current_count < target_count:
            bot.send_message(user_id, f"📥 تم استلام الصورة رقم ({current_count}). أرسل الصورة التالية:")
        else:
            session['step'] = "wait_template_text"
            user_sessions[user_id] = session
            bot.send_message(user_id, "✍️ رائع، تم استلام جميع الصور المطلوبة بنجاح. أرسل الآن نص التقرير المكتوب ليتم كتابته وتنسيقه أسفل القالب:")
        return

    elif step == "wait_template_text" and message.content_type == 'text':
        session['template_text'] = message.text
        user_sessions[user_id] = session
        process_and_generate_template(user_id)
        return

    # 5. استقبال مدخلات البحث باليوم أو الأسبوع
    elif step == "wait_search_day" and message.content_type == 'text':
        fetch_and_send_archive_by_time(user_id, "day", message.text.strip())
        return
    elif step == "wait_search_week" and message.content_type == 'text':
        fetch_and_send_archive_by_time(user_id, "week", message.text.strip())
        return

    # 6. مدخلات إدارة الأقسام من المالك الرئيسي
    elif step == "wait_new_cat" and message.content_type == 'text':
        parts = message.text.split("-")
        if len(parts) == 2:
            conn = sqlite3.connect('library_archive.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO activity_types (category, sub_category) VALUES (?, ?)", (parts[0].strip(), parts[1].strip()))
            conn.commit()
            conn.close()
            bot.send_message(user_id, "✅ تم إضافة القسم والتصنيف الجديد بنجاح إلى شجرة الأنشطة الديناميكية.", reply_markup=build_main_menu(user_id))
        else:
            bot.send_message(user_id, "❌ صيغة خاطئة. يجب كتابة: القسم الرئيسي - التصنيف الفرعي")
        user_sessions[user_id] = {}
        return
        
    elif step == "wait_new_user_pass" and message.content_type == 'text':
        set_setting('user_pass', message.text.strip())
        bot.send_message(user_id, f"🔒 تم تحديث رمز دخول المستخدمين الجديد إلى: {message.text.strip()}", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    elif step == "wait_new_admin_pass" and message.content_type == 'text':
        set_setting('owner_pass', message.text.strip())
        bot.send_message(user_id, f"👑 تم تحديث رمز دخول المشرفين الجديد إلى: {message.text.strip()}", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    elif step == "wait_add_admin_id" and message.content_type == 'text':
        try:
            target_id = int(message.text.strip())
            conn = sqlite3.connect('library_archive.db')
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO members VALUES (?, 'مضاف يدويا', 'admin', 'active')", (target_id,))
            conn.commit()
            conn.close()
            bot.send_message(user_id, f"✅ تم ترقية الحساب رقم {target_id} إلى رتبة مشرف عادي بنجاح.", reply_markup=build_main_menu(user_id))
        except:
            bot.send_message(user_id, "❌ حدث خطأ، تأكد من إرسال معرف رقمي صحيح (User ID).")
        user_sessions[user_id] = {}
        return

    elif step == "wait_ban_user_id" and message.content_type == 'text':
        try:
            target_id = int(message.text.strip())
            conn = sqlite3.connect('library_archive.db')
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO members VALUES (?, 'محظور يدويا', 'user', 'banned')", (target_id,))
            conn.commit()
            conn.close()
            bot.send_message(user_id, f"🚫 تم حظر الحساب رقم {target_id} ومنعه من استخدام المنظومة نهائياً.", reply_markup=build_main_menu(user_id))
        except:
            bot.send_message(user_id, "❌ حدث خطأ، تأكد من إرسال معرف رقمي صحيح.")
        user_sessions[user_id] = {}
        return

# --- معالجة الضغط على الأزرار (Callback Queries) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_queries(call):
    user_id = call.message.chat.id
    role = get_user_role(user_id)
    data = call.data
    
    if role == 'banned': return
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
        
    session = user_sessions[user_id]

    # العودة للرئيسية
    if data == "go_home":
        user_sessions[user_id] = {}
        bot.edit_message_text("الرجاء اختيار أحد الخيارات لتشغيل النظام:", user_id, call.message.message_id, reply_markup=build_main_menu(user_id))
        return

    # ==========================================
    # 🔄 مسار الأرشفة والتصنيف المتطور
    # ==========================================
    if data == "ui_archive":
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(f"شهر {i}", callback_data=f"arch_m_{i}") for i in range(1, 13)]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("⬅️ العودة للقائمة الرئيسية", callback_data="go_home"))
        bot.edit_message_text("📅 الخطوة [1/3]: يرجى اختيار الشهر الهجري للنشاط المراد توثيقه:", user_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("arch_m_"):
        session['hijri_month'] = data.split("_")[2]
        markup = types.InlineKeyboardMarkup(row_width=2)
        weeks = ["الأسبوع الأول", "الأسبوع الثاني", "الأسبوع الثالث", "الأسبوع الرابع"]
        for w in weeks:
            markup.add(types.InlineKeyboardButton(w, callback_data=f"arch_w_{w}"))
        bot.edit_message_text("📅 الخطوة [1/3]: يرجى تحديد الأسبوع التابع للشهر الهجري المختار:", user_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("arch_w_"):
        session['hijri_week'] = data.split("_")[2]
        user_sessions[user_id] = session
        
        # جلب الأقسام الرئيسية ديناميكياً من قاعدة البيانات
        conn = sqlite3.connect('library_archive.db')
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM activity_types")
        categories = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for cat in categories:
            markup.add(types.InlineKeyboardButton(cat[0], callback_data=f"arch_cat_{cat[0]}"))
            
        # إظهار الخانة المخفية للمشرف العام والمالك فقط بحسب التوصيف
        if role == 'owner':
            markup.add(types.InlineKeyboardButton("🔒 الخانة المخفية (خاص بالمشرف العام)", callback_data="arch_cat_الخانة المخفية"))
            
        bot.edit_message_text("🗂️ الخطوة [2/3]: يرجى اختيار نوع النشاط الرئيسي/التصنيف العام للتقرير:", user_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("arch_cat_"):
        selected_cat = data.replace("arch_cat_", "")
        session['main_category'] = selected_cat
        user_sessions[user_id] = session
        
        if selected_cat == "الخانة المخفية":
            session['sub_category'] = "توثيق حساس وسري جداً"
            user_sessions[user_id] = session
            ask_for_archive_file(user_id, call.message.message_id)
            return
            
        # جلب التصنيفات الفرعية للقسم المختار ديناميكياً
        conn = sqlite3.connect('library_archive.db')
        cursor = conn.cursor()
        cursor.execute("SELECT sub_category FROM activity_types WHERE category=?", (selected_cat,))
        sub_cats = cursor.fetchall()
        conn.close()
        
        if sub_cats and sub_cats[0][0] != "عام":
            markup = types.InlineKeyboardMarkup(row_width=1)
            for sub in sub_cats:
                markup.add(types.InlineKeyboardButton(sub[0], callback_data=f"arch_sub_{sub[0]}"))
            bot.edit_message_text(f"🔍 الأنشطة التابعة لـ ({selected_cat}): يرجى تحديد التصنيف الدقيق:", user_id, call.message.message_id, reply_markup=markup)
        else:
            session['sub_category'] = "عام"
            user_sessions[user_id] = session
            ask_for_archive_file(user_id, call.message.message_id)

    elif data.startswith("arch_sub_"):
        sub_val = data.replace("arch_sub_", "")
        session['sub_category'] = sub_val
        user_sessions[user_id] = session
        
        # فحص استثنائي لـ الإعلام الصحفي لطلب رقم الإصدار
        if sub_val == "الإعلام الصحفي":
            bot.edit_message_text("✍️ التوثيق للإعلام الصحفي يتطلب كتابة التفاصيل؛ يرجى لاحقاً ذكر (عدد الإصدار) ضمن نص المضمون المرفق.", user_id, call.message.message_id)
            
        ask_for_archive_file(user_id, call.message.message_id)

    elif data == "time_auto":
        session['actual_date'] = datetime.now().strftime("%Y-%m-%d")
        user_sessions[user_id] = session
        execute_final_archiving(user_id)
        
    elif data == "time_manual":
        session['step'] = "wait_manual_date"
        user_sessions[user_id] = session
        bot.send_message(user_id, "✍️ يرجى إرسال تاريخ اليوم المطلوب أرشفة التقرير فيه بصيغة نصية واضحة (مثال: 2026-07-05):")

    # ==========================================
    # 🎨 مسار نظام القولبة الذكي والتكامل المطور
    # ==========================================
    elif data == "ui_template":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🖼️ تقرير مصور بـ (صورة واحدة)", callback_data="tpl_count_1"))
        markup.add(types.InlineKeyboardButton("👥 تقرير مصور بـ (صورة مزدوجة - صورتين)", callback_data="tpl_count_2"))
        markup.add(types.InlineKeyboardButton("🎴 تقرير مصور بـ (4 صور في شبكة واحدة)", callback_data="tpl_count_4"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة للقائمة", callback_data="go_home"))
        bot.edit_message_text("🎨 أهلاً بك في استوديو القولبة الذكي. حدد عدد الصور المراد دمجها وبنائها داخل التقرير المصور الموحد للجهة:", user_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("tpl_count_"):
        count = int(data.split("_")[2])
        session['target_photos_count'] = count
        session['template_photos'] = []
        session['step'] = "wait_template_photos"
        user_sessions[user_id] = session
        bot.send_message(user_id, f"📥 الاستوديو جاهز. يرجى إرسال الصورة الأولى الآن:")

    elif data.startswith("archive_instant_"):
        # التكامل الفوري للأرشفة التلقائية/اليدوية من زر القالب المصمم
        file_id = data.replace("archive_instant_", "")
        session['instant_file_id'] = file_id
        user_sessions[user_id] = session
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("⚡ الأرشفة التلقائية (تاريخ اليوم والأسبوع الحالي)", callback_data="inst_mode_auto"))
        markup.add(types.InlineKeyboardButton("🛠️ التخصيص اليدوي (تحديد فترة أو شهر سابق)", callback_data="inst_mode_manual"))
        bot.send_message(user_id, "📥 معالج الترحيل الفوري للأرشيف: حدد نمط الأرشفة الذي تريده لهذا التصميم الجاهز:", reply_markup=markup)

    elif data == "inst_mode_auto":
        # حساب التوقيت الحالي تلقائياً وتحديد نوع النشاط فقط
        session['hijri_month'] = str((datetime.now().month % 12) + 1) # محاكاة تقريبية للشهر الحالي
        session['hijri_week'] = "الأسبوع الأول"
        session['actual_date'] = datetime.now().strftime("%Y-%m-%d")
        user_sessions[user_id] = session
        
        # الذهاب لاختيار النشاط مباشرة اختصاراً للوقت
        conn = sqlite3.connect('library_archive.db')
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM activity_types")
        categories = cursor.fetchall()
        conn.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        for cat in categories:
            markup.add(types.InlineKeyboardButton(cat[0], callback_data=f"arch_cat_{cat[0]}"))
        bot.send_message(user_id, "📌 التوقيت حُسب تلقائياً. يرجى فقط تحديد نوع النشاط الرئيسي لترحيل الملف فوراً للأرشيف:", reply_markup=markup)

    elif data == "inst_mode_manual":
        # إعادة توجيه لمسار الأرشفة العادي لكن مع الاحتفاظ بملف التصميم المخزن في الذاكرة
        bot.send_message(user_id, "🛠️ نمط التخصيص اليدوي نشط. سيتم توجيهك الآن للفهرسة الكاملة:")
        bot.edit_message_text("📅 اختر الشهر الهجري للتصنييف اليدوي:", user_id, call.message.message_id, reply_markup=build_main_menu(user_id))
        # تزييف حدث بالدخول للأرشفة للبدء من جديد مع الحفاظ على البيانات
        call.data = "ui_archive"
        handle_callback_queries(call)

    # ==========================================
    # 📊 مسار التقارير الإحصائية والاسترجاع
    # ==========================================
    elif data == "ui_stats":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📈 توليد وتصدير ملف Excel إحصائي شامل لشهر هجري", callback_data="st_export_excel"))
        markup.add(types.InlineKeyboardButton("🔍 محرك البحث والاسترجاع باليوم المحدد", callback_data="st_search_day"))
        markup.add(types.InlineKeyboardButton("🔎 محرك البحث والاسترجاع بالأسبوع الكامل", callback_data="st_search_week"))
        markup.add(types.InlineKeyboardButton("⬅️ العودة للقائمة الرئيسية", callback_data="go_home"))
        bot.edit_message_text("📊 قسم التقارير والاسترجاع الذكي؛ حدد الإجراء المطلوب عمله الآن من قاعدة البيانات:", user_id, call.message.message_id, reply_markup=markup)

    elif data == "st_export_excel":
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(f"شهر {i}", callback_data=f"run_excel_{i}") for i in range(1, 13)]
        markup.add(*buttons)
        bot.edit_message_text("📊 اختر الشهر الهجري المطلوب تصدير وإخراج الحصاد والإحصائيات الخاصة به كملف Excel مدمج ومجدول:", user_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("run_excel_"):
        m_target = data.split("_")[2]
        generate_excel_statistics(user_id, m_target)

    elif data == "st_search_day":
        session['step'] = "wait_search_day"
        user_sessions[user_id] = session
        bot.send_message(user_id, "🔍 يرجى إرسال تاريخ اليوم المراد البحث عنه واسترجاع ملفاته (مثال: 2026-07-05):")

    elif data == "st_search_week":
        session['step'] = "wait_search_week"
        user_sessions[user_id] = session
        bot.send_message(user_id, "🔎 يرجى إرسال أي تاريخ يقع ضمن الأسبوع المطلوب، وسيتعرف النظام عليه ويسحب توثيقات الأسبوع كاملة تلقائياً:")

    # ==========================================
    # ⚙️ لوحة الإدارة والمشرفين والرقابة المطلقة
    # ==========================================
    elif data == "admin_main" and role in ['owner', 'admin']:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📈 تقرير أداء المستخدمين وقياس الالتزام (Excel)", callback_data="adm_perf_report"))
        
        # صلاحيات المالك الحصرية والمطلقة فقط بحسب التوصيف الفني لبناء البوت
        if role == 'owner':
            markup.add(types.InlineKeyboardButton("➕ إضافة قسم/نشاط جديد للشجرة", callback_data="adm_add_cat"))
            markup.add(types.InlineKeyboardButton("👤 ترقية مستخدم إلى رتبة مشرف جديد", callback_data="adm_add_admin"))
            markup.add(types.InlineKeyboardButton("🚫 حظر حساب موظف مقصر من النظام", callback_data="adm_ban_user"))
            markup.add(types.InlineKeyboardButton("🔐 تحديث وتغيير الرموز السرية للمنظومة", callback_data="adm_change_passes"))
            
        markup.add(types.InlineKeyboardButton("⬅️ العودة للقائمة الرئيسية", callback_data="go_home"))
        bot.edit_message_text("⚙️ لوحة تحكم الإدارة والرقابة المركزية. حدد الخيار الإداري المطلوب تنفيذه:", user_id, call.message.message_id, reply_markup=markup)

    elif data == "adm_perf_report":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("📆 تقرير الالتزام الأسبوعي", callback_data="perf_calc_week"))
        markup.add(types.InlineKeyboardButton("📅 تقرير الالتزام الشهري", callback_data="perf_calc_month"))
        bot.edit_message_text("📊 حدد النطاق الرقابي المطلوب لبناء جدول قياس الالتزام والنسب المئوية لحصاد الموظفين:", user_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("perf_calc_"):
        mode = data.replace("perf_calc_", "")
        generate_user_performance_excel(user_id, mode)

    elif data == "adm_add_cat" and role == 'owner':
        session['step'] = "wait_new_cat"
        user_sessions[user_id] = session
        bot.send_message(user_id, "✍️ يرجى إرسال اسم القسم الرئيسي متبوعاً بشرطة ثم التصنيف الفرعي المراد إضافته لشجرة الأزرار.\n\nمثال:\nالأنشطة الهندسية - فحص وصيانة شبكات وتمديدات")

    elif data == "adm_change_passes" and role == 'owner':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔑 تعديل رمز الأعضاء/المستخدمين", callback_data="pass_mod_user"))
        markup.add(types.InlineKeyboardButton("👑 تعديل رمز الملاك والمشرفين", callback_data="pass_mod_admin"))
        bot.edit_message_text("🔐 اختر الرمز الأمني المراد إدخال تعديل فوري عليه لحماية المنظومة:", user_id, call.message.message_id, reply_markup=markup)

    elif data == "pass_mod_user" and role == 'owner':
        session['step'] = "wait_new_user_pass"
        user_sessions[user_id] = session
        bot.send_message(user_id, "✍️ أرسل الآن الرمز السري الجديد المخصص لدخول المستخدمين والعاملين:")

    elif data == "pass_mod_admin" and role == 'owner':
        session['step'] = "wait_new_admin_pass"
        user_sessions[user_id] = session
        bot.send_message(user_id, "✍️ أرسل الآن الرمز السري الجديد المخصص لدخول الملاك والمشرفين:")

    elif data == "adm_add_admin" and role == 'owner':
        session['step'] = "wait_add_admin_id"
        user_sessions[user_id] = session
        bot.send_message(user_id, "👤 يرجى إرسال المعرف الرقمي (User ID) للشخص المراد ترقيته فوراً لرتبة مشرف عادي:")

    elif data == "adm_ban_user" and role == 'owner':
        session['step'] = "wait_ban_user_id"
        user_sessions[user_id] = session
        bot.send_message(user_id, "🚫 يرجى إرسال المعرف الرقمي (User ID) للحساب المطلوب حظره وطرده نهائياً من الصلاحيات:")

# --- دالة مساعدة لطلب إرسال الملف في الأرشفة ---
def ask_for_archive_file(user_id, message_id):
    session = user_sessions[user_id]
    session['step'] = "wait_archive_file"
    user_sessions[user_id] = session
    
    details = f"📅 الشهر: {session['hijri_month']} | 📌 الأسبوع: {session['hijri_week']}\n🗂️ التصنيف العام: {session['main_category']}\n🔍 الفرع: {session['sub_category']}"
    bot.send_message(user_id, f"📥 *المسار مهيأ وجاهز لاستقبال التقارير والوثائق:*\n\n{details}\n\nيرجى الآن رفع المادة المطلوبة (سواء كانت رسالة نصية، صورة مفردة، مقطع فيديو، أو مستند بأي صيغة كانت).", parse_mode="Markdown")

# --- دالة التنفيذ النهائي والادخال الفعلي للأرشيف الماستر ---
def execute_final_archiving(user_id):
    session = user_sessions.get(user_id, {})
    msg = session.get('msg_content')
    
    # التحقق مما إذا كانت الأرشفة قادمة من زر التكامل الفوري لنظام القولبة الجاهز
    is_instant = 'instant_file_id' in session
    
    content_type = "نص"
    content_data = ""
    file_id = ""
    username = "غير معروف"
    
    if is_instant:
        content_type = "صورة مقولبة جاهزة"
        file_id = session['instant_file_id']
        content_data = "تقرير مصور ومقوْلب تم توليده وترحيله عبر النظام الفوري للبوت."
        conn = sqlite3.connect('library_archive.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM members WHERE user_id=?", (user_id,))
        res = cursor.fetchone()
        if res: username = res[0]
        conn.close()
    else:
        username = msg.from_user.username if msg.from_user.username else "لا يوجد"
        if msg.content_type == 'text':
            content_type = "نص"
            content_data = msg.text
        elif msg.content_type == 'photo':
            content_type = "صورة"
            content_data = msg.caption if msg.caption else "تقرير مصور بدون تعليق نصي"
            file_id = msg.photo[-1].file_id
        elif msg.content_type == 'video':
            content_type = "فيديو"
            content_data = msg.caption if msg.caption else "توثيق مرئي/فيديو"
            file_id = msg.video.file_id
        elif msg.content_type == 'document':
            content_type = "مستند/ملف"
            content_data = msg.caption if msg.caption else msg.document.file_name
            file_id = msg.document.file_id

    # الحفظ النهائي في قاعدة بيانات الأرشيف العام
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO archive_master 
                      (user_id, username, hijri_month, hijri_week, main_category, sub_category, content_type, content_data, file_id, actual_date, timestamp) 
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (user_id, username, session['hijri_month'], session['hijri_week'], session['main_category'], session['sub_category'], content_type, content_data, file_id, session['actual_date'], str(datetime.now())))
    conn.commit()
    
    # جلب المشرفين لإرسال إشعارات فورية لهم بحسب الرقابة الصارمة للمنظومة
    cursor.execute("SELECT user_id FROM members WHERE role IN ('owner', 'admin')")
    admins = cursor.fetchall()
    conn.close()
    
    bot.send_message(user_id, "✅ تم أرشفة المادة وفهرستها بنجاح داخل قاعدة البيانات المركزية للمكتبة الإلكترونية.", reply_markup=build_main_menu(user_id))
    
    # بث الإشعار الفوري للمشرفين
    for adm in admins:
        try:
            alert = f"🔔 *إشعار رقابي بأرشفة مادة جديدة:*\n\n👤 الموظف: @{username}\n📅 الفترة: شهر {session['hijri_month']} - {session['hijri_week']}\n🗂️ التصنيف: {session['main_category']} -> {session['sub_category']}\n⏱️ التاريخ الفعلي المعتمد: {session['actual_date']}"
            bot.send_message(adm[0], alert, parse_mode="Markdown")
        except:
            pass
            
    # تصفير الجلسة تماماً
    user_sessions[user_id] = {}

# =====================================================================
# 📊 نظام تصدير البيانات إلى ملفات Excel الذكية (الإحصائيات والالتزام)
# =====================================================================
def generate_excel_statistics(user_id, month):
    conn = sqlite3.connect('library_archive.db')
    query = "SELECT hijri_week, main_category, sub_category, content_type, actual_date, username FROM archive_master WHERE hijri_month=?"
    df = pd.read_sql_query(query, conn, params=(month,))
    conn.close()
    
    if df.empty:
        bot.send_message(user_id, f"📭 لا توجد أي بيانات مؤرشفة لشهر {month} لتوليد التقارير الإحصائية المجدولة لها.")
        return
        
    filename = f"حصاد_إحصائي_شهر_{month}.xlsx"
    
    # إنشاء وحفظ ملف الإكسل المجدول والمنسق تلقائياً عبر Pandas
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='السجل التفصيلي العام', index=False)
        
        # إنشاء جدول محوري إحصائي يوضح أداء وحصاد كل أسبوع للأنشطة المختلفة بشكل منظم
        summary = df.groupby(['hijri_week', 'main_category']).size().reset_index(name='إجمالي التوثيقات المرفوعة')
        summary.to_excel(writer, sheet_name='الملخص الإحصائي المجمع', index=False)
        
    with open(filename, 'rb') as file:
        bot.send_document(user_id, file, caption=f"📊 التقرير الإحصائي وجدول الحصاد الشامل المعتمد لشهر هجري ({month}) بصيغة Excel الجاهزة للطباعة الإدارية.")
    os.remove(filename)

def generate_user_performance_excel(admin_id, mode):
    conn = sqlite3.connect('library_archive.db')
    # جلب جميع المستخدمين المسجلين في النظام
    users_df = pd.read_sql_query("SELECT user_id, username FROM members WHERE role='user'", conn)
    archive_df = pd.read_sql_query("SELECT user_id, hijri_week, hijri_month FROM archive_master", conn)
    conn.close()
    
    if users_df.empty:
        bot.send_message(admin_id, "❌ لا يوجد مستخدمين مسجلين بالنظام حالياً لقياس كفاءة أداء التزامهم.")
        return
        
    perf_data = []
    
    if mode == "week":
        weeks = ["الأسبوع الأول", "الأسبوع الثاني", "الأسبوع الثالث", "الأسبوع الرابع"]
        for _, u in users_df.iterrows():
            row = {"اسم المستخدم": f"@{u['username']}"}
            total_score = 0
            for w in weeks:
                # الفحص والتدقيق: هل يمتلك الشخص على الأقل مرفوعاً واحداً في هذا الأسبوع؟
                has_uploaded = archive_df[(archive_df['user_id'] == u['user_id']) & (archive_df['hijri_week'] == w)]
                score = 1 if not has_uploaded.empty else 0
                row[w] = score
                total_score += score
            row["إجمالي المرفوعات الملتزم بها"] = total_score
            row["نسبة الالتزام والتقييم"] = f"{(total_score / 4) * 100}%"
            perf_data.append(row)
    else:
        # التقييم والرقابة على النطاق الشهري للأشهر الـ 12 هجرية
        for _, u in users_df.iterrows():
            row = {"اسم المستخدم": f"@{u['username']}"}
            total_score = 0
            for m in range(1, 13):
                has_uploaded = archive_df[(archive_df['user_id'] == u['user_id']) & (archive_df['hijri_month'] == str(m))]
                score = 1 if not has_uploaded.empty else 0
                row[f"شهر {m}"] = score
                total_score += score
            row["إجمالي الأشهر الملتزم بها"] = total_score
            row["نسبة الالتزام والتقييم الشهري"] = f"{(total_score / 12) * 100:.1f}%"
            perf_data.append(row)
            
    final_perf_df = pd.DataFrame(perf_data)
    fn = f"جدول_الالتزام_ورقابة_الأداء_{mode}.xlsx"
    final_perf_df.to_excel(fn, index=False)
    
    with open(fn, 'rb') as f:
        bot.send_document(admin_id, f, caption=f"📈 كشف تقييم الأداء ومصفوفة نسب الالتزام الدورية للعاملين والموثقين بالمنظومة بنمط الحساب التلقائي (1 ملتزم، 0 غائب ومقصر).")
    os.remove(fn)

# =====================================================================
# 🔍 محرك استعراض وتنزيل الملفات الذكي
# =====================================================================
def fetch_and_send_archive_by_time(user_id, type_search, value_search):
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    
    if type_search == "day":
        cursor.execute("SELECT content_type, content_data, file_id, main_category, username FROM archive_master WHERE actual_date=?", (value_search,))
    else:
        # الاسترجاع بالأسبوع الكامل: قراءة التاريخ والبحث عنه في أي سجل يطابق نفس الشهر والاسبوع المسجلين في هذا التاريخ
        cursor.execute("SELECT hijri_month, hijri_week FROM archive_master WHERE actual_date=?", (value_search,))
        res_match = cursor.fetchone()
        if res_match:
            cursor.execute("SELECT content_type, content_data, file_id, main_category, username FROM archive_master WHERE hijri_month=? AND hijri_week=?", res_match)
        else:
            conn.close()
            bot.send_message(user_id, "📭 لم يتم العثور على أي ملفات مؤرشفة مسجلة في التواريخ التابعة لهذا النطاق الزمني.")
            user_sessions[user_id] = {}
            return
            
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(user_id, "📭 لم يتم العثور على أي ملفات مؤرشفة مسجلة في التواريخ التابعة لهذا النطاق الزمني.")
        user_sessions[user_id] = {}
        return
        
    bot.send_message(user_id, f"📦 جاري تنزيل وسحب التوثيقات التي تم العثور عليها ومطابقتها بالنظام والبالغ عددها ({len(rows)})... يرجى الانتظار:")
    
    for r in rows:
        c_type, c_data, file_id, main_cat, creator = r
        cap = f"📁 القسم: {main_cat}\n👤 الموثق: @{creator}\n📝 المضمون/التعليق: {c_data}"
        
        if c_type == "نص":
            bot.send_message(user_id, f"📄 *[تقرير نصي محفوظ]*\n\n{cap}", parse_mode="Markdown")
        elif c_type in ["صورة", "صورة مقولبة جاهزة"]:
            bot.send_photo(user_id, file_id, caption=cap)
        elif c_type == "فيديو":
            bot.send_video(user_id, file_id, caption=cap)
        elif c_type == "مستند/ملف":
            bot.send_document(user_id, file_id, caption=cap)
            
    user_sessions[user_id] = {}

# =====================================================================
# 🎨 نظام القولبة الذكي وتوليد تقارير الـ Grid الشبكية
# =====================================================================
def process_and_generate_template(user_id):
    session = user_sessions[user_id]
    photos_list = session['template_photos']
    text_to_write = session['template_text']
    
    bot.send_message(user_id, "⏳ جاري تحميل الصور المرفوعة ومعالجتها وتركيبها داخل القالب الرسمي للجهة وتنسيق الخطوط العربي...")
    
    downloaded_paths = []
    for idx, f_id in enumerate(photos_list):
        f_info = bot.get_file(f_id)
        downloaded = bot.download_file(f_info.file_path)
        path = f"tmp_img_{user_id}_{idx}.jpg"
        with open(path, 'wb') as f:
            f.write(downloaded)
        downloaded_paths.append(path)
        
    try:
        # إنشاء اللوحة الفنية الأساسية (Canvas) بمقاس افتراضي ثابت للتقارير الفاخرة (1200x1200) بكسل
        canvas_w, canvas_h = 1200, 1350
        output_image = Image.new("RGB", (canvas_w, canvas_h), "white")
        draw = ImageDraw.Draw(output_image)
        
        # فتح وتجهيز الصور وتصغير أحجامها لتتلاءم مع النطاق الشبكي (Grid Setup)
        opened_images = [Image.open(p) for p in downloaded_paths]
        
        if len(opened_images) == 1:
            # صورة واحدة تغطي مساحة النصف العلوي بامتياز
            img_resized = opened_images[0].resize((1100, 750), Image.Resampling.LANCZOS)
            output_image.paste(img_resized, (50, 50))
            
        elif len(opened_images) == 2:
            # صورتين بجانب بعضهما البعض
            img1 = opened_images[0].resize((540, 750), Image.Resampling.LANCZOS)
            img2 = opened_images[1].resize((540, 750), Image.Resampling.LANCZOS)
            output_image.paste(img1, (50, 50))
            output_image.paste(img2, (610, 50))
            
        elif len(opened_images) == 4:
            # أربعة صور مصفوفة في شبكة هيدروليكية كاملة (2x2)
            img1 = opened_images[0].resize((540, 360), Image.Resampling.LANCZOS)
            img2 = opened_images[1].resize((540, 360), Image.Resampling.LANCZOS)
            img3 = opened_images[2].resize((540, 360), Image.Resampling.LANCZOS)
            img4 = opened_images[3].resize((540, 360), Image.Resampling.LANCZOS)
            
            output_image.paste(img1, (50, 50))
            output_image.paste(img2, (610, 50))
            output_image.paste(img3, (50, 440))
            output_image.paste(img4, (610, 440))

        # طباعة نص التقرير المكتوب أسفل الصور
        # ملاحظة: يمكنك تحميل ملف خط عربي مثل Arial أو Amiri ووضعه في السيرفر لتنسيقه
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            font = ImageFont.load_default()
            
        # رسم منطقة للكتابة بحدود وهوامش آمنة
        text_y_position = 880 if len(opened_images) < 4 else 850
        
        # كتابة النص المكتوب بأسلوب يراعي التفاف النص التلقائي البسيط
        draw.text((60, text_y_position), f"المضمون الإخباري والتوثيقي للنشاط:\n{text_to_write}", fill="black", font=font)
        
        # في حال وجود ملف شعار للجهة باسم logo.png يتم تركيبه تلقائياً كعلامة مائية احترافية متكاملة
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            logo = logo.resize((150, 150), Image.Resampling.LANCZOS)
            output_image.paste(logo, (1000, canvas_h - 180), mask=logo)
            
        output_filename = f"final_template_{user_id}.jpg"
        output_image.save(output_filename, "JPEG")
        
        # إرسال الصورة النهائية والمنسقة للمستخدم ومرفق بها زر التكامل والترحيل للأرشيف
        with open(output_filename, 'rb') as ready_photo:
            sent_msg = bot.send_photo(user_id, ready_photo, caption="✨ تم توليد وبناء قالب التصميم التوثيقي الموحد للجهة بنجاح وبشكل فوري.")
            
            # زر ذكي تفاعلي أسفل المادة يحتوي على المعرف الرقمي للملف المولد لترحيله بكبسة زر واحدة
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 [ إرسال هذه المادة الجاهزة إلى الأرشيف العام ]", callback_data=f"archive_instant_{sent_msg.photo[-1].file_id}"))
            markup.add(types.InlineKeyboardButton("⬅️ العودة للقائمة الرئيسية", callback_data="go_home"))
            bot.send_message(user_id, "⚙️ يمكنك الآن ترحيل هذا القالب مباشرة للأرشيف العام من هنا للفهرسة الحية:", reply_markup=markup)
            
        os.remove(output_filename)
    except Exception as e:
        bot.send_message(user_id, f"❌ حدث خطأ غير متوقع أثناء معالجة الصور وبناء القالب: {str(e)}")
        
    # تنظيف وتفريغ الملفات المؤقتة من السيرفر فوراً
    for p in downloaded_paths:
        if os.path.exists(p): os.remove(p)

# --- بدء تشغيل البوت وحث خوادم تليجرام على الإنصات الفوري الطويل ---
if __name__ == '__main__':
    print("⚡ منظومة المكتبة الإلكترونية للأرشفة والقولبة تعمل الآن على السيرفر المركزي...")
    bot.infinity_polling()