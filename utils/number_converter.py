"""
تحويل الأرقام العربية إلى إنجليزية
"""

def convert_to_english_numbers(text: str) -> str:
    """
    تحويل الأرقام العربية إلى إنجليزية في النص
    """
    arabic_numbers = {'٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
                     '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
                     '.': '.', '٫': '.'}
    
    result = ''
    for char in text:
        result += arabic_numbers.get(char, char)
    
    return result
