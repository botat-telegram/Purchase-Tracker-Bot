"""
معالجات الأوامر
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.config import WELCOME_MESSAGE as welcome_message
from database.sheets import add_to_sheets

# إعداد التسجيل
logger = logging.getLogger(__name__)

# كلمات تخطي الملاحظات
SKIP_NOTES_WORDS = [".", "لا", "-", "/s", "s", "لأ"]

# حالات المحادثة
PRODUCT = 0
PRICE = 1
NOTES = 2

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أمر /start"""
    # مسح أي بيانات سابقة
    context.user_data.clear()
    
    await update.message.reply_text("تم إلغاء العملية السابقة ")
    await update.message.reply_text(welcome_message)
    return PRODUCT  # العودة لحالة إدخال اسم المنتج

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر المساعدة"""
    help_text = """
🛍️ مرحباً بك في بوت تتبع المشتريات!

الأوامر المتاحة:
/start - بدء محادثة جديدة
/s - تخطي الملاحظات
/cancel - إلغاء العملية الحالية
/help - عرض هذه المساعدة

يمكنك أيضاً تخطي الملاحظات عن طريق:
- إرسال '.' (نقطة)
- إرسال 'لا'
- إرسال '-'
"""
    await update.message.reply_text(help_text)

async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أمر التخطي"""
    logger.debug("تم استدعاء skip_command") # إضافة تسجيل للتتبع
    
    try:
        # إذا كنا في مرحلة الملاحظات
        if 'product' in context.user_data and 'price' in context.user_data:
            product = context.user_data['product']
            price = context.user_data['price']
            
            logger.debug(f"تخطي الملاحظات للمنتج: {product} بسعر {price}")
            
            await add_to_sheets(product, price, '')
            await update.message.reply_text(f"تم إضافة {product} بسعر {price} بدون ملاحظات")
            
            context.user_data.clear()
            await update.message.reply_text(welcome_message)
            return ConversationHandler.END
            
        # إذا كنا في مرحلة السعر
        elif context.user_data.get('product'):
            print("DEBUG: لدينا منتج فقط - لا يمكن تخطي السعر")
            await update.message.reply_text("لا يمكن تخطي إدخال السعر. الرجاء إدخال السعر:")
            return PRICE
            
        # إذا كنا في مرحلة المنتج
        else:
            print("DEBUG: لا يوجد منتج - لا يمكن تخطي اسم المنتج")
            await update.message.reply_text("لا يمكن تخطي إدخال اسم المنتج. الرجاء إدخال اسم المنتج:")
            return PRODUCT
            
    except Exception as e:
        print(f"DEBUG: حدث خطأ: {str(e)}")
        await update.message.reply_text(f"حدث خطأ: {str(e)}")
        return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    بداية المحادثة مع البوت
    يتم تنفيذ هذه الدالة عند إرسال الأمر /start
    """
    await update.message.reply_text(welcome_message)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    إلغاء المحادثة الحالية
    يتم تنفيذ هذه الدالة عند إرسال الأمر /cancel
    """
    await update.message.reply_text("تم إلغاء العملية الحالية. يمكنك البدء من جديد.")
    return ConversationHandler.END

async def handle_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج إدخال اسم المنتج"""
    product = update.message.text
    context.user_data['product'] = product
    await update.message.reply_text(f"تم استلام اسم المنتج: {product}\nالآن أدخل السعر:")
    return PRICE

async def handle_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج إدخال السعر"""
    try:
        price = float(update.message.text)
        if price <= 0:
            await update.message.reply_text("السعر يجب أن يكون أكبر من صفر. الرجاء إدخال السعر مرة أخرى:")
            return PRICE
            
        context.user_data['price'] = price
        await update.message.reply_text(
            f"تم استلام السعر: {price}\n"
            "هل تريد إضافة ملاحظة؟\n"
            "يمكنك تخطي الملاحظات عن طريق:\n"
            "- إرسال '.' (نقطة)\n"
            "- إرسال 'لا'\n"
            "- إرسال '-'\n"
            "- إرسال '/s'"
        )
        return NOTES
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح للسعر:")
        return PRICE

async def handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج إدخال الملاحظات"""
    # تجاهل الرسالة إذا كان المستخدم قد استخدم skip
    if not context.user_data:  # إذا تم مسح البيانات بواسطة skip
        return ConversationHandler.END
        
    notes = update.message.text
    
    # تخطي الملاحظات إذا كانت من كلمات التخطي
    if notes.strip().lower() in SKIP_NOTES_WORDS:
        notes = ''
    
    product = context.user_data['product']
    price = context.user_data['price']
    
    try:
        await add_to_sheets(product, price, notes)
        if notes:
            await update.message.reply_text(f"تم إضافة {product} بسعر {price} مع ملاحظة: {notes}")
        else:
            await update.message.reply_text(f"تم إضافة {product} بسعر {price}")
        
        # مسح بيانات المستخدم
        context.user_data.clear()
        
        await update.message.reply_text(welcome_message)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {str(e)}")
        return ConversationHandler.END
