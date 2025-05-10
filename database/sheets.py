"""
التعامل مع قاعدة البيانات (Google Sheets)

هذا الملف يحتوي على الدوال المسؤولة عن التعامل مع Google Sheets.
يستخدم مكتبة gspread للاتصال بـ Google Sheets API.

المتطلبات:
    - ملف client_secret_*.json يحتوي على بيانات اعتماد Google Sheets API
    - ورقة عمل باسم "المشتريات" في Google Sheets
"""
import os
import json
import logging
import pickle
from typing import Optional, Tuple, List, Dict, Any
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound, APIError
import traceback
from functools import lru_cache
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time

# إعداد التسجيل
logger = logging.getLogger(__name__)

# اسم ملف جدول البيانات
SPREADSHEET_NAME = "المشتريات"

# حدود السعر
MIN_PRICE = 0.01
MAX_PRICE = 1000000

# عدد محاولات إعادة الاتصال
MAX_RETRIES = 3
# فترة الانتظار بين المحاولات (بالثواني)
RETRY_DELAY = 2

# سنستخدم وضع تجريبي في حالة كان هناك مشكلة في الاتصال
DEMO_MODE = False

# مخزن مؤقت للمنتجات في الوضع التجريبي
DEMO_PRODUCTS: List[Dict] = []

# ملف لتخزين المنتجات المضافة
DEMO_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEMO_DATA_FILE = os.path.join(DEMO_DATA_DIR, "demo_products.pkl")

# تأكد من وجود مجلد البيانات
if not os.path.exists(DEMO_DATA_DIR):
    try:
        os.makedirs(DEMO_DATA_DIR, exist_ok=True)
        logger.info(f"تم إنشاء مجلد البيانات: {DEMO_DATA_DIR}")
    except Exception as e:
        logger.error(f"فشل في إنشاء مجلد البيانات: {str(e)}")

# تحميل المنتجات السابقة من الملف إذا كان موجوداً
try:
    if os.path.exists(DEMO_DATA_FILE):
        with open(DEMO_DATA_FILE, 'rb') as f:
            DEMO_PRODUCTS = pickle.load(f)
            logger.info(f"تم تحميل {len(DEMO_PRODUCTS)} منتج من الملف المؤقت")
except Exception as e:
    logger.error(f"فشل في تحميل المنتجات من الملف: {str(e)}")
    DEMO_PRODUCTS = []

# دالة لحفظ المنتجات إلى ملف
def save_demo_products():
    try:
        with open(DEMO_DATA_FILE, 'wb') as f:
            pickle.dump(DEMO_PRODUCTS, f)
        logger.info(f"تم حفظ {len(DEMO_PRODUCTS)} منتج إلى الملف المؤقت")
    except Exception as e:
        logger.error(f"فشل في حفظ المنتجات إلى الملف: {str(e)}")

class SheetsError(Exception):
    """فئة مخصصة للأخطاء المتعلقة بـ Google Sheets"""
    pass

def find_client_secret_file():
    """البحث عن ملف client_secret في المجلد الرئيسي"""
    for file in os.listdir('.'):
        if file.startswith('client_secret_') and file.endswith('.json'):
            return file
    return None

# التخزين المؤقت للعميل مع التحقق من انتهاء صلاحية الجلسة
@lru_cache(maxsize=1)
def get_google_sheets_client() -> Tuple[Optional[gspread.Client], datetime]:
    """
    الحصول على عميل Google Sheets مع تخزين مؤقت
    
    Returns:
        Tuple[Optional[gspread.Client], datetime]: (عميل جوجل شيتس، وقت الإنشاء)
    """
    global DEMO_MODE
    
    if DEMO_MODE:
        logger.info("تشغيل في الوضع التجريبي - لن يتم الاتصال بـ Google Sheets")
        return None, datetime.now()
    
    try:
        # صلاحيات Google Sheets و Google Drive
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        # استخدام ملف الاعتماد مباشرة
        credentials_file = "sheet-bot-444713-d558e2ce2ee8.json"
        
        # تحقق من وجود الملف
        if not os.path.exists(credentials_file):
            logger.error(f"ملف الاعتماد غير موجود: {credentials_file}")
            DEMO_MODE = True
            return None, datetime.now()
            
        # تهيئة الاعتمادات باستخدام ملف client_secret
        try:
            # استخدام ServiceAccountCredentials مباشرة
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                credentials_file, scope
            )
            
            # إنشاء عميل gspread
            client = gspread.authorize(credentials)
            logger.info("تم الاتصال بنجاح بـ Google Sheets API")
            return client, datetime.now()
            
        except Exception as e:
            logger.error(f"فشل في إنشاء اعتمادات: {str(e)}")
            DEMO_MODE = True
            return None, datetime.now()
    
    except Exception as e:
        logger.error(f"خطأ في إنشاء عميل Google Sheets: {str(e)}")
        logger.error(traceback.format_exc())
        logger.info("تغيير إلى الوضع التجريبي")
        DEMO_MODE = True
        return None, datetime.now()

def with_retry(func):
    """
    مزخرف لإضافة إعادة المحاولة للدوال التي تتعامل مع Google Sheets API
    
    Args:
        func: الدالة التي ستتم إعادة محاولة تنفيذها
        
    Returns:
        نتيجة تنفيذ الدالة في حال النجاح
        
    Raises:
        SheetsError: في حال فشل جميع المحاولات
    """
    async def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except (APIError, ConnectionError, TimeoutError) as e:
                logger.warning(f"فشل الاتصال (محاولة {attempt+1}/{MAX_RETRIES}): {str(e)}")
                last_error = e
                # انتظار قبل إعادة المحاولة
                time.sleep(RETRY_DELAY)
                # إعادة تحميل العميل
                get_google_sheets_client.cache_clear()
            except Exception as e:
                # الأخطاء الأخرى تُرفع مباشرة
                logger.error(f"خطأ غير متوقع: {str(e)}")
                raise
        
        # بعد فشل جميع المحاولات
        error_msg = f"فشلت جميع محاولات الاتصال بـ Google Sheets ({MAX_RETRIES} محاولات)"
        if last_error:
            error_msg += f": {str(last_error)}"
        logger.error(error_msg)
        raise SheetsError(error_msg)
        
    return wrapper

def get_worksheet() -> Optional[gspread.Worksheet]:
    """
    الحصول على ورقة العمل مع التعامل مع الأخطاء
    
    Returns:
        Optional[gspread.Worksheet]: ورقة العمل أو None في حالة الوضع التجريبي
    """
    global DEMO_MODE
    
    if DEMO_MODE:
        logger.info("تشغيل في الوضع التجريبي - لن يتم الاتصال بـ Google Sheets")
        return None
        
    try:
        client, created_time = get_google_sheets_client()
        
        # إعادة إنشاء العميل إذا مر أكثر من 30 دقيقة
        if datetime.now() - created_time > timedelta(minutes=30):
            get_google_sheets_client.cache_clear()
            client, _ = get_google_sheets_client()
        
        try:
            # محاولة فتح جدول البيانات بالاسم
            try:
                spreadsheet = client.open(SPREADSHEET_NAME)
            except SpreadsheetNotFound:
                # إذا لم يتم العثور على الجدول، محاولة البحث عن أي جدول
                all_spreadsheets = client.openall()
                if not all_spreadsheets:
                    raise SheetsError("لا توجد جداول بيانات متاحة")
                spreadsheet = all_spreadsheets[0]
                logger.info(f"استخدام جدول بديل: {spreadsheet.title}")
            
            worksheet = spreadsheet.sheet1
            
            # التحقق من رؤوس الأعمدة
            headers = worksheet.row_values(1)
            # إذا كان الصف الأول فارغًا، سنضيف العناوين
            if not headers or len(headers) < 4:
                worksheet.update('A1:D1', [["التاريخ", "المنتج", "السعر", "ملاحظات"]])
                worksheet.format('A1:D1', {
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    "horizontalAlignment": "CENTER",
                    "textFormat": {"bold": True}
                })
            
            return worksheet
            
        except Exception as e:
            logger.error(f"خطأ في فتح ورقة العمل: {str(e)}")
            DEMO_MODE = True
            return None
            
    except Exception as e:
        logger.error(f"خطأ في الاتصال بـ Google Sheets: {str(e)}")
        logger.error(traceback.format_exc())
        DEMO_MODE = True
        return None

def validate_product_data(product: str, price: float) -> None:
    """
    التحقق من صحة بيانات المنتج
    
    Args:
        product (str): اسم المنتج
        price (float): سعر المنتج
        
    Raises:
        ValueError: إذا كانت البيانات غير صالحة
    """
    if not product or not product.strip():
        raise ValueError("اسم المنتج لا يمكن أن يكون فارغاً")
        
    if not isinstance(price, (int, float)):
        raise ValueError("السعر يجب أن يكون رقماً")
        
    if price < MIN_PRICE or price > MAX_PRICE:
        raise ValueError(f"السعر يجب أن يكون بين {MIN_PRICE} و {MAX_PRICE}")

def format_date(dt: datetime) -> str:
    """
    تنسيق التاريخ بالشكل المطلوب YYYY/MM/DD
    
    Args:
        dt (datetime): كائن تاريخ
    
    Returns:
        str: التاريخ بالتنسيق المطلوب
    """
    return dt.strftime("%Y/%m/%d")

@with_retry
async def add_to_sheets(product: str, price: float, notes: str = "") -> bool:
    """
    إضافة منتج جديد إلى Google Sheets
    
    Args:
        product (str): اسم المنتج
        price (float): سعر المنتج
        notes (str): ملاحظات إضافية (اختياري)
        
    Returns:
        bool: True إذا تمت الإضافة بنجاح، False إذا فشلت
        
    Raises:
        SheetsError: في حال فشل الاتصال بعد عدة محاولات
        ValueError: في حال كانت البيانات غير صالحة
    """
    global DEMO_MODE
    
    try:
        # تنظيف المدخلات
        product = product.strip()
        notes = notes.strip()
        
        # التحقق من صحة البيانات
        validate_product_data(product, price)
        
        if DEMO_MODE:
            # في وضع التجريبي، نضيف إلى القائمة المحلية
            date = format_date(datetime.now())
            # إضافة المنتج إلى القائمة المؤقتة
            DEMO_PRODUCTS.append({
                'date': date,
                'name': product,
                'price': price,
                'notes': notes
            })
            logger.info(f"[وضع تجريبي] تمت إضافة المنتج: {product} بسعر {price} بتاريخ {date} مع ملاحظات: {notes}")
            logger.info(f"[وضع تجريبي] عدد المنتجات في الذاكرة: {len(DEMO_PRODUCTS)}")
            
            # حفظ المنتجات إلى ملف
            save_demo_products()
            
            return True
        
        # الحصول على ورقة العمل
        worksheet = get_worksheet()
        
        # إذا تم تحويل الوضع إلى تجريبي في get_worksheet
        if DEMO_MODE:
            return await add_to_sheets(product, price, notes)
            
        # إضافة المنتج إلى الجدول
        date = format_date(datetime.now())
        row = [date, product, price, notes]
        worksheet.append_row(row)
        
        logger.info(f"تمت إضافة المنتج: {product} بسعر {price} بتاريخ {date} مع ملاحظات: {notes}")
        return True
        
    except ValueError as e:
        # أخطاء التحقق من صحة البيانات
        logger.error(f"بيانات غير صالحة: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"خطأ في إضافة المنتج: {str(e)}")
        logger.error(traceback.format_exc())
        if not DEMO_MODE:
            logger.info("محاولة استخدام الوضع التجريبي...")
            DEMO_MODE = True
            return await add_to_sheets(product, price, notes)
        else:
            raise SheetsError(f"فشل في إضافة المنتج: {str(e)}")

async def add_product_to_sheet(chat_id, product: str, price, notes: str = "") -> bool:
    """
    إضافة منتج جديد إلى Google Sheets مع دعم معرف المحادثة
    
    المعطيات:
        chat_id: معرف المحادثة (للتسجيل)
        product (str): اسم المنتج
        price: سعر المنتج (يمكن أن يكون نص أو رقم)
        notes (str): ملاحظات إضافية (اختياري)
        
    تعيد:
        bool: True إذا تمت الإضافة بنجاح، False إذا فشلت
    """
    try:
        # محاولة تحويل السعر إلى رقم عشري
        try:
            price_float = float(price)
        except (ValueError, TypeError):
            logger.error(f"خطأ في تحويل السعر '{price}' إلى رقم")
            return False
            
        # استدعاء الدالة الأساسية لإضافة المنتج
        result = await add_to_sheets(product, price_float, notes)
        
        # تسجيل معلومات إضافية
        if result:
            logger.info(f"تمت إضافة المنتج من المستخدم {chat_id}: {product} بسعر {price_float}")
        
        return result
        
    except Exception as e:
        logger.error(f"خطأ في add_product_to_sheet: {str(e)}")
        logger.error(traceback.format_exc())
        return False

async def add_multiple_to_sheets(products: list) -> Tuple[int, list]:
    """
    إضافة عدة منتجات دفعة واحدة
    
    المعطيات:
        products: قائمة من الأزواج (المنتج، السعر، الملاحظات)
        
    تعيد:
        عدد المنتجات التي تمت إضافتها بنجاح وقائمة بالأخطاء
    """
    global DEMO_MODE
    
    if DEMO_MODE:
        success_count = 0
        errors = []
        date = format_date(datetime.now())
        
        for product, price, notes in products:
            try:
                product = product.strip()
                notes = notes.strip() if notes else ""
                validate_product_data(product, price)
                # إضافة المنتج إلى القائمة المؤقتة
                DEMO_PRODUCTS.append({
                    'date': date,
                    'name': product,
                    'price': price,
                    'notes': notes
                })
                logger.info(f"[وضع تجريبي] تمت إضافة المنتج: {product} بسعر {price} بتاريخ {date} مع ملاحظات: {notes}")
                success_count += 1
            except ValueError as e:
                errors.append(f"خطأ في المنتج {product}: {str(e)}")
        
        # حفظ المنتجات إلى ملف
        save_demo_products()
            
        return success_count, errors
    
    try:
        worksheet = get_worksheet()
        
        # إذا تم تحويل الوضع إلى تجريبي في get_worksheet
        if DEMO_MODE:
            return await add_multiple_to_sheets(products)
        
        success_count = 0
        errors = []
        
        rows_to_add = []
        date = format_date(datetime.now())
        
        for product, price, notes in products:
            try:
                product = product.strip()
                notes = notes.strip() if notes else ""
                validate_product_data(product, price)
                rows_to_add.append([date, product, price, notes])
                success_count += 1
            except ValueError as e:
                errors.append(f"خطأ في المنتج {product}: {str(e)}")
        
        if rows_to_add:
            worksheet.append_rows(rows_to_add)
        
        return success_count, errors
        
    except Exception as e:
        logger.error(f"خطأ: {str(e)}")
        DEMO_MODE = True
        return await add_multiple_to_sheets(products)

async def get_products(limit: int = 10) -> list:
    """
    الحصول على آخر المنتجات المضافة
    
    المعطيات:
        limit (int): عدد المنتجات التي يجب إرجاعها (افتراضي: 10)
        
    تعيد:
        قائمة بالمنتجات، كل منتج يحتوي على رقم الصف الفعلي (sheet_row)، مرتبة بحيث آخر المنتجات المضافة تكون أولاً
    """
    global DEMO_MODE
    
    if DEMO_MODE:
        # إرجاع المنتجات من القائمة المؤقتة
        if DEMO_PRODUCTS:
            # إرجاع آخر منتجات مضافة، بحد أقصى limit
            # إضافة sheet_row وهمي (للوضع التجريبي)
            demo = DEMO_PRODUCTS[-limit:]
            for idx, p in enumerate(demo):
                p['sheet_row'] = idx + 2  # الصفوف تبدأ من 2
            # عكس الترتيب ليكون آخر المنتجات أولاً
            return list(reversed(demo))
        else:
            # إذا لم تكن هناك منتجات، نعيد بيانات تجريبية
            demo_products = [
                {
                    'date': format_date(datetime.now()),
                    'name': 'كولا',
                    'price': 23.0,
                    'notes': 'مثال تجريبي',
                    'sheet_row': 2
                },
                {
                    'date': format_date(datetime.now()),
                    'name': 'شيبس',
                    'price': 15.0,
                    'notes': 'حار',
                    'sheet_row': 3
                }
            ]
            return demo_products
    
    try:
        worksheet = get_worksheet()
        
        # إذا تم تحويل الوضع إلى تجريبي في get_worksheet
        if DEMO_MODE:
            return await get_products(limit)
        
        # الحصول على جميع القيم
        values = worksheet.get_all_values()
        
        # تحويل القيم إلى قائمة من القواميس مع رقم الصف الفعلي
        products = []
        # تخطي الصف الأول (العناوين)
        for idx, row in enumerate(values[1:], start=2):  # الصف 2 هو أول منتج فعلي
            try:
                if len(row) >= 3:
                    products.append({
                        'date': row[0],
                        'name': row[1],
                        'price': float(row[2]),
                        'notes': row[3] if len(row) > 3 else '',
                        'sheet_row': idx
                    })
            except (IndexError, ValueError) as e:
                logger.warning(f"خطأ في تحويل الصف {row}: {str(e)}")
                continue
        # الحصول على آخر المنتجات فقط، مع عكس الترتيب ليكون آخر المنتجات أولاً
        return list(reversed(products[-limit:])) if products else []
        
    except Exception as e:
        logger.error(f"خطأ في الحصول على المنتجات: {str(e)}")
        DEMO_MODE = True
        return await get_products(limit)

@with_retry
async def delete_product(index: int) -> bool:
    """
    حذف منتج من قاعدة البيانات حسب الفهرس
    
    Args:
        index: فهرس المنتج في جدول البيانات (الصف بدءًا من 2)
        
    Returns:
        bool: True في حالة النجاح، False في حالة الفشل
    """
    global DEMO_MODE, DEMO_PRODUCTS
    
    logger.info(f"محاولة حذف المنتج بالفهرس {index}")
    
    if DEMO_MODE:
        try:
            # في الوضع التجريبي، نحذف من القائمة المحلية
            if 0 <= index < len(DEMO_PRODUCTS):
                deleted_product = DEMO_PRODUCTS.pop(index)
                logger.info(f"تم حذف المنتج: {deleted_product.get('name', 'غير معروف')} من القائمة المحلية")
                save_demo_products()
                return True
            else:
                logger.error(f"فهرس غير صالح: {index}, العدد الكلي للمنتجات: {len(DEMO_PRODUCTS)}")
                return False
        except Exception as e:
            logger.error(f"فشل في حذف المنتج: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    try:
        # استخدام دالة delete_products للحذف بشكل متسق
        success_count, failed_indices = await delete_products([index])
        return success_count > 0
        
    except Exception as e:
        logger.error(f"فشل في حذف المنتج: {str(e)}")
        logger.error(traceback.format_exc())
        return False

@with_retry
async def delete_products(indices: list) -> Tuple[int, list]:
    """
    حذف عدة منتجات من قاعدة البيانات
    
    Args:
        indices: قائمة بأرقام الصفوف الفعلية للمنتجات المراد حذفها (sheet_row)
        
    Returns:
        Tuple[int, list]: (عدد المنتجات التي تم حذفها بنجاح، قائمة بالفهارس التي فشل حذفها)
    """
    global DEMO_MODE, DEMO_PRODUCTS
    
    logger.info(f"محاولة حذف {len(indices)} منتج بأرقام الصفوف: {indices}")
    
    success_count = 0
    failed_indices = []
    
    # تحقق من الفهارس وإصلاحها إذا لزم الأمر
    valid_indices = []
    for i in indices:
        try:
            if isinstance(i, str):
                i = int(i.strip())
            elif not isinstance(i, int):
                logger.warning(f"تخطي فهرس غير صالح: {i} (النوع: {type(i)})")
                failed_indices.append(i)
                continue
                
            valid_indices.append(i)
        except (ValueError, TypeError) as e:
            logger.warning(f"فشل في تحويل الفهرس: {i}, خطأ: {str(e)}")
            failed_indices.append(i)
    
    if not valid_indices:
        logger.warning("لا توجد فهارس صالحة للحذف")
        return 0, failed_indices
    
    # في الوضع التجريبي
    if DEMO_MODE:
        logger.info(f"محاولة حذف من القائمة المحلية، عدد المنتجات: {len(DEMO_PRODUCTS)}")
        
        # احتفاظ بالمنتجات الجديدة بعد الحذف
        new_products = []
        deleted_products = []
        
        for idx, product in enumerate(DEMO_PRODUCTS):
            # تحديد ما إذا كان يجب الاحتفاظ بهذا المنتج
            # المنتج له قيمة sheet_row مساوية للفهرس أو ليس له sheet_row وموضعه في القائمة مساوٍ للفهرس
            sheet_row = product.get('sheet_row', idx + 2)  # بشكل افتراضي، استخدم الموقع + 2 (لتخطي صف العنوان)
            
            if sheet_row in valid_indices:
                # هذا منتج مراد حذفه
                logger.info(f"حذف المنتج: {product.get('name', 'غير معروف')} من الصف {sheet_row}")
                deleted_products.append(product)
                success_count += 1
            else:
                # احتفظ بهذا المنتج
                new_products.append(product)
        
        # تحديث القائمة المحلية
        if success_count > 0:
            logger.info(f"تم حذف {success_count} منتج: {[p.get('name', 'غير معروف') for p in deleted_products]}")
            DEMO_PRODUCTS = new_products
            save_demo_products()
            
        logger.info(f"نتيجة عملية الحذف (وضع تجريبي): {success_count} نجاح، {len(failed_indices)} فشل")
        return success_count, failed_indices
    
    # للوضع العادي (Google Sheets)
    try:
        # الحصول على ورقة العمل
        worksheet = get_worksheet()
        
        # إذا تم تحويل الوضع إلى تجريبي في get_worksheet
        if DEMO_MODE:
            return await delete_products(indices)
            
        # الحصول على جميع الصفوف
        all_rows = worksheet.get_all_values()
        num_rows = len(all_rows)
        
        # التحقق من أن لدينا صفوف كافية
        if num_rows <= 1:  # فقط عنوان
            logger.warning("لا توجد صفوف للحذف")
            return 0, valid_indices
        
        # ترتيب أرقام الصفوف تنازليًا (مهم للحذف!)
        sorted_indices = sorted(valid_indices, reverse=True)
        logger.info(f"أرقام الصفوف للحذف بعد الترتيب: {sorted_indices}")
        
        # تسجيل معلومات الصفوف
        logger.info(f"إجمالي عدد الصفوف في الجدول: {num_rows}")
        
        # تحديد عدد الأعمدة في الورقة
        num_cols = len(all_rows[0]) if all_rows else 5  # استخدام 5 أعمدة افتراضية
        
        # الحد الأقصى للأعمدة هو 26 (من A إلى Z)
        if num_cols > 26:
            num_cols = 26
        
        for row_index in sorted_indices:
            try:
                if row_index <= 1:
                    # لا نريد حذف صف العنوان (الصف 1)
                    logger.error(f"محاولة حذف صف العنوان أو صف غير صالح: {row_index}")
                    failed_indices.append(row_index)
                    continue
                
                if row_index > num_rows:
                    logger.error(f"الصف {row_index} غير موجود. عدد الصفوف: {num_rows}")
                    failed_indices.append(row_index)
                    continue
                
                # طباعة محتوى الصف قبل الحذف للتحقق
                try:
                    if row_index <= len(all_rows):
                        row_content = all_rows[row_index - 1]  # التعديل من 1-based إلى 0-based للوصول للقائمة
                        logger.info(f"محتوى الصف {row_index} قبل الحذف: {row_content}")
                except Exception as e:
                    logger.warning(f"لا يمكن طباعة محتوى الصف {row_index}: {str(e)}")
                
                # إنشاء صف فارغ للاستبدال - نفس عدد الأعمدة الموجودة في الجدول
                empty_row_values = [['' for _ in range(num_cols)]]
                
                # تحديد نطاق الصف بطريقة صحيحة
                # نستخدم الأحرف من A إلى آخر عمود (على سبيل المثال A:E للخمسة أعمدة الأولى)
                last_column_letter = chr(64 + num_cols)  # 65 = 'A', 66 = 'B', إلخ
                cell_range = f'A{row_index}:{last_column_letter}{row_index}'
                
                logger.info(f"محاولة مسح النطاق: {cell_range} باستخدام batch_update")
                
                try:
                    # تحديث الصف بقيم فارغة باستخدام batch_update
                    worksheet.batch_update([{
                        'range': cell_range,
                        'values': empty_row_values
                    }])
                    
                    logger.info(f"تم مسح محتويات الصف {row_index} بنجاح")
                    success_count += 1
                except Exception as batch_error:
                    logger.error(f"فشل في استخدام batch_update لحذف الصف {row_index}: {str(batch_error)}")
                    
                    # محاولة بديلة باستخدام update_cell
                    try:
                        logger.info(f"محاولة حذف الصف {row_index} باستخدام update_cell لكل عمود...")
                        
                        # مسح كل خلية على حدة
                        for col in range(1, num_cols + 1):
                            worksheet.update_cell(row_index, col, '')
                        
                        logger.info(f"تم مسح محتويات الصف {row_index} باستخدام update_cell")
                        success_count += 1
                    except Exception as cell_error:
                        logger.error(f"فشل في حذف الصف {row_index}: {str(cell_error)}")
                        failed_indices.append(row_index)
                        
            except Exception as e:
                logger.error(f"فشل في حذف الصف {row_index}: {str(e)}")
                logger.error(traceback.format_exc())
                failed_indices.append(row_index)
        
        logger.info(f"نتيجة عملية الحذف: {success_count} نجاح، {len(failed_indices)} فشل")
        return success_count, failed_indices
        
    except Exception as e:
        logger.error(f"خطأ عام في عملية الحذف: {str(e)}")
        logger.error(traceback.format_exc())
        for idx in valid_indices:
            if idx not in failed_indices:
                failed_indices.append(idx)
        return 0, failed_indices

load_dotenv()
GOOGLE_SHEETS_KEY = os.getenv("GOOGLE_SHEETS_KEY")
