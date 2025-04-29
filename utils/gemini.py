"""
التكامل مع Gemini API
هذه الوحدة توفر دوال لإرسال نصوص غير منظمة إلى Gemini وتحليلها لاستخراج المنتجات والسعر والملاحظة.
"""
import requests
from typing import List, Dict, Optional
import json
import re
import logging
import os
from src.config import GEMINI_API_KEY
import google.generativeai as genai

# إعداد التسجيل
logger = logging.getLogger(__name__)

# مصفوفة الكلمات التي تعتبر ملاحظات (يمكن تعديلها لاحقاً)
DEFAULT_NOTES_KEYWORDS = [
    "ك", "كيلو", "حبة", "قطعة", "علبة", "درزن", "باكيت", "جرام", "جم", "سعر خاص", "عرض"
]

class GeminiAPIError(Exception):
    pass

def initialize_genai_client():
    """
    تهيئة عميل Google Generative AI
    """
    api_key = GEMINI_API_KEY
    if not api_key:
        raise GeminiAPIError("مفتاح API غير محدد. يرجى تعيين GEMINI_API_KEY في ملف .env")
    
    genai.configure(api_key=api_key)
    return genai

async def analyze_products_with_gemini(text: str) -> List[Dict[str, str]]:
    """
    تحليل رسالة نصية غير منظمة باستخدام Gemini API
    """
    try:
        client = initialize_genai_client()
        model = client.GenerativeModel("gemini-1.5-flash")

        # تقسيم النص إلى أسطر (إذا كان يحتوي على أسطر متعددة)
        lines = text.split('\n')
        
        # إذا كان لدينا سطر واحد فقط، نتعامل معه كما كنا من قبل
        if len(lines) == 1:
            prompt = f"""
أنا بوت تتبع المشتريات. المستخدم أرسل النص التالي: "{text}"
قم باستخراج المعلومات من هذا النص. المعلومات المطلوبة هي:
1. اسم المنتج
2. سعر المنتج
3. أي ملاحظات إضافية حول المنتج (مثل الوزن أو الكمية)

أعطني النتيجة بتنسيق JSON بدون أي تفسير إضافي. استخدم المفاتيح التالية:
"product" لاسم المنتج
"price" للسعر، كرقم فقط بدون عملة أو رموز
"notes" للملاحظات

مثال للخرج:
[{{"product": "تفاح", "price": "50", "notes": "1 كيلو"}}]
            """
            response = await model.generate_content_async(prompt)
            
            # استخراج JSON من الرد
            json_str = extract_json_from_response(response.text)
            
            # تحويل JSON إلى قائمة من القواميس
            products = json.loads(json_str)
            
            # التحقق من صحة البيانات المستخرجة
            validate_products(products)
            
            return products
            
        # إذا كان لدينا أسطر متعددة، نتعامل مع كل سطر على حدة
        else:
            all_products = []
            
            # إزالة الأسطر الفارغة
            filtered_lines = [line.strip() for line in lines if line.strip()]
            
            if not filtered_lines:
                return []
                
            # نرسل جميع الأسطر في طلب واحد للتحليل
            prompt = f"""
أنا بوت تتبع المشتريات. المستخدم أرسل قائمة مشتريات متعددة كالتالي:
{text}

كل سطر يحتوي على منتج مختلف. قم باستخراج المعلومات من كل سطر. المعلومات المطلوبة هي:
1. اسم المنتج
2. سعر المنتج
3. أي ملاحظات إضافية حول المنتج (مثل الوزن أو الكمية)

أعطني النتيجة بتنسيق JSON بدون أي تفسير إضافي. استخدم المفاتيح التالية:
"product" لاسم المنتج
"price" للسعر، كرقم فقط بدون عملة أو رموز
"notes" للملاحظات

النتيجة المتوقعة هي قائمة من المنتجات، واحد لكل سطر.
مثال للخرج:
[
  {{"product": "تفاح", "price": "50", "notes": "1 كيلو"}},
  {{"product": "موز", "price": "30", "notes": "2 كيلو"}}
]
            """
            response = await model.generate_content_async(prompt)
            
            # استخراج JSON من الرد
            json_str = extract_json_from_response(response.text)
            
            # تحويل JSON إلى قائمة من القواميس
            products = json.loads(json_str)
            
            # التحقق من صحة البيانات المستخرجة
            validate_products(products)
            
            return products
            
    except Exception as e:
        logger.error(f"خطأ في تحليل النص باستخدام Gemini: {str(e)}")
        raise GeminiAPIError(f"فشل تحليل النص: {str(e)}")


def extract_json_from_response(text: str) -> str:
    """
    استخراج نص JSON من استجابة الذكاء الاصطناعي
    
    قد يقوم النموذج بتضمين تعليقات أو نص قبل/بعد JSON
    هذه الدالة تستخرج نص JSON فقط
    """
    # البحث عن أي نص بين [] أو {}
    json_pattern = r'(\[.*?\]|\{.*?\})'
    matches = re.findall(json_pattern, text, re.DOTALL)
    
    if matches:
        for match in matches:
            # محاولة تحليل JSON للتأكد من صحته
            try:
                json.loads(match)
                return match
            except:
                continue
    
    # إذا لم نجد تنسيق JSON صالح، نستخدم النص كما هو
    # ولكن نحاول تنظيفه
    cleaned_text = text.strip()
    # إذا بدأ النص بـ ``` وانتهى بـ ```، نزيل هذه العلامات
    if cleaned_text.startswith("```") and cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[3:-3].strip()
        # قد يحتوي على "json" أو "JSON" في البداية
        if cleaned_text.lower().startswith("json"):
            cleaned_text = cleaned_text[4:].strip()
    
    return cleaned_text


def validate_products(products: List[Dict[str, str]]) -> None:
    """
    التحقق من صحة المنتجات المستخرجة
    """
    if not isinstance(products, list):
        raise GeminiAPIError("النتيجة المتوقعة هي قائمة من المنتجات")
        
    for product in products:
        if not isinstance(product, dict):
            raise GeminiAPIError("كل منتج يجب أن يكون عبارة عن قاموس")
            
        if "product" not in product or not product["product"]:
            raise GeminiAPIError("كل منتج يجب أن يحتوي على حقل 'product' غير فارغ")
            
        if "price" not in product or not product["price"]:
            raise GeminiAPIError("كل منتج يجب أن يحتوي على حقل 'price' غير فارغ")
            
        # حاول تحويل السعر إلى رقم للتأكد من صحته
        try:
            float(product["price"])
        except ValueError:
            raise GeminiAPIError(f"السعر '{product['price']}' ليس رقمًا صالحًا")

# --- كود اختبار بدون واجهة ---
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    test_text = "55 رمان 44ك"
    try:
        products = analyze_products_with_gemini(test_text, api_key=api_key)
        print("النتيجة:")
        print(products)
    except Exception as e:
        print(f"خطأ: {e}") 