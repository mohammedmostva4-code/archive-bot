import os
import threading
import time
from image_processor import process_template

# ذاكرة مؤقتة لجلسات القوالب
template_sessions = {}

def start_template_session(bot, chat_id, message_id):
    template_sessions[chat_id] = {
        'images': [],
        'title': '',
        'details': '',
        'step': 'images',
        'last_status_msg': None
    }
    bot.edit_message_text(
        "🖼 *مرحباً بك في خدمة قالب وجد أثر العمل*\n\n📸 فضلاً أرسل الآن 4 صور للنشاط (يمكنك إرسالها دفعة واحدة).",
        chat_id,
        message_id,
        parse_mode="Markdown"
    )

def handle_template_photo(bot, message):
    chat_id = message.chat.id
    if chat_id not in template_sessions or template_sessions[chat_id]['step'] != 'images':
        return False

    session = template_sessions[chat_id]
    
    # منع استقبال أكثر من 4 صور
    if len(session['images']) >= 4:
        return True

    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_dir = '/home/ubuntu/archive-bot/temp'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    img_path = f'{temp_dir}/{chat_id}_{len(session["images"])}.jpg'
    with open(img_path, 'wb') as f:
        f.write(downloaded_file)
    
    session['images'].append(img_path)
    
    # إدارة رسائل الحالة بشكل ذكي عند الإرسال دفعة واحدة
    def update_status():
        time.sleep(0.8)
        count = len(session['images'])
        if count < 4:
            if session['last_status_msg']:
                try: bot.delete_message(chat_id, session['last_status_msg'])
                except: pass
            msg = bot.send_message(chat_id, f"✅ تم استلام {count} من 4 صور. أرسل الباقي...")
            session['last_status_msg'] = msg.message_id
        elif count == 4 and session['step'] == 'images':
            session['step'] = 'title'
            if session['last_status_msg']:
                try: bot.delete_message(chat_id, session['last_status_msg'])
                except: pass
            msg = bot.send_message(chat_id, "✅ اكتمل استلام الصور الأربع.\n\n✍️ الآن أرسل *عنوان النشاط*:", parse_mode="Markdown")
            bot.register_next_step_handler(msg, lambda m: process_title_step(bot, m))

    threading.Thread(target=update_status).start()
    return True

def process_title_step(bot, message):
    chat_id = message.chat.id
    if chat_id not in template_sessions: return
    
    if message.content_type != 'text':
        msg = bot.send_message(chat_id, "❌ يرجى إرسال نص للعنوان:")
        bot.register_next_step_handler(msg, lambda m: process_title_step(bot, m))
        return

    template_sessions[chat_id]['title'] = message.text
    template_sessions[chat_id]['step'] = 'details'
    msg = bot.send_message(chat_id, "✍️ رائع، الآن أرسل *تفاصيل النشاط* (التاريخ، الجهة، المكان):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: process_details_step(bot, m))

def process_details_step(bot, message):
    chat_id = message.chat.id
    if chat_id not in template_sessions: return
    
    if message.content_type != 'text':
        msg = bot.send_message(chat_id, "❌ يرجى إرسال نص للتفاصيل:")
        bot.register_next_step_handler(msg, lambda m: process_details_step(bot, m))
        return

    session = template_sessions[chat_id]
    session['details'] = message.text
    
    bot.send_message(chat_id, "⏳ جاري معالجة الصور وتوليد القالب، يرجى الانتظار...")
    
    try:
        output_path = f'/home/ubuntu/archive-bot/temp/result_{chat_id}.png'
        success = process_template(session['images'], session['title'], session['details'], output_path)
        
        if success and os.path.exists(output_path):
            with open(output_path, 'rb') as photo:
                bot.send_photo(chat_id, photo, caption="✨ تم تجهيز قالب (وجد أثر العمل) بنجاح!")
        else:
            bot.send_message(chat_id, "❌ فشل في معالجة الصور. يرجى المحاولة مرة أخرى.")
            
        # تنظيف
        for img in session['images']:
            if os.path.exists(img): os.remove(img)
        if os.path.exists(output_path): os.remove(output_path)
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ: {str(e)}")
    
    # إنهاء الجلسة والعودة للقائمة الرئيسية (سيتم استدعاء main_menu من bot.py)
    del template_sessions[chat_id]
    return True
