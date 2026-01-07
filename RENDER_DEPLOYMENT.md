# Render Deployment Guide for Education Loader

## Prerequisites
- GitHub repository with your code (can be private)
- Render account (sign up at https://render.com)
- Groq API key

## Deployment Steps

### 1. Push Configuration Files to GitHub
```bash
git add render.yaml .streamlit/config.toml
git commit -m "Add Render deployment configuration"
git push origin main
```

### 2. Deploy on Render

1. **Sign up/Login to Render**
   - Go to https://render.com
   - Sign up or login with your GitHub account

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub account (if not already connected)
   - Select your `Education_Loader` repository (private repos are supported on free tier!)

3. **Configure the Service**
   - **Name**: education-loader (or any name you prefer)
   - **Region**: Choose closest to your users
   - **Branch**: main (or your default branch)
   - **Runtime**: Python 3
   - Render will auto-detect the `render.yaml` file and configure everything

4. **Add Environment Variables**
   - In the service dashboard, go to "Environment" tab
   - Add your environment variable:
     - Key: `GROQ_API_KEY`
     - Value: [Your Groq API Key]
   - Click "Save Changes"

5. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your app
   - First deployment takes 3-5 minutes

### 3. Access Your App
- Once deployed, you'll get a URL like: `https://education-loader.onrender.com`
- Your app will be live and accessible!

## Important Notes

### Free Tier Limitations
- Service spins down after 15 minutes of inactivity
- First request after inactivity takes 30-60 seconds (cold start)
- 750 hours/month free

### Environment Variables in Code
Make sure your [main.py](main.py) reads the API key from environment:
```python
import os
api_key = os.getenv("GROQ_API_KEY") or st.text_input("Enter Groq API Key", type="password")
```

### Auto-Deployment
- Every push to your main branch automatically redeploys
- Takes 2-3 minutes per deployment

### Troubleshooting

**Build Fails?**
- Check that [requirements.txt](requirements.txt) has all dependencies
- View build logs in Render dashboard

**App Won't Start?**
- Check runtime logs in Render dashboard
- Verify GROQ_API_KEY is set correctly

**Port Issues?**
- Render automatically sets $PORT environment variable
- Our config uses `--server.port=$PORT` to handle this

### Cost-Free Alternatives If Free Tier Insufficient
- Upgrade to Render paid plan ($7/month for always-on service)
- Railway.app ($5/month credit)
- Fly.io (generous free tier)

## Testing Locally Before Deployment
```bash
streamlit run main.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
```

## Support
- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
