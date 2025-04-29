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
from handlers.gemini_integration import handle_unstructured_message, GEMINI_CONFIRM, GEMINI_SELECT

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
        
        # التحقق من أن المنتج غير فارغ
        if not product.strip():
            return None
            
        return product.strip(), price, notes.strip()

    except Exception as e:
        logger.error(f"خطأ في تحليل السطر {line}: {str(e)}")
        return None

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أي رسالة نصية"""
    text = update.message.text.strip()
    
    # تحقق مما إذا كان النص يحتوي على أسطر متعددة
    lines = text.split('\n')
    
    # تحديد ما إذا كان يجب إرسال النص مباشرة إلى Gemini
    should_use_gemini_directly = False
    
    # الشرط 1: إذا كان هناك أكثر من 3 أسطر
    if len([l for l in lines if l.strip()]) > 3:
        should_use_gemini_directly = True
        logger.info("استخدام Gemini مباشرة: أكثر من 3 أسطر")
    
    # الشرط 2: تحقق من تنسيق غير معتاد (أرقام في الملاحظات، السعر قبل المنتج، إلخ)
    if not should_use_gemini_directly:
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # تحويل الأرقام العربية إلى إنجليزية للفحص
            converted_line = convert_to_english_numbers(line)
            
            # تحقق من وجود أرقام متعددة في السطر (قد يشير إلى وجود رقم في الملاحظات)
            numbers_count = sum(1 for part in converted_line.split() if any(char.isdigit() for char in part))
            if numbers_count > 1:
                should_use_gemini_directly = True
                logger.info(f"استخدام Gemini مباشرة: وجود أرقام متعددة في السطر: '{line}'")
                break
            
            # تحقق مما إذا كان السطر يبدأ برقم (قد يعني أن السعر قبل المنتج)
            if converted_line and any(char.isdigit() for char in converted_line.split()[0]):
                should_use_gemini_directly = True
                logger.info(f"استخدام Gemini مباشرة: السطر يبدأ برقم: '{line}'")
                break
            
            # تجربة تحليل السطر التقليدي
            result = parse_product_line(line)
            if not result or result[1] is None:
                # إذا فشل التحليل التقليدي
                should_use_gemini_directly = True
                logger.info(f"استخدام Gemini مباشرة: فشل التحليل التقليدي للسطر: '{line}'")
                break
    
    # إذا كان يجب استخدام Gemini مباشرة
    if should_use_gemini_directly:
        try:
            logger.info("إرسال النص مباشرة إلى Gemini للتحليل")
            result = await handle_unstructured_message(update, context)
            return result
        except Exception as e:
            logger.error(f"خطأ في استدعاء Gemini: {str(e)}")
            await update.message.reply_text(f"حدث خطأ أثناء تحليل الرسالة: {str(e)}")
            return ConversationHandler.END
    
    # إذا كان النص يحتوي على أسطر متعددة
    if len(lines) > 1:
        # معالجة رسالة متعددة الأسطر
        products_to_add = []
        errors = []
        parsed_lines = 0  # عدد الأسطر التي تم تحليلها بنجاح
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            result = parse_product_line(line)
            if result and result[1] is not None:  # إذا وجدنا منتج وسعر صالحين
                product, price, notes = result
                if not product:
                    errors.append(f"خطأ: المنتج فارغ في السطر '{line}'")
                    continue
                products_to_add.append((product, price, notes))
                parsed_lines += 1
            else:
                errors.append(f"تعذر فهم السطر: '{line}'")
        
        # فقط إذا نجحنا في تحليل جميع الأسطر وليس هناك أخطاء، أضف المنتجات
        if products_to_add and len(errors) == 0:
            try:
                success_count, add_errors = await add_multiple_to_sheets(products_to_add)
                
                # تجهيز رسالة الرد
                if success_count > 0:
                    message = f"تمت إضافة {success_count} منتج بنجاح."
                    if add_errors:
                        message += f"\nولكن حدثت {len(add_errors)} أخطاء:\n" + "\n".join(add_errors)
                    if errors:
                        message += f"\n\nتم تجاهل {len(errors)} سطر:\n" + "\n".join(errors)
                    
                    await update.message.reply_text(message)
                    return ConversationHandler.END
                else:
                    message = "لم تتم إضافة أي منتجات."
                    if add_errors:
                        message += f"\nحدثت الأخطاء التالية:\n" + "\n".join(add_errors)
                    if errors:
                        message += f"\n\nتم تجاهل {len(errors)} سطر:\n" + "\n".join(errors)
                    
                    await update.message.reply_text(message)
            except Exception as e:
                logger.error(f"خطأ في إضافة المنتجات: {str(e)}")
                await update.message.reply_text(f"حدث خطأ أثناء إضافة المنتجات: {str(e)}")
        
        # إذا لم نتمكن من معالجة أي من الأسطر، نستخدم Gemini
        if errors or len(products_to_add) == 0:
            try:
                # تخزين المنتجات التي تم إضافتها بنجاح
                if 'successful_products' not in context.user_data:
                    context.user_data['successful_products'] = []
                context.user_data['successful_products'].extend(products_to_add)
                
                # نرسل النص الأصلي كما هو إلى Gemini للتحليل
                logger.info("إرسال النص إلى Gemini بعد فشل التحليل التقليدي")
                result = await handle_unstructured_message(update, context)
                return result
                    
            except Exception as e:
                logger.error(f"خطأ في استدعاء Gemini: {str(e)}")
                await update.message.reply_text(f"حدث خطأ أثناء تحليل الرسالة: {str(e)}")
                return ConversationHandler.END
        
        return ConversationHandler.END
    else:
        # معالجة رسالة ذات سطر واحد
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
                await update.message.reply_text(f"خطأ في إضافة المنتج: {str(e)}")
        
        # إذا لم ننجح في تحليل النص، نجرب الذكاء الاصطناعي Gemini
        try:
            logger.info("إرسال النص إلى Gemini بعد فشل التحليل التقليدي (سطر واحد)")
            result = await handle_unstructured_message(update, context)
            return result
        except Exception as e:
            logger.error(f"خطأ في استدعاء Gemini: {str(e)}")
            await update.message.reply_text(f"حدث خطأ أثناء تحليل الرسالة: {str(e)}")
            return ConversationHandler.END

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