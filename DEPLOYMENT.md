# 🚀 Deploy EduParser to Streamlit Cloud

## Quick Deploy (5 minutes)

### Step 1: Prerequisites
✅ GitHub repository: https://github.com/moizjokhio/LoaderApp.git
✅ Google Gemini API Key: Get free at https://aistudio.google.com/apikey

### Step 2: Deploy to Streamlit Cloud

1. **Go to Streamlit Cloud**
   - Visit: https://share.streamlit.io/
   - Sign in with GitHub

2. **Create New App**
   - Click "New app"
   - Repository: `moizjokhio/LoaderApp`
   - Branch: `main`
   - Main file path: `main.py`
   - Click "Deploy"

3. **Wait for Deployment**
   - Takes 2-3 minutes
   - App will automatically install dependencies from requirements.txt

4. **Your App is Live! 🎉**
   - You'll get a URL like: `https://loaderapp-xxxxx.streamlit.app`
   - Share this URL with users

### Step 3: Use the App

1. **Enter API Key**
   - Open the deployed app
   - Enter Google Gemini API key in sidebar
   - Or share the key with users

2. **Process Documents**
   - Upload educational documents (JPG, PNG, PDF)
   - Click "Process Documents"
   - Download Excel file

3. **Use Spreadsheet Loader**
   - Scroll to bottom section
   - Upload employee file + education file
   - Download merged Oracle loader file

## Alternative: Deploy Locally

If you want to run on your own server:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run main.py
```

The app will be available at: http://localhost:8501

## Environment Variables (Optional)

For production, you can set default API key:

**Streamlit Cloud:**
- Go to App Settings → Secrets
- Add: `GEMINI_API_KEY = "your-api-key-here"`

**Local:**
- Create `.env` file
- Add: `GEMINI_API_KEY=your-api-key-here`

## Files Pushed to GitHub

✅ Essential files only:
- `main.py` - Main application
- `requirements.txt` - Python dependencies
- `README.md` - Documentation
- `GET_API_KEY.md` - API key guide
- `SPREADSHEET_LOADER_GUIDE.txt` - Feature guide
- `sample_employees.xlsx` - Sample employee data
- `sample_education.xlsx` - Sample education data
- `.gitignore` - Excludes test/temp files

❌ Excluded:
- Virtual environment (.venv/)
- Test scripts
- Document samples
- Output Excel files
- __pycache__

## Update the App

To push updates:

```bash
git add .
git commit -m "Update message"
git push origin main
```

Streamlit Cloud will automatically redeploy!

## Troubleshooting

**Issue: App won't start**
- Check requirements.txt has correct versions
- Check main.py has no syntax errors

**Issue: Can't process documents**
- Verify Gemini API key is valid
- Check internet connection
- Ensure free tier limits not exceeded (1500/day)

**Issue: Merge not working**
- Verify employee file has: CNIC, EMPLOYEE_NUMBER, FULL_NAME
- Check education file has: Name column
- Names must match (case-insensitive)

## Support

Repository: https://github.com/moizjokhio/LoaderApp
Issues: https://github.com/moizjokhio/LoaderApp/issues

---

**Your app is now live and ready to use! 🎊**
