"""
اختبارات خاصة بوظائف Google Sheets
يحتوي على اختبارات لوظائف التعامل مع جداول البيانات
"""
import asyncio
import logging
import sys
import os
import json
from datetime import datetime

# إضافة المجلد الرئيسي إلى مسار البحث
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from database.sheets import add_to_sheets, add_multiple_to_sheets

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# اسم ملف جدول البيانات
SPREADSHEET_NAME = "المشتريات"

# قائمة المنتجات للاختبار
TEST_PRODUCTS = [
    ("بيتزا", 95.0, "جبن"),
    ("لفائف", 35.0, ""),
    ("لبن", 7.0, ""),
    ("شريط لاصق", 29.0, ""),
    ("عصير", 35.0, ""),
    ("بيض", 99.0, ""),
    ("مناديل", 55.0, "")
]

def format_date(dt: datetime) -> str:
    """تنسيق التاريخ بالشكل المطلوب YYYY/MM/DD"""
    return dt.strftime("%Y/%m/%d")

def get_credentials_file():
    """الحصول على مسار ملف الاعتماد"""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_files = [
        os.path.join(root_dir, "sheet-bot-444713-d558e2ce2ee8.json"),
        os.path.join(root_dir, "client_secret_sheet.json"),
        os.path.join(root_dir, "credentials.json")
    ]
    
    for file in credentials_files:
        if os.path.exists(file):
            logger.info(f"تم العثور على ملف اعتماد: {file}")
            return file
    
    logger.warning("لم يتم العثور على أي ملف اعتماد!")
    return None

async def test_add_products_via_module():
    """اختبار إضافة منتجات باستخدام وحدة database.sheets"""
    logger.info("=== اختبار إضافة منتجات عبر وحدة database.sheets ===")
    
    success_count = 0
    for product, price, notes in TEST_PRODUCTS:
        try:
            success = await add_to_sheets(product, price, notes)
            if success:
                logger.info(f"✅ تم إضافة {product} بسعر {price}" + (f" مع ملاحظة: {notes}" if notes else ""))
                success_count += 1
            else:
                logger.error(f"❌ فشل في إضافة {product}")
        except Exception as e:
            logger.error(f"❌ خطأ عند إضافة {product}: {str(e)}")
            
    logger.info(f"تم إضافة {success_count} من أصل {len(TEST_PRODUCTS)} منتج بنجاح")
    return success_count

async def test_add_products_direct():
    """اختبار إضافة منتجات مباشرة إلى Google Sheets"""
    logger.info("=== اختبار إضافة منتجات مباشرة إلى Google Sheets ===")
    
    # الحصول على ملف الاعتماد
    credentials_file = get_credentials_file()
    if not credentials_file:
        logger.error("لا يمكن إكمال الاختبار بدون ملف اعتماد")
        return False
    
    try:
        # صلاحيات Google Sheets و Google Drive
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        # تهيئة الاعتمادات
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            credentials_file, scope)
        
        # إنشاء عميل gspread
        client = gspread.authorize(credentials)
        
        try:
            # محاولة فتح جدول البيانات بالاسم
            spreadsheet = client.open(SPREADSHEET_NAME)
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
                logger.info("تم إنشاء رؤوس الأعمدة")
            
            # إضافة المنتجات
            date = format_date(datetime.now())
            rows_to_add = []
            
            for product, price, notes in TEST_PRODUCTS:
                rows_to_add.append([date, product, price, notes])
                logger.info(f"✅ تجهيز {product} بسعر {price}" + (f" مع ملاحظة: {notes}" if notes else ""))
            
            if rows_to_add:
                worksheet.append_rows(rows_to_add)
                logger.info(f"✅ تمت إضافة {len(rows_to_add)} منتج إلى جدول البيانات")
                return True
            
        except Exception as e:
            logger.error(f"خطأ في فتح ورقة العمل: {str(e)}")
            return False
    
    except Exception as e:
        logger.error(f"خطأ في الاتصال بـ Google Sheets: {str(e)}")
        return False
    
    return False

async def test_add_multiple_products():
    """اختبار إضافة منتجات متعددة دفعة واحدة"""
    logger.info("=== اختبار إضافة منتجات متعددة دفعة واحدة ===")
    
    try:
        success_count, errors = await add_multiple_to_sheets(TEST_PRODUCTS)
        logger.info(f"تم إضافة {success_count} من أصل {len(TEST_PRODUCTS)} منتج بنجاح")
        if errors:
            for error in errors:
                logger.error(f"❌ خطأ: {error}")
        return success_count
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {str(e)}")
        return 0

async def run_all_tests():
    """تشغيل جميع الاختبارات"""
    tests = [
        ("إضافة منتجات عبر وحدة database.sheets", test_add_products_via_module),
        ("إضافة منتجات مباشرة إلى Google Sheets", test_add_products_direct),
        ("إضافة منتجات متعددة دفعة واحدة", test_add_multiple_products)
    ]
    
    results = {}
    
    for name, test_func in tests:
        logger.info(f"\n\n⏱️ جاري تشغيل اختبار: {name}")
        try:
            result = await test_func()
            results[name] = result
            logger.info(f"✅ اكتمل اختبار: {name} بنتيجة: {result}")
        except Exception as e:
            logger.error(f"❌ فشل اختبار: {name} بسبب: {str(e)}")
            results[name] = None
            
    return results

if __name__ == "__main__":
    try:
        logger.info("🚀 بدء تشغيل اختبارات Google Sheets")
        
        # اختيار الاختبار المطلوب تشغيله
        # 1: test_add_products_via_module
        # 2: test_add_products_direct
        # 3: test_add_multiple_products
        # 0: all tests
        test_to_run = 0
        
        if test_to_run == 1:
            asyncio.run(test_add_products_via_module())
        elif test_to_run == 2:
            asyncio.run(test_add_products_direct())
        elif test_to_run == 3:
            asyncio.run(test_add_multiple_products())
        else:
            asyncio.run(run_all_tests())
            
    except KeyboardInterrupt:
        logger.info("تم إيقاف الاختبار بواسطة المستخدم")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {str(e)}")
    finally:
        logger.info("🏁 انتهت اختبارات Google Sheets") 