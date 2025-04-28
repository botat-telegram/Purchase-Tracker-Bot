# بوت تتبع المشتريات 🛒

بوت تيليجرام لتتبع المشتريات وتسجيلها في Google Sheets. يمكنك إضافة المنتجات وأسعارها وملاحظات إضافية بسهولة.

## المميزات 🌟

- إضافة منتج واحد مع سعره (مثل: كولا ٢٣)
- إضافة قائمة منتجات مع أسعارها (كل منتج في سطر)
- إضافة اسم منتج فقط والبوت سيطلب السعر
- دعم الأرقام العربية والإنجليزية
- تخزين البيانات في Google Sheets
- إمكانية إضافة ملاحظات لكل منتج (اختياري)

## المتطلبات 📋

- Python 3.7 أو أحدث
- حساب Google Cloud مع تفعيل Google Sheets API
- بوت تيليجرام (يمكن إنشاؤه عبر [@BotFather](https://t.me/BotFather))

## التثبيت ⚙️

1. استنساخ المشروع:
```bash
git clone https://github.com/yourusername/telegram_sheets_bot.git
cd telegram_sheets_bot
```

2. تثبيت المتطلبات:
```bash
pip install -r requirements.txt
```

3. إعداد الملفات:
   - إنشاء ملف `.env` وإضافة توكن البوت:
     ```
     TELEGRAM_TOKEN=your_bot_token_here
     ```
   - وضع ملف `credentials.json` من Google Cloud في المجلد الرئيسي
   - إنشاء ملف Google Sheets باسم "مشترياتي"

## التشغيل 🚀

```bash
python run.py
```

## هيكل المشروع 📁

```
telegram_sheets_bot/
├── src/             # الكود الرئيسي
│   ├── config.py    # الإعدادات
│   └── main.py      # نقطة البداية
├── handlers/        # معالجات البوت
│   ├── commands.py  # معالجات الأوامر
│   └── conversation.py  # معالجات المحادثة
├── database/        # التعامل مع قاعدة البيانات
│   └── sheets.py    # التعامل مع Google Sheets
├── utils/           # أدوات مساعدة
│   └── number_converter.py  # تحويل الأرقام العربية
├── .env            # متغيرات البيئة
├── credentials.json # اعتمادات Google
└── requirements.txt # المكتبات المطلوبة
```

## المساهمة 🤝

نرحب بمساهماتكم! يرجى:
1. عمل Fork للمشروع
2. إنشاء فرع جديد (`git checkout -b feature/amazing_feature`)
3. عمل Commit للتغييرات (`git commit -m 'إضافة ميزة رائعة'`)
4. رفع التغييرات (`git push origin feature/amazing_feature`)
5. فتح طلب Pull Request

## الترخيص 📄

هذا المشروع مرخص تحت رخصة MIT. راجع ملف `LICENSE` للمزيد من المعلومات.

## الدعم 💬

إذا واجهت أي مشكلة أو لديك اقتراح، يرجى فتح Issue جديد في صفحة المشروع.





















# Purchase Tracker Bot 🛒

A Telegram bot that helps you track your purchases by logging them into Google Sheets. Easily add products, prices, and optional notes.

## Features 🌟

- Add single product with price (e.g., "cola 23")
- Add multiple products with prices (one per line)
- Add product name only and bot will ask for price
- Support for both Arabic and English numbers
- Store data in Google Sheets
- Add optional notes for each product

## Requirements 📋

- Python 3.7 or newer
- Google Cloud account with Google Sheets API enabled
- Telegram bot (create one via [@BotFather](https://t.me/BotFather))

## Installation ⚙️

1. Clone the repository:
```bash
git clone https://github.com/yourusername/telegram_sheets_bot.git
cd telegram_sheets_bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables in `.env`:
```
BOT_TOKEN=your_telegram_bot_token
```

4. Place your Google Sheets API credentials in `credentials.json`

5. Create a Google Sheet named "My Purchases"

## Running the Bot 🚀

```bash
python run.py
```

## Project Structure 📁

```
telegram_sheets_bot/
├── src/             # Main code
│   ├── config.py    # Configuration
│   └── main.py      # Entry point
├── handlers/        # Bot handlers
│   ├── commands.py  # Command handlers
│   └── conversation.py  # Conversation handlers
├── database/        # Database interactions
│   └── sheets.py    # Google Sheets integration
├── utils/           # Utility functions
│   └── number_converter.py  # Number conversion
├── .env            # Environment variables
├── credentials.json # Google Sheets API credentials
└── requirements.txt # Python dependencies
```

## Contributing 🤝

Contributions are welcome! Please:
1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing_feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push your changes (`git push origin feature/amazing_feature`)
5. Open a Pull Request

## License 📄

This project is licensed under the MIT License. See the `LICENSE` file for more information.

## Support 💬

If you encounter any issues or have suggestions, please open a new Issue on the project page.
