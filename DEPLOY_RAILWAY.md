# Deploying GISL Schools to Railway

## One-time setup (5 minutes)

### 1. Push code to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/gisl-schools.git
git push -u origin main
```

### 2. Create Railway project
1. Go to https://railway.app and sign up / log in
2. Click **New Project → Deploy from GitHub repo**
3. Select your `gisl-schools` repository
4. Railway will auto-detect Python and deploy using `railway.toml`

### 3. Add a Persistent Volume (CRITICAL — keeps your database safe)
Without this, all data is lost on every redeploy.

1. In your Railway project, click your service
2. Go to **Settings → Volumes**
3. Click **Add Volume**
4. Set mount path to: `/data`
5. Click **Create**

### 4. Set environment variable
1. Go to **Variables** tab in your service
2. Add: `DATA_DIR` = `/data`
3. Railway will restart the service automatically

### 5. Get your URL
Railway gives you a public URL like `https://gisl-schools-production.up.railway.app`
Share this with staff and parents.

---

## Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `PORT` | (set automatically by Railway) | HTTP port |
| `DATA_DIR` | `/data` | Where database and uploads are stored |
| `ENVIRONMENT` | `production` | Enables production safety checks |
| `ALLOWED_ORIGIN` | `https://your-app.up.railway.app` | Restricts browser access to your real domain |
| `APP_URL` | `https://your-app.up.railway.app` | Public base URL for links and callbacks |
| `INITIAL_ADMIN_NAME` | `School Admin` | Name of first admin |
| `INITIAL_ADMIN_EMAIL` | your real admin email | Secure first admin login |
| `INITIAL_ADMIN_PASSWORD` | strong password | Secure first admin password |
| `ALLOW_DEFAULT_ADMIN` | `false` | Prevents insecure demo admin in production |
| `ALLOW_DESTRUCTIVE_MIGRATIONS` | `false` | Prevents destructive schema repair unless explicitly allowed |

---

## First Login (first run)

Use the `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` values you configured.

⚠️ The app is now designed to avoid creating an insecure default admin automatically in production.

---

## Costs
- Railway free trial: $5 credit (enough for ~1 month)
- After trial: ~$5–10/month depending on usage
- Volume storage: ~$0.25/GB/month

---

## Updating the app
```bash
git add .
git commit -m "Update"
git push
```
Railway redeploys automatically. Your data on `/data` is untouched.

---

## Recommended verification after deploy

1. Open `/health` and confirm the app reports `status: ok`
2. Sign in with your configured admin account
3. Go to **Settings** and review:
   - Production readiness
   - Backup list
4. Create a manual backup after initial setup
5. Test SMTP / Paystack / WhatsApp integrations before going live
