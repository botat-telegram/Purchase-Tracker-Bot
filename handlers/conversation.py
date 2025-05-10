"""
معالجات المحادثة
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.config import WELCOME_MESSAGE as welcome_message, PRICE, NOTES
from utils.number_converter import convert_to_english_numbers, extract_price_from_text
from database.sheets import add_to_sheets, add_multiple_to_sheets, SheetsError
import traceback
import re
from handlers.gemini_integration import handle_unstructured_message, GEMINI_CONFIRM, GEMINI_SELECT

# إعداد التسجيل
logger = logging.getLogger(__name__)

# كلمات تخطي الملاحظات
SKIP_NOTES_WORDS = [".", "لا", "-", "/s", "s", "لأ"]

def parse_product_line(line: str) -> tuple:
    """
    تحليل سطر منتج واحد
    
    يدعم الأنماط التالية:
    1. منتج سعر - مثال: كولا 23
    2. سعر منتج - مثال: 23 كولا
    3. منتج سعر ملاحظات - مثال: كولا 23 بارد
    4. منتج بدون سعر - مثال: كولا
    5. التعامل مع العملات - مثال: كولا 23 ريال
    
    Args:
        line (str): سطر المنتج للتحليل
        
    Returns:
        tuple: (المنتج، السعر، الملاحظات) أو None في حالة الفشل
    """
    try:
        # تنظيف النص من المسافات الزائدة
        line = ' '.join(line.split())
        
        # تحويل الأرقام العربية إلى إنجليزية
        line = convert_to_english_numbers(line.strip())
        if not line:
            return None
            
        # استخراج جميع الأرقام من النص
        price_matches = re.findall(r'\b\d+(?:\.\d+)?\b', line)
        
        # إذا لم نجد أرقام، قد يكون منتج بدون سعر
        if not price_matches:
            return line.strip(), None, ""
            
        # نحاول البحث عن النمط الشائع: منتج سعر ملاحظات
        parts = line.split()
        
        # تحديد موقع الرقم (السعر)
        price_index = -1
        for i, part in enumerate(parts):
            try:
                float(part)
                price_index = i
                break
            except ValueError:
                continue
        
        # إذا وجدنا رقم (نمط: منتج سعر ملاحظات)
        if price_index > 0:
            product = " ".join(parts[:price_index])
            price = float(parts[price_index])
            notes = " ".join(parts[price_index + 1:])
            return product.strip(), price, notes.strip()
            
        # قد يكون النمط: سعر منتج
        elif price_index == 0:
            price = float(parts[0])
            product = " ".join(parts[1:])
            
            # قد يكون جزء من الاسم هو ملاحظات
            # نفترض أن أول 3 كلمات هي المنتج، وما بعدها ملاحظات
            product_parts = product.split()
            if len(product_parts) > 3:
                product = " ".join(product_parts[:3])
                notes = " ".join(product_parts[3:])
                return product.strip(), price, notes.strip()
            
            return product.strip(), price, ""
        
        # إذا كان النص لا يتبع النمط المعتاد
        # نحاول استخراج أول رقم واعتباره السعر
        price = float(price_matches[0])
        
        # نحذف الرقم والعملات من النص ونعتبر الباقي اسم المنتج
        text_without_price = line
        for match in price_matches:
            text_without_price = text_without_price.replace(match, " ")
        
        # إزالة أي كلمات عملة تم تركها (مثل "ريال" أو "دولار")
        currencies = ["ريال", "دولار", "جنيه", "درهم", "يورو", "رس", "r.s", "rs", "ر.س", "ر.س."]
        for currency in currencies:
            text_without_price = re.sub(r'\b' + re.escape(currency) + r'\b', " ", text_without_price, flags=re.IGNORECASE)
        
        # تنظيف النص النهائي
        text_without_price = ' '.join(text_without_price.split())
        
        # الآن يمكننا تقسيم النص إلى منتج وملاحظات
        product_parts = text_without_price.split()
        if not product_parts:
            return "منتج بدون اسم", price, ""
        
        # نفترض أن أول 3 كلمات هي المنتج، وما بعدها ملاحظات
        if len(product_parts) > 3:
            product = " ".join(product_parts[:3])
            notes = " ".join(product_parts[3:])
        else:
            product = text_without_price
            notes = ""
            
        return product.strip(), price, notes.strip()

    except Exception as e:
        logger.error(f"خطأ في تحليل السطر {line}: {str(e)}")
        logger.error(traceback.format_exc())
        return None

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أي رسالة نصية"""
    # التحقق مما إذا كنا في حالة حذف المنتجات
    if context.user_data.get('delete_type'):
        # نحن في حالة حذف، لذا لا نقوم بمعالجة الرسالة هنا
        # وبدلاً من ذلك نترك handler معالجة الحذف يقوم بذلك
        logger.info("تخطي معالجة الرسالة في handle_any_message لأننا في حالة حذف")
        return None
    
    text = update.message.text.strip()
    
    # تحقق مما إذا كان النص يحتوي على أسطر متعددة
    lines = text.split('\n')
    
    # تحديد ما إذا كان يجب إرسال النص مباشرة إلى Gemini
    should_use_gemini_directly = False
    
    # الشرط 1: إذا كان هناك أكثر من 3 أسطر
    if len([l for l in lines if l.strip()]) > 3:
        should_use_gemini_directly = True
        logger.info("استخدام Gemini مباشرة: أكثر من 3 أسطر")
    
    # الشرط 2: تحقق من طول النص (قد يكون وصف طويل)
    if not should_use_gemini_directly and len(text) > 100:
        should_use_gemini_directly = True
        logger.info("استخدام Gemini مباشرة: النص طويل")
    
    # الشرط 3: تحقق من تنسيق غير معتاد
    if not should_use_gemini_directly:
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # تحويل الأرقام العربية إلى إنجليزية للفحص
            converted_line = convert_to_english_numbers(line)
            
            # تحقق من وجود أرقام متعددة في السطر (قد يشير إلى وجود رقم في الملاحظات)
            numbers_count = sum(1 for part in converted_line.split() if any(char.isdigit() for char in part))
            if numbers_count > 2:  # تغيير من 1 إلى 2 للسماح بأنماط أكثر مرونة
                should_use_gemini_directly = True
                logger.info(f"استخدام Gemini مباشرة: وجود أرقام متعددة في السطر: '{line}'")
                break
                
            # تجربة تحليل السطر التقليدي
            result = parse_product_line(line)
            if not result:
                # إذا فشل التحليل تماماً
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
                    await update.message.reply_text(welcome_message)
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
        
        # إذا لم نتمكن من معالجة جميع الأسطر، نستخدم Gemini
        if errors:
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
                    
                # إرسال رسالة ترحيب بعد الإضافة
                await update.message.reply_text(welcome_message)
                return ConversationHandler.END
            except SheetsError as e:
                logger.error(f"خطأ في إضافة المنتج: {str(e)}")
                await update.message.reply_text(f"خطأ في الاتصال بقاعدة البيانات: {str(e)}")
            except ValueError as e:
                logger.error(f"خطأ في بيانات المنتج: {str(e)}")
                await update.message.reply_text(f"خطأ في بيانات المنتج: {str(e)}")
            except Exception as e:
                logger.error(f"خطأ غير متوقع: {str(e)}")
                await update.message.reply_text(f"حدث خطأ غير متوقع: {str(e)}")
        elif result and result[1] is None:  # إذا وجدنا منتج بدون سعر
            # حفظ المنتج وانتقل إلى مرحلة إدخال السعر
            context.user_data['product'] = result[0]
            await update.message.reply_text(f"أدخل سعر المنتج {result[0]}:")
            return PRICE
        else:
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
        # تحويل النص إلى أرقام إنجليزية
        text = convert_to_english_numbers(update.message.text.strip())
        
        # استخراج السعر
        price_value = extract_price_from_text(text)
        
        if price_value is None:
            await update.message.reply_text("لم أتمكن من فهم السعر. الرجاء إدخال رقم صحيح:")
            return PRICE
            
        if price_value <= 0:
            await update.message.reply_text("السعر يجب أن يكون أكبر من صفر. الرجاء إدخال السعر مرة أخرى:")
            return PRICE
            
        context.user_data['price'] = price_value
        await update.message.reply_text(
            f"تم استلام السعر: {price_value}\n"
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
    except SheetsError as e:
        await update.message.reply_text(f"خطأ في الاتصال بقاعدة البيانات: {str(e)}")
    except ValueError as e:
        await update.message.reply_text(f"خطأ في بيانات المنتج: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ غير متوقع: {str(e)}")
    
    return ConversationHandler.END