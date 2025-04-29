"""
معالجة النصوص غير المنظمة باستخدام Gemini
هذا الملف يحتوي على منطق إرسال النصوص إلى Gemini، عرض النتائج للمستخدم، وانتظار الموافقة.
"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler
from utils.gemini import analyze_products_with_gemini, GeminiAPIError, DEFAULT_NOTES_KEYWORDS
from database.sheets import add_product_to_sheet
from src.config import GEMINI_API_KEY, WELCOME_MESSAGE
import json

# إعداد التسجيل
logger = logging.getLogger(__name__)

# حالات المحادثة
GEMINI_CONFIRM = 1000
GEMINI_SELECT = 1001

async def handle_unstructured_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text=None) -> int:
    """
    إرسال رسالة غير منظمة إلى Gemini للتحليل، وعرض نتائج التحليل للمستخدم.
    
    Args:
        update: تحديث التليجرام
        context: سياق المحادثة
        text: نص اختياري للتحليل (إذا كان None، سيتم استخدام نص الرسالة)
        
    Returns:
        حالة المحادثة التالية
    """
    chat_id = update.effective_chat.id
    # استخدام النص المحدد إذا تم تمريره، وإلا استخدام نص الرسالة
    message_text = text if text is not None else update.message.text
    
    # تقسيم الرسالة إلى أسطر متعددة وإزالة الأسطر الفارغة
    lines = [line.strip() for line in message_text.split('\n') if line.strip()]
    
    if len(lines) == 1:
        # إذا كان هناك سطر واحد فقط، قم بتحليله باستخدام Gemini
        try:
            products = await analyze_products_with_gemini(message_text)
            if not products:
                await update.message.reply_text("لم أتمكن من تحليل رسالتك. يرجى المحاولة مرة أخرى بصيغة مختلفة.")
                return ConversationHandler.END
                
            # حفظ المنتجات في سياق المستخدم
            context.user_data['gemini_products'] = products
            
            # عرض المنتجات التي تم تحليلها للمستخدم
            message = "🔎 لقد حللت رسالتك وحددت المنتجات التالية:\n\n"
            for i, product in enumerate(products, 1):
                product_name = product.get('product', 'غير معروف')
                price = product.get('price', 'غير معروف')
                notes = product.get('notes', '')
                notes_text = f" - ملاحظات: {notes}" if notes else ""
                message += f"{i}. {product_name} - السعر: {price}{notes_text}\n"
            
            message += "\nهل تريد إضافة هذه المنتجات إلى الجدول؟"
            
            # إنشاء أزرار التأكيد
            keyboard = [
                [InlineKeyboardButton("✅ تأكيد الكل", callback_data="gemini_confirm_all")],
                [InlineKeyboardButton("🔀 اختيار منتجات محددة", callback_data="gemini_select_products")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="gemini_cancel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
            
            return GEMINI_CONFIRM
            
        except GeminiAPIError as e:
            await update.message.reply_text(f"حدث خطأ أثناء تحليل رسالتك: {str(e)}")
            return ConversationHandler.END
    else:
        # إذا كان هناك عدة أسطر، قم بتحليلها كل سطر على حدة أو كمجموعة
        all_products = []
        try:
            # أولاً، جرب التحليل كنص كامل
            products = await analyze_products_with_gemini(message_text)
            if products:
                all_products = products
            else:
                # إذا فشل ذلك، قم بتحليل كل سطر بشكل منفصل
                for line in lines:
                    if not line.strip():
                        continue
                    products_in_line = await analyze_products_with_gemini(line)
                    if products_in_line:
                        all_products.extend(products_in_line)
                        
            if not all_products:
                await update.message.reply_text("لم أتمكن من تحليل رسالتك. يرجى المحاولة مرة أخرى بصيغة مختلفة.")
                return ConversationHandler.END
                
            # حفظ المنتجات في سياق المستخدم
            context.user_data['gemini_products'] = all_products
            
            # عرض المنتجات التي تم تحليلها للمستخدم
            message = "🔎 لقد حللت رسالتك وحددت المنتجات التالية:\n\n"
            for i, product in enumerate(all_products, 1):
                product_name = product.get('product', 'غير معروف')
                price = product.get('price', 'غير معروف')
                notes = product.get('notes', '')
                notes_text = f" - ملاحظات: {notes}" if notes else ""
                message += f"{i}. {product_name} - السعر: {price}{notes_text}\n"
            
            message += "\nهل تريد إضافة هذه المنتجات إلى الجدول؟"
            
            # إنشاء أزرار التأكيد
            keyboard = [
                [InlineKeyboardButton("✅ تأكيد الكل", callback_data="gemini_confirm_all")],
                [InlineKeyboardButton("🔀 اختيار منتجات محددة", callback_data="gemini_select_products")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="gemini_cancel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
            
            return GEMINI_CONFIRM
            
        except GeminiAPIError as e:
            await update.message.reply_text(f"حدث خطأ أثناء تحليل رسالتك: {str(e)}")
            return ConversationHandler.END

async def gemini_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    معالجة ردود الاستعلام من تحليل Gemini
    """
    query = update.callback_query
    await query.answer()
    
    if query.data == "gemini_confirm_all":
        # تأكيد وإضافة جميع المنتجات إلى الجدول
        products = context.user_data.get('gemini_products', [])
        if not products:
            await query.message.edit_text("لم يتم العثور على منتجات للإضافة.")
            return ConversationHandler.END
        
        try:
            # إضافة المنتجات إلى الجدول
            for product in products:
                await add_product_to_sheet(
                    query.message.chat_id,
                    product.get('product', ''),
                    product.get('price', ''),
                    product.get('notes', '')
                )
            
            # تحديث الرسالة مع تأكيد الإضافة
            await query.message.edit_text(f"✅ تمت إضافة {len(products)} منتج(ات) إلى الجدول بنجاح.")
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"خطأ أثناء إضافة المنتجات: {str(e)}")
            await query.message.edit_text(f"حدث خطأ أثناء إضافة المنتجات: {str(e)}")
            return ConversationHandler.END
    
    elif query.data == "gemini_select_products":
        # عرض قائمة اختيار المنتجات
        products = context.user_data.get('gemini_products', [])
        if not products:
            await query.message.edit_text("لم يتم العثور على منتجات للاختيار منها.")
            return ConversationHandler.END
        
        # إنشاء لوحة مفاتيح للاختيار
        keyboard = []
        for i, product in enumerate(products, 1):
            product_name = product.get('product', 'غير معروف')
            price = product.get('price', 'غير معروف')
            notes = product.get('notes', '')
            display_text = f"{product_name} - {price}"
            if notes:
                display_text += f" ({notes})"
            keyboard.append([InlineKeyboardButton(display_text, callback_data=f"select_product_{i-1}")])
        
        # إضافة زر للتأكيد وزر للإلغاء
        keyboard.append([
            InlineKeyboardButton("✅ تأكيد الاختيار", callback_data="confirm_selected_products"),
            InlineKeyboardButton("❌ إلغاء", callback_data="gemini_cancel")
        ])
        
        # إنشاء قائمة في سياق المستخدم لتتبع الاختيارات
        context.user_data['selected_products'] = []
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("اختر المنتجات التي تريد إضافتها (انقر على المنتج للاختيار/إلغاء الاختيار):", reply_markup=reply_markup)
        
        return GEMINI_SELECT
    
    elif query.data == "gemini_cancel":
        # إلغاء العملية
        await query.message.edit_text("تم إلغاء عملية إضافة المنتجات.")
        return ConversationHandler.END
    
    elif query.data.startswith("select_product_"):
        # معالجة اختيار منتج معين
        return await handle_product_selection(update, context)
    
    elif query.data == "confirm_selected_products":
        # معالجة تأكيد المنتجات المختارة
        return await handle_selected_products_confirmation(update, context)
    
    return ConversationHandler.END

async def handle_product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    معالجة اختيار منتج من القائمة
    """
    query = update.callback_query
    await query.answer()
    
    # استخراج مؤشر المنتج من بيانات الاستعلام
    product_index = int(query.data.split('_')[-1])
    products = context.user_data.get('gemini_products', [])
    
    if product_index < 0 or product_index >= len(products):
        await query.message.reply_text("مؤشر المنتج غير صالح.")
        return GEMINI_SELECT
    
    # التحقق مما إذا كان المنتج مختارًا بالفعل
    selected_products = context.user_data.get('selected_products', [])
    
    if product_index in selected_products:
        # إلغاء اختيار المنتج
        selected_products.remove(product_index)
    else:
        # اختيار المنتج
        selected_products.append(product_index)
    
    # تحديث قائمة المنتجات المختارة
    context.user_data['selected_products'] = selected_products
    
    # تحديث لوحة المفاتيح لتعكس الاختيار
    keyboard = []
    for i, product in enumerate(products, 1):
        product_name = product.get('product', 'غير معروف')
        price = product.get('price', 'غير معروف')
        notes = product.get('notes', '')
        
        # إضافة علامة للمنتجات المختارة
        prefix = "✅ " if (i-1) in selected_products else ""
        display_text = f"{prefix}{product_name} - {price}"
        if notes:
            display_text += f" ({notes})"
            
        keyboard.append([InlineKeyboardButton(display_text, callback_data=f"select_product_{i-1}")])
    
    # إضافة زر للتأكيد وزر للإلغاء
    keyboard.append([
        InlineKeyboardButton("✅ تأكيد الاختيار", callback_data="confirm_selected_products"),
        InlineKeyboardButton("❌ إلغاء", callback_data="gemini_cancel")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # تحديث الرسالة مع الاختيارات الجديدة
    selected_count = len(selected_products)
    message = f"اختر المنتجات التي تريد إضافتها (تم اختيار {selected_count} منتج(ات)):"
    
    await query.message.edit_text(message, reply_markup=reply_markup)
    
    return GEMINI_SELECT

async def handle_selected_products_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    معالجة تأكيد المنتجات المختارة
    """
    query = update.callback_query
    await query.answer()
    
    # الحصول على المنتجات المختارة
    selected_indices = context.user_data.get('selected_products', [])
    all_products = context.user_data.get('gemini_products', [])
    
    if not selected_indices:
        await query.message.edit_text("لم تقم باختيار أي منتجات. تم إلغاء العملية.")
        return ConversationHandler.END
    
    # فلترة المنتجات المختارة
    selected_products = [all_products[i] for i in selected_indices if i < len(all_products)]
    
    try:
        # إضافة المنتجات المختارة إلى الجدول
        for product in selected_products:
            await add_product_to_sheet(
                query.message.chat_id,
                product.get('product', ''),
                product.get('price', ''),
                product.get('notes', '')
            )
        
        # تحديث الرسالة مع تأكيد الإضافة
        await query.message.edit_text(f"✅ تمت إضافة {len(selected_products)} منتج(ات) مختار(ة) إلى الجدول بنجاح.")
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"خطأ أثناء إضافة المنتجات المختارة: {str(e)}")
        await query.message.edit_text(f"حدث خطأ أثناء إضافة المنتجات المختارة: {str(e)}")
        return ConversationHandler.END

# ملاحظة: عند دمج هذا الملف مع ConversationHandler الرئيسي،
# أضف الحالة GEMINI_CONFIRM و CallbackQueryHandler(gemini_callback_handler)
# واستخدم handle_unstructured_message عند الحاجة (مثلاً إذا فشل التحليل التقليدي)

# تعليمات جلب مفتاح Gemini API:
# يمكنك الحصول على مفتاح Gemini API من Google AI Studio أو منصة Google Cloud (Gemini/Generative Language API)
# بعد التسجيل، ستجد خيار "API Key" في لوحة التحكم. انسخه وضعه في المتغير GEMINI_API_KEY أو في متغير بيئ. 