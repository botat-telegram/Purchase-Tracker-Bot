"""
نقطة بداية تشغيل البوت

هذا الملف هو نقطة البداية لتشغيل البوت. يقوم بما يلي:
1. إضافة المجلد الرئيسي إلى مسار البحث عن الوحدات
2. التحقق من وجود ملفات الاعتماد المطلوبة
3. تهيئة السجلات
4. بدء تشغيل البوت

تم إصلاح مشكلة استيراد gemini_confirmation_callback واستبدالها بـ gemini_callback_handler
وإضافة تحقق من نسخ البوت المتعددة لمنع خطأ "Conflict: terminated by other getUpdates request"
"""

import os
import sys
import logging
import logging.handlers
import atexit
import tempfile
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackQueryHandler
)

# إعداد مسار البحث أولاً
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
    
# استيراد الوحدات المحلية
try:
    from src.config import WELCOME_MESSAGE, PRICE, NOTES
    from handlers.conversation import handle_any_message, price, notes
    from handlers.commands import (
        start, cancel, skip_command, help_command, 
        last_products_command, handle_button_clicks,
        handle_callback_query, last_ten_command, today_command,
        handle_delete_selection, handle_delete_confirm, DELETE_SELECTION, DELETE_CONFIRM
    )
    from handlers.gemini_integration import gemini_callback_handler, GEMINI_CONFIRM, GEMINI_SELECT
except ImportError as e:
    # طباعة الخطأ للتشخيص
    print(f"خطأ في الاستيراد: {e}")
    sys.exit(1)

# إعداد السجلات
logger = logging.getLogger(__name__)

def setup_python_path():
    """
    إضافة المجلد الرئيسي إلى مسار البحث عن الوحدات
    لضمان استيراد الوحدات بشكل صحيح
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
        logger.debug(f"تمت إضافة المجلد {current_dir} إلى مسار البحث")

def check_credentials():
    """
    التحقق من وجود ملفات الاعتماد المطلوبة
    """
    # التحقق من وجود ملف .env
    if not os.path.exists('.env'):
        logger.error("ملف .env غير موجود!")
        print("""
        يجب إنشاء ملف .env يحتوي على:
        TELEGRAM_TOKEN=your_bot_token_here
        """)
        sys.exit(1)

    # تم تعطيل التحقق من وجود ملف credentials.json مؤقتاً للاختبار
    # if not os.path.exists('credentials.json'):
    #     logger.error("ملف credentials.json غير موجود!")
    #     print("""
    #     يجب وضع ملف credentials.json في المجلد الرئيسي
    #     يمكنك الحصول عليه من لوحة تحكم Google Cloud
    #     """)
    #     sys.exit(1)

def setup_logging():
    """إعداد السجلات"""
    # إنشاء مجلد للسجلات إذا لم يكن موجوداً
    log_dir = Path("logs")
    if not log_dir.exists():
        print("تم إنشاء مجلد السجلات")
        log_dir.mkdir()

    # تنسيق اسم ملف السجل
    log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    print(f"مجلد السجلات: {log_dir.absolute()}")

    # إعداد تنسيق السجلات
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # إعداد معالج الملف
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # إعداد معالج وحدة التحكم
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # إعداد السجل الرئيسي
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def is_bot_running():
    """التحقق مما إذا كان البوت يعمل بالفعل"""
    pid_file = os.path.join(tempfile.gettempdir(), "telegram_sheets_bot.pid")
    
    try:
        if os.path.exists(pid_file):
            try:
                # محاولة حذف الملف أولاً لتجنب التعارضات
                os.remove(pid_file)
                logger.info("تم حذف ملف PID قديم")
            except Exception as e:
                logger.warning(f"تعذر حذف ملف PID: {str(e)}")
                return False
                    
        # كتابة PID الحالي
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        # تسجيل دالة لحذف ملف PID عند إغلاق البوت
        atexit.register(lambda: os.remove(pid_file) if os.path.exists(pid_file) else None)
        return False
        
    except Exception as e:
        logger.error(f"خطأ في التحقق من حالة البوت: {str(e)}")
        # في حالة حدوث خطأ، نفترض أن البوت لا يعمل
        return False

async def post_init(application: Application) -> None:
    """يتم تنفيذ هذه الدالة بعد بدء البوت"""
    from database.sheets import DEMO_MODE
    logger.info("تم بدء تشغيل البوت!")
    if DEMO_MODE:
        mode_msg = "⚠️ البوت يعمل في الوضع التجريبي - لن يتم إضافة المنتجات إلى Google Sheets الفعلي"
    else:
        mode_msg = "🟢 البوت يعمل في الوضع العادي - سيتم إضافة المنتجات إلى Google Sheets"
    
    print(f"تم بدء تشغيل البوت! يمكنك الآن التفاعل معه على تيليجرام.")
    print(mode_msg)
    
    # إرسال رسالة للمشرفين (إذا كانت معرّفاتهم معروفة)
    try:
        admins = [123456789]  # ضع هنا معرّفات المشرفين
        for admin_id in admins:
            try:
                await application.bot.send_message(
                    chat_id=admin_id,
                    text=f"تم بدء تشغيل البوت!\n{mode_msg}"
                )
            except Exception:
                pass
    except Exception:
        pass

# تعريف المتغيرات العالمية
PRODUCT = 0

def main() -> None:
    """
    الدالة الرئيسية لبدء تشغيل البوت
    """
    # إعداد السجلات
    setup_logging()
    logger.info("=== بدء تشغيل البوت ===")
    
    # التحقق من عدم وجود نسخة أخرى من البوت
    if is_bot_running():
        logger.error("هناك نسخة أخرى من البوت قيد التشغيل! الخروج...")
        print("هناك نسخة أخرى من البوت قيد التشغيل! الرجاء إغلاق النسخة السابقة قبل تشغيل نسخة جديدة.")
        sys.exit(1)
    
    try:
        # إعداد مسار البحث
        setup_python_path()
        
        # التحقق من ملفات الاعتماد
        check_credentials()
        
        # تحميل المتغيرات البيئية
        load_dotenv()
        
        # الحصول على رمز البوت
        TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
        if not TELEGRAM_TOKEN:
            logger.error("لم يتم العثور على رمز البوت في ملف .env")
            sys.exit(1)
            
        # إنشاء التطبيق
        application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        
        # تأكد من وجود معرفات Gemini
        GEMINI_CONFIRM_STATE = GEMINI_CONFIRM
        GEMINI_SELECT_STATE = GEMINI_SELECT
        
        # إضافة معالجات الأوامر أولًا
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('last', last_products_command))
        application.add_handler(CommandHandler('last10', last_ten_command, filters.Regex(r'^/last10$')))
        application.add_handler(CommandHandler('today', today_command, filters.Regex(r'^/today$')))
        application.add_handler(CommandHandler('cancel', cancel))
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('s', skip_command))
        
        # إنشاء محادثة خاصة لعملية الحذف
        delete_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(handle_callback_query, pattern="^delete_today$"),
                CallbackQueryHandler(handle_callback_query, pattern="^delete_last10$"),
            ],
            states={
                DELETE_SELECTION: [
                    MessageHandler(filters.TEXT & filters.Regex(r'^❌ إلغاء العملية$'), cancel),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_selection),
                ],
                DELETE_CONFIRM: [
                    CallbackQueryHandler(handle_delete_confirm, pattern=r"^(confirm_delete|cancel_delete)$"),
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            name="delete_conversation",
            persistent=False,
        )

        # التأكد من إضافة معالج الحذف أولًا قبل أي معالجات أخرى
        logger.info("جاري إضافة معالج الحذف...")
        application.add_handler(delete_handler)

        # إضافة معالجات للأزرار العامة
        application.add_handler(CallbackQueryHandler(handle_callback_query, pattern="^total_"))
        application.add_handler(CallbackQueryHandler(handle_callback_query, pattern="^skip_notes$"))

        # إعداد المحادثة الرئيسية
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message),
            ],
            states={
                PRODUCT: [
                    MessageHandler(filters.TEXT & filters.Regex(r'^❌ إلغاء العملية$'), cancel),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message),
                ],
                PRICE: [
                    MessageHandler(filters.TEXT & filters.Regex(r'^❌ إلغاء العملية$'), cancel),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, price),
                    CommandHandler('s', skip_command),
                ],
                NOTES: [
                    MessageHandler(filters.TEXT & filters.Regex(r'^❌ إلغاء العملية$'), cancel),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, notes),
                    CommandHandler('s', skip_command),
                    CallbackQueryHandler(handle_callback_query, pattern=r"^skip_notes$"),
                ],
                # إضافة حالات Gemini بشكل صريح
                GEMINI_CONFIRM_STATE: [
                    CallbackQueryHandler(gemini_callback_handler),
                ],
                GEMINI_SELECT_STATE: [
                    CallbackQueryHandler(gemini_callback_handler),
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            name="main_conversation",
            persistent=False,
            per_message=False
        )

        # إضافة معالج المحادثة الرئيسية بعد معالج الحذف
        application.add_handler(conv_handler)

        # معالج عام للأزرار التي لم يتم التعامل معها بعد
        general_button_handler = CallbackQueryHandler(handle_callback_query)
        application.add_handler(general_button_handler)

        # معالج الرسائل النصية لأزرار الواجهة
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, handle_button_clicks
        ))
        
        # بدء البوت
        logger.info("جاري بدء البوت...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"خطأ: {str(e)}")
        if "Conflict: terminated by other getUpdates request" in str(e):
            logger.error("يبدو أن هناك نسخة أخرى من البوت قيد التشغيل. الرجاء إيقاف النسخة الأخرى قبل تشغيل نسخة جديدة.")
        
if __name__ == "__main__":
    main()
