# CS2 Market Watcher - Deployment Guide

This guide covers various deployment options for the CS2 Market Watcher application, ranging from free to low-cost solutions.

## Application Requirements

Your app needs:
- **Docker support** (multi-container orchestration)
- **Postgres** database
- **~512MB-1GB RAM** minimum (Playwright browser + services)
- **Persistent storage** for Postgres data
- **24/7 uptime** (worker must run continuously)

## Quick Comparison

| Platform | Cost | RAM | Setup Difficulty | Playwright Support | Best For |
|----------|------|-----|------------------|-------------------|----------|
| **DigitalOcean Droplet** | $6/mo | 1GB | ⭐ Easy | ✅ Yes | Simplicity + Reliability |
| **Oracle Cloud Free** | FREE | 24GB (ARM) | ⭐⭐⭐ Hard | ✅ Yes | Free + Powerful |
| **Fly.io** | FREE | 768MB | ⭐⭐ Medium | ⚠️ Tight | Free + Easy |
| **Railway** | $5-10/mo | Variable | ⭐ Easy | ✅ Yes | Auto-deploy + Dashboard |
| **Render Free** | FREE | 512MB | ⭐ Easy | ❌ Sleeps | Not suitable (worker) |

---

## Option 1: DigitalOcean Droplet ($6/month) 🏆 RECOMMENDED

**Best for:** Developers who want it "just working" with minimal hassle.

### What You Get
- 1GB RAM, 25GB SSD, 1 vCPU
- Root access, full Docker support
- Flat $6/month pricing (no surprises)
- Simple, predictable environment

### Setup Steps

**1. Create Droplet**
```bash
# On DigitalOcean dashboard:
# - Choose Ubuntu 22.04 LTS
# - Select $6/month (1GB RAM) plan
# - Add your SSH key
# - Create droplet
```

**2. SSH into server**
```bash
ssh root@your-droplet-ip
```

**3. Install Docker**
```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

**4. Clone and configure your app**
```bash
# Clone repository
git clone https://github.com/yourusername/cs2bot.git
cd cs2bot

# Create .env file
nano .env
# Paste your environment variables (see .env.example)
# Ctrl+X, Y, Enter to save

# Important: Update these in .env:
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID
```

**5. Start services**
```bash
# Start all services in background
docker compose up -d

# View logs
docker compose logs -f worker

# Check status
docker compose ps
```

**6. Set up database**
```bash
# Run migrations
docker compose exec -T postgres psql -U steam -d steam < migrations/001_init.sql
```

**7. Configure firewall (optional but recommended)**
```bash
ufw allow 22/tcp    # SSH
ufw allow 8000/tcp  # API (if you want external access)
ufw enable
```

### Monitoring & Maintenance
```bash
# View worker logs
docker compose logs -f worker

# Restart services
docker compose restart

# Update code
git pull
docker compose up -d --build

# Stop everything
docker compose down
```

**Cost:** $6/month flat

---

## Option 2: Oracle Cloud Free Tier (Forever Free) 💰

**Best for:** Developers who want powerful free hosting and don't mind complex setup.

### What You Get
- **ARM instances:** 4x VMs with 24GB RAM total (or 2x AMD with 1GB each)
- 200GB storage
- **Forever free** (not a trial)
- Full root access

### Setup Steps

**1. Sign up for Oracle Cloud**
- Visit https://cloud.oracle.com/free
- Complete registration (requires credit card for verification, NOT charged)
- Choose home region (can't change later)

**2. Create Compute Instance**
```
# In Oracle Cloud Console:
1. Compute > Instances > Create Instance
2. Image: Ubuntu 22.04 (Minimal)
3. Shape: Ampere (ARM) - VM.Standard.A1.Flex
4. OCPU: 2, RAM: 12GB (adjust as needed, max 24GB free total)
5. Add your SSH key
6. Create
```

**3. Configure VCN (Virtual Cloud Network)**
```
# Add ingress rules:
1. Networking > Virtual Cloud Networks
2. Select your VCN > Security Lists > Default Security List
3. Add Ingress Rules:
   - Port 22 (SSH)
   - Port 8000 (API, optional)
```

**4. SSH and install Docker**
```bash
ssh ubuntu@your-instance-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo apt install -y docker-compose-plugin

# Logout and login to apply docker group
exit
ssh ubuntu@your-instance-ip
```

**5. Deploy app (same as DigitalOcean steps 4-6)**
```bash
git clone https://github.com/yourusername/cs2bot.git
cd cs2bot
nano .env  # Add your config
docker compose up -d
docker compose exec -T postgres psql -U steam -d steam < migrations/001_init.sql
```

**6. Configure instance firewall**
```bash
# Oracle Cloud has both cloud firewall + instance firewall
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save
```

**Cost:** $0/month (forever free)

**Note:** ARM architecture is well-supported by Docker, Playwright, and all dependencies.

---

## Option 3: Fly.io (Free Tier) 🚀

**Best for:** Free hosting with easy deployment, if you can fit in 768MB RAM.

### What You Get
- 3x free VMs (256MB RAM each = 768MB total)
- 3GB persistent volumes
- Free Postgres (shared CPU)
- Auto-scaling and deployments

### Setup Steps

**1. Install Fly CLI**
```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Login
fly auth login
```

**2. Create Fly.io configuration**

Create `fly.toml` in your project root:
```toml
app = "cs2bot"
primary_region = "sjc"

[build]
  dockerfile = "Dockerfile"

[env]
  STEAM_CURRENCY_ID = "1"
  FLOAT_API_TIMEOUT = "30"
  POLL_INTERVAL_S = "10"
  COMBINED_FEE_RATE = "0.15"
  COMBINED_FEE_MIN_CENTS = "1"
  ADMIN_DEFAULT_MIN_PROFIT_USD = "0.0"

[[services]]
  internal_port = 8000
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

[processes]
  api = "uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
  worker = "python -m src.worker.main"
```

**3. Create Postgres**
```bash
# Create Postgres
fly postgres create --name cs2bot-db --region sjc --vm-size shared-cpu-1x --volume-size 1

# Attach to app
fly postgres attach cs2bot-db
```

**4. Set secrets**
```bash
fly secrets set TELEGRAM_BOT_TOKEN=your-token
fly secrets set TELEGRAM_CHAT_ID=your-chat-id
```

**5. Deploy**
```bash
fly launch --no-deploy  # Configure app
fly deploy              # Deploy
```

**6. Run migrations**
```bash
fly ssh console
# Inside the VM:
psql $DATABASE_URL -f migrations/001_init.sql
exit
```

**7. Scale services**
```bash
# Run 1 API instance and 1 worker instance
fly scale count api=1 worker=1
```

**Cost:** $0/month (free tier)

**Limitations:**
- Tight memory (256MB per VM)
- Playwright might be slow
- May need to optimize/reduce browser count

---

## Option 4: Railway ($5-10/month) 🎨

**Best for:** Auto-deployment with nice UI, willing to pay for convenience.

### What You Get
- Usage-based pricing (~$5-10/month for your app)
- GitHub auto-deploy
- 1-click Postgres addon
- Beautiful dashboard

### Setup Steps

**1. Sign up**
- Visit https://railway.app
- Connect GitHub account

**2. Create new project**
```
1. New Project > Deploy from GitHub repo
2. Select your cs2bot repository
3. Railway auto-detects Docker
```

**3. Add services**
```
1. Add Postgres: New > Database > PostgreSQL
2. Railway auto-injects DATABASE_URL
```

**4. Set environment variables**
```
# In Railway dashboard > Variables:
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_ID=your-chat-id
STEAM_CURRENCY_ID=1
FLOAT_API_TIMEOUT=30
POLL_INTERVAL_S=10
COMBINED_FEE_RATE=0.15
COMBINED_FEE_MIN_CENTS=1
```

**5. Configure services**
```
# Create railway.json in project root:
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE"
  }
}
```

**6. Split API and Worker (optional)**

Railway can run multiple services from one repo:
```
# Create railway.toml:
[[services]]
name = "api"
command = "uvicorn src.api.main:app --host 0.0.0.0 --port 8000"

[[services]]
name = "worker"
command = "python -m src.worker.main"
```

**7. Deploy**
- Push to GitHub → Railway auto-deploys
- View logs in dashboard

**Cost:** ~$5-10/month (usage-based)

---

## Option 5: Render (NOT Recommended)

**Why not:**
- Free tier **sleeps after 15 minutes of inactivity**
- Worker needs 24/7 uptime
- Would need paid plan ($7/month) which is worse than DigitalOcean

**Only use if:** You're okay with paid tier ($7/month) and want GitHub auto-deploy.

---

## Resource Estimates

Based on your app's requirements:

```
Service    | RAM Usage | Notes
-----------|-----------|----------------------------------
Postgres   | 100-150MB | Minimal with small dataset
API        | 100-150MB | FastAPI + dependencies
Worker     | 300-500MB | Playwright browser + scraping
-----------|-----------|----------------------------------
TOTAL      | 500-800MB | Minimum recommended: 1GB
```

**Playwright Notes:**
- Chromium headless: ~200-300MB per instance
- Your app runs 1 browser instance at a time
- Rate limiting (0.25 RPS) keeps memory stable

---

## Recommended Setup by Budget

### $0/month (Free)
**Oracle Cloud Free Tier (ARM)**
- Most powerful free option
- 12-24GB RAM available
- Forever free
- More complex setup

### $5-6/month (Minimal)
**DigitalOcean $6/month Droplet**
- Simplest setup
- Reliable and fast
- Predictable cost
- Best bang-for-buck

### $5-10/month (Convenience)
**Railway**
- Auto-deploy from GitHub
- Nice dashboard
- Easy monitoring
- Pay-as-you-go

---

## Post-Deployment Checklist

After deploying to any platform:

1. **Run database migrations**
   ```bash
   psql $DATABASE_URL -f migrations/001_init.sql
   psql $DATABASE_URL -f migrations/002_add_cascade_to_inspect_history.sql
   psql $DATABASE_URL -f migrations/003_add_worker_settings.sql
   ```

2. **Verify services are running**
   ```bash
   # Check API
   curl http://your-host:8000/health

   # Check logs
   docker compose logs -f worker  # Docker deployments
   fly logs                        # Fly.io
   # or check platform dashboard
   ```

3. **Create a test watch**
   ```bash
   # Via API
   curl -X POST http://your-host:8000/watch \
     -H "Content-Type: application/json" \
     -d '{
       "appid": 730,
       "market_hash_name": "AK-47 | Redline (Field-Tested)",
       "url": "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29",
       "rules": {
         "float_min": 0.15,
         "float_max": 0.38,
         "target_resale_usd": 10.0,
         "min_profit_usd": 1.0
       }
     }'

   # Or visit http://your-host:8000/admin/watches
   ```

4. **Monitor for errors**
   - Watch logs for Playwright errors
   - Check CSFloat scraping is working
   - Verify Telegram alerts are sent

5. **Set up monitoring (optional)**
   - UptimeRobot (free) for health check monitoring
   - Sentry (free tier) for error tracking

---

## Troubleshooting

### Playwright Issues
```bash
# If browser fails to launch:
# - Check available RAM (need 512MB+ free)
# - Verify chromium installed: docker compose exec worker playwright --version
# - Check logs: docker compose logs worker | grep -i playwright
```

### Database Connection Issues
```bash
# Verify DATABASE_URL is correct
docker compose exec worker env | grep DATABASE_URL

# Test connection
docker compose exec postgres psql -U steam -d steam -c "SELECT 1"
```

### Worker Not Processing
```bash
# Check worker is running
docker compose ps worker

# Check database connection
docker compose exec postgres psql -U steam -d steam -c "SELECT * FROM worker_settings"

# Enable worker if paused
# Visit http://your-host:8000/admin/watches and click "Start Worker"
```

### CSFloat Rate Limiting
```bash
# If you see "inspect attempt failed" errors:
# - Current rate: 0.25 RPS (1 req every 4 seconds)
# - Reduce in src/worker/main.py if needed
# - Check inspect cache is working (InspectHistory table)
```

---

## Cost Optimization Tips

1. **Use inspect caching** - Already implemented via `InspectHistory` table
2. **Limit watches** - Each watch polls Steam every ~10 seconds
3. **Increase POLL_INTERVAL_S** - Reduce polling frequency if needed
4. **Monitor resource usage** - Most platforms show RAM/CPU graphs

---

## Security Recommendations

1. **Don't commit secrets**
   - `.env` is in `.gitignore` ✅
   - Use platform secret management

2. **Firewall configuration**
   ```bash
   # Only expose port 8000 if you need external API access
   # Otherwise, keep it internal
   ```

3. **Database backups**
   ```bash
   # DigitalOcean/Oracle: Set up automated backups
   # Fly.io/Railway: Enable automated backups in dashboard
   ```

4. **Update dependencies regularly**
   ```bash
   pip install --upgrade -r requirements.txt
   playwright install chromium
   ```

---

## Getting Help

- **Application issues:** Check logs and refer to CLAUDE.md
- **Platform-specific issues:**
  - DigitalOcean: https://docs.digitalocean.com/
  - Oracle Cloud: https://docs.oracle.com/en-us/iaas/
  - Fly.io: https://fly.io/docs/
  - Railway: https://docs.railway.app/

Good luck with your deployment! 🚀
