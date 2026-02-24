# 🤖 Cold Email Bot

Automated cold email outreach manager controlled entirely through Telegram.  
Built with **FastAPI + Motor (MongoDB Atlas) + Brevo API + python-telegram-bot**.

---

## 📁 Project Structure

```
cold-email-bot/
├── main.py            # FastAPI app + lifespan (startup/shutdown)
├── telegram_bot.py    # All Telegram commands and conversation flows
├── email_service.py   # Brevo API integration
├── db.py              # All MongoDB operations (motor async)
├── models.py          # Pydantic models + helpers
├── config.py          # Environment variable loader
├── requirements.txt
├── Dockerfile
├── choreo.yaml        # Choreo deployment config
├── .env.example       # Template for your .env file
└── .gitignore
```

---

## ⚡ Quick Start (Local)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/cold-email-bot.git
cd cold-email-bot

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your real keys

# 5. Run
python main.py
```

---

## 🔧 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | From @BotFather |
| `ADMIN_CHAT_IDS` | ✅ | Comma-separated Telegram user IDs |
| `MONGO_URI` | ✅ | MongoDB Atlas connection string |
| `MONGO_DB_NAME` | | DB name (default: `cold_email_bot`) |
| `BREVO_API_KEY` | ✅ | Brevo API key |
| `SENDER_EMAIL` | ✅ | Verified sender email in Brevo |
| `SENDER_NAME` | | Display name for outgoing emails |
| `SEND_DELAY_MIN` | | Min seconds between emails (default: 2) |
| `SEND_DELAY_MAX` | | Max seconds between emails (default: 5) |
| `DAILY_SEND_LIMIT` | | Max emails per day (default: 100) |
| `MAX_RETRIES` | | Failed email retry attempts (default: 3) |
| `PORT` | | Server port (default: 8000) |
| `LOG_LEVEL` | | INFO / DEBUG / WARNING |

---

## 🤖 Telegram Commands

### Lead Management

| Command | Description |
|---|---|
| `/add` | Start adding leads (guided conversation) |
| `/remove email1, email2` | Remove leads by email |
| `/export` | Export all leads to CSV |
| `/export dental clinic` | Export leads for a specific tag |
| `/markreplied email@x.com` | Manually mark a lead as replied |

**Adding leads:**
```
/add
→ Bot asks for leads in format: NAME:email, NAME:email
→ John Doe:john@clinic.com, Jane Smith:jane@gym.com
→ Bot asks for niche tag
→ dental clinic
```

### Template Management

| Command | Description |
|---|---|
| `/addtemplate` | Add/update template (guided conversation) |
| `/removetemplate dental clinic` | Remove a template |
| `/listtemplates` | List all templates |

**Template body supports `{NAME}` placeholder:**
```
Hello {NAME},

We noticed your dental clinic could benefit from...
```

### Sending Emails

| Command | Description |
|---|---|
| `/send dental clinic` | Send to all unsent leads with this tag |
| `/retry dental clinic` | Retry failed emails for this tag |

### Other

| Command | Description |
|---|---|
| `/stats` | Show total/sent/replied/remaining stats |
| `/inbox` | Manually check for replies |
| `/blacklist add email@x.com` | Add to blacklist |
| `/blacklist remove email@x.com` | Remove from blacklist |
| `/blacklist list` | View blacklist |
| `/cancel` | Cancel current operation |

---

## 📬 Reply Detection

The bot supports **two modes** for reply detection:

### Mode 1: Brevo Inbound Domain (recommended)
1. Set up an inbound domain in Brevo → Settings → Inbound Parsing
2. Point MX records to Brevo
3. Set webhook URL to: `https://your-choreo-app-url/webhook/reply`
4. Replies will automatically trigger a Telegram notification

### Mode 2: Manual Check
Press the **📥 Inbox** button or run `/inbox` to poll Brevo events.

---

## 🚀 Deploy to Choreo

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/cold-email-bot.git
git push -u origin main
```

### Step 2: Create Choreo Service
1. Go to [console.choreo.dev](https://console.choreo.dev)
2. Create new **Component** → **Service**
3. Connect your GitHub repository
4. Choreo will detect the `Dockerfile` automatically
5. Set the build context to `/` and Dockerfile to `./Dockerfile`

### Step 3: Set Environment Variables
In Choreo → Component → **Configs & Secrets**:
- Add all variables from `.env.example` as **Secrets**
- Sensitive values (tokens, API keys, MONGO_URI) → use **Secret** type
- Non-sensitive values → use **Config** type

### Step 4: Deploy
- Click **Deploy** → Choreo will build and run your container
- Copy the public URL and use it for the Brevo webhook

---

## 🗃️ MongoDB Collections

### `leads`
```json
{
  "name": "John Doe",
  "email": "john@clinic.com",
  "niche_tag": "dental clinic",
  "used": false,
  "replied": false,
  "template_used": null,
  "sent_at": null,
  "failed": false,
  "fail_count": 0,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### `templates`
```json
{
  "niche_tag": "dental clinic",
  "subject": "Grow Your Practice",
  "body": "Hello {NAME},\n\nWe help dental clinics...",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### `blacklist`
```json
{
  "email": "noreply@example.com",
  "reason": "manual",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## 🛡️ Safety Features

- ✅ Admin-only access (whitelist by Telegram user ID)
- ✅ Duplicate email prevention (MongoDB unique index)
- ✅ Email format validation before storage
- ✅ Blacklist prevents sending to blocked addresses
- ✅ Daily send limit (configurable)
- ✅ Random delay between emails (anti-spam)
- ✅ Failed email retry with max-attempt limit
- ✅ Template required before sending
- ✅ Replied leads are skipped on `/send`
- ✅ All secrets via environment variables
- ✅ Non-root Docker user

---

## 💾 Resource Usage

Designed to run comfortably within:
- **RAM:** ~100–150 MB
- **CPU:** minimal (async I/O bound)
- **Storage:** none (fully MongoDB-backed)
