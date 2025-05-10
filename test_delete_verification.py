import asyncio
import logging
import sys
import os

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# إضافة المسار الحالي إلى مسار النظام
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# استيراد الوظائف المطلوبة
from database.sheets import get_products, delete_products, add_to_sheets

async def test_add_then_verify_delete():
    """
    اختبار إضافة منتج ثم التحقق من صحة الحذف بعد الإصلاحات
    """
    print("=== اختبار إضافة ثم حذف منتج للتحقق من الإصلاحات ===")
    
    # 1. إضافة منتج اختباري جديد
    print("\n1. إضافة منتج اختباري...")
    
    test_product_name = "اختبار التحقق من الحذف"
    test_product_price = 100.0
    test_product_notes = "هذا منتج اختباري لتحقق وظيفة الحذف"
    
    try:
        success = await add_to_sheets(test_product_name, test_product_price, test_product_notes)
        
        if not success:
            print("❌ فشل في إضافة المنتج الاختباري")
            return
            
        print("✅ تم إضافة المنتج الاختباري بنجاح")
        
        # الانتظار قليلاً قبل جلب المنتجات
        print("انتظار 2 ثانية...")
        await asyncio.sleep(2)
        
        # 2. التحقق من إضافة المنتج والحصول على رقم الصف
        print("\n2. التحقق من إضافة المنتج...")
        
        products = await get_products(limit=10)
        
        found = False
        sheet_row = None
        
        for idx, product in enumerate(products):
            name = product.get('name', '')
            if name == test_product_name:
                row = product.get('sheet_row', 'غير معروف')
                print(f"✅ تم العثور على المنتج في القائمة: #{idx+1}, الصف: {row}")
                sheet_row = row
                found = True
                break
        
        if not found or sheet_row is None:
            print("❌ لم يتم العثور على المنتج الاختباري في القائمة أو لم يكن له رقم صف!")
            return
            
        # 3. محاولة حذف المنتج
        print(f"\n3. حذف المنتج الاختباري من الصف {sheet_row}...")
        
        # استخدام رقم الصف الفعلي للحذف
        success_count, failed_indices = await delete_products([sheet_row])
        
        if success_count > 0:
            print(f"✅ تم حذف المنتج بنجاح! نجاح: {success_count}")
        else:
            print(f"❌ فشل حذف المنتج! أخطاء: {failed_indices}")
            return
            
        # انتظار قبل التحقق النهائي
        print("انتظار 2 ثانية...")
        await asyncio.sleep(2)
        
        # 4. التحقق من الحذف
        print("\n4. التحقق من حذف المنتج...")
        
        products = await get_products(limit=10)
        
        found = False
        for product in products:
            name = product.get('name', '')
            if name == test_product_name:
                found = True
                break
                
        if found:
            print("❌ المنتج الاختباري ما زال موجوداً في القائمة!")
        else:
            print("✅ تم حذف المنتج الاختباري بنجاح!")
    
    except Exception as e:
        print(f"❌ حدث خطأ أثناء الاختبار: {str(e)}")
        logger.error(f"خطأ: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_add_then_verify_delete()) 