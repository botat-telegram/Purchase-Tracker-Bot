"""
معالج إدخال المنتجات
يتيح التعرف على صيغ متعددة من إدخال المنتجات
"""
import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Tuple

from utils.number_converter import convert_to_english_numbers

class InputFormat(Enum):
    """أنماط إدخال المنتجات المدعومة"""
    STANDARD = "standard"  # منتج سعر ملاحظة (مثال: تفاح 10 أحمر)
    COLON = "colon"  # منتج:سعر:ملاحظة (مثال: تفاح:10:أحمر)
    COMMA = "comma"  # منتج,سعر,ملاحظة (مثال: تفاح,10,أحمر)
    DASH = "dash"  # منتج-سعر-ملاحظة (مثال: تفاح-10-أحمر)
    EQUALS = "equals"  # منتج=سعر ملاحظة (مثال: تفاح=10 أحمر)
    MULTILINE = "multiline"  # عدة منتجات كل منتج في سطر

@dataclass
class ProductData:
    """بيانات المنتج المستخرجة من الإدخال"""
    product: str
    price: Optional[float] = None
    notes: str = ""
    format_used: InputFormat = InputFormat.STANDARD
    is_valid: bool = True
    
    def __str__(self) -> str:
        """تمثيل نصي للمنتج"""
        if not self.is_valid:
            return f"[غير صالح] {self.product}"
        
        price_str = f"{self.price}" if self.price is not None else "؟"
        notes_str = f" ({self.notes})" if self.notes else ""
        return f"{self.product}: {price_str}{notes_str}"

def _extract_standard_format(text: str) -> ProductData:
    """
    استخراج بيانات المنتج من الصيغة القياسية
    منتج سعر ملاحظة (مثال: تفاح 10 أحمر)
    """
    # تنظيف النص
    text = ' '.join(text.split())
    
    # تحويل الأرقام العربية إلى إنجليزية
    text = convert_to_english_numbers(text)
    
    # تقسيم النص إلى كلمات
    parts = text.split()
    if not parts:
        return ProductData("", None, "", InputFormat.STANDARD, False)
    
    # البحث عن أول رقم (السعر)
    product_parts = []
    price = None
    price_index = -1
    
    for i, part in enumerate(parts):
        try:
            # محاولة تحويل الجزء إلى رقم
            price = float(part)
            price_index = i
            break
        except ValueError:
            # إذا لم يكن رقمًا، فهو جزء من اسم المنتج
            product_parts.append(part)
    
    # إذا لم نجد سعرًا
    if price_index == -1:
        product = " ".join(parts)
        return ProductData(product, None, "", InputFormat.STANDARD, True)
    
    # إذا لم يكن هناك أجزاء قبل السعر
    if not product_parts:
        return ProductData("", price, " ".join(parts[price_index+1:]), InputFormat.STANDARD, False)
    
    # استخراج اسم المنتج والملاحظات
    product = " ".join(product_parts)
    notes = " ".join(parts[price_index+1:]) if price_index + 1 < len(parts) else ""
    
    return ProductData(product, price, notes, InputFormat.STANDARD, True)

def _extract_separated_format(text: str, separator: str, format_type: InputFormat) -> ProductData:
    """
    استخراج بيانات المنتج من صيغة تستخدم فاصلاً محددًا
    منتج{separator}سعر{separator}ملاحظة
    """
    # تنظيف النص
    text = text.strip()
    
    # تقسيم النص باستخدام الفاصل المحدد
    parts = text.split(separator)
    
    # في حالة عدم وجود أجزاء كافية، نعود إلى الصيغة القياسية
    if len(parts) < 2:
        return _extract_standard_format(text)
    
    # استخراج اسم المنتج
    product = parts[0].strip()
    
    # استخراج السعر
    price_text = convert_to_english_numbers(parts[1].strip())
    try:
        price = float(price_text)
    except ValueError:
        return ProductData(product, None, " ".join(parts[1:]), format_type, True)
    
    # استخراج الملاحظات
    notes = separator.join(parts[2:]).strip() if len(parts) > 2 else ""
    
    return ProductData(product, price, notes, format_type, True)

def parse_product_input(text: str) -> ProductData:
    """
    تحليل نص إدخال المستخدم واستخراج بيانات المنتج
    يدعم عدة صيغ مختلفة
    """
    if not text or not text.strip():
        return ProductData("", None, "", InputFormat.STANDARD, False)
    
    # تنظيف النص
    text = text.strip()
    
    # تحديد الصيغة المستخدمة
    if ":" in text:
        return _extract_separated_format(text, ":", InputFormat.COLON)
    elif "," in text:
        return _extract_separated_format(text, ",", InputFormat.COMMA)
    elif "-" in text and not text.startswith("-"):  # تجنب الخلط مع الأرقام السالبة
        return _extract_separated_format(text, "-", InputFormat.DASH)
    elif "=" in text:
        return _extract_separated_format(text, "=", InputFormat.EQUALS)
    else:
        return _extract_standard_format(text)

def parse_multiline_input(text: str) -> List[ProductData]:
    """
    تحليل نص متعدد الأسطر واستخراج بيانات المنتجات
    كل سطر يمثل منتجًا مختلفًا
    """
    if not text or not text.strip():
        return []
    
    # تقسيم النص إلى أسطر
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    # تحليل كل سطر
    products = []
    for line in lines:
        product_data = parse_product_input(line)
        product_data.format_used = InputFormat.MULTILINE
        products.append(product_data)
    
    return products

# اختبار الوحدة
if __name__ == "__main__":
    test_inputs = [
        "تفاح 10",
        "تفاح 10 أحمر",
        "تفاح ١٠ أحمر",
        "تفاح:10:أحمر",
        "تفاح,10,أحمر كبير",
        "تفاح-10-أحمر",
        "تفاح=10 أحمر",
        "تفاح",
        "10",
        "",
        "تفاح:عشرة"
    ]
    
    print("اختبار تحليل إدخال فردي:")
    for input_text in test_inputs:
        result = parse_product_input(input_text)
        print(f"الإدخال: '{input_text}' -> {result} (الصيغة: {result.format_used.value})")
    
    multiline_input = """
    تفاح 10 أحمر
    موز 5
    عنب:15:أخضر
    """
    
    print("\nاختبار تحليل إدخال متعدد الأسطر:")
    results = parse_multiline_input(multiline_input)
    for i, result in enumerate(results):
        print(f"{i+1}. {result} (الصيغة: {result.format_used.value})") 