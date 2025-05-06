"""
محول الأرقام
يتيح تحويل الأرقام العربية والهندية إلى أرقام إنجليزية
"""
import re

# قاموس تحويل الأرقام
ARABIC_TO_ENGLISH = {
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
    # الأرقام الهندية
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
}

# قاموس تحويل الكلمات الرقمية العربية
ARABIC_WORDS_TO_NUMBERS = {
    'صفر': '0',
    'واحد': '1', 'وحدة': '1', 'وحده': '1', 'أحد': '1',
    'اثنان': '2', 'اثنين': '2', 'اتنين': '2', 
    'ثلاثة': '3', 'ثلاث': '3', 'تلات': '3', 'تلاته': '3',
    'أربعة': '4', 'اربعة': '4', 'اربع': '4', 'أربع': '4',
    'خمسة': '5', 'خمس': '5',
    'ستة': '6', 'ست': '6',
    'سبعة': '7', 'سبع': '7',
    'ثمانية': '8', 'ثمان': '8', 'تمانية': '8', 'تمنية': '8',
    'تسعة': '9', 'تسع': '9',
    'عشرة': '10', 'عشر': '10',
    'مية': '100', 'ميه': '100', 'مائة': '100',
    'ألف': '1000', 'الف': '1000',
}

# قاموس للعملات الشائعة
CURRENCY_WORDS = {
    'ريال': '', 'ريالات': '', 'ر.س': '', 'ر.س.': '', 'رس': '', 'ر س': '', 'rs': '', 'SR': '', 'SAR': '',
    'دولار': '', '$': '', 'USD': '', 'دولارات': '',
    'يورو': '', '€': '', 'EUR': '', 'يوروهات': '',
    'جنيه': '', 'جنيهات': '', 'ج.م': '', 'EGP': '',
    'درهم': '', 'دراهم': '', 'AED': '', 'د.إ': '',
}

def convert_to_english_numbers(text: str) -> str:
    """
    تحويل الأرقام العربية والهندية في النص إلى أرقام إنجليزية
    
    Args:
        text (str): النص المحتوي على أرقام عربية/هندية
        
    Returns:
        str: النص بعد تحويل الأرقام إلى إنجليزية
    """
    if not text:
        return text
        
    # تحويل الأرقام العربية والهندية
    for arabic, english in ARABIC_TO_ENGLISH.items():
        if arabic in text:
            text = text.replace(arabic, english)
    
    # تحويل كلمات العملات إلى مساحة (لتسهيل تحليل النص)
    for currency, replacement in CURRENCY_WORDS.items():
        # نضيف حدود الكلمة لنتأكد من أنها كلمة مستقلة
        pattern = r'\b' + re.escape(currency) + r'\b'
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # التعامل مع التنسيقات المختلفة للعملات
    # مثال: 100ريال، 200 درهم، ر.س 150
    
    # 1. نمط رقم متبوع بكلمة عملة بدون مسافة: 100ريال
    currency_patterns = [re.escape(currency) for currency in CURRENCY_WORDS.keys() if currency]
    if currency_patterns:
        currency_pattern = '|'.join(currency_patterns)
        pattern = r'(\d+)(' + currency_pattern + r')'
        text = re.sub(pattern, r'\1', text, flags=re.IGNORECASE)
    
    # 2. نمط كلمة عملة متبوعة برقم بدون مسافة: ريال100
    pattern = r'(' + currency_pattern + r')(\d+)'
    text = re.sub(pattern, r'\2', text, flags=re.IGNORECASE)
    
    # استخراج الأجزاء العشرية والتعامل معها
    # مثال: 10.5 أو 10,5
    text = text.replace(',', '.')
    
    # تحويل الكلمات العربية للأرقام
    # هذا تحسين إضافي للتعامل مع كلمات الأرقام
    for word, number in ARABIC_WORDS_TO_NUMBERS.items():
        pattern = r'\b' + re.escape(word) + r'\b'
        text = re.sub(pattern, number, text, flags=re.IGNORECASE)
    
    return text

def extract_price_from_text(text: str) -> float:
    """
    استخراج السعر من النص
    
    Args:
        text (str): النص الذي يحتوي على سعر
        
    Returns:
        float: السعر المستخرج أو None إذا لم يتم العثور على سعر
    """
    if not text:
        return None
    
    # تحويل الأرقام العربية والهندية
    text = convert_to_english_numbers(text)
    
    # نمط للعثور على رقم (مع دعم الأرقام العشرية)
    pattern = r'\b\d+(?:\.\d+)?\b'
    
    matches = re.findall(pattern, text)
    if matches:
        try:
            # نأخذ أول مطابقة
            return float(matches[0])
        except ValueError:
            return None
    
    return None

if __name__ == "__main__":
    # اختبار وظائف التحويل
    test_numbers = [
        "١٢٣٤٥٦٧٨٩٠",
        "۱۲۳۴۵۶۷۸۹۰",
        "مبلغ ١٠٠ ريال",
        "١٢.٥",
        "۲,۵۰۰",
        "123456789"
    ]

    for test in test_numbers:
        result = convert_to_english_numbers(test)
        print(f"الأصل: {test}")
        print(f"بعد التحويل: {result}")
        print("----------")
