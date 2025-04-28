import asyncio
import logging
import os
import sys
import json
from datetime import datetime

# إضافة المجلد الرئيسي إلى مسار البحث
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# اسم ملف جدول البيانات
SPREADSHEET_NAME = "المشتريات"

def format_date(dt: datetime) -> str:
    """تنسيق التاريخ بالشكل المطلوب YYYY/MM/DD"""
    return dt.strftime("%Y/%m/%d")

async def add_products_to_sheet():
    """إضافة منتجات مباشرة إلى جدول البيانات"""
    products = [
        ("بيتزا", 95.0, "جبن"),
        ("لفائف", 35.0, ""),
        ("لبن", 7.0, ""),
        ("شريط لاصق", 29.0, ""),
        ("عصير", 35.0, ""),
        ("بيض", 99.0, ""),
        ("مناديل", 55.0, "")
    ]
    
    logger.info("جاري الاتصال بـ Google Sheets...")
    
    # الحصول على المسار المطلق للمجلد الرئيسي
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # اختيار ملف الاعتماد
    credentials_file = os.path.join(root_dir, "sheet-bot-444713-d558e2ce2ee8.json")
    
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
            
            for product, price, notes in products:
                rows_to_add.append([date, product, price, notes])
                logger.info(f"✅ تجهيز {product} بسعر {price}" + (f" مع ملاحظة: {notes}" if notes else ""))
            
            if rows_to_add:
                worksheet.append_rows(rows_to_add)
                logger.info(f"✅ تمت إضافة {len(rows_to_add)} منتج إلى جدول البيانات")
            
        except Exception as e:
            logger.error(f"خطأ في فتح ورقة العمل: {str(e)}")
            return False
    
    except Exception as e:
        logger.error(f"خطأ في الاتصال بـ Google Sheets: {str(e)}")
        return False
    
    logger.info("تم الانتهاء من الاختبار")
    return True

if __name__ == "__main__":
    try:
        # تشغيل الدالة غير المتزامنة
        asyncio.run(add_products_to_sheet())
    except KeyboardInterrupt:
        print("تم إيقاف البرنامج بواسطة المستخدم")
    except Exception as e:
        logger.error(f"حدث خطأ: {str(e)}") 