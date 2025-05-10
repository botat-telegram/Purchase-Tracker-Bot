"""
معالجات الأوامر
"""
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from src.config import WELCOME_MESSAGE as welcome_message
from database.sheets import add_to_sheets, get_products
from datetime import datetime
import traceback

# إعداد التسجيل
logger = logging.getLogger(__name__)

# كلمات تخطي الملاحظات
SKIP_NOTES_WORDS = [".", "لا", "-", "/s", "s", "لأ"]

# حالات المحادثة
PRODUCT = 0
PRICE = 1
NOTES = 2

# حالات المحادثة الجديدة للحذف
DELETE_SELECTION = 3
DELETE_CONFIRM = 4

# لوحة المفاتيح الرئيسية
MAIN_KEYBOARD = [
    ["❌ إلغاء العملية"]
]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أمر /start"""
    # مسح أي بيانات سابقة
    context.user_data.clear()
    
    # إنشاء لوحة المفاتيح
    reply_markup = ReplyKeyboardMarkup(
        MAIN_KEYBOARD,
        resize_keyboard=True
    )
    
    # إرسال رسالة الترحيب مع لوحة المفاتيح
    await update.message.reply_text("مرحباً بك! 👋", reply_markup=reply_markup)
    await update.message.reply_text(welcome_message)
    return PRODUCT  # العودة لحالة إدخال اسم المنتج

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر المساعدة"""
    help_text = """
🛍️ <b>مرحباً بك في بوت تتبع المشتريات!</b>

<b>الأوامر المتاحة:</b>
/start - بدء محادثة جديدة
/s - تخطي الملاحظات
/cancel - إلغاء العملية الحالية
/help - عرض هذه المساعدة
/last - عرض آخر المنتجات المضافة

<b>طرق إضافة المنتجات:</b>
- <code>كولا 23</code> (منتج ثم سعر)
- <code>23 كولا</code> (سعر ثم منتج)
- <code>كولا ٢٣ ريال</code> (دعم للأرقام العربية والعملات)
- <code>كولا</code> (سيطلب منك البوت إدخال السعر)

<b>إضافة منتجات متعددة:</b>
اكتب كل منتج في سطر منفصل:
<code>كولا 23
شيبس 15
قهوة 10</code>

<b>تخطي الملاحظات:</b>
- إرسال نقطة (.)
- إرسال "لا"
- إرسال شرطة (-)
- إرسال الأمر /s
"""
    # إرسال رسالة المساعدة مع تنسيق HTML
    await update.message.reply_text(help_text, parse_mode="HTML")

async def last_products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر عرض آخر المنتجات المضافة"""
    try:
        # الحصول على آخر 10 منتجات
        products = await get_products(10)
        
        if not products:
            await update.message.reply_text("لا توجد منتجات مضافة حتى الآن.")
            return
            
        # إنشاء رسالة تحتوي على المنتجات
        message = "<b>📋 آخر المنتجات المضافة:</b>\n\n"
        
        for i, product in enumerate(products, 1):
            date = product.get('date', 'غير معروف')
            name = product.get('name', 'غير معروف')
            price = product.get('price', 'غير معروف')
            notes = product.get('notes', '')
            
            notes_text = f" - <i>{notes}</i>" if notes else ""
            message += f"{i}. <b>{name}</b> - {price}{notes_text} ({date})\n"
            
        # إرسال الرسالة مع تنسيق HTML
        await update.message.reply_text(message, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"خطأ في عرض آخر المنتجات: {str(e)}")
        await update.message.reply_text(f"حدث خطأ أثناء جلب المنتجات: {str(e)}")

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
            
            # إنشاء لوحة المفاتيح
            reply_markup = ReplyKeyboardMarkup(
                MAIN_KEYBOARD,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                f"✅ تم إضافة {product} بسعر {price} بدون ملاحظات", 
                reply_markup=reply_markup
            )
            
            context.user_data.clear()
            return ConversationHandler.END
            
        # إذا كنا في مرحلة السعر
        elif context.user_data.get('product'):
            logger.debug("لدينا منتج فقط - لا يمكن تخطي السعر")
            await update.message.reply_text("⚠️ لا يمكن تخطي إدخال السعر. الرجاء إدخال السعر:")
            return PRICE
            
        # إذا كنا في مرحلة المنتج
        else:
            logger.debug("لا يوجد منتج - لا يمكن تخطي اسم المنتج")
            await update.message.reply_text("⚠️ لا يمكن تخطي إدخال اسم المنتج. الرجاء إدخال اسم المنتج:")
            return PRODUCT
            
    except Exception as e:
        logger.error(f"حدث خطأ: {str(e)}")
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    بداية المحادثة مع البوت
    يتم تنفيذ هذه الدالة عند إرسال الأمر /start
    """
    # إنشاء لوحة المفاتيح
    reply_markup = ReplyKeyboardMarkup(
        MAIN_KEYBOARD,
        resize_keyboard=True
    )
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    إلغاء المحادثة الحالية
    يتم تنفيذ هذه الدالة عند إرسال الأمر /cancel
    """
    # مسح بيانات المستخدم
    context.user_data.clear()
    
    # إنشاء لوحة المفاتيح
    reply_markup = ReplyKeyboardMarkup(
        MAIN_KEYBOARD,
        resize_keyboard=True
    )
    
    await update.message.reply_text(
        "✅ تم إلغاء العملية الحالية. يمكنك البدء من جديد.", 
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def handle_button_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج النقر على الأزرار في لوحة المفاتيح"""
    text = update.message.text
    
    # قائمة الأزرار المعروفة
    KNOWN_BUTTONS = ["❌ إلغاء العملية"]
    
    # التحقق أن النص هو زر معروف
    if text in KNOWN_BUTTONS:
        if text == "❌ إلغاء العملية":
            await cancel(update, context)
            return ConversationHandler.END
    
    # إذا لم يكن النص زراً معروفاً، نعيد None
    return None

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
            await update.message.reply_text("⚠️ السعر يجب أن يكون أكبر من صفر. الرجاء إدخال السعر مرة أخرى:")
            return PRICE
            
        context.user_data['price'] = price
        
        # إنشاء أزرار تخطي الملاحظات
        keyboard = [
            [InlineKeyboardButton("تخطي الملاحظات ⏭️", callback_data="skip_notes")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ تم استلام السعر: {price}\n"
            "هل تريد إضافة ملاحظة؟\n"
            "يمكنك تخطي الملاحظات عن طريق:\n"
            "- إرسال '.' (نقطة)\n"
            "- إرسال 'لا'\n"
            "- إرسال '-'\n"
            "- إرسال '/s'",
            reply_markup=reply_markup
        )
        return NOTES
    except ValueError:
        await update.message.reply_text("⚠️ الرجاء إدخال رقم صحيح للسعر:")
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
        
        # إنشاء لوحة المفاتيح
        reply_markup = ReplyKeyboardMarkup(
            MAIN_KEYBOARD,
            resize_keyboard=True
        )
        
        if notes:
            await update.message.reply_text(
                f"✅ تم إضافة {product} بسعر {price} مع ملاحظة: {notes}",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"✅ تم إضافة {product} بسعر {price}",
                reply_markup=reply_markup
            )
        
        # مسح بيانات المستخدم
        context.user_data.clear()
        
        await update.message.reply_text(welcome_message)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ConversationHandler.END

async def today_products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض المنتجات المسجلة اليوم"""
    try:
        # تجنب تكرار الإرسال
        user_id = update.effective_user.id
        message_id = update.message.message_id
        request_key = f"today_{user_id}_{message_id}"
        
        if context.bot_data.get(request_key):
            logger.info(f"تجاهل طلب مكرر: {request_key}")
            return
            
        # تسجيل هذا الطلب
        context.bot_data[request_key] = True
        
        # الحصول على المنتجات من قاعدة البيانات
        products = await get_products()
        
        # تصفية المنتجات المسجلة اليوم
        today = datetime.now().strftime("%Y/%m/%d")
        today_products = [
            p for p in products 
            if p.get('date', '').startswith(today)
        ]
        
        if not today_products:
            await update.message.reply_text("لا توجد منتجات مسجلة اليوم.")
            return
            
        # تخزين المنتجات في بيانات المستخدم لاستخدامها لاحقاً
        context.user_data['today_products'] = today_products
            
        # تنسيق الرسالة
        message = "📊 المنتجات المسجلة اليوم:\n\n"
        total = 0
        
        for i, product in enumerate(today_products, 1):
            product_name = product.get('name') or product.get('product', 'غير معروف')
            price = product.get('price', 0)
            notes = product.get('notes', '')
            
            message += f"{i}. {product_name} - {price}"
            if notes:
                message += f" ({notes})"
            message += "\n"
            total += float(price)
            
        message += f"\n💰 المجموع: {total}"
        
        # إنشاء أزرار التحكم بشكل أبسط
        keyboard = [
            [
                InlineKeyboardButton("🗑️ حذف منتجات", callback_data="delete_today"),
                InlineKeyboardButton("💰 عرض المجموع", callback_data="total_today")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الرسالة مع الأزرار
        await update.message.reply_text(message, reply_markup=reply_markup)
        logger.info("تم إرسال منتجات اليوم مع الأزرار")
        
    except Exception as e:
        logger.error(f"خطأ في عرض منتجات اليوم: {str(e)}")
        logger.error(traceback.format_exc())
        await update.message.reply_text("حدث خطأ أثناء جلب المنتجات. الرجاء المحاولة مرة أخرى.")

async def last_ten_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر /last10 لعرض آخر 10 عمليات"""
    # سجل معلومات عن الاستدعاء
    user_id = update.effective_user.id
    message_id = update.message.message_id
    request_id = f"last10_cmd_{user_id}_{message_id}"
    
    logger.info(f"تم استدعاء last_ten_command من قبل {user_id}, message_id: {message_id}")
    
    # التحقق من عدم تكرار نفس الطلب
    if context.bot_data.get(request_id):
        logger.info(f"تجاهل طلب مكرر: {request_id}")
        return
    
    # تسجيل هذا الطلب لمنع التكرار
    context.bot_data[request_id] = True
    
    # استدعاء الدالة الفعلية مباشرة دون إعادة استدعاء last_ten_operations_command
    try:
        # الحصول على المنتجات من قاعدة البيانات
        products = await get_products(10)
        
        if not products:
            await update.message.reply_text("لا توجد عمليات مسجلة.")
            return
        
        # ترتيب المنتجات حسب التاريخ تنازلياً إذا أمكن
        try:
            sorted_products = sorted(
                products,
                key=lambda x: x.get('date', ''),
                reverse=True
            )
        except Exception:
            sorted_products = products
            
        # تخزين المنتجات في بيانات المستخدم لاستخدامها لاحقاً
        context.user_data['last10_products'] = sorted_products
        
        # تنسيق الرسالة
        message = "🔄 آخر 10 عمليات:\n\n"
        total = 0
        
        for i, product in enumerate(sorted_products, 1):
            date = product.get('date', 'غير معروف')
            name = product.get('name') or product.get('product', 'غير معروف')
            price = product.get('price', 0)
            notes = product.get('notes', '')
            message += f"{i}. {name} - {price}"
            if notes:
                message += f" ({notes})"
            message += f" ({date})\n"
            try:
                total += float(price)
            except (ValueError, TypeError):
                logger.warning(f"قيمة سعر غير صالحة: {price}")
        
        message += f"\n💰 المجموع: {total}"
        
        # إنشاء أزرار التحكم بشكل أبسط ومباشر
        keyboard = [
            [
                InlineKeyboardButton("🗑️ حذف منتجات", callback_data="delete_last10"),
                InlineKeyboardButton("💰 عرض المجموع", callback_data="total_last10")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الرسالة مع الأزرار
        await update.message.reply_text(message, reply_markup=reply_markup)
        logger.info(f"تم إرسال آخر 10 عمليات مع الأزرار لـ {user_id}")
        
    except Exception as e:
        logger.error(f"خطأ في عرض آخر العمليات: {str(e)}")
        logger.error(traceback.format_exc())
        await update.message.reply_text("حدث خطأ أثناء جلب العمليات. الرجاء المحاولة مرة أخرى.")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج الضغط على أزرار الاستعلام"""
    query = update.callback_query
    
    # سجل بيانات التفاعل للتصحيح
    logger.info(f"تم الضغط على زر: {query.data}")
    
    # الرد على الاستعلام لإزالة علامة التحميل
    try:
        await query.answer()  
    except Exception as e:
        logger.error(f"خطأ عند محاولة الرد على الاستعلام: {str(e)}")
    
    # التعامل مع زر تخطي الملاحظات
    if query.data == "skip_notes":
        logger.info("تنفيذ إجراء skip_notes")
        # تخطي الملاحظات مباشرة
        if 'product' in context.user_data and 'price' in context.user_data:
            product = context.user_data['product']
            price = context.user_data['price']
            
            try:
                await add_to_sheets(product, price, '')
                
                # إنشاء لوحة المفاتيح
                reply_markup = ReplyKeyboardMarkup(
                    MAIN_KEYBOARD,
                    resize_keyboard=True
                )
                
                await query.message.reply_text(
                    f"✅ تم إضافة {product} بسعر {price} بدون ملاحظات",
                    reply_markup=reply_markup
                )
                
                # مسح بيانات المستخدم
                context.user_data.clear()
                
                return ConversationHandler.END
            except Exception as e:
                await query.message.reply_text(f"❌ حدث خطأ: {str(e)}")
                return ConversationHandler.END
    
    # التعامل مع أزرار حذف المنتجات
    elif query.data == "delete_today":
        logger.info("تنفيذ إجراء delete_today")
        try:
            # إعادة جلب المنتجات للتأكد من أحدث البيانات
            products = await get_products()
            # تصفية منتجات اليوم
            today = datetime.now().strftime("%Y/%m/%d")
            today_products = [
                p for p in products 
                if p.get('date', '').startswith(today)
            ]
            
            # تحديث القائمة المخزنة
            context.user_data['today_products'] = today_products
            
            if not today_products:
                await query.message.reply_text("⚠️ لا توجد منتجات اليوم للحذف.")
                return ConversationHandler.END
                
            message = "🗑️ اختر أرقام المنتجات التي تريد حذفها:\n\n"
            for i, product in enumerate(today_products, 1):
                name = product.get('name') or product.get('product', 'غير معروف')
                price = product.get('price', 'غير معروف')
                message += f"{i}. {name} - {price}\n"
            
            message += "\nأرسل أرقام المنتجات (مثال: 2 أو 1,3,5)"
            
            # ضبط نوع الحذف بوضوح
            context.user_data['delete_type'] = 'today'
            logger.info("تم الانتقال إلى حالة DELETE_SELECTION")
            
            await query.message.reply_text(message)
            # العودة إلى حالة اختيار المنتجات للحذف
            return DELETE_SELECTION
            
        except Exception as e:
            logger.error(f"خطأ عند محاولة جلب منتجات اليوم للحذف: {str(e)}")
            await query.message.reply_text("⚠️ حدث خطأ أثناء جلب المنتجات. الرجاء المحاولة مرة أخرى.")
            return ConversationHandler.END
    
    elif query.data == "delete_last10":
        logger.info("تنفيذ إجراء delete_last10")
        try:
            # إعادة جلب آخر المنتجات للتأكد من أحدث البيانات
            products = await get_products(10)
            
            # ترتيب المنتجات حسب التاريخ
            try:
                products = sorted(
                    products,
                    key=lambda x: x.get('date', ''),
                    reverse=True
                )
            except Exception:
                pass  # استمر بدون الترتيب إذا فشل
            
            # تحديث المنتجات المخزنة
            context.user_data['last10_products'] = products
            
            if not products:
                await query.message.reply_text("⚠️ لا توجد منتجات للحذف.")
                return ConversationHandler.END
                
            message = "🗑️ اختر أرقام المنتجات التي تريد حذفها:\n\n"
            for i, product in enumerate(products, 1):
                name = product.get('name') or product.get('product', 'غير معروف')
                price = product.get('price', 'غير معروف')
                message += f"{i}. {name} - {price}\n"
            
            message += "\nأرسل أرقام المنتجات (مثال: 2 أو 1,3,5)"
            
            # ضبط نوع الحذف بوضوح
            context.user_data['delete_type'] = 'last10'
            logger.info("تم الانتقال إلى حالة DELETE_SELECTION")
            
            await query.message.reply_text(message)
            # العودة إلى حالة اختيار المنتجات للحذف
            return DELETE_SELECTION
            
        except Exception as e:
            logger.error(f"خطأ عند محاولة جلب آخر المنتجات للحذف: {str(e)}")
            await query.message.reply_text("⚠️ حدث خطأ أثناء جلب المنتجات. الرجاء المحاولة مرة أخرى.")
            return ConversationHandler.END
    
    # التعامل مع أزرار عرض المجموع
    elif query.data == "total_today":
        logger.info("تنفيذ إجراء total_today")
        # عرض مجموع منتجات اليوم
        if 'today_products' in context.user_data:
            products = context.user_data['today_products']
            total = sum(float(p.get('price', 0)) for p in products)
            await query.message.reply_text(f"💰 مجموع منتجات اليوم: {total}")
        else:
            await query.message.reply_text("⚠️ لا توجد منتجات معروضة. الرجاء عرض المنتجات أولاً.")
    
    elif query.data == "total_last10":
        logger.info("تنفيذ إجراء total_last10")
        # عرض مجموع آخر 10 منتجات
        if 'last10_products' in context.user_data:
            products = context.user_data['last10_products']
            total = sum(float(p.get('price', 0)) for p in products)
            await query.message.reply_text(f"💰 مجموع آخر 10 منتجات: {total}")
        else:
            await query.message.reply_text("⚠️ لا توجد منتجات معروضة. الرجاء عرض المنتجات أولاً.")
    
    # التعامل مع أزرار تأكيد الحذف
    elif query.data == "confirm_delete":
        logger.info("تنفيذ إجراء confirm_delete")
        # تأكيد حذف المنتجات
        return await handle_delete_confirm(update, context)
    
    elif query.data == "cancel_delete":
        logger.info("تنفيذ إجراء cancel_delete")
        # إلغاء حذف المنتجات
        await query.message.reply_text("✅ تم إلغاء عملية الحذف.")
        
        # مسح بيانات الحذف
        if 'delete_indices' in context.user_data:
            del context.user_data['delete_indices']
        if 'products_to_delete' in context.user_data:
            del context.user_data['products_to_delete']
        if 'delete_type' in context.user_data:
            del context.user_data['delete_type']
            
        return ConversationHandler.END
            
    # إذا وصلنا إلى هنا، فهذا يعني أننا لم نتعرف على البيانات
    else:
        logger.warning(f"بيانات استعلام غير معروفة: {query.data}")
    
    # إذا كنا في حالة NOTES، نعود إليها
    if context.user_data.get('price'):
        return NOTES
    
    return ConversationHandler.END

async def handle_delete_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج اختيار المنتجات للحذف"""
    from database.sheets import delete_products
    
    try:
        # الحصول على أرقام المنتجات المراد حذفها
        text = update.message.text.strip()
        
        logger.info(f"استلام طلب حذف: {text}")
        
        # التأكد من أن لدينا بيانات للمنتجات المعروضة
        delete_type = context.user_data.get('delete_type')
        logger.debug(f"نوع الحذف الحالي: {delete_type}")
        
        if not delete_type:
            logger.warning("لم يتم تحديد نوع المنتجات للحذف")
            await update.message.reply_text("⚠️ لم يتم تحديد نوع المنتجات للحذف. الرجاء عرض المنتجات أولاً.")
            return ConversationHandler.END
            
        # تحليل النص للحصول على الأرقام
        indices = []
        
        # تحسين استخراج الأرقام باستخدام regex
        import re
        numbers = re.findall(r'\d+', text)
        
        logger.debug(f"الأرقام المستخرجة من النص: {numbers}")
        
        if numbers:
            # تحويل الأرقام إلى صفر-based indices
            for num in numbers:
                try:
                    # الأرقام المعروضة للمستخدم تبدأ من 1
                    index = int(num) - 1  # تحويل من 1-based إلى 0-based
                    indices.append(index)
                except ValueError:
                    pass
        else:
            # إذا لم يتم العثور على أرقام
            logger.warning(f"لم يتم العثور على أرقام في النص: {text}")
            await update.message.reply_text("⚠️ لم يتم تحديد أي منتجات صالحة للحذف. الرجاء إرسال أرقام المنتجات (مثال: 2 أو 1,3,5).")
            return DELETE_SELECTION
        
        # إزالة الفهارس المكررة مع الاحتفاظ بالترتيب
        unique_indices = []
        for i in indices:
            if i not in unique_indices:
                unique_indices.append(i)
        
        indices = unique_indices
        
        if not indices:
            logger.warning(f"لم يتم استخراج أي أرقام صالحة من النص: {text}")
            await update.message.reply_text("⚠️ لم يتم تحديد أي منتجات صالحة للحذف. الرجاء إرسال أرقام المنتجات (مثال: 2 أو 1,3,5).")
            return DELETE_SELECTION
        
        logger.info(f"تم استخراج هذه الفهارس (0-based): {indices}")
        
        # الحصول على المنتجات المناسبة
        products = []
        
        # تحديث قائمة المنتجات قبل عملية الحذف
        if delete_type == 'today':
            # إعادة جلب منتجات اليوم
            all_products = await get_products()
            today = datetime.now().strftime("%Y/%m/%d")
            logger.debug(f"تصفية المنتجات لليوم: {today}")
            today_products = [
                p for p in all_products 
                if p.get('date', '').startswith(today)
            ]
            context.user_data['today_products'] = today_products
            products = today_products
            logger.debug(f"تم تحديث منتجات اليوم، العدد: {len(products)}")
        elif delete_type == 'last10':
            # إعادة جلب آخر 10 منتجات
            products = await get_products(10)
            context.user_data['last10_products'] = products
            logger.debug(f"تم تحديث آخر 10 منتجات، العدد: {len(products)}")
        else:
            logger.error(f"نوع حذف غير معروف: {delete_type}")
            await update.message.reply_text("⚠️ حدث خطأ في تحديد نوع المنتجات.")
            return ConversationHandler.END
        
        # المخرجات التفصيلية للمساعدة في تشخيص المشكلة
        logger.info(f"عدد المنتجات المتاحة: {len(products)}")
        for i, p in enumerate(products):
            logger.debug(f"المنتج {i+1}: {p.get('name')} - {p.get('price')} - sheet_row={p.get('sheet_row')}")
        
        # التحقق من صحة الفهارس
        valid_indices = []
        invalid_indices = []
        selected_products = []
        
        for i in indices:
            if 0 <= i < len(products):
                product = products[i]
                # التأكد من وجود رقم الصف الفعلي للمنتج
                if 'sheet_row' in product and product['sheet_row'] is not None:
                    valid_indices.append(i)
                    selected_products.append(product)
                else:
                    logger.warning(f"منتج بدون رقم صف معروف في الفهرس {i}: {product}")
                    invalid_indices.append(i + 1)  # تحويل إلى 1-based للعرض
            else:
                logger.warning(f"فهرس خارج النطاق: {i}, الحد الأقصى: {len(products)-1}")
                invalid_indices.append(i + 1)  # تحويل إلى 1-based للعرض
        
        if not valid_indices:
            logger.warning(f"لا توجد فهارس صالحة من بين: {indices}, عدد المنتجات: {len(products)}")
            await update.message.reply_text(f"⚠️ جميع الأرقام التي أدخلتها غير صالحة ({invalid_indices}). الرجاء إدخال أرقام ضمن نطاق المنتجات المعروضة (1-{len(products)}).")
            return DELETE_SELECTION
        
        # إذا كانت هناك فهارس غير صالحة، نعرض رسالة تحذير
        if invalid_indices:
            logger.warning(f"فهارس غير صالحة: {invalid_indices}")
            await update.message.reply_text(f"⚠️ بعض الأرقام التي أدخلتها غير صالحة: {invalid_indices}. سيتم تجاهلها.")
        
        logger.info(f"الفهارس الصالحة (0-based): {valid_indices}")
        
        # تأكيد الحذف
        message = "⚠️ هل أنت متأكد من حذف المنتجات التالية؟\n\n"
        products_to_delete = []
        
        for product in selected_products:
            name = product.get('name') or product.get('product', 'غير معروف')
            price = product.get('price', 'غير معروف')
            sheet_row = product.get('sheet_row', 'غير معروف')
            message += f"- {name} - {price} (صف {sheet_row})\n"
            products_to_delete.append(product)
        
        # تخزين المنتجات المراد حذفها
        context.user_data['products_to_delete'] = products_to_delete
        
        # إنشاء أزرار التأكيد
        keyboard = [
            [
                InlineKeyboardButton("✅ نعم، احذف", callback_data="confirm_delete"),
                InlineKeyboardButton("❌ لا، إلغاء", callback_data="cancel_delete")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        logger.info(f"تم إرسال رسالة تأكيد الحذف مع الأزرار")
        
        return DELETE_CONFIRM
        
    except Exception as e:
        logger.error(f"خطأ في معالجة اختيار المنتجات للحذف: {str(e)}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ConversationHandler.END

async def handle_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج تأكيد حذف المنتجات"""
    from database.sheets import delete_products
    
    query = update.callback_query
    
    logger.info(f"معالجة تأكيد الحذف: {query.data}")
    
    try:
        # الرد على query لإزالة علامة التحميل
        await query.answer()
    except Exception as e:
        logger.error(f"خطأ عند محاولة الإجابة على استعلام التأكيد: {str(e)}")
    
    if query.data == "cancel_delete":
        # إلغاء عملية الحذف
        logger.info("تم إلغاء عملية الحذف")
        await query.message.reply_text("✅ تم إلغاء عملية الحذف.")
        
        # مسح بيانات الحذف
        for key in ['delete_indices', 'products_to_delete', 'delete_type']:
            if key in context.user_data:
                del context.user_data[key]
            
        return ConversationHandler.END
    
    if query.data == "confirm_delete":
        logger.info("تأكيد حذف المنتجات")
        try:
            # الحصول على المنتجات المراد حذفها مباشرة
            products_to_delete = context.user_data.get('products_to_delete', [])
            
            if not products_to_delete:
                logger.error("لا توجد منتجات محددة للحذف")
                await query.message.reply_text("⚠️ لم يتم تحديد أي منتجات للحذف.")
                # مسح بيانات الحذف
                for key in ['delete_indices', 'products_to_delete', 'delete_type']:
                    if key in context.user_data:
                        del context.user_data[key]
                return ConversationHandler.END
                
            # استخراج أرقام الصفوف الفعلية من المنتجات
            rows_to_delete = []
            products_info = []
            
            # تسجيل محتوى الـمنتجات المراد حذفها للتحقق
            logger.debug(f"المنتجات المراد حذفها: {products_to_delete}")
            
            for product in products_to_delete:
                if 'sheet_row' in product and product['sheet_row'] is not None:
                    sheet_row = product['sheet_row']
                    rows_to_delete.append(sheet_row)
                    products_info.append(f"{product.get('name', 'غير معروف')} (صف {sheet_row})")
                    logger.info(f"إضافة المنتج للحذف: {product.get('name')} - صف {sheet_row}")
                else:
                    logger.warning(f"منتج بدون sheet_row أو قيمة sheet_row فارغة: {product}")
            
            if not rows_to_delete:
                logger.error("لا توجد أرقام صفوف صالحة للحذف")
                await query.message.reply_text("⚠️ لم يتم تحديد أي أرقام صفوف صالحة للحذف.")
                return ConversationHandler.END
                
            # تنفيذ عملية الحذف
            logger.info(f"جاري إرسال أمر حذف الصفوف: {rows_to_delete}")
            await query.message.reply_text("⏳ جاري حذف المنتجات...")
            
            # استدعاء دالة الحذف من sheets.py
            success_count, failed_indices = await delete_products(rows_to_delete)
            
            logger.info(f"نتيجة الحذف: {success_count} منتج تم حذفه بنجاح، {len(failed_indices)} منتج فشل")
            
            if success_count > 0:
                # إذا نجح حذف بعض المنتجات على الأقل
                if failed_indices:
                    # بعض الحذف نجح وبعضه فشل
                    await query.message.reply_text(f"✅ تم حذف {success_count} منتج بنجاح.\n⚠️ فشل حذف {len(failed_indices)} منتج.")
                else:
                    # كل عمليات الحذف نجحت
                    await query.message.reply_text(f"✅ تم حذف {success_count} منتج بنجاح!")
            else:
                # فشلت كل عمليات الحذف
                await query.message.reply_text(f"❌ فشل حذف المنتجات. الرجاء المحاولة مرة أخرى.")
                logger.error(f"فشل حذف جميع المنتجات: {failed_indices}")
            
            # مسح بيانات الحذف
            for key in ['delete_indices', 'products_to_delete', 'delete_type']:
                if key in context.user_data:
                    del context.user_data[key]
                    
            return ConversationHandler.END
                
        except Exception as e:
            logger.error(f"خطأ في عملية تأكيد الحذف: {str(e)}")
            logger.error(traceback.format_exc())
            await query.message.reply_text(f"❌ حدث خطأ أثناء محاولة الحذف: {str(e)}")
            
            # مسح بيانات الحذف
            for key in ['delete_indices', 'products_to_delete', 'delete_type']:
                if key in context.user_data:
                    del context.user_data[key]
                    
            return ConversationHandler.END
    
    # في حالة بيانات callback غير متوقعة
    logger.warning(f"بيانات callback غير معروفة: {query.data}")
    await query.message.reply_text("⚠️ حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.")
    return ConversationHandler.END

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر /today لعرض المنتجات المسجلة اليوم"""
    # سجل معلومات عن الاستدعاء
    user_id = update.effective_user.id
    message_id = update.message.message_id
    request_id = f"today_cmd_{user_id}_{message_id}"
    
    logger.info(f"تم استدعاء today_command من قبل {user_id}, message_id: {message_id}")
    
    # التحقق من عدم تكرار نفس الطلب
    if context.bot_data.get(request_id):
        logger.info(f"تجاهل طلب مكرر: {request_id}")
        return
    
    # تسجيل هذا الطلب لمنع التكرار
    context.bot_data[request_id] = True
    
    # تنفيذ الدالة مباشرة بدلاً من استدعاء today_products_command
    try:
        # الحصول على المنتجات من قاعدة البيانات
        products = await get_products()
        
        # تصفية المنتجات المسجلة اليوم
        today = datetime.now().strftime("%Y/%m/%d")
        today_products = [
            p for p in products 
            if p.get('date', '').startswith(today)
        ]
        
        if not today_products:
            await update.message.reply_text("لا توجد منتجات مسجلة اليوم.")
            return
            
        # تخزين المنتجات في بيانات المستخدم لاستخدامها لاحقاً
        context.user_data['today_products'] = today_products
            
        # تنسيق الرسالة
        message = "📊 المنتجات المسجلة اليوم:\n\n"
        total = 0
        
        for i, product in enumerate(today_products, 1):
            product_name = product.get('name') or product.get('product', 'غير معروف')
            price = product.get('price', 0)
            notes = product.get('notes', '')
            
            message += f"{i}. {product_name} - {price}"
            if notes:
                message += f" ({notes})"
            message += "\n"
            try:
                total += float(price)
            except (ValueError, TypeError):
                logger.warning(f"قيمة سعر غير صالحة: {price}")
            
        message += f"\n💰 المجموع: {total}"
        
        # إنشاء أزرار التحكم بشكل أبسط
        keyboard = [
            [
                InlineKeyboardButton("🗑️ حذف منتجات", callback_data="delete_today"),
                InlineKeyboardButton("💰 عرض المجموع", callback_data="total_today")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الرسالة مع الأزرار
        await update.message.reply_text(message, reply_markup=reply_markup)
        logger.info(f"تم إرسال منتجات اليوم مع الأزرار لـ {user_id}")
        
    except Exception as e:
        logger.error(f"خطأ في عرض منتجات اليوم: {str(e)}")
        logger.error(traceback.format_exc())
        await update.message.reply_text("حدث خطأ أثناء جلب المنتجات. الرجاء المحاولة مرة أخرى.")
