# EduParser - Pakistani Educational Document Parser

## 🆕 Now Using Google Gemini (FREE!)

EduParser now uses **Google Gemini API** instead of OpenAI. Benefits:
- ✅ **100% FREE** - No credit card required
- ✅ **No quota limits** for free tier (generous limits: 1500 requests/day)
- ✅ **Multimodal** - Handles images and PDFs
- ✅ **Fast & accurate** - Uses gemini-2.5-flash model

## 🔑 Get Your Free Gemini API Key

1. Visit: **https://aistudio.google.com/apikey**
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the API key
5. Paste it into the EduParser sidebar

**That's it! No credit card, no billing, completely free!**

## 📦 Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run main.py
```

## 🚀 Features

- **Multi-format Support**: JPG, PNG, PDF
- **Merged Document Detection**: Automatically separates multiple certificates in one file
- **Name Extraction**: Extracts person's name from documents
- **Smart Date Calculation**: Calculates start/end dates based on exam year
- **Board Standardization**: Formats board names correctly for Oracle
- **Excel Export**: Ready-to-import format for Oracle systems

## 📄 Supported Documents

- Matriculation / SSC / O-Level
- Intermediate / HSSC / FSc / FA / A-Level
- Bachelor's Degrees (BS, BA, B.Com, BSc, BBA)
- Master's Degrees (MS, MSc, MBA, MA)
- Associate's Degrees
- Diplomas (DAE)

## 💡 Usage

1. Enter your Gemini API key in the sidebar
2. Enter the Person Number
3. Upload educational document images or PDFs
4. Click **Process Documents**
5. Download the Excel file

## 🔧 Tech Stack

- **Python 3.9+**
- **Streamlit** - UI framework
- **Google Gemini** - AI model (gemini-2.5-flash)
- **Pandas** - Data processing
- **OpenPyxl** - Excel export
- **PyMuPDF** - PDF processing
- **Pillow** - Image handling

## 📊 Output Format

Excel file with columns:
- Person Number
- Name
- Degree Start Date
- Degree End Date
- Average Grade
- Education Level (Oracle code)
- Degree Name
- Major
- School
- Percentage
- Graduated
- Country Code
- Source File

## 🎯 Business Logic

### Date Calculation
- **Matric/SSC**: End: 7/7/[Year], Start: 5/5/[Year-2]
- **Inter/HSSC**: End: 7/7/[Year], Start: 8/8/[Year-2]
- **Bachelor's**: End: 6/6/[Year], Start: 9/9/[Year-4]
- **Master's**: End: 6/6/[Year], Start: 9/9/[Year-2]

### Education Level Codes
- 32: Matriculation / SSC
- 30: Intermediate / HSSC / FSc / FA
- 27: Bachelor's
- 26: Master's
- 28: Associate's Degree
- 33: Diploma (DAE)

## 🔄 Merged Documents

The app automatically detects and separates multiple certificates in one file:
- Upload: `merged.jpg` (contains Matric + Inter + Bachelor's)
- Output: 3 separate rows in Excel
- Each row labeled: "merged.jpg (Doc 1/3)", "merged.jpg (Doc 2/3)", etc.

## 📝 License

MIT License - Free to use and modify

---

**Made with ❤️ for Pakistani Education System**
