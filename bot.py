import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "YOUR_BOT_TOKEN_HERE"

# مراحل المحادثة الممتدة
(CHOOSING_MONTH, CHOOSING_SECTOR, CHOOSING_ACTIVITY, AWAITING_CONTENT, 
 VIEW_MONTH, VIEW_SECTOR, VIEW_ACTIVITY, VIEW_STATS_OPTION) = range(8)

HIJRI_MONTHS = ["محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة"]

# هيكلية القطاعات والأنشطة الموسعة
SECTORS = {
    "🔬 علمي وتعليمي": ["محاضرة", "ندوة", "مؤتمر", "حلقة نقاشية"],
    "🏫 تدريب وتطوير": ["دورة تدريبية", "ورشة عمل", "برنامج تأهيلي"],
    "💼 عمل إداري": ["اجتماع دوري", "لقاء تنسيقي", "محضر جلسة", "قرار وتكليف"],
    "🎥 إنتاج إعلامي": ["فيديو/مونتاج", "تصميم/جرافيك", "تغطية صحفية", "بودكاست"],
    "📝 مخرجات ورقـية": ["تقرير دوري", "كتاب/إصدار", "بحث ودراسة"],
    "✨ مبادرات ومواسم": ["حملة توعوية", "زيارة ميدانية", "فعالية موسمية"]
}

def init_db():
    conn = sqlite3.connect("advanced_archive.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT, sector TEXT, activity TEXT, content_type TEXT, content_value TEXT, caption TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# دالة مساعدة لإنشاء الأزرار ديناميكياً
def build_keyboard(items, col_size=2, back_target="cancel"):
    keyboard = []
    for i in range(0, len(items), col_size):
        row = [InlineKeyboardButton(item, callback_data=item) for item in items[i:i+col_size]]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 العودة للرئيسية", callback_data=back_target)])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📥 أرشفة توثيق جديد", callback_data="act_add")],
        [InlineKeyboardButton("🔍 تصفح الأرشيف الموسع", callback_data="act_view")],
        [InlineKeyboardButton("📊 لوحة الإحصائيات والتقارير", callback_data="act_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = "🗄 *مرحباً بك في نظام الأرشفة الهجرية الذكي*\n\nيرجى اختيار الإجراء المطلوب من القائمة أدناه:"
    
    if update.message:
        await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
    return ConversationHandler.END

# --- مسار الأرشفة ---
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("📅 اختر الشهر الهجري المراد الأرشفة فيه:", reply_markup=build_keyboard(HIJRI_MONTHS, 2))
    return CHOOSING_MONTH

async def save_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await start(update, context)
    context.user_data["add_month"] = query.data
    await query.message.edit_text("📁 اختر القطاع الرئيسي للنشاط:", reply_markup=build_keyboard(list(SECTORS.keys()), 1))
    return CHOOSING_SECTOR

async def save_sector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await start(update, context)
    context.user_data["add_sector"] = query.data
    activities = SECTORS[query.data]
    await query.message.edit_text(f"📍 قطاع {query.data}\nاختر النشاط الفرعي الدقيق:", reply_markup=build_keyboard(activities, 2))
    return CHOOSING_ACTIVITY

async def save_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await start(update, context)
    context.user_data["add_activity"] = query.data
    await query.message.edit_text(f"📅 الشهر: {context.user_data['add_month']}\n📌 النشاط: {query.data}\n\n📥 *الرجاء إرسال ملف التوثيق الآن* (صورة، فيديو، نص، ملف، تحويل)...", parse_mode="Markdown")
    return AWAITING_CONTENT

async def save_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    msg = update.message
    caption = msg.caption if msg.caption else ""
    
    if msg.text:
        content_type, content_value = "text", msg.text
    elif msg.photo:
        content_type, content_value = "photo", msg.photo[-1].file_id
    elif msg.video:
        content_type, content_value = "video", msg.video.file_id
    elif msg.document:
        content_type, content_value = "document", msg.document.file_id
    else:
        content_type, content_value = "unknown", ""

    conn = sqlite3.connect("advanced_archive.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO archive (month, sector, activity, content_type, content_value, caption) VALUES (?, ?, ?, ?, ?, ?)",
                   (ud["add_month"], ud["add_sector"], ud["add_activity"], content_type, content_value, caption))
    conn.commit()
    conn.close()
    
    await msg.reply_text(f"✅ تم بنجاح أرشفة المادة تحت تصنيف:\n📊 *{ud['add_month']}* ◄ *{ud['add_activity']}*", parse_mode="Markdown")
    ud.clear()
    return ConversationHandler.END

# --- مسار الإحصائيات ---
async def start_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📊 إحصائية شهر محدد", callback_data="stats_month")],
        [InlineKeyboardButton("📈 تقرير الأداء العام للعام الحالي", callback_data="stats_full")],
        [InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="cancel")]
    ]
    await query.message.edit_text("📊 *لوحة الإحصائيات الرقمية*\nاختر نوع التقرير المطلوب توليده كالتالي:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return VIEW_STATS_OPTION

async def process_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await start(update, context)
    
    conn = sqlite3.connect("advanced_archive.db")
    cursor = conn.cursor()
    
    if query.data == "stats_full":
        cursor.execute("SELECT month, COUNT(*) FROM archive GROUP BY month")
        rows = cursor.fetchall()
        conn.close()
        
        report = "📈 *تقرير حجم التوثيق العام للأشهر الهجرية:*\n\n"
        if not rows:
            report += "🗀 الأرشيف فارغ حالياً."
        for row in rows:
            report += f"• 📅 شهر *{row[0]}*: تم توثيق ({row[1]}) مادة.\n"
        
        await query.message.edit_text(report, parse_mode="Markdown", reply_markup=build_keyboard([], 1))
        return ConversationHandler.END
        
    elif query.data == "stats_month":
        await query.message.edit_text("📊 اختر الشهر المراد استخراج تقريره الرقمي التفصيلي:", reply_markup=build_keyboard(HIJRI_MONTHS, 2))
        return VIEW_MONTH

async def show_month_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await start(update, context)
    
    month = query.data
    conn = sqlite3.connect("advanced_archive.db")
    cursor = conn.cursor()
    cursor.execute("SELECT activity, COUNT(*) FROM archive WHERE month=? GROUP BY activity", (month,))
    rows = cursor.fetchall()
    conn.close()
    
    report = f"📊 *تحليل نشاط شهر ({month}):*\n\n"
    if not rows:
        report += "⚠️ لا توجد أنشطة مؤرشفة في هذا الشهر بعد."
    else:
        total = 0
        for row in rows:
            report += f"• {row[0]}: {row[1]} مادة مؤرشفة.\n"
            total += row[1]
        report += f"\n📥 *إجمالي العمليات الموثقة: {total}*"
        
    await query.message.edit_text(report, parse_mode="Markdown", reply_markup=build_keyboard([], 1))
    return ConversationHandler.END

# --- مسار تصفح واسترجاع المواد المرسلة ---
async def start_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("🔍 تصفح الأرشيف - اختر الشهر الهجري للتفتيش:", reply_markup=build_keyboard(HIJRI_MONTHS, 2))
    return VIEW_MONTH

async def view_month_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await start(update, context)
    context.user_data["view_month"] = query.data
    await query.message.edit_text(f"🔍 أرشيف شهر: *{query.data}*\nاختر القطاع المستهدف:", parse_mode="Markdown", reply_markup=build_keyboard(list(SECTORS.keys()), 1))
    return VIEW_SECTOR

async def view_sector_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await start(update, context)
    context.user_data["view_sector"] = query.data
    activities = SECTORS[query.data]
    await query.message.edit_text(f"📋 أرشيف شهر: {context.user_data['view_month']}\nاختر نوع النشاط التفصيلي لجلب ملفاته:", reply_markup=build_keyboard(activities, 2))
    return VIEW_ACTIVITY

async def view_final_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await start(update, context)
    
    month = context.user_data["view_month"]
    activity = query.data
    
    await query.message.edit_text(f"⏳ جاري تحميل مستندات وملفات قسم (*{month} ◄ {activity}*)...", parse_mode="Markdown")
    
    conn = sqlite3.connect("advanced_archive.db")
    cursor = conn.cursor()
    cursor.execute("SELECT content_type, content_value, caption FROM archive WHERE month=? AND activity=?", (month, activity))
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        await query.message.reply_text("📂 هذا القسم لا يحتوي على مواد مؤرشفة حالياً.")
        return ConversationHandler.END
        
    for c_type, c_val, caption in results:
        try:
            if c_type == "text":
                await query.message.reply_text(c_val)
            elif c_type == "photo":
                await query.message.reply_photo(photo=c_val, caption=caption)
            elif c_type == "video":
                await query.message.reply_video(video=c_val, caption=caption)
            elif c_type == "document":
                await query.message.reply_document(document=c_val, caption=caption)
        except Exception as e:
            logger.error(f"خطأ استرجاع: {e}")
            
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    return ConversationHandler.END

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add, pattern="^act_add$"),
            CallbackQueryHandler(start_view, pattern="^act_view$"),
            CallbackQueryHandler(start_stats, pattern="^act_stats$")
        ],
        states={
            CHOOSING_MONTH: [CallbackQueryHandler(save_month, pattern=f"^({'|'.join(HIJRI_MONTHS)}|cancel)$")],
            CHOOSING_SECTOR: [CallbackQueryHandler(save_sector, pattern=f"^({'|'.join(SECTORS.keys())}|cancel)$")],
            CHOOSING_ACTIVITY: [CallbackQueryHandler(save_activity, pattern=".*")],
            AWAITING_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, save_content)],
            
            VIEW_MONTH: [CallbackQueryHandler(view_month_selected, pattern=f"^({'|'.join(HIJRI_MONTHS)}|cancel)$"), CallbackQueryHandler(show_month_stats, pattern=f"^({'|'.join(HIJRI_MONTHS)}|cancel)$")],
            VIEW_SECTOR: [CallbackQueryHandler(view_sector_selected, pattern=f"^({'|'.join(SECTORS.keys())}|cancel)$")],
            VIEW_ACTIVITY: [CallbackQueryHandler(view_final_results, pattern=".*")],
            
            VIEW_STATS_OPTION: [CallbackQueryHandler(process_stats, pattern=".*")]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel, pattern="^cancel$")],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start, pattern="^cancel$"))
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
