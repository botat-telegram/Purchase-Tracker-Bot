"""
نقطة البداية للنسخة CLI من برنامج تسجيل المشتريات
"""
import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def setup_argparse():
    """إعداد معالج الأوامر"""
    parser = argparse.ArgumentParser(description='أداة تسجيل المشتريات في Google Sheets')
    subparsers = parser.add_subparsers(dest='command', help='الأوامر المتاحة')

    # أمر إضافة منتج
    add_parser = subparsers.add_parser('add', help='إضافة منتج جديد')
    add_parser.add_argument('product', help='اسم المنتج')
    add_parser.add_argument('price', type=float, help='سعر المنتج')
    add_parser.add_argument('notes', nargs='?', default='', help='ملاحظات إضافية')

    # أمر إضافة عدة منتجات من ملف
    bulk_parser = subparsers.add_parser('add-bulk', help='إضافة عدة منتجات من ملف')
    bulk_parser.add_argument('file', help='مسار ملف المنتجات')

    # أمر عرض المنتجات
    list_parser = subparsers.add_parser('list', help='عرض المنتجات')
    list_parser.add_argument('--limit', type=int, default=10, help='عدد المنتجات للعرض')

    return parser

async def add_product(product: str, price: float, notes: str = '') -> bool:
    """إضافة منتج جديد"""
    from database.sheets import add_to_sheets
    try:
        # كلمات تخطي الملاحظات
        SKIP_NOTES_WORDS = [".", "لا", "-", "/s", "s", "لأ"]
        notes = '' if notes.strip().lower() in SKIP_NOTES_WORDS else notes
        
        success = await add_to_sheets(product, price, notes)
        if success:
            logger.info(f"تم إضافة {product} بسعر {price}")
            return True
        else:
            logger.error(f"فشل في إضافة {product}")
            return False
    except Exception as e:
        logger.error(f"خطأ في إضافة المنتج: {str(e)}")
        return False

async def add_bulk_products(file_path: str) -> bool:
    """إضافة عدة منتجات من ملف"""
    from database.sheets import add_multiple_to_sheets
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            products = []
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        product = parts[0]
                        price = float(parts[1])
                        notes = ' '.join(parts[2:]) if len(parts) > 2 else ''
                        products.append((product, price, notes))

        if products:
            success_count, errors = await add_multiple_to_sheets(products)
            if errors:
                for error in errors:
                    logger.error(error)
            if success_count > 0:
                logger.info(f"تم إضافة {success_count} منتج")
                return True
        
        logger.error("لم يتم إضافة أي منتجات")
        return False
        
    except Exception as e:
        logger.error(f"خطأ في إضافة المنتجات: {str(e)}")
        return False

async def list_products(limit: int = 10) -> None:
    """عرض المنتجات"""
    from database.sheets import get_products
    try:
        products = await get_products(limit)
        if products:
            print("\nآخر المنتجات المضافة:")
            print("-" * 50)
            for product in products:
                print(f"المنتج: {product['name']}")
                print(f"السعر: {product['price']}")
                if product.get('notes'):
                    print(f"ملاحظات: {product['notes']}")
                print("-" * 50)
        else:
            print("لا توجد منتجات")
    except Exception as e:
        logger.error(f"خطأ في عرض المنتجات: {str(e)}")

async def main() -> None:
    """الدالة الرئيسية"""
    try:
        # تحميل المتغيرات البيئية
        load_dotenv()
        
        # التحقق من وجود ملف credentials.json
        if not os.path.exists('credentials.json'):
            logger.error("ملف credentials.json غير موجود!")
            sys.exit(1)

        # إعداد معالج الأوامر
        parser = setup_argparse()
        args = parser.parse_args()

        if args.command == 'add':
            await add_product(args.product, args.price, args.notes)
        elif args.command == 'add-bulk':
            await add_bulk_products(args.file)
        elif args.command == 'list':
            await list_products(args.limit)
        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"خطأ: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
