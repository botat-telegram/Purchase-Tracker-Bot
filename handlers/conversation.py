"""
معالجات المحادثة
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.config import WELCOME_MESSAGE as welcome_message, PRICE, NOTES
from utils.number_converter import convert_to_english_numbers
from database.sheets import add_to_sheets, add_multiple_to_sheets, SheetsError
import traceback

# إعداد التسجيل
logger = logging.getLogger(__name__)

# كلمات تخطي الملاحظات
SKIP_NOTES_WORDS = [".", "لا", "-", "/s", "s", "لأ"]

def parse_product_line(line: str) -> tuple:
    """تحليل سطر منتج واحد"""
    try:
        # تنظيف النص من المسافات الزائدة
        line = ' '.join(line.split())
        
        # تحويل الأرقام العربية إلى إنجليزية
        line = convert_to_english_numbers(line.strip())
        if not line:
            return None
            
        # تقسيم النص إلى كلمات
        parts = line.split()
        if len(parts) < 1:  
            return None
            
        # البحث عن السعر (أول رقم نجده)
        price_index = -1
        for i, part in enumerate(parts):
            try:
                float(part)
                price_index = i
                break
            except ValueError:
                continue
                
        # إذا لم يتم العثور على سعر
        if price_index == -1:
            return " ".join(parts), None, ""
            
        # كل ما بعد السعر يعتبر ملاحظات
        product = " ".join(parts[:price_index])
        price = float(parts[price_index])
        notes = " ".join(parts[price_index + 1:])
        
        return product.strip(), price, notes.strip()

    except Exception as e:
        logger.error(f"خطأ في تحليل السطر {line}: {str(e)}")
        return None

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أي رسالة نصية"""
    text = update.message.text.strip()
    # محاولة تحليل النص كإدخال سريع
    result = parse_product_line(text)
    
    if result and result[1] is not None:  # إذا وجدنا منتج وسعر
        product, price, notes = result
        try:
            await add_to_sheets(product, price, notes)
            if notes:
                await update.message.reply_text(f"تم إضافة {product} بسعر {price} مع ملاحظة: {notes}")
            else:
                await update.message.reply_text(f"تم إضافة {product} بسعر {price}")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"خطأ في إضافة المنتج: {str(e)}")
    
    # إذا لم ننجح في تحليل النص، نتعامل معه كاسم منتج فقط
    context.user_data.clear()
    context.user_data['product'] = text
    await update.message.reply_text(f"تم استلام اسم المنتج: {text}\nالآن أدخل السعر:")
    return PRICE

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

async def notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج إدخال الملاحظات"""
    logger.debug("تم استدعاء معالج الملاحظات") # إضافة تسجيل للتتبع
    
    # تحقق من وجود البيانات الأساسية
    if 'product' not in context.user_data or 'price' not in context.user_data:
        logger.error("لا توجد بيانات للمنتج أو السعر")
        await update.message.reply_text("حدث خطأ. الرجاء البدء من جديد.")
        return ConversationHandler.END
        
    # تجاهل الرسالة إذا كان المستخدم قد استخدم skip
    if not context.user_data:  # إذا تم مسح البيانات بواسطة skip
        return ConversationHandler.END
        
    text = update.message.text
    
    # تخطي الملاحظات إذا كانت من كلمات التخطي
    if text.strip().lower() in SKIP_NOTES_WORDS:
        text = ''
    
    try:
        product = context.user_data['product']
        price = context.user_data['price']
        await add_to_sheets(product, price, text)
        
        if text:
            await update.message.reply_text(f"تم إضافة {product} بسعر {price} مع ملاحظة: {text}")
        else:
            await update.message.reply_text(f"تم إضافة {product} بسعر {price}")
        
        # مسح بيانات المستخدم
        context.user_data.clear()
        
        await update.message.reply_text(WELCOME_MESSAGE)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {str(e)}")
        return ConversationHandler.END