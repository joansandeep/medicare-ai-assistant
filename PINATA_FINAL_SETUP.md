# 🔑 PINATA PERMISSIONS - WHAT TO ENABLE

## ❌ DO NOT ENABLE ADMIN
**Admin permissions are for account management, not file uploads!**

---

## ✅ ENABLE ONLY THESE PERMISSIONS

### For PDF Upload Functionality:
```bash
✅ pinFileToIPFS     (REQUIRED - Upload PDF files)
✅ pinList           (RECOMMENDED - See your uploaded files)
```

### Leave Everything Else UNCHECKED:
```bash
❌ Admin permissions     (Not needed - account management only)
❌ hashMetadata         (Optional - file metadata, not essential)
❌ pinByHash            (Not needed for direct uploads)
❌ pinJobs              (Not needed for simple uploads)
❌ pinJSONToIPFS        (Not needed - we upload PDFs, not JSON)
❌ unpin                (Not needed - we don't delete files)
❌ All Pin Objects APIs (Not needed for basic file uploads)
❌ userPinnedDataTotal  (Optional - usage stats only)
```

---

## 🎯 MINIMAL SETUP (RECOMMENDED)

**For your MediCare AI app, just enable:**

```bash
✅ pinFileToIPFS
```

**That's it!** This single permission is all you need for PDF uploads.

---

## 🔧 EXACT SETUP STEPS

### Step 1: Create API Key
```bash
1. In Pinata dashboard → "API Keys"
2. Click "New Key" 
3. Name it: "Medicare-PDF-Upload"
```

### Step 2: Set Permissions
```bash
4. Under "Files" section:
   ✅ Check ONLY "pinFileToIPFS"
   ❌ Leave everything else unchecked
   
5. Ignore all other sections (Groups, Gateways, etc.)
6. Click "Create Key"
```

### Step 3: Copy Credentials
```bash
7. Copy the API Key (long random string)
8. Copy the API Secret (another long random string)
9. Save both - you won't see them again!
```

---

## 🚀 ADD TO RAILWAY

### Environment Variables:
```bash
PINATA_API_KEY=your_copied_api_key_here
PINATA_SECRET_KEY=your_copied_secret_here
```

---

## 💡 WHY NO ADMIN?

**Admin permissions control:**
- Account billing settings
- Team member management  
- Account-wide configurations
- Security settings

**Your app only needs:**
- File upload capability (`pinFileToIPFS`)
- That's it!

**Admin permissions would:**
- ❌ Not help with file uploads
- ❌ Create unnecessary security risks
- ❌ Give broader access than needed

---

## 🧪 TEST YOUR SETUP

After creating the API key with just `pinFileToIPFS`:

### 1. Add to Railway:
```bash
PINATA_API_KEY=your_key
PINATA_SECRET_KEY=your_secret
```

### 2. Redeploy your app

### 3. Test PDF upload:
```bash
1. Go to chatbot page
2. Click upload button
3. Select a PDF file
4. Should see "Upload successful via pinata"
```

### 4. Check Pinata dashboard:
```bash
1. Go back to pinata.cloud
2. Check "Files" section
3. Your uploaded PDF should appear there
```

---

## ✅ FINAL CHECKLIST

Before testing:
- [ ] Created Pinata API key
- [ ] Enabled ONLY "pinFileToIPFS" permission
- [ ] Did NOT enable admin permissions
- [ ] Copied both API Key and Secret
- [ ] Added to Railway environment variables
- [ ] Redeployed the app

**Result: PDF uploads work perfectly with minimal permissions!** 🎉

---

## 🎯 SECURITY BEST PRACTICE

**Principle of Least Privilege:**
- Only enable the minimum permissions needed
- `pinFileToIPFS` is all you need for PDF uploads
- Admin permissions are unnecessary and create security risks

**Your setup is now secure and functional!** 🛡️
