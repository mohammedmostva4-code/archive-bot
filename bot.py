import telebot
from telebot import types
import sqlite3
import os
import json
from datetime import datetime
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# --- الإعدادات والرموز الافتراضية الثنائية ---
TOKEN = '8951535425:AAHUWdQgR36yjvIq-6NdUt1sIDrreYXGAuE'  # ضع توكن البوت هنا
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
            bot.send_message(user_id, "❌ حدث خطأ، تأكد من إرسال معرف رقمي صحيح.", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    elif step == "wait_remove_admin_id" and message.content_type == 'text':
        try:
            target_id = int(message.text.strip())
            conn = sqlite3.connect('library_archive.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM members WHERE user_id=? AND role='admin'", (target_id,))
            conn.commit()
            conn.close()
            bot.send_message(user_id, f"✅ تم إزالة الحساب رقم {target_id} من رتبة مشرف بنجاح.", reply_markup=build_main_menu(user_id))
        except:
            bot.send_message(user_id, "❌ حدث خطأ، تأكد من إرسال معرف رقمي صحيح.", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    elif step == "wait_ban_user_id" and message.content_type == 'text':
        try:
            target_id = int(message.text.strip())
            conn = sqlite3.connect('library_archive.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE members SET status='banned' WHERE user_id=?", (target_id,))
            conn.commit()
            conn.close()
            bot.send_message(user_id, f"✅ تم حظر الحساب رقم {target_id} بنجاح.", reply_markup=build_main_menu(user_id))
        except:
            bot.send_message(user_id, "❌ حدث خطأ، تأكد من إرسال معرف رقمي صحيح.", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    elif step == "wait_unban_user_id" and message.content_type == 'text':
        try:
            target_id = int(message.text.strip())
            conn = sqlite3.connect('library_archive.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE members SET status='active' WHERE user_id=?", (target_id,))
            conn.commit()
            conn.close()
            bot.send_message(user_id, f"✅ تم إلغاء حظر الحساب رقم {target_id} بنجاح.", reply_markup=build_main_menu(user_id))
        except:
            bot.send_message(user_id, "❌ حدث خطأ، تأكد من إرسال معرف رقمي صحيح.", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    # 7. مدخلات تغيير رتبة المستخدم
    elif step == "wait_change_role_id" and message.content_type == 'text':
        try:
            target_id = int(message.text.strip())
            session['target_user_id'] = target_id
            user_sessions[user_id] = session
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("ترقية إلى مشرف", callback_data="change_role_admin"))
            markup.add(types.InlineKeyboardButton("تنزيل إلى مستخدم عادي", callback_data="change_role_user"))
            bot.send_message(user_id, f"اختر الرتبة الجديدة للحساب رقم {target_id}:", reply_markup=markup)
        except:
            bot.send_message(user_id, "❌ حدث خطأ، تأكد من إرسال معرف رقمي صحيح.", reply_markup=build_main_menu(user_id))
        return

    # رسائل غير متوقعة في غير سياقها
    if step:
        bot.send_message(user_id, "⚠️ رسالة غير متوقعة في هذا السياق. يرجى استخدام الأزرار أو إدخال البيانات المطلوبة.", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    # رسائل عامة لا تتطلب رداً محدداً
    bot.send_message(user_id, "👋 أهلاً بك! يرجى استخدام الأزرار المتاحة أو أمر /start للبدء.", reply_markup=build_main_menu(user_id))

# --- دالة معالجة الاستدعاءات (Callbacks) من الأزرار ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data
    role = get_user_role(user_id)
    
    bot.answer_callback_query(call.id)
    
    if role == 'banned':
        bot.send_message(user_id, "❌ عذراً، لقد تم حظر حسابك من قبل المشرف العام.")
        return

    session = user_sessions.get(user_id, {})

    # 1. القائمة الرئيسية (UI)
    if data == "ui_archive":
        if role not in ['owner', 'admin', 'user']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة. يرجى إدخال الرمز السري أولاً.")
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="main_menu"))
        bot.edit_message_text("📂 *البدء في الأرشفة والتصنيف:*
\nالرجاء إرسال المادة التوثيقية (صورة، مستند، فيديو) التي ترغب بأرشفتها. بعد إرسالها، سيطلب منك إدخال تفاصيل التصنيف.", user_id, message_id, reply_markup=markup, parse_mode="Markdown")
        session['step'] = "wait_archive_file"
        user_sessions[user_id] = session
        
    elif data == "ui_stats":
        if role not in ['owner', 'admin', 'user']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة. يرجى إدخال الرمز السري أولاً.")
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📊 تقارير إحصائية عامة", callback_data="stats_general"))
        markup.add(types.InlineKeyboardButton("🔍 البحث عن تقارير حسب اليوم", callback_data="search_by_day"))
        markup.add(types.InlineKeyboardButton("🗓️ البحث عن تقارير حسب الأسبوع", callback_data="search_by_week"))
        markup.add(types.InlineKeyboardButton("⬇️ تصدير الأرشيف إلى Excel", callback_data="export_excel"))
        markup.add(types.InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="main_menu"))
        bot.edit_message_text("📊 *التقارير الإحصائية والاسترجاع:*
\nاختر نوع التقرير أو البحث الذي ترغب به:", user_id, message_id, reply_markup=markup, parse_mode="Markdown")
        user_sessions[user_id] = {}

    elif data == "ui_template":
        if role not in ['owner', 'admin', 'user']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة. يرجى إدخال الرمز السري أولاً.")
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🖼️ قالب صورة واحدة", callback_data="template_single_photo"))
        markup.add(types.InlineKeyboardButton("📸 قالب صورتين", callback_data="template_two_photos"))
        markup.add(types.InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="main_menu"))
        bot.edit_message_text("🎨 *نظام القولبة الذكي:*
\nاختر نوع القالب الذي ترغب بإنشائه:", user_id, message_id, reply_markup=markup, parse_mode="Markdown")
        user_sessions[user_id] = {}

    # 2. أزرار الأرشفة والتصنيف
    elif data == "time_auto":
        execute_final_archiving(user_id, auto_date=True)
        bot.edit_message_text("✅ تم الأرشفة بنجاح بتاريخ اليوم الحالي.", user_id, message_id, reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}

    elif data == "time_manual":
        bot.edit_message_text("✏️ الرجاء إدخال التاريخ الذي ترغب بأرشفة المادة به (مثال: 2026-07-06):
\n*ملاحظة: إذا أدخلت تاريخاً هجرياً، سيتم تحويله تلقائياً إلى ميلادي.*", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_manual_date"
        user_sessions[user_id] = session

    elif data.startswith("cat_"):
        session['main_category'] = data.replace("cat_", "")
        user_sessions[user_id] = session
        send_sub_categories(user_id, message_id, session['main_category'])

    elif data.startswith("subcat_"):
        session['sub_category'] = data.replace("subcat_", "")
        user_sessions[user_id] = session
        send_content_types(user_id, message_id)

    elif data.startswith("ctype_"):
        session['content_type'] = data.replace("ctype_", "")
        user_sessions[user_id] = session
        execute_final_archiving(user_id)
        bot.edit_message_text("✅ تم الأرشفة بنجاح.", user_id, message_id, reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}

    # 3. أزرار التقارير والإحصائيات
    elif data == "stats_general":
        if role not in ['owner', 'admin', 'user']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        send_general_stats(user_id, message_id)
        user_sessions[user_id] = {}

    elif data == "search_by_day":
        if role not in ['owner', 'admin', 'user']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        bot.edit_message_text("🔍 *البحث عن تقارير حسب اليوم:*
\nالرجاء إدخال التاريخ المطلوب (مثال: 2026-07-06 أو 1447-12-10 هـ):
\n*ملاحظة: يمكنك إدخال التاريخ الميلادي أو الهجري، وسيتم البحث في كلاهما.*", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_search_day"
        user_sessions[user_id] = session

    elif data == "search_by_week":
        if role not in ['owner', 'admin', 'user']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        bot.edit_message_text("🗓️ *البحث عن تقارير حسب الأسبوع:*
\nالرجاء إدخال رقم الأسبوع في السنة (مثال: 28) أو تاريخ ضمن الأسبوع (مثال: 2026-07-06):
\n*ملاحظة: إذا أدخلت تاريخاً، سيتم استخراج رقم الأسبوع منه تلقائياً.*", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_search_week"
        user_sessions[user_id] = session

    elif data == "export_excel":
        if role not in ['owner', 'admin']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية لتصدير الأرشيف إلى Excel.")
            return
        export_archive_to_excel(user_id)
        bot.edit_message_text("✅ جاري إعداد ملف Excel وتصديره لك...", user_id, message_id, reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}

    # 4. أزرار القولبة الذكية
    elif data == "template_single_photo":
        if role not in ['owner', 'admin', 'user']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        bot.edit_message_text("🖼️ *قالب صورة واحدة:*
\nالرجاء إرسال الصورة التي ترغب بوضع النص عليها.", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_template_photos"
        session['target_photos_count'] = 1
        user_sessions[user_id] = session

    elif data == "template_two_photos":
        if role not in ['owner', 'admin', 'user']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        bot.edit_message_text("📸 *قالب صورتين:*
\nالرجاء إرسال الصورة الأولى.", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_template_photos"
        session['target_photos_count'] = 2
        user_sessions[user_id] = session

    # 5. لوحة التحكم الإدارية (للمالك والمشرفين)
    elif data == "admin_main":
        if role not in ['owner', 'admin']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى لوحة التحكم الإدارية.")
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة قسم/تصنيف جديد", callback_data="admin_add_category"))
        markup.add(types.InlineKeyboardButton("🔑 تغيير رمز دخول المستخدمين", callback_data="admin_change_user_pass"))
        if role == 'owner': # فقط المالك يمكنه تغيير رمز المشرفين وإدارة المشرفين
            markup.add(types.InlineKeyboardButton("👑 تغيير رمز دخول المشرفين", callback_data="admin_change_admin_pass"))
            markup.add(types.InlineKeyboardButton("➕ إضافة مشرف جديد", callback_data="admin_add_admin"))
            markup.add(types.InlineKeyboardButton("➖ إزالة مشرف", callback_data="admin_remove_admin"))
            markup.add(types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user"))
            markup.add(types.InlineKeyboardButton("✅ إلغاء حظر مستخدم", callback_data="admin_unban_user"))
            markup.add(types.InlineKeyboardButton("🔄 تغيير رتبة مستخدم", callback_data="admin_change_role"))
        markup.add(types.InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="main_menu"))
        bot.edit_message_text("⚙️ *لوحة التحكم الإدارية:*
\nاختر الإجراء الإداري المطلوب:", user_id, message_id, reply_markup=markup, parse_mode="Markdown")
        user_sessions[user_id] = {}

    elif data == "admin_add_category":
        if role not in ['owner', 'admin']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        bot.edit_message_text("➕ *إضافة قسم/تصنيف جديد:*
\nالرجاء إدخال القسم الرئيسي والتصنيف الفرعي مفصولين بعلامة '-' (مثال: أنشطة الإعلام - التحرير الإخباري):
\n*ملاحظة: سيتم إضافة القسم والتصنيف إلى شجرة الأنشطة الديناميكية.*", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_new_cat"
        user_sessions[user_id] = session

    elif data == "admin_change_user_pass":
        if role not in ['owner', 'admin']:
            bot.send_message(user_id, "❌ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        bot.edit_message_text("🔑 *تغيير رمز دخول المستخدمين:*
\nالرجاء إدخال الرمز السري الجديد للمستخدمين:", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_new_user_pass"
        user_sessions[user_id] = session

    elif data == "admin_change_admin_pass":
        if role != 'owner':
            bot.send_message(user_id, "❌ ليس لديك صلاحية لتغيير رمز دخول المشرفين.")
            return
        bot.edit_message_text("👑 *تغيير رمز دخول المشرفين:*
\nالرجاء إدخال الرمز السري الجديد للمشرفين:", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_new_admin_pass"
        user_sessions[user_id] = session

    elif data == "admin_add_admin":
        if role != 'owner':
            bot.send_message(user_id, "❌ ليس لديك صلاحية لإضافة مشرفين.")
            return
        bot.edit_message_text("➕ *إضافة مشرف جديد:*
\nالرجاء إدخال معرف المستخدم (User ID) الخاص بالمستخدم الذي ترغب بترقيته إلى مشرف:", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_add_admin_id"
        user_sessions[user_id] = session

    elif data == "admin_remove_admin":
        if role != 'owner':
            bot.send_message(user_id, "❌ ليس لديك صلاحية لإزالة مشرفين.")
            return
        bot.edit_message_text("➖ *إزالة مشرف:*
\nالرجاء إدخال معرف المستخدم (User ID) الخاص بالمشرف الذي ترغب بإزالته:", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_remove_admin_id"
        user_sessions[user_id] = session

    elif data == "admin_ban_user":
        if role != 'owner':
            bot.send_message(user_id, "❌ ليس لديك صلاحية لحظر المستخدمين.")
            return
        bot.edit_message_text("🚫 *حظر مستخدم:*
\nالرجاء إدخال معرف المستخدم (User ID) الخاص بالمستخدم الذي ترغب بحظره:", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_ban_user_id"
        user_sessions[user_id] = session

    elif data == "admin_unban_user":
        if role != 'owner':
            bot.send_message(user_id, "❌ ليس لديك صلاحية لإلغاء حظر المستخدمين.")
            return
        bot.edit_message_text("✅ *إلغاء حظر مستخدم:*
\nالرجاء إدخال معرف المستخدم (User ID) الخاص بالمستخدم الذي ترغب بإلغاء حظره:", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_unban_user_id"
        user_sessions[user_id] = session

    elif data == "admin_change_role":
        if role != 'owner':
            bot.send_message(user_id, "❌ ليس لديك صلاحية لتغيير رتب المستخدمين.")
            return
        bot.edit_message_text("🔄 *تغيير رتبة مستخدم:*
\nالرجاء إدخال معرف المستخدم (User ID) الخاص بالمستخدم الذي ترغب بتغيير رتبته:", user_id, message_id, parse_mode="Markdown")
        session['step'] = "wait_change_role_id"
        user_sessions[user_id] = session

    elif data == "change_role_admin":
        if role != 'owner' or 'target_user_id' not in session:
            bot.send_message(user_id, "❌ ليس لديك صلاحية لتغيير رتب المستخدمين أو حدث خطأ.")
            return
        target_id = session['target_user_id']
        conn = sqlite3.connect('library_archive.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE members SET role='admin' WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        bot.edit_message_text(f"✅ تم ترقية الحساب رقم {target_id} إلى رتبة مشرف بنجاح.", user_id, message_id, reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}

    elif data == "change_role_user":
        if role != 'owner' or 'target_user_id' not in session:
            bot.send_message(user_id, "❌ ليس لديك صلاحية لتغيير رتب المستخدمين أو حدث خطأ.")
            return
        target_id = session['target_user_id']
        conn = sqlite3.connect('library_archive.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE members SET role='user' WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        bot.edit_message_text(f"✅ تم تنزيل الحساب رقم {target_id} إلى رتبة مستخدم عادي بنجاح.", user_id, message_id, reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}

    # 6. العودة للقائمة الرئيسية
    elif data == "main_menu":
        bot.edit_message_text("📲 مرحباً بك مجدداً في منظومة الأرشفة الإلكترونية. اختر من القائمة التالية:", user_id, message_id, reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}

# --- دالات مساعدة للأرشفة والتقارير ---
def send_categories(user_id, message_id):
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM activity_types")
    categories = cursor.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        markup.add(types.InlineKeyboardButton(cat[0], callback_data=f"cat_{cat[0]}"))
    markup.add(types.InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="main_menu"))
    bot.edit_message_text("الرجاء اختيار القسم الرئيسي للمادة المؤرشفة:", user_id, message_id, reply_markup=markup)

def send_sub_categories(user_id, message_id, main_category):
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sub_category FROM activity_types WHERE category=?", (main_category,))
    sub_categories = cursor.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    for sub_cat in sub_categories:
        markup.add(types.InlineKeyboardButton(sub_cat[0], callback_data=f"subcat_{sub_cat[0]}"))
    markup.add(types.InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="main_menu"))
    bot.edit_message_text(f"الرجاء اختيار التصنيف الفرعي ضمن '{main_category}':", user_id, message_id, reply_markup=markup)

def send_content_types(user_id, message_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("نص", callback_data="ctype_text"))
    markup.add(types.InlineKeyboardButton("صورة", callback_data="ctype_photo"))
    markup.add(types.InlineKeyboardButton("مستند", callback_data="ctype_document"))
    markup.add(types.InlineKeyboardButton("فيديو", callback_data="ctype_video"))
    markup.add(types.InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="main_menu"))
    bot.edit_message_text("الرجاء تحديد نوع المحتوى الذي تم إرساله:", user_id, message_id, reply_markup=markup)

def execute_final_archiving(user_id, auto_date=False):
    session = user_sessions.get(user_id, {})
    msg_content = session.get('msg_content')
    main_category = session.get('main_category')
    sub_category = session.get('sub_category')
    content_type = session.get('content_type')
    actual_date = session.get('actual_date')

    if not msg_content or not main_category or not sub_category or not content_type:
        bot.send_message(user_id, "❌ حدث خطأ في استكمال بيانات الأرشفة. يرجى المحاولة مرة أخرى من البداية.", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    file_id = None
    content_data = None

    if msg_content.content_type == 'text':
        content_data = msg_content.text
    elif msg_content.content_type == 'photo':
        file_id = msg_content.photo[-1].file_id
        content_data = msg_content.caption if msg_content.caption else "صورة بدون وصف"
    elif msg_content.content_type == 'document':
        file_id = msg_content.document.file_id
        content_data = msg_content.caption if msg_content.caption else "مستند بدون وصف"
    elif msg_content.content_type == 'video':
        file_id = msg_content.video.file_id
        content_data = msg_content.caption if msg_content.caption else "فيديو بدون وصف"

    if auto_date:
        actual_date = datetime.now().strftime("%Y-%m-%d")

    # تحويل التاريخ الهجري إلى ميلادي إذا لزم الأمر
    if actual_date and ('هـ' in actual_date or 'H' in actual_date.upper()):
        try:
            # هذه دالة وهمية، تحتاج إلى مكتبة تحويل حقيقية مثل hijri-converter
            # لغرض التجربة، نفترض أننا نحولها إلى تاريخ ميلادي افتراضي
            # يجب تثبيت: pip install hijri-converter
            from hijri_converter import Hijri
            hijri_date_parts = actual_date.replace('هـ', '').replace('H', '').strip().split('-')
            h_year, h_month, h_day = int(hijri_date_parts[0]), int(hijri_date_parts[1]), int(hijri_date_parts[2])
            gregorian_date = Hijri(h_year, h_month, h_day).to_gregorian()
            actual_date = gregorian_date.strftime("%Y-%m-%d")
        except Exception as e:
            bot.send_message(user_id, f"❌ حدث خطأ في تحويل التاريخ الهجري: {e}. يرجى إدخال تاريخ ميلادي صحيح.", reply_markup=build_main_menu(user_id))
            user_sessions[user_id] = {}
            return
    elif not actual_date:
        bot.send_message(user_id, "❌ لم يتم تحديد تاريخ للأرشفة. يرجى المحاولة مرة أخرى.", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO archive_master (user_id, username, hijri_month, hijri_week, main_category, sub_category, content_type, content_data, file_id, actual_date, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (user_id, msg_content.from_user.username, "", "", main_category, sub_category, content_type, content_data, file_id, actual_date, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    user_sessions[user_id] = {}
    send_categories(user_id, msg_content.message_id) # لإعادة توجيه المستخدم لاختيار التصنيف التالي

def send_general_stats(user_id, message_id):
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    cursor.execute("SELECT main_category, COUNT(*) FROM archive_master GROUP BY main_category")
    main_cat_stats = cursor.fetchall()
    cursor.execute("SELECT sub_category, COUNT(*) FROM archive_master GROUP BY sub_category")
    sub_cat_stats = cursor.fetchall()
    cursor.execute("SELECT username, COUNT(*) FROM archive_master GROUP BY username")
    user_stats = cursor.fetchall()
    cursor.execute("SELECT content_type, COUNT(*) FROM archive_master GROUP BY content_type")
    content_type_stats = cursor.fetchall()
    conn.close()

    stats_text = "📊 *إحصائيات الأرشيف العامة:*
\n*الأقسام الرئيسية:*
"
    for cat, count in main_cat_stats:
        stats_text += f"- {cat}: {count} مادة\n"
    
    stats_text += "\n*التصنيفات الفرعية:*
"
    for sub_cat, count in sub_cat_stats:
        stats_text += f"- {sub_cat}: {count} مادة\n"

    stats_text += "\n*المستخدمون الأكثر أرشفة:*
"
    for username, count in user_stats:
        stats_text += f"- {username}: {count} مادة\n"

    stats_text += "\n*أنواع المحتوى:*
"
    for ctype, count in content_type_stats:
        stats_text += f"- {ctype}: {count} مادة\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("العودة للقائمة الرئيسية", callback_data="main_menu"))
    bot.edit_message_text(stats_text, user_id, message_id, reply_markup=markup, parse_mode="Markdown")

def fetch_and_send_archive_by_time(user_id, time_unit, query_value):
    conn = sqlite3.connect('library_archive.db')
    cursor = conn.cursor()
    results = []
    title = ""

    if time_unit == "day":
        # محاولة تحويل التاريخ الهجري إلى ميلادي للبحث
        search_date = query_value
        if 'هـ' in query_value or 'H' in query_value.upper():
            try:
                from hijri_converter import Hijri
                hijri_date_parts = query_value.replace('هـ', '').replace('H', '').strip().split('-')
                h_year, h_month, h_day = int(hijri_date_parts[0]), int(hijri_date_parts[1]), int(hijri_date_parts[2])
                gregorian_date = Hijri(h_year, h_month, h_day).to_gregorian()
                search_date = gregorian_date.strftime("%Y-%m-%d")
            except Exception as e:
                bot.send_message(user_id, f"❌ حدث خطأ في تحويل التاريخ الهجري: {e}. يرجى إدخال تاريخ صحيح.", reply_markup=build_main_menu(user_id))
                conn.close()
                user_sessions[user_id] = {}
                return
        
        cursor.execute("SELECT username, main_category, sub_category, content_type, content_data, file_id, actual_date FROM archive_master WHERE actual_date=?", (search_date,))
        results = cursor.fetchall()
        title = f"تقارير يوم {search_date}"

    elif time_unit == "week":
        week_number = None
        try:
            # إذا كان المدخل تاريخاً، استخرج رقم الأسبوع منه
            if '-' in query_value:
                input_date = datetime.strptime(query_value, "%Y-%m-%d")
                week_number = input_date.isocalendar()[1]
            else:
                week_number = int(query_value)
            
            # البحث عن التقارير التي تقع ضمن هذا الأسبوع
            # هذه العملية قد تكون معقدة وتعتمد على كيفية تخزين رقم الأسبوع في DB
            # لغرض التبسيط، سنبحث عن أي تاريخ يقع ضمن الأسبوع المحدد في السنة الحالية
            # يجب تحسين هذه الجزئية لتكون أكثر دقة
            current_year = datetime.now().year
            cursor.execute("SELECT username, main_category, sub_category, content_type, content_data, file_id, actual_date FROM archive_master WHERE STRFTIME('%W', actual_date) = ? AND STRFTIME('%Y', actual_date) = ?", (f'{week_number:02d}', str(current_year)))
            results = cursor.fetchall()
            title = f"تقارير الأسبوع رقم {week_number} في سنة {current_year}"

        except ValueError:
            bot.send_message(user_id, "❌ الرجاء إدخال رقم أسبوع صحيح أو تاريخ بصيغة YYYY-MM-DD.", reply_markup=build_main_menu(user_id))
            conn.close()
            user_sessions[user_id] = {}
            return

    conn.close()

    if results:
        response_text = f"📊 *{title}:*\n\n"
        for i, res in enumerate(results):
            response_text += f"*تقرير رقم {i+1}:*\n"
            response_text += f"  المستخدم: {res[0]}\n"
            response_text += f"  القسم الرئيسي: {res[1]}\n"
            response_text += f"  التصنيف الفرعي: {res[2]}\n"
            response_text += f"  نوع المحتوى: {res[3]}\n"
            response_text += f"  التاريخ: {res[6]}\n"
            if res[4]: # content_data
                response_text += f"  المحتوى: {res[4][:100]}...\n" # عرض أول 100 حرف
            if res[5]: # file_id
                response_text += f"  معرف الملف: {res[5]}\n"
            response_text += "\n"
        bot.send_message(user_id, response_text, parse_mode="Markdown", reply_markup=build_main_menu(user_id))
    else:
        bot.send_message(user_id, f"❌ لا توجد تقارير متاحة لـ {title}.", reply_markup=build_main_menu(user_id))
    user_sessions[user_id] = {}

def export_archive_to_excel(user_id):
    conn = sqlite3.connect('library_archive.db')
    df = pd.read_sql_query("SELECT user_id, username, hijri_month, hijri_week, main_category, sub_category, content_type, content_data, file_id, actual_date, timestamp FROM archive_master", conn)
    conn.close()

    if not df.empty:
        excel_file_path = "/home/ubuntu/archive-bot/archive_report.xlsx"
        df.to_excel(excel_file_path, index=False, engine='openpyxl')
        with open(excel_file_path, 'rb') as excel_file:
            bot.send_document(user_id, excel_file, caption="✅ تم تصدير الأرشيف بنجاح إلى ملف Excel.", reply_markup=build_main_menu(user_id))
    else:
        bot.send_message(user_id, "❌ لا توجد بيانات في الأرشيف لتصديرها.", reply_markup=build_main_menu(user_id))

def process_and_generate_template(user_id):
    session = user_sessions.get(user_id, {})
    photos = session.get('template_photos')
    text = session.get('template_text')
    target_count = session.get('target_photos_count')

    if not photos or not text or len(photos) != target_count:
        bot.send_message(user_id, "❌ حدث خطأ في بيانات القولبة. يرجى المحاولة مرة أخرى.", reply_markup=build_main_menu(user_id))
        user_sessions[user_id] = {}
        return

    # لغرض التبسيط، سنقوم بإنشاء صورة واحدة فقط تحتوي على النص
    # في تطبيق حقيقي، ستحتاج إلى تحميل الصور من Telegram باستخدام file_id
    # ودمجها مع النص باستخدام مكتبة PIL (Pillow)
    
    # مثال بسيط لإنشاء صورة مع النص (يحتاج إلى تحسين كبير)
    try:
        # افتراض أننا نعمل على الصورة الأولى فقط
        # يجب تحميل الصورة الفعلية من تليجرام
        # file_info = bot.get_file(photos[0])
        # downloaded_file = bot.download_file(file_info.file_path)
        # with open("temp_template_image.jpg", 'wb') as new_file:
        #     new_file.write(downloaded_file)
        # img = Image.open("temp_template_image.jpg")

        # إنشاء صورة بيضاء كقاعدة للاختبار
        img = Image.new('RGB', (800, 600), color = (255, 255, 255))
        d = ImageDraw.Draw(img)
        
        # محاولة تحميل خط يدعم العربية
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20) # مثال لخط موجود في معظم أنظمة لينكس
        except IOError:
            font = ImageFont.load_default() # الخط الافتراضي إذا لم يتوفر

        # تقسيم النص إلى أسطر لتناسب عرض الصورة
        def wrap_text(text, font, max_width):
            lines = []
            if not text: return lines
            words = text.split(' ')
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                if d.textbbox((0,0), test_line, font=font)[2] <= max_width:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            lines.append(' '.join(current_line))
            return lines

        wrapped_text = wrap_text(text, font, 750) # 750 بكسل عرض للنص
        
        y_text = 50 # بداية النص من الأعلى
        for line in wrapped_text:
            # لتصحيح اتجاه النص العربي
            bidi_text = line[::-1] # عكس النص ليعرض بشكل صحيح (تبسيط)
            d.text((50, y_text), bidi_text, fill=(0,0,0), font=font)
            y_text += 30 # مسافة بين الأسطر

        output_image_path = "/home/ubuntu/archive-bot/generated_template.png"
        img.save(output_image_path)

        with open(output_image_path, 'rb') as photo_file:
            bot.send_photo(user_id, photo_file, caption="✅ تم إنشاء القالب بنجاح مع النص.", reply_markup=build_main_menu(user_id))

    except Exception as e:
        bot.send_message(user_id, f"❌ حدث خطأ أثناء إنشاء القالب: {e}. يرجى المحاولة مرة أخرى.", reply_markup=build_main_menu(user_id))

    user_sessions[user_id] = {}

# --- بدء تشغيل البوت ---
if __name__ == '__main__':
    print("Bot started...")
    bot.polling(none_stop=True)
