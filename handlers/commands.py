"""
معالجات الأوامر
"""
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from src.config import WELCOME_MESSAGE as welcome_message
from database.sheets import add_to_sheets, get_products

# إعداد التسجيل
logger = logging.getLogger(__name__)

# كلمات تخطي الملاحظات
SKIP_NOTES_WORDS = [".", "لا", "-", "/s", "s", "لأ"]

# حالات المحادثة
PRODUCT = 0
PRICE = 1
NOTES = 2

# لوحة المفاتيح الرئيسية
MAIN_KEYBOARD = [
    ["📝 إضافة منتج جديد"],
    ["📋 آخر المنتجات", "❓ مساعدة"]
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
    
    if text == "📝 إضافة منتج جديد":
        await update.message.reply_text("أدخل اسم المنتج أو اكتب المنتج مع السعر مباشرة:")
        return PRODUCT
        
    elif text == "📋 آخر المنتجات":
        await last_products_command(update, context)
        return ConversationHandler.END
        
    elif text == "❓ مساعدة":
        await help_command(update, context)
        return ConversationHandler.END
        
    else:
        # معالجة النص كمدخلات منتج عادية
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

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج الضغط على أزرار الاستعلام"""
    query = update.callback_query
    await query.answer()  # الرد على الاستعلام لإزالة علامة التحميل
    
    if query.data == "skip_notes":
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
    
    return NOTES
