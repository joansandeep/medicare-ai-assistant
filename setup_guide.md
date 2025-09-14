# 🆓 Free Services Setup Guide for MediCare AI

## 🔑 API Keys (100% Free)

### 1. Groq API (Free LLM Inference)
**What you get:** 30 requests/minute, unlimited usage
1. **Visit:** [console.groq.com](https://console.groq.com)
2. **Sign up** with Google/GitHub or email
3. **Go to API Keys** section
4. **Create New API Key**
5. **Copy the key** (starts with `gsk_`)
6. **Set environment variable:** `GROQ_API_KEY=gsk_your_key_here`

### 2. OpenRouter API (Free Backup)
**What you get:** 200 requests/minute, multiple models
1. **Visit:** [openrouter.ai](https://openrouter.ai)
2. **Sign up** with Google/GitHub
3. **Go to Keys** tab
4. **Create API Key**
5. **Copy the key** (starts with `sk-or-`)
6. **Set environment variable:** `OPENROUTER_API_KEY=sk-or-your_key_here`

## 🚀 Deployment Platforms

### Option 1: Railway (Recommended for MySQL)
**What you get:** 500 hours/month, 512MB RAM, 1GB storage

#### Step-by-step Railway Setup:
1. **Visit:** [railway.app](https://railway.app)
2. **Sign up** with GitHub account
3. **Create New Project** → **Deploy from GitHub repo**
4. **Connect your repository**
5. **Add MySQL database:**
   - Click **+ New** → **Database** → **Add MySQL**
   - Wait for deployment (2-3 minutes)
   - Copy connection details from **Variables** tab

#### Railway Environment Variables:
```bash
# Database (from Railway MySQL service)
DB_HOST=containers-us-west-xxx.railway.app
DB_USER=root
DB_PASSWORD=xxxxxxxxxxxx
DB_NAME=railway
DB_PORT=7691

# API Keys
GROQ_API_KEY=gsk_your_groq_key_here
OPENROUTER_API_KEY=sk-or-your_openrouter_key_here

# App Config
SECRET_KEY=your_super_secret_key_here
RAILWAY_ENVIRONMENT=true
PORT=8080
```

### Option 2: Render.com (Great for PostgreSQL)
**What you get:** 750 hours/month, 512MB RAM

#### Step-by-step Render Setup:
1. **Visit:** [render.com](https://render.com)
2. **Sign up** with GitHub
3. **New Web Service** → **Connect Repository**
4. **Configure:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python app.py`
5. **Add PostgreSQL:**
   - **New** → **PostgreSQL** → **Free**
   - Copy connection string

#### Render Environment Variables:
```bash
# Database (PostgreSQL format)
DATABASE_URL=postgresql://user:pass@host:port/dbname
DB_HOST=host
DB_USER=user
DB_PASSWORD=password
DB_NAME=dbname

# API Keys
GROQ_API_KEY=gsk_your_groq_key_here
OPENROUTER_API_KEY=sk-or-your_openrouter_key_here

# App Config
SECRET_KEY=your_super_secret_key_here
RENDER=true
```

### Option 3: Vercel (Serverless, but limited)
**What you get:** Unlimited deployments, 100GB bandwidth

#### Vercel Setup:
1. **Visit:** [vercel.com](https://vercel.com)
2. **Import Git Repository**
3. **Add Environment Variables** in dashboard
4. **Note:** May need external database (see database options below)

## 🗄️ Free Database Options

### Option 1: Railway MySQL (with Railway deployment)
- **Included** with Railway app deployment
- **1GB storage, 100 hours/month**
- **Easy integration**

### Option 2: PlanetScale (MySQL Compatible)
**What you get:** 5GB storage, 1 billion reads/month
1. **Visit:** [planetscale.com](https://planetscale.com)
2. **Sign up** with GitHub
3. **Create Database**
4. **Create Branch** (main)
5. **Get connection string** from **Connect** button
6. **Use connection details** in your app

#### PlanetScale Connection:
```bash
DB_HOST=aws.connect.psdb.cloud
DB_USER=xxxxxxxxx
DB_PASSWORD=pscale_pw_xxxxxxxxx
DB_NAME=your_database_name
DB_SSL=true
```

### Option 3: Supabase (PostgreSQL)
**What you get:** 500MB database, 2GB bandwidth
1. **Visit:** [supabase.com](https://supabase.com)
2. **Start your project**
3. **Go to Settings** → **Database**
4. **Copy connection string**

### Option 4: Aiven (Multiple engines)
**What you get:** 1 month free trial
1. **Visit:** [aiven.io](https://aiven.io)
2. **Sign up** for free trial
3. **Create MySQL/PostgreSQL service**
4. **Use during trial period**

## 🎯 Recommended Free Stack

### Best Combination:
```
✅ Railway (App + MySQL database)
✅ Groq API (Primary LLM)
✅ OpenRouter API (Backup LLM)
✅ GitHub (Code hosting)
```

**Total Cost:** $0/month
**Setup Time:** 15-20 minutes

## 📋 Quick Setup Checklist

### Prerequisites:
- [ ] GitHub account
- [ ] Email address
- [ ] Your code pushed to GitHub

### API Keys:
- [ ] Get Groq API key from console.groq.com
- [ ] Get OpenRouter API key from openrouter.ai
- [ ] Generate secure SECRET_KEY (use online generator)

### Deployment:
- [ ] Sign up for Railway with GitHub
- [ ] Create new project from GitHub repo
- [ ] Add MySQL database service
- [ ] Set all environment variables
- [ ] Deploy and test

### Testing:
- [ ] App loads successfully
- [ ] Database connection works
- [ ] User registration/login works
- [ ] Chatbot responds to messages
- [ ] All pages load without errors

## 🔧 Environment Variables Template

Create a `.env.production` file for reference:

```bash
# Copy these to your deployment platform's environment variables

# Database Configuration
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=your_database_name
DB_PORT=3306

# API Keys (Free tiers)
GROQ_API_KEY=gsk_your_groq_api_key_here
OPENROUTER_API_KEY=sk-or-your_openrouter_key_here

# Security
SECRET_KEY=your_super_secure_random_secret_key

# Platform Detection
RAILWAY_ENVIRONMENT=true
# OR
RENDER=true
# OR 
VERCEL=true

# App Configuration
PORT=8080
HOST=0.0.0.0
DEBUG=false
```

## 🌐 Custom Domain (Optional Free)

### Free Domain Options:
1. **Freenom:** Get .tk, .ml, .ga domains free
2. **GitHub Pages:** Use your_username.github.io
3. **Subdomain:** Most platforms offer free subdomains

### Connect Custom Domain:
- **Railway:** Project Settings → Domains → Add Domain
- **Render:** Service Settings → Custom Domains
- **Vercel:** Project Settings → Domains

## 🛠️ Troubleshooting Common Issues

### Database Connection Fails:
```bash
# Check environment variables are set correctly
# Verify database service is running
# Test connection string manually
```

### App Won't Start:
```bash
# Check build logs
# Verify requirements.txt is complete
# Ensure PORT environment variable is set
```

### API Keys Not Working:
```bash
# Verify keys are copied correctly
# Check API quotas/limits
# Test keys with curl/postman first
```

### Memory/Resource Limits:
```bash
# Optimize imports
# Use lazy loading for large models
# Implement caching
# Monitor usage dashboards
```

## 📞 Support Resources

### Platform Support:
- **Railway:** [Discord](https://discord.gg/railway) + [Docs](https://docs.railway.app)
- **Render:** [Documentation](https://render.com/docs) + Support chat
- **Vercel:** [Documentation](https://vercel.com/docs) + [Discord](https://vercel.com/discord)

### API Support:
- **Groq:** [Documentation](https://console.groq.com/docs)
- **OpenRouter:** [Documentation](https://openrouter.ai/docs)

## 🎉 Next Steps After Deployment

1. **Test all features** thoroughly
2. **Set up monitoring** (platform dashboards)
3. **Configure custom domain** (optional)
4. **Add SSL certificate** (usually automatic)
5. **Set up backup strategy** for database
6. **Monitor API usage** to stay within limits
7. **Implement caching** for better performance

---

**Total Setup Cost:** $0
**Monthly Cost:** $0 (within free limits)
**Deployment Time:** ~20 minutes
**Maintenance:** Minimal
