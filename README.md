# 🤖 WhatsApp Resume Evaluation Bot

A production-ready AI-powered bot that evaluates resumes against job descriptions via WhatsApp, provides ATS scoring, improvement suggestions, and generates downloadable improved resumes.

---

## 📐 Architecture Overview

```
WhatsApp User
     │
     ▼
Twilio WhatsApp API
     │  (POST /webhook/whatsapp)
     ▼
FastAPI Application (main.py)
     │
     ├── routes/
     │   ├── whatsapp.py       ← Validates Twilio signature, extracts message/media
     │   └── health.py         ← Uptime monitoring endpoint
     │
     ├── services/
     │   ├── session_manager.py    ← Per-user conversation state (in-memory / Redis)
     │   ├── conversation_handler.py ← State machine routing messages to actions
     │   ├── resume_parser.py      ← PDF/DOCX text extraction
     │   ├── evaluator.py          ← Claude API evaluation with structured prompts
     │   └── resume_generator.py   ← DOCX + PDF resume generation
     │
     └── utils/
         ├── formatter.py          ← WhatsApp message formatting
         ├── twilio_helpers.py     ← Media download from Twilio
         └── logger.py             ← Centralized logging
```

---

## 💬 Conversation Flow

```
User sends JD text
        │
        ▼
Bot saves JD, asks for resume
        │
        ▼
User uploads PDF/DOCX
        │
        ▼
Bot parses resume text
        │
        ▼
Claude evaluates JD vs Resume
        │
        ▼
Bot sends:
  • ATS Score (0-100)
  • Score Breakdown
  • Missing Skills
  • Top Suggestions
  • ATS Warnings
        │
        ▼
Interactive Menu:
  1. Rewrite bullets
  2. Missing skills detail
  3. Rewrite summary
  4. Generate DOCX + PDF
  5. Show results again
        │
        ▼
User downloads improved resume
```

---

## 🚀 Quick Start (Local)

### Prerequisites
- Python 3.11+
- [ngrok](https://ngrok.com) (to expose local server to Twilio)
- Twilio account with WhatsApp sandbox enabled
- Anthropic API key

### 1. Clone & Install

```bash
git clone https://github.com/yourname/whatsapp-resume-bot
cd whatsapp-resume-bot

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual keys
nano .env
```

Required values in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
BASE_URL=https://your-ngrok-url.ngrok.io
```

### 3. Start the Server

```bash
uvicorn main:app --reload --port 8000
```

### 4. Expose with ngrok

```bash
# In a new terminal
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`) and:
1. Update `BASE_URL` in your `.env`
2. Set it as the Twilio webhook: `https://abc123.ngrok.io/webhook/whatsapp`

### 5. Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to **Messaging → Try it out → Send a WhatsApp message**
3. In **Sandbox Settings**, set:
   - **When a message comes in:** `https://your-ngrok-url.ngrok.io/webhook/whatsapp`
   - **Method:** `HTTP POST`
4. Save

### 6. Test

Send a WhatsApp message to your Twilio sandbox number and follow the bot's prompts.

---

## 🐳 Docker Deployment

### Local Docker

```bash
# Build and start
docker-compose up --build

# Run in background
docker-compose up -d --build
```

### Production (any Linux server)

```bash
# On your server
git clone https://github.com/yourname/whatsapp-resume-bot
cd whatsapp-resume-bot

# Create .env file
cp .env.example .env
nano .env   # Fill in production values

# Start
docker-compose up -d --build

# View logs
docker-compose logs -f bot
```

---

## ☁️ Cloud Deployment

### Railway (Recommended — easiest)

1. Push code to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables in Railway dashboard
4. Railway auto-detects Dockerfile and deploys
5. Use the Railway-provided URL as your `BASE_URL` and Twilio webhook

### Render

1. Create a new **Web Service** on [render.com](https://render.com)
2. Connect GitHub repo
3. Set **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 8000`
4. Add environment variables
5. Deploy

### AWS / GCP / DigitalOcean

```bash
# On your VM (Ubuntu 22.04)
sudo apt update && sudo apt install -y docker.io docker-compose

git clone https://github.com/yourname/whatsapp-resume-bot
cd whatsapp-resume-bot
cp .env.example .env && nano .env

sudo docker-compose up -d --build

# Set up nginx reverse proxy (optional but recommended)
sudo apt install nginx
# Configure nginx to proxy port 80 → 8000
```

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhook/whatsapp` | Twilio WhatsApp webhook |
| GET | `/health` | Health check |
| GET | `/output/{filename}` | Download generated resume |
| GET | `/` | Service info |

---

## 🧪 Testing Without WhatsApp

You can test the evaluation logic directly via the FastAPI interactive docs:

```bash
# Start server
uvicorn main:app --reload

# Open in browser
http://localhost:8000/docs
```

Or test the evaluator directly:

```python
# test_eval.py
import asyncio
from app.services.evaluator import ResumeEvaluator

async def test():
    evaluator = ResumeEvaluator()
    result = await evaluator.evaluate(
        job_description="Senior Python developer with FastAPI, Docker, AWS...",
        resume_text="John Doe\njohn@email.com\n\nExperience:\nPython Developer at XYZ...",
    )
    import json
    print(json.dumps(result, indent=2))

asyncio.run(test())
```

---

## 📁 Project Structure

```
whatsapp-resume-bot/
├── main.py                    # FastAPI app entry point
├── config.py                  # Settings & environment variables
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker build config
├── docker-compose.yml         # Local Docker orchestration
├── .env.example               # Environment variable template
├── output/                    # Generated resumes (auto-created)
└── app/
    ├── routes/
    │   ├── whatsapp.py        # Twilio webhook handler
    │   └── health.py          # Health check endpoint
    ├── services/
    │   ├── session_manager.py # User conversation state
    │   ├── conversation_handler.py # Message routing state machine
    │   ├── resume_parser.py   # PDF/DOCX text extraction
    │   ├── evaluator.py       # Claude API evaluation
    │   └── resume_generator.py # DOCX/PDF resume generation
    └── utils/
        ├── formatter.py       # WhatsApp message formatting
        ├── twilio_helpers.py  # Media download utilities
        └── logger.py          # Logging configuration
```

---

## 🔧 Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | — | Claude API key |
| `TWILIO_ACCOUNT_SID` | ✅ | — | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | ✅ | — | Twilio Auth Token |
| `TWILIO_WHATSAPP_NUMBER` | ✅ | — | Your Twilio WhatsApp number |
| `BASE_URL` | ✅ | `http://localhost:8000` | Public server URL for download links |
| `SESSION_TTL_MINUTES` | ❌ | `60` | Session inactivity timeout |
| `MAX_FILE_SIZE_MB` | ❌ | `10` | Max resume file size |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |
| `CLAUDE_MODEL` | ❌ | `claude-sonnet-4-20250514` | Claude model to use |

---

## 🔒 Security Notes

- **Twilio Signature Validation**: Every webhook request is verified using Twilio's HMAC signature. Invalid requests return 403.
- **File Size Limits**: Resumes over `MAX_FILE_SIZE_MB` are rejected before download.
- **Temp File Cleanup**: Resume files are stored in OS temp directory. Add a cron job to clean `/tmp/resume_*` files older than 24 hours.
- **Environment Variables**: Never commit `.env` to version control. Use `.env.example` as the template.
- **Non-root Docker**: The container runs as a non-root `appuser` for security.

---

## 🚀 Scaling to Production

### Session Storage (Redis)
The default in-memory session store works for a single instance. For multiple instances:

1. Uncomment the Redis service in `docker-compose.yml`
2. Install `redis-py`: `pip install redis`
3. Update `session_manager.py` to use Redis:

```python
import redis
r = redis.Redis(host='redis', port=6379, db=0)

def get(self, user_id: str):
    data = r.get(user_id)
    return pickle.loads(data) if data else UserSession(user_id=user_id)

def save(self, session: UserSession):
    r.setex(user_id, TTL_SECONDS, pickle.dumps(session))
```

### File Storage (S3)
Replace local `output/` directory with S3 for generated resumes:

```python
import boto3
s3 = boto3.client('s3')
s3.upload_file(local_path, 'your-bucket', f'resumes/{filename}')
download_url = f"https://your-bucket.s3.amazonaws.com/resumes/{filename}"
```

---

## 📝 Example Evaluation Output

```
📊 RESUME EVALUATION RESULTS

🟡 ATS Score: 72/100
[███████░░░] 72%

📈 Score Breakdown:
• Skill Match: 22/30
• Keyword Density: 17/25
• Experience Relevance: 20/25
• ATS Friendliness: 13/20

💬 Your resume shows strong Python experience but lacks key DevOps
   skills required for this role. The formatting may cause ATS parsing
   issues due to the use of tables.

✅ Matched Skills: Python, FastAPI, PostgreSQL, REST APIs, Git

❌ Critical Missing Skills:
• Docker
• Kubernetes
• CI/CD (GitHub Actions / Jenkins)

💡 Top Improvements:
• Add quantifiable metrics to all bullet points
• Replace table-based layout with single-column format
• Include Docker and CI/CD keywords in skills section
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `403 Forbidden` on webhook | Twilio signature validation failing — check `TWILIO_AUTH_TOKEN` and that `BASE_URL` matches exactly |
| PDF parsing returns empty text | Resume is image-based (scanned) — ask user to provide a text-based PDF |
| `docx2pdf` fails | Install LibreOffice: `sudo apt install libreoffice` |
| Session not persisting | Check `SESSION_TTL_MINUTES` — sessions expire after inactivity |
| Claude returns non-JSON | Rare model failure — bot auto-retries with fallback evaluation |

---

## 📜 License

MIT License — free for personal and commercial use.
