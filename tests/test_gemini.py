import sys
import os
import asyncio

# إضافة المسار الجذري للمشروع إلى sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.gemini import analyze_products_with_gemini

async def main():
    try:
        text = "55 رمان 44ك"
        print(f"تحليل النص: {text}")
        result = await analyze_products_with_gemini(text)
        print("النتيجة:")
        print(result)
    except Exception as e:
        print(f"حدث خطأ: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 