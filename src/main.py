"""
النقطة الرئيسية لتشغيل البوت

هذا الملف هو النقطة الرئيسية للبوت. يقوم بما يلي:
1. إعداد التسجيل (logging)
2. التحقق من توكن البوت
3. إنشاء وإعداد التطبيق
4. إضافة معالجات الأوامر والمحادثة
5. تشغيل البوت

يجب أن يكون ملف .env موجوداً ويحتوي على:
TELEGRAM_TOKEN=your_bot_token_here
"""
import os
import logging
import signal
import sys
import atexit
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler

from src.config import TOKEN, PRICE, NOTES, PRODUCT
from handlers.commands import (
    start_command, 
    help_command, 
    skip_command, 
    cancel,
    handle_product,
    handle_price,
    handle_notes,
)
from handlers.conversation import handle_any_message
from handlers.gemini_integration import gemini_callback_handler, GEMINI_CONFIRM, GEMINI_SELECT

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# مسار ملف القفل
LOCK_FILE = Path("bot.lock")

def cleanup():
    """تنظيف الموارد عند إغلاق البوت"""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            logger.info("تم حذف ملف القفل")
    except Exception as e:
        logger.error(f"خطأ في حذف ملف القفل: {str(e)}")

def signal_handler(signum, frame):
    """معالج إشارات النظام للإغلاق الآمن"""
    logger.info("تم استلام إشارة إيقاف. جاري إغلاق البوت...")
    cleanup()
    sys.exit(0)

async def error_handler(update: Update, context) -> None:
    """معالج الأخطاء العامة"""
    logger.error(f"حدث خطأ أثناء معالجة التحديث: {context.error}")
    if update:
        await update.message.reply_text(
            "عذراً، حدث خطأ أثناء معالجة طلبك. الرجاء المحاولة مرة أخرى."
        )

def main() -> None:
    """
    الدالة الرئيسية للبوت
    تقوم بإعداد وتشغيل البوت
    
    Raises:
        ValueError: إذا لم يتم العثور على توكن البوت
        Exception: إذا حدث خطأ أثناء تشغيل البوت
    """
    try:
        # إعداد معالج الإشارات
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("جاري التحقق من توكن البوت...")
        if not TOKEN:
            raise ValueError("لم يتم العثور على توكن البوت. تأكد من وجود TELEGRAM_TOKEN في ملف .env")
        logger.info(f"تم العثور على التوكن: {TOKEN[:5]}...")
        
        logger.info("جاري إنشاء التطبيق...")
        app = Application.builder().token(TOKEN).build()
        logger.info("تم إنشاء التطبيق بنجاح")
        
        # إضافة معالج الأخطاء
        app.add_error_handler(error_handler)
        
        logger.info("جاري إعداد معالج المحادثة...")
        logger.info("تسجيل الأوامر: start, s, cancel")
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', start_command),
            ],
            states={
                PRODUCT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product),
                    CommandHandler('s', skip_command),
                ],
                PRICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price),
                    CommandHandler('s', skip_command),
                ],
                NOTES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_notes),
                    CommandHandler('s', skip_command),
                ],
                GEMINI_CONFIRM: [
                    CallbackQueryHandler(gemini_callback_handler),
                ],
                GEMINI_SELECT: [
                    CallbackQueryHandler(gemini_callback_handler),
                ],
            },
            fallbacks=[
                CommandHandler('start', start_command),
                CommandHandler('cancel', cancel),
            ],
            name="المحادثة_الرئيسية",
            persistent=False
        )
        logger.info("تم إعداد معالج المحادثة بنجاح")
        
        logger.info("جاري إضافة المعالجات...")
        app.add_handler(conv_handler)
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CallbackQueryHandler(gemini_callback_handler))
        
        # إضافة معالج للرسائل النصية العادية
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message))
        
        logger.info("تم إضافة المعالجات بنجاح")
        
        logger.info("جاري تشغيل البوت...")
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # تجاهل التحديثات القديمة
            stop_signals=[],  # منع الإيقاف التلقائي
            close_loop=False
        )
        logger.info("تم تشغيل البوت بنجاح!")
        
    except ValueError as e:
        logger.error(f"خطأ في التحقق: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"حدث خطأ غير متوقع: {str(e)}")
        if "Conflict: terminated by other getUpdates request" in str(e):
            logger.error("يبدو أن هناك نسخة أخرى من البوت قيد التشغيل. الرجاء إيقاف النسخة الأخرى قبل تشغيل نسخة جديدة.")
        sys.exit(1)

if __name__ == '__main__':
    atexit.register(cleanup)
    if LOCK_FILE.exists():
        logger.error("يبدو أن هناك نسخة أخرى من البوت قيد التشغيل. الرجاء إيقاف النسخة الأخرى قبل تشغيل نسخة جديدة.")
        sys.exit(1)
    else:
        LOCK_FILE.touch()
        logger.info("تم إنشاء ملف القفل")
        main()
