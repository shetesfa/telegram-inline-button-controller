# Telegram Multi-Channel / Multi-Group Future-Post Automation System

A production-ready Telegram channel and group post automation system built with Python 3.11+ and `python-telegram-bot`.

Whenever an administrator publishes a **NEW** post in a configured Telegram channel or group, this system automatically attaches modern, interactive inline keyboard buttons underneath the post.

---

## 🎯 How It Works

```
                        YOU / ADMINISTRATOR
                                ↓
                 [ Controller Telegram Bot ]
       (Configure channels, groups, buttons & layouts)
                                ↓
                    Python System Runs 24/7
                                ↓
        You publish a NEW post manually in your channel/group
                                ↓
                Telegram sends incoming update
                                ↓
            Python detects it & checks duplicate DB
                                ↓
         System attaches Inline Keyboard underneath post
                                ↓
        Subscribers see original post with modern buttons!
```

---

## 🛡️ Core Guarantees & Architecture Decisions

1. **Zero Historical Post Modification (Non-Negotiable)**:
   - The system **NEVER** reads, edits, migrates, deletes, or alters old channel messages.
   - On startup, `drop_pending_updates=True` prevents processing past backlog. Automation strictly triggers on **new** posts arriving while active.
2. **100% Content Preservation**:
   - Uses Telegram API's `editMessageReplyMarkup` method.
   - Preserves original post text, Amharic/Unicode characters, captions, formatting entities, photos, videos, audio, documents, and animations. Never re-uploads media.
3. **Multi-Destination Independence**:
   - Each channel, group, and supergroup maintains its own separate configuration, enable/disable switches, layout mode, and button list.
4. **Duplicate Protection & Idempotency**:
   - Fast in-memory LRU cache + persistent `ProcessedPost` database table ensures posts are processed exactly once.
5. **Media Group / Album Handling**:
   - For multi-photo/video albums sharing a `media_group_id`, the system attaches the inline keyboard exclusively to the primary item (the message with the caption / first received item) and debounces subsequent album items.
6. **Strict Security & Authorization**:
   - Only Telegram user IDs listed in `ADMIN_IDS` can access controller menus. Unauthorized users receive a clean `403 Access Denied` response with zero technical details or secrets exposed.

---

## 📁 Project Structure

```
telegram_manager/
│
├── app/
│   ├── __init__.py
│   ├── config.py                 # Environment & admin whitelist settings
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py           # Async SQLAlchemy engine & session lifecycle
│   │   ├── models.py             # Destination, Button, ProcessedPost, SystemSetting
│   │   └── repository.py         # Async CRUD repository layer
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── destination_service.py # Channels & groups management
│   │   ├── button_service.py      # Button CRUD, ordering & keyboard generation
│   │   ├── post_service.py        # Duplicate protection & album deduplication
│   │   └── system_service.py      # Diagnostics, health metrics & global settings
│   │
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── permissions.py        # Channel/group administrator rights validator
│   │   └── post_processor.py     # Channel_post & message handler with error isolation
│   │
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── bot.py                # Application builder & polling lifecycle
│   │   ├── permissions.py        # Security filters & @admin_required decorator
│   │   ├── keyboards/
│   │   │   ├── admin_kb.py       # Controller bot UI inline menus
│   │   │   └── post_kb.py        # Live preview inline keyboard builder
│   │   └── handlers/
│   │       ├── start.py          # /start dashboard & master switch
│   │       ├── channels.py       # Channels list, add wizard, toggles, delete
│   │       ├── groups.py         # Groups list, add wizard, toggles, delete
│   │       ├── buttons.py        # Button manager, reorder, preview, edit wizards
│   │       ├── settings.py       # Global settings & admin whitelist
│   │       └── status.py         # System health & diagnostic reports
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py            # Structured logger with secret token masking
│       ├── validation.py         # URL & chat identifier validators
│       └── helpers.py            # UI badges, formatters & timestamp utils
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Test database fixtures
│   ├── test_security.py          # Authorization & security unit tests
│   ├── test_buttons.py           # Button CRUD, ordering & layout tests
│   ├── test_destinations.py      # Channel/group addition & toggle tests
│   ├── test_post_processor.py    # Post processing, duplicate & album tests
│   └── test_persistence.py       # SQLite restart persistence tests
│
├── .env.example
├── .gitignore
├── requirements.txt
├── pytest.ini
├── README.md
└── main.py                       # Application entry point
```

---

## 🚀 Quick Setup Guide (Windows Local Testing)

### Step 1: Prerequisites
Ensure you have **Python 3.11+** installed. Check in PowerShell or Command Prompt:
```powershell
python --version
```

### Step 2: Create Telegram Bot & Obtain Admin ID
1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, follow prompts, and copy your **HTTP API Token** (e.g. `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
3. To find your own Telegram User ID, message [@userinfobot](https://t.me/userinfobot) or [@raw_data_bot](https://t.me/raw_data_bot) and copy your numeric `id` (e.g. `123456789`).

### Step 3: Configure Environment
Navigate to the project folder and copy `.env.example` to `.env`:
```powershell
cd C:\Users\Tesfa\.gemini\antigravity\scratch\telegram_manager
copy .env.example .env
```
Edit `.env` with your values:
```env
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
ADMIN_IDS=123456789
DATABASE_URL=sqlite+aiosqlite:///telegram_manager.db
LOG_LEVEL=INFO
APP_ENV=development
```

### Step 4: Install Dependencies
Create and activate a virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 5: Run Automated Tests
Verify all components:
```powershell
python -m pytest -v
```

### Step 6: Start the Application
```powershell
python main.py
```
You will see the startup banner:
```
=====================================================
   TELEGRAM MULTI-DESTINATION POST AUTOMATION SYSTEM
=====================================================
 Environment       : DEVELOPMENT
 Bot Token         : 123456789:ABC...xyZ
 Authorized Admins : 1 admin ID(s) configured
 Database          : OK (SQLite async)
 Channels Active   : 0
 Groups Active     : 0
 Master Automation : ENABLED (ON)
 Mode              : Future-post automation (zero history scan)
=====================================================
🤖 System is running and listening for Telegram updates...
```

---

## 📱 Controller Bot Usage Walkthrough

### 1. Open Controller Bot
Open Telegram, search for your bot, and send `/start`.

### 2. Add a Channel
1. In Telegram, go to your target channel settings -> **Administrators** -> **Add Administrator**.
2. Add your bot and grant **Edit Messages of Others** permission.
3. In the Controller Bot, click `[📢 Channels]` -> `[➕ Add Channel]`.
4. Send the channel username (e.g. `@mychannel`) or numeric ID (e.g. `-1001234567890`), or forward a post from the channel.
5. The bot verifies permissions with Telegram and asks:
   - `[🔘 Use Default Buttons Template]` (Creates Channel, Group, Bot buttons)
   - `[✨ Start Empty]`
6. Select your choice. The channel is now active!

### 3. Customize Buttons
1. Click `[📢 Channels]` -> Select your channel -> `[🔘 Manage Buttons]`.
2. Options available:
   - `[➕ Add Button]`: Enter label (e.g. `📚 Course Materials`) and URL (`https://example.com/courses`).
   - `[✏️ Edit Label]`, `[🔗 Edit URL]`, `[😀 Edit Emoji]`.
   - `[⬆️ Move Up]` / `[⬇️ Move Down]`: Adjust button order.
   - `[🟢/🔴 Status]`: Enable or temporarily disable individual buttons.
   - `[👁 Preview]`: Render the exact inline keyboard layout before publishing.

### 4. Publish a Test Post
1. Open your configured Telegram channel.
2. Publish a **NEW** post:
   ```
   📚 Today's Lesson
   
   This is today's educational content...
   ```
3. Within milliseconds, the bot attaches the configured inline buttons underneath your post!

---

## 🌐 Production Deployment Guide (Linux VPS 24/7)

### Step 1: Deploy Files to Server
Upload the `telegram_manager` folder to your Linux server (e.g. `/opt/telegram_manager`):
```bash
sudo mkdir -p /opt/telegram_manager
sudo chown -R $USER:$USER /opt/telegram_manager
cd /opt/telegram_manager
```

### Step 2: Setup Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure `.env`
```bash
cp .env.example .env
nano .env
```
Ensure `BOT_TOKEN`, `ADMIN_IDS`, and `DATABASE_URL` are set.

### Step 4: Configure systemd 24/7 Service
Create the service unit file:
```bash
sudo nano /etc/systemd/system/telegram-manager.service
```
Paste the following configuration:
```ini
[Unit]
Description=Telegram Multi-Channel Future-Post Automation Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram_manager
EnvironmentFile=/opt/telegram_manager/.env
ExecStart=/opt/telegram_manager/venv/bin/python main.py
Restart=always
RestartSec=5s
KillMode=mixed
TimeoutStopSec=10s

[Install]
WantedBy=multi-user.target
```

### Step 5: Start & Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-manager
sudo systemctl start telegram-manager
```

### Step 6: Monitor Logs & Manage Service
```bash
# View live structured logs
sudo journalctl -u telegram-manager -f

# Check service status
sudo systemctl status telegram-manager

# Restart service
sudo systemctl restart telegram-manager

# Stop service
sudo systemctl stop telegram-manager
```

---

## 🔍 Troubleshooting & FAQs

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **"⛔ Access Denied" when messaging bot** | Your Telegram User ID is not in `ADMIN_IDS` | Get your ID from `@userinfobot`, add to `ADMIN_IDS` in `.env`, and restart. |
| **"Permission Problem" when adding channel** | Bot is not an Administrator in the channel | Open channel settings -> Administrators -> Add bot -> Grant "Edit Messages" rights. |
| **Buttons not appearing on new channel post** | Automation switch is OFF or bot lacks edit permissions | Check `[🛠 System Status]` in controller bot. Ensure channel is set to `🟢 Enabled` and `🟢 Auto-Post: ON`. |
| **Only 1st photo of album has buttons** | Expected behavior for Telegram media groups | Telegram Bot API attaches reply markup per message object. Attaching to the main caption item prevents UI clutter. |
| **Old posts did not receive buttons** | Expected core design guarantee | The system intentionally operates **only** on newly incoming updates to protect past channel history. |

---

## 📄 License
MIT License. Free for commercial and private use.
