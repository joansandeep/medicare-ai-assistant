# MediCare AI Assistant - Free Deployment Guide

## 🚀 Free Deployment Options

### Option 1: Railway (Recommended)
1. **Sign up** at [railway.app](https://railway.app) with GitHub
2. **Create new project** → Deploy from GitHub repo
3. **Add MySQL database** from Railway's database tab
4. **Set environment variables**:
   ```
   DB_HOST=<railway_mysql_host>
   DB_USER=<railway_mysql_user>
   DB_PASSWORD=<railway_mysql_password>
   DB_NAME=<railway_mysql_database>
   GROQ_API_KEY=gsk_your_groq_key_here
   OPENROUTER_API_KEY=sk-or-your_openrouter_key_here
   SECRET_KEY=your_secure_random_secret_key
   RAILWAY_ENVIRONMENT=true
   ```
5. **Deploy** - Railway auto-deploys on git push

### Option 2: Render.com
1. **Sign up** at [render.com](https://render.com) with GitHub
2. **Create Web Service** → Connect GitHub repo
3. **Add PostgreSQL database** (free tier)
4. **Set environment variables** (same as above but use PostgreSQL)
5. **Deploy** - Auto-deploys from main branch

### Option 3: Heroku (Limited Free Tier)
1. **Install Heroku CLI**
2. **Login**: `heroku login`
3. **Create app**: `heroku create your-app-name`
4. **Add database**: `heroku addons:create jawsdb:kitefin` (MySQL)
5. **Set config vars**: `heroku config:set GROQ_API_KEY=your_key`
6. **Deploy**: `git push heroku main`

## 🗄️ Free Database Options

### Railway MySQL (Recommended)
- 1GB storage
- 100 hours/month runtime
- Easy integration

### PlanetScale (MySQL Compatible)
- 5GB storage
- 1 billion row reads/month
- Serverless MySQL

### Supabase (PostgreSQL)
- 500MB database
- 2GB bandwidth
- Real-time features

### Aiven (Multiple engines)
- 1 month free trial
- MySQL, PostgreSQL, Redis

## 🔧 Pre-Deployment Setup

1. **Push code to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/medicare-ai.git
   git push -u origin main
   ```

2. **Get free API keys**:
   - Groq: [console.groq.com](https://console.groq.com) (Free tier: 30 requests/minute)
   - OpenRouter: [openrouter.ai](https://openrouter.ai) (Free tier: 200 requests/minute)

3. **Prepare RAG data** (optional):
   - Upload `Website/data/` folder to your repo
   - Or disable RAG features for simpler deployment

## 🌐 Domain Setup (Optional)

### Free Custom Domain Options:
- **Freenom**: .tk, .ml, .ga domains
- **GitHub Pages**: username.github.io
- **Netlify**: Custom subdomain

### Connect Custom Domain:
1. **Railway**: Project Settings → Domains → Add Custom Domain
2. **Render**: Service Settings → Custom Domains
3. **Heroku**: `heroku domains:add yourdomain.com`

## 📊 Monitoring & Logs

### Railway:
- Dashboard → Deployments → View Logs
- Metrics tab for performance monitoring

### Render:
- Service Dashboard → Logs
- Events tab for deployment history

### Heroku:
- `heroku logs --tail`
- Dashboard for metrics

## 🔒 Security Best Practices

1. **Never commit .env files**
2. **Use strong SECRET_KEY**
3. **Set up environment variables properly**
4. **Enable HTTPS** (auto on most platforms)
5. **Regular security updates**

## 💡 Cost Optimization

1. **Use Railway for backend** (better MySQL support)
2. **Host static files on Netlify/Vercel** (faster CDN)
3. **Implement caching** (Redis on Railway)
4. **Monitor usage** to stay within free limits

## 🆘 Troubleshooting

### Common Issues:
- **Database connection**: Check environment variables
- **Port binding**: Ensure PORT environment variable is set
- **Dependencies**: Check requirements.txt is complete
- **Memory limits**: Optimize imports and data loading

### Support:
- Railway: [Discord community](https://discord.gg/railway)
- Render: [Documentation](https://render.com/docs)
- Heroku: [Dev Center](https://devcenter.heroku.com/)
