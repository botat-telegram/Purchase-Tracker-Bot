import asyncio
import sys
import os
import logging
import time

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# إضافة المسار الحالي إلى مسار النظام
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# استيراد الوظائف المطلوبة
from database.sheets import get_worksheet, delete_products

async def final_test_delete():
    print("=== اختبار نهائي لحذف منتجات الاختبار ===")
    
    # 1. البحث عن منتجات الاختبار
    print("\n1. البحث عن منتجات الاختبار...")
    
    worksheet = get_worksheet()
    
    if worksheet is None:
        print("تعذر الاتصال بجدول البيانات!")
        return
    
    # الحصول على جميع القيم في الجدول
    all_values = worksheet.get_all_values()
    
    # البحث عن منتجات الاختبار وحفظ أرقام صفوفها
    test_products = []
    
    for i, row in enumerate(all_values):
        # تخطي صف العناوين
        if i == 0:
            continue
            
        # البحث عن منتجات الاختبار
        if len(row) > 1 and row[1].strip().startswith("اختبار الحذف"):
            row_number = i + 1  # رقم الصف الفعلي (+1 لأن الفهرسة تبدأ من 0)
            test_products.append({
                "row": row_number,
                "name": row[1],
                "price": row[2] if len(row) > 2 else "-"
            })
    
    if not test_products:
        print("لم يتم العثور على أي منتجات اختبار!")
        return
    
    print(f"تم العثور على {len(test_products)} منتج اختبار:")
    for prod in test_products:
        print(f"  المنتج {prod['name']} (السعر: {prod['price']}) - الصف {prod['row']}")
    
    # 2. حذف منتجات الاختبار واحدًا تلو الآخر
    print("\n2. جاري حذف منتجات الاختبار واحدًا تلو الآخر...")
    
    total_success = 0
    total_failed = 0
    
    for prod in test_products:
        try:
            # نحذف منتج واحد في كل مرة
            print(f"  جاري حذف المنتج {prod['name']} (صف رقم {prod['row']})...")
            
            # استخدام رقم الصف الفعلي للحذف وليس الفهرس
            row_number = prod['row']
            
            # محاولة الحذف
            success_count, failed_indices = await delete_products([row_number])
            
            # عرض النتيجة
            if success_count > 0:
                print(f"  تم حذف المنتج {prod['name']} بنجاح!")
                total_success += 1
            else:
                print(f"  فشل في حذف المنتج {prod['name']}! الأخطاء: {failed_indices}")
                total_failed += 1
            
            # انتظار 5 ثوان بين كل عملية حذف لتجنب تجاوز الحصة
            print("  انتظار 5 ثوانٍ...")
            time.sleep(5)
            
        except Exception as e:
            print(f"  حدث خطأ أثناء محاولة الحذف: {str(e)}")
            total_failed += 1
            # انتظار أطول في حالة حدوث خطأ
            print("  انتظار 10 ثوانٍ بعد الخطأ...")
            time.sleep(10)
    
    # 3. التحقق من نتيجة الحذف
    print(f"\n3. نتيجة الحذف: تم حذف {total_success} منتج، وفشل حذف {total_failed} منتج")
    
    # التحقق النهائي بعد الانتظار
    print("\nانتظار 5 ثوانٍ إضافية للتأكد من تطبيق التغييرات...")
    time.sleep(5)
    
    print("\nالتحقق النهائي من وجود منتجات الاختبار:")
    
    # إعادة تحميل القيم
    all_values = worksheet.get_all_values()
    remaining_test_products = []
    
    for i, row in enumerate(all_values):
        # تخطي صف العناوين
        if i == 0:
            continue
            
        # البحث عن منتجات الاختبار المتبقية
        if len(row) > 1 and row[1].strip().startswith("اختبار الحذف"):
            remaining_test_products.append({
                "row": i + 1,
                "name": row[1]
            })
    
    if remaining_test_products:
        print(f"تم العثور على {len(remaining_test_products)} منتج اختبار متبقي:")
        for prod in remaining_test_products:
            print(f"  الصف {prod['row']}: {prod['name']}")
    else:
        print("تم حذف جميع منتجات الاختبار بنجاح!")

if __name__ == "__main__":
    asyncio.run(final_test_delete()) 