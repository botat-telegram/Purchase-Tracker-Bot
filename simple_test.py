import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from database.sheets import get_products, delete_products, add_to_sheets

# إعداد مجلد السجلات
log_dir = Path("logs")
if not log_dir.exists():
    os.makedirs(log_dir, exist_ok=True)

# تنسيق اسم ملف السجل
log_file = log_dir / f"delete_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# إعداد التسجيل
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # الإخراج إلى وحدة التحكم أيضًا
    ]
)

logger = logging.getLogger(__name__)

async def test_products_order():
    """اختبار ترتيب المنتجات عند استرجاعها من قاعدة البيانات"""
    logger.info("=== بدء اختبار ترتيب المنتجات ===")
    print("=== اختبار ترتيب المنتجات ===")
    print(f"سيتم حفظ تسجيلات مفصلة في: {log_file}")
    
    # 1. إضافة 3 منتجات اختبارية بترتيب معروف
    logger.info("1. إضافة منتجات اختبارية جديدة...")
    print("1. إضافة منتجات اختبارية جديدة...")
    
    test_products = [
        ("منتج اختبار الترتيب 1", 100.0, "اختبار 1"),
        ("منتج اختبار الترتيب 2", 200.0, "اختبار 2"),
        ("منتج اختبار الترتيب 3", 300.0, "اختبار 3")
    ]
    
    # إضافة المنتجات واحداً تلو الآخر مع فاصل زمني بسيط
    for name, price, notes in test_products:
        logger.info(f"إضافة المنتج: {name}")
        success = await add_to_sheets(name, price, notes)
        if success:
            print(f"✅ تم إضافة: {name} - {price}")
        else:
            print(f"❌ فشل إضافة: {name}")
        await asyncio.sleep(1)  # فاصل زمني للتأكد من الترتيب
    
    # 2. استرجاع المنتجات
    logger.info("2. استرجاع المنتجات للتحقق من الترتيب...")
    print("\n2. استرجاع المنتجات للتحقق من الترتيب...")
    
    products = await get_products(limit=10)
    
    if not products:
        logger.warning("لا توجد منتجات متاحة للاختبار")
        print("لا توجد منتجات متاحة للاختبار")
        return
    
    # 3. عرض الترتيب
    logger.info(f"تم استرجاع {len(products)} منتج")
    print(f"\nتم استرجاع {len(products)} منتج")
    print("\nترتيب المنتجات كما يظهر في البوت (من الأعلى إلى الأسفل):")
    
    for i, product in enumerate(products):
        name = product.get('name', 'غير معروف')
        price = product.get('price', 'غير معروف')
        date = product.get('date', 'غير معروف')
        sheet_row = product.get('sheet_row', 'غير معروف')
        print(f"{i+1}. {name} - {price} - تاريخ: {date} - صف رقم {sheet_row}")
        logger.debug(f"المنتج {i+1}: {name} - {price} - تاريخ: {date} - صف رقم {sheet_row}")
    
    # 4. التحقق من ترتيب المنتجات التي تم إضافتها
    logger.info("3. التحقق من ترتيب المنتجات الاختبارية...")
    print("\n3. التحقق من ترتيب المنتجات الاختبارية...")
    
    # البحث عن المنتجات الاختبارية
    test_product_1 = None
    test_product_2 = None
    test_product_3 = None
    
    for p in products:
        name = p.get('name', '')
        if "منتج اختبار الترتيب 1" in name:
            test_product_1 = p
        elif "منتج اختبار الترتيب 2" in name:
            test_product_2 = p
        elif "منتج اختبار الترتيب 3" in name:
            test_product_3 = p
    
    # التحقق من الترتيب
    if test_product_1 and test_product_2 and test_product_3:
        # ترتيب المنتجات الثلاثة بناءً على مواقعها في القائمة
        position_1 = products.index(test_product_1) + 1
        position_2 = products.index(test_product_2) + 1
        position_3 = products.index(test_product_3) + 1
        
        logger.info(f"موقع منتج اختبار الترتيب 1: {position_1}")
        logger.info(f"موقع منتج اختبار الترتيب 2: {position_2}")
        logger.info(f"موقع منتج اختبار الترتيب 3: {position_3}")
        
        print(f"موقع منتج اختبار الترتيب 1: {position_1}")
        print(f"موقع منتج اختبار الترتيب 2: {position_2}")
        print(f"موقع منتج اختبار الترتيب 3: {position_3}")
        
        # الترتيب المتوقع: المنتج 3 ثم 2 ثم 1 (لأنهم أضيفوا بهذا الترتيب والأحدث يظهر أولاً)
        if position_3 < position_2 < position_1:
            logger.info("✅ الترتيب صحيح: المنتج 3 ثم 2 ثم 1")
            print("✅ الترتيب صحيح: المنتج 3 ثم 2 ثم 1")
        else:
            logger.warning("❌ الترتيب غير صحيح!")
            print("❌ الترتيب غير صحيح!")
            if position_1 < position_2 < position_3:
                logger.warning("الترتيب معكوس تماماً: المنتج 1 ثم 2 ثم 3")
                print("الترتيب معكوس تماماً: المنتج 1 ثم 2 ثم 3")
            else:
                logger.warning(f"ترتيب غير متوقع: {position_1}, {position_2}, {position_3}")
                print(f"ترتيب غير متوقع: {position_1}, {position_2}, {position_3}")
    else:
        missing = []
        if not test_product_1:
            missing.append("منتج اختبار الترتيب 1")
        if not test_product_2:
            missing.append("منتج اختبار الترتيب 2")
        if not test_product_3:
            missing.append("منتج اختبار الترتيب 3")
        
        logger.warning(f"لم يتم العثور على بعض المنتجات الاختبارية: {', '.join(missing)}")
        print(f"❌ لم يتم العثور على بعض المنتجات الاختبارية: {', '.join(missing)}")

async def test_delete_specific_product():
    """اختبار بسيط لحذف منتج محدد باستخدام رقم الصف الفعلي في جدول البيانات"""
    logger.info("=== بدء اختبار حذف منتج محدد ===")
    print("=== اختبار حذف منتج محدد ===")
    print(f"سيتم حفظ تسجيلات مفصلة في: {log_file}")
    
    # 1. جلب المنتجات
    logger.info("1. جاري جلب المنتجات...")
    products = await get_products(limit=10)
    
    if not products:
        logger.warning("لا توجد منتجات متاحة للاختبار")
        print("لا توجد منتجات متاحة للاختبار")
        return
    
    # عكس ترتيب المنتجات ليتم عرض الأحدث أولاً
    products.reverse()
    logger.info(f"تم عكس ترتيب المنتجات، الآن الأحدث سيظهر أولاً")
    
    # 2. عرض المنتجات مع أرقام الصفوف
    logger.info(f"تم جلب {len(products)} منتج")
    print("\nالمنتجات المتاحة:")
    for i, product in enumerate(products):
        name = product.get('name', 'غير معروف')
        price = product.get('price', 'غير معروف')
        sheet_row = product.get('sheet_row', 'غير معروف')
        print(f"{i+1}. {name} - {price} - صف رقم {sheet_row}")
        logger.debug(f"المنتج {i+1}: {name} - {price} - صف رقم {sheet_row}")
    
    # 3. طلب إدخال رقم المنتج
    try:
        user_input = input("\nأدخل رقم المنتج للحذف (1-" + str(len(products)) + "): ")
        logger.info(f"تم اختيار المنتج رقم: {user_input}")
        product_index = int(user_input) - 1
        
        if product_index < 0 or product_index >= len(products):
            error_msg = f"رقم غير صالح! يجب أن يكون بين 1 و {len(products)}"
            logger.warning(error_msg)
            print(error_msg)
            return
        
        selected_product = products[product_index]
        sheet_row = selected_product.get('sheet_row')
        
        if not sheet_row:
            error_msg = f"المنتج المحدد ليس له رقم صف معروف: {selected_product}"
            logger.warning(error_msg)
            print(error_msg)
            return
        
        # 4. تأكيد الحذف
        logger.info(f"طلب تأكيد حذف المنتج: {selected_product.get('name')} - صف {sheet_row}")
        confirm = input(f"\nهل أنت متأكد من حذف المنتج: {selected_product.get('name')} - {selected_product.get('price')} (y/n)? ")
        
        if confirm.lower() != 'y':
            logger.info("تم إلغاء الحذف بواسطة المستخدم")
            print("تم إلغاء الحذف")
            return
        
        # 5. تنفيذ الحذف
        logger.info(f"جاري حذف المنتج من الصف {sheet_row}...")
        print(f"\nجاري حذف المنتج من الصف {sheet_row}...")
        success_count, failed_indices = await delete_products([sheet_row])
        
        # 6. عرض النتيجة
        if success_count > 0:
            logger.info(f"تم حذف المنتج بنجاح! رقم الصف: {sheet_row}")
            print(f"✅ تم حذف المنتج بنجاح!")
        else:
            logger.error(f"فشل حذف المنتج من الصف {sheet_row}. الأخطاء: {failed_indices}")
            print(f"❌ فشل حذف المنتج. الأخطاء: {failed_indices}")
        
        # 7. التحقق من النتيجة
        logger.info("جاري التحقق من نتيجة الحذف...")
        print("\nجاري التحقق من النتيجة...")
        updated_products = await get_products(limit=10)
        
        # البحث عن المنتج المحذوف
        found = False
        for p in updated_products:
            if (p.get('name') == selected_product.get('name') and 
                p.get('price') == selected_product.get('price')):
                found = True
                logger.debug(f"وجد منتج مطابق: {p}")
                break
        
        if found:
            logger.warning("المنتج لا يزال موجودًا في قاعدة البيانات بعد الحذف")
            print("❌ المنتج لا يزال موجودًا في قاعدة البيانات")
        else:
            logger.info("تم التأكد من حذف المنتج بنجاح")
            print("✅ تم التأكد من حذف المنتج بنجاح")
        
    except ValueError:
        logger.error("خطأ في تحويل رقم المنتج - يرجى إدخال رقم صحيح")
        print("يرجى إدخال رقم صحيح")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {str(e)}", exc_info=True)
        print(f"حدث خطأ: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    logger.info("بدء تشغيل اختبار الترتيب والحذف")
    # اختيار الاختبار
    print("\nاختر الاختبار المطلوب:")
    print("1. اختبار ترتيب المنتجات")
    print("2. اختبار حذف منتج محدد")
    
    choice = input("اختيارك (1 أو 2): ")
    
    if choice == "1":
        asyncio.run(test_products_order())
    elif choice == "2":
        asyncio.run(test_delete_specific_product())
    else:
        print("اختيار غير صالح!")
    
    logger.info("انتهاء اختبار الترتيب والحذف") 