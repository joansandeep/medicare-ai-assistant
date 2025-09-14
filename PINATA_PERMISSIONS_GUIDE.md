# 🔑 PINATA PERMISSIONS SETUP FOR MEDICARE AI

## ✅ REQUIRED PERMISSIONS (Enable These)

For PDF upload functionality, enable these permissions:

### Files Section:
```bash
✅ pinFileToIPFS     (REQUIRED - Upload PDF files)
✅ pinList           (OPTIONAL - List uploaded files)
✅ hashMetadata      (OPTIONAL - File metadata)
✅ userPinnedDataTotal (OPTIONAL - Usage stats)
```

### NOT Needed for This Project:
```bash
❌ pinByHash         (Not needed)
❌ pinJobs           (Not needed)
❌ pinJSONToIPFS     (Not needed - we upload files, not JSON)
❌ unpin             (Not needed)
❌ addPinObject      (Not needed)
❌ getPinObject      (Not needed)
❌ listPinObjects    (Not needed)
❌ removePinObject   (Not needed)
❌ replacePinObject  (Not needed)
```

---

## 🎯 MINIMUM SETUP (Just Enable This One)

**If you want the simplest setup, just enable:**

```bash
✅ pinFileToIPFS
```

This single permission is all you need for PDF uploads to work!

---

## 🔧 HOW TO SET PERMISSIONS

### Step 1: Create API Key
```bash
1. In Pinata dashboard, go to "API Keys"
2. Click "New Key"
3. Give it a name like "Medicare-PDF-Upload"
```

### Step 2: Enable Permissions
```bash
4. In the permissions list, check:
   ✅ pinFileToIPFS (most important)
   ✅ pinList (optional but recommended)
   
5. Leave everything else unchecked
6. Click "Create Key"
```

### Step 3: Copy Credentials
```bash
7. Copy the API Key (starts with random letters/numbers)
8. Copy the API Secret (also random letters/numbers)
9. Save both safely - you won't see them again!
```

---

## 🚀 ADD TO RAILWAY

### Environment Variables:
```bash
PINATA_API_KEY=your_api_key_here
PINATA_SECRET_KEY=your_secret_key_here
```

---

## 🧪 TEST YOUR SETUP

After adding to Railway and deploying:

### Test 1: Upload a PDF
```bash
1. Go to your app chatbot page
2. Click upload button
3. Select any PDF file
4. Should see "Upload successful" message
```

### Test 2: Check Pinata Dashboard
```bash
1. Go back to pinata.cloud
2. Check "Files" section
3. Should see your uploaded PDF listed
```

### Test 3: Ask AI About PDF
```bash
1. After upload, ask: "What's in this PDF?"
2. AI should analyze and respond
3. PDF features fully working!
```

---

## ⚠️ TROUBLESHOOTING

### Upload Fails?
```bash
Problem: "Upload failed" or "403 Forbidden"

Solution:
1. Check pinFileToIPFS is enabled
2. Verify API keys are correct
3. Check Railway environment variables
4. Redeploy app after adding variables
```

### API Key Invalid?
```bash
Problem: "Invalid API key"

Solution:
1. Go back to Pinata
2. Create new API key
3. Make sure to copy BOTH API Key and Secret
4. Update Railway variables
```

### Files Not Appearing?
```bash
Problem: Upload succeeds but can't see files

Solution:
1. Enable "pinList" permission
2. Check Pinata dashboard "Files" section
3. Files should appear there automatically
```

---

## 💡 RECOMMENDED SETUP

**For best experience, enable these 2 permissions:**

```bash
✅ pinFileToIPFS     (Required for uploads)
✅ pinList           (Shows your uploaded files)
```

This gives you full PDF functionality while keeping permissions minimal and secure!

---

## 🎉 FINAL CHECK

After setup, your Pinata API key should have:
- ✅ pinFileToIPFS enabled
- ✅ Valid API Key and Secret copied
- ✅ Added to Railway environment variables
- ✅ App redeployed

**Result: PDF uploads work perfectly!** 🚀
