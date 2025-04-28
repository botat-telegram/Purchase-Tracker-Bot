import asyncio
import logging
from database.sheets import add_to_sheets

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_add_products():
    """اختبار إضافة منتجات متعددة إلى جدول البيانات"""
    products = [
        ("بيتزا", 95.0, "جبن"),
        ("لفائف", 35.0, ""),
        ("لبن", 7.0, ""),
        ("شريط لاصق", 29.0, ""),
        ("عصير", 35.0, ""),
        ("بيض", 99.0, ""),
        ("مناديل", 55.0, "")
    ]
    
    logger.info("جاري اختبار إضافة المنتجات إلى Google Sheets...")
    
    for product, price, notes in products:
        success = await add_to_sheets(product, price, notes)
        if success:
            logger.info(f"✅ تم إضافة {product} بسعر {price}" + (f" مع ملاحظة: {notes}" if notes else ""))
        else:
            logger.error(f"❌ فشل في إضافة {product}")
    
    logger.info("تم الانتهاء من الاختبار")

if __name__ == "__main__":
    try:
        # تشغيل الدالة غير المتزامنة
        asyncio.run(test_add_products())
    except KeyboardInterrupt:
        print("تم إيقاف البرنامج بواسطة المستخدم")
    except Exception as e:
        logger.error(f"حدث خطأ: {str(e)}") 