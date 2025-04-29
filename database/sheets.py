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
from typing import Optional, Tuple, List, Dict
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
import traceback
from functools import lru_cache
from datetime import datetime, timedelta
from dotenv import load_dotenv

# إعداد التسجيل
logger = logging.getLogger(__name__)

# اسم ملف جدول البيانات
SPREADSHEET_NAME = "المشتريات"

# حدود السعر
MIN_PRICE = 0.01
MAX_PRICE = 1000000

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

@lru_cache(maxsize=1)
def get_google_sheets_client() -> Tuple[gspread.Client, datetime]:
    """
    الحصول على عميل Google Sheets مع تخزين مؤقت
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

def get_worksheet() -> gspread.Worksheet:
    """
    الحصول على ورقة العمل مع التعامل مع الأخطاء
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
    """
    return dt.strftime("%Y/%m/%d")

async def add_to_sheets(product: str, price: float, notes: str = "") -> bool:
    """
    إضافة منتج جديد إلى Google Sheets
    
    المعطيات:
        product (str): اسم المنتج
        price (float): سعر المنتج
        notes (str): ملاحظات إضافية (اختياري)
        
    تعيد:
        bool: True إذا تمت الإضافة بنجاح، False إذا فشلت
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

        # إضافة المنتج إلى ورقة العمل
        date = format_date(datetime.now())
        worksheet.append_row([date, product, price, notes])
        
        logger.info(f"تمت إضافة المنتج: {product} بسعر {price} بتاريخ {date} مع ملاحظات: {notes}")
        
        return True
        
    except Exception as e:
        logger.error(f"خطأ في إضافة المنتج: {str(e)}")
        logger.error(traceback.format_exc())
        return False

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
        قائمة بالمنتجات
    """
    global DEMO_MODE
    
    if DEMO_MODE:
        # إرجاع المنتجات من القائمة المؤقتة
        if DEMO_PRODUCTS:
            # إرجاع آخر منتجات مضافة، بحد أقصى limit
            return DEMO_PRODUCTS[-limit:]
        else:
            # إذا لم تكن هناك منتجات، نعيد بيانات تجريبية
            demo_products = [
                {
                    'date': format_date(datetime.now()),
                    'name': 'كولا',
                    'price': 23.0,
                    'notes': 'مثال تجريبي'
                },
                {
                    'date': format_date(datetime.now()),
                    'name': 'شيبس',
                    'price': 15.0,
                    'notes': 'حار'
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
        
        # تحويل القيم إلى قائمة من القواميس
        products = []
        # تخطي الصف الأول (العناوين)
        for row in values[1:]:
            try:
                if len(row) >= 3:
                    products.append({
                        'date': row[0],
                        'name': row[1],
                        'price': float(row[2]),
                        'notes': row[3] if len(row) > 3 else ''
                    })
            except (IndexError, ValueError) as e:
                logger.warning(f"خطأ في تحويل الصف {row}: {str(e)}")
                continue
        
        # الحصول على آخر المنتجات فقط
        return products[-limit:] if products else []
        
    except Exception as e:
        logger.error(f"خطأ في الحصول على المنتجات: {str(e)}")
        DEMO_MODE = True
        return await get_products(limit)

load_dotenv()
GOOGLE_SHEETS_KEY = os.getenv("GOOGLE_SHEETS_KEY")
