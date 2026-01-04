# AI Fitness Dashboard

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20%7C%20Linux%20%7C%20Windows-green)

**Your personal fitness command center. Automate data collection. Visualize progress. Generate AI-powered workout plans.**

This project creates a comprehensive fitness tracking system that automatically aggregates your biometrics (Garmin) and weightlifting data (Hevy), displays them in a real-time dashboard, and uses AI (Google Gemini) to generate personalized workout routines.

---

## Features

### Dashboard
- **Training Analytics** - Volume progression, muscle group distribution, workout history
- **Recovery Metrics** - Sleep scores, HRV, weight trends, resting heart rate
- **Cardio Tracking** - Running distance, pace trends, heart rate zones
- **System Monitoring** - Task status, cron jobs, system vitals
- **Trend Lines** - Smooth rolling averages overlay on charts

### Data Sync
- **Garmin Connect** - Sleep, HRV, weight, body composition, SpO2, respiration, VO2 Max
- **Hevy App** - Workouts, exercises, sets, reps, RPE
- **Running Activities** - Pace, distance, HR zones, training effect

### AI Integration
- **Gemini AI Coach** - Generates personalized 4-week PPL routines
- **Auto-Upload** - Pushes AI-generated routines directly to Hevy app
- **Smart Context** - Uses your training history and recovery data

---

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/johnson4601/AI_Fitness.git
cd AI_Fitness

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Run interactive setup
python3 setup.py
```

The setup wizard will guide you through:
- Installing dependencies
- Configuring Garmin, Hevy, and Gemini integrations
- Setting up scheduled tasks
- Configuring dashboard autostart

### 2. Start Dashboard

```bash
streamlit run dashboard_local_server.py
```

Access at: `http://localhost:8501` (or `http://<pi-ip>:8501` from other devices)

---

## Project Structure

```
AI_Fitness/
├── setup.py                  # Interactive setup wizard (START HERE)
├── dashboard_local_server.py # Streamlit dashboard
├── .env                      # Configuration (created by setup.py)
│
├── Daily Scripts (Cron)
│   ├── daily_garmin_health.py   # Health metrics sync
│   ├── daily_garmin_runs.py     # Running activities sync
│   └── daily_hevy_workouts.py   # Workout sync
│
├── History Import (One-time)
│   ├── history_garmin_import.py # Bulk import Garmin history
│   ├── history_garmin_runs.py   # Bulk import run history
│   └── history_hevy_import.py   # Bulk import Hevy history
│
├── AI Coach
│   ├── Gemini_Hevy.py           # AI routine generator
│   └── MONTHLY_PROMPT_TEXT.txt  # AI personality config
│
├── Auth
│   ├── setup_garmin_login.py    # Garmin authentication
│   ├── .garth/                  # Garmin tokens (auto-created)
│   ├── credentials.json         # Google OAuth (you provide)
│   └── token.pickle             # Google tokens (auto-created)
│
└── requirements.txt          # Python dependencies
```

---

## Configuration

### Environment Variables (.env)

The setup wizard creates this automatically. Manual configuration:

```ini
# File Paths
SAVE_PATH=/home/pi/GDrive/Gemini Gems/Personal trainer
DRIVE_MOUNT_PATH=/home/pi/GDrive

# Garmin Connect
GARMIN_EMAIL=your_email@example.com
GARMIN_PASSWORD=your_password

# Hevy App (get from Hevy Settings > API)
HEVY_API_KEY=your_hevy_api_key

# Google Services
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_DRIVE_FOLDER_ID=your_folder_id

# System Settings
CHECK_MOUNT_STATUS=True
```

### Reconfigure Anytime

```bash
python3 setup.py
```

Your existing settings are preserved - just press Enter to keep current values.

---

## Raspberry Pi Setup

### Dashboard as a Service

```bash
# Copy service file
sudo cp ai-fitness-dashboard.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable ai-fitness-dashboard
sudo systemctl start ai-fitness-dashboard

# Check status
sudo systemctl status ai-fitness-dashboard
```

### Scheduled Tasks (Cron)

```bash
crontab -e
```

Add these lines:
```bash
# Garmin health sync (every hour at :30)
30 * * * * cd /home/pi/Documents/AI_Fitness && /usr/bin/python3 daily_garmin_health.py >> /home/pi/cron_log.txt 2>&1

# Hevy workout sync (every hour at :35)
35 * * * * cd /home/pi/Documents/AI_Fitness && /usr/bin/python3 daily_hevy_workouts.py >> /home/pi/cron_log.txt 2>&1

# Garmin runs sync (every hour at :40)
40 * * * * cd /home/pi/Documents/AI_Fitness && /usr/bin/python3 daily_garmin_runs.py >> /home/pi/cron_log.txt 2>&1

# Monthly AI plan (1st of month at 1:00 AM)
0 1 1 * * cd /home/pi/Documents/AI_Fitness && ./venv/bin/python Gemini_Hevy.py >> /home/pi/cron_log.txt 2>&1
```

### Google Drive Mount (rclone)

```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Configure
rclone config

# Mount (add to /etc/fstab for boot)
rclone mount gdrive: /home/pi/GDrive --vfs-cache-mode writes &
```

---

## Usage

### Initial Data Import

Before automation, backfill your history:

```bash
python3 history_hevy_import.py      # All past workouts
python3 history_garmin_import.py    # Past health metrics
python3 history_garmin_runs.py      # Past runs
```

### Generate AI Workout Plan

```bash
python3 Gemini_Hevy.py
```

This analyzes your last 6 months of data and creates personalized routines uploaded to Hevy.

### Dashboard Controls

Access from **System & Tools** tab:
- **Run** buttons for manual task execution
- **Restart Dashboard** / **Reboot System**
- **Configuration** panel to view settings
- **Monthly Prompt Editor** to customize AI coach

---

## Dashboard Screenshots

### Training Tab
- Volume progression with trend lines
- Muscle group distribution (pie + bar charts)
- Cardio section with HR zones and pace trends

### Recovery Tab
- Body weight tracking
- Sleep score & HRV trends
- Daily steps and RHR

### System Tab
- Task status and scheduling
- System vitals (CPU, RAM, temp)
- Configuration management

---

## Troubleshooting

### Garmin Login Fails
```bash
rm -rf .garth
# Wait 15-30 minutes (Garmin rate limiting)
python3 setup_garmin_login.py
```

### Dashboard Won't Start
```bash
# Check logs
sudo journalctl -u ai-fitness-dashboard -f

# Restart service
sudo systemctl restart ai-fitness-dashboard
```

### Missing Data in Charts
- Check `.env` paths are correct
- Verify CSV files exist in `SAVE_PATH`
- Run daily scripts manually to test

### Date Format Errors
The system handles mixed date formats automatically. If issues persist:
```bash
# Check CSV format
head -5 /path/to/garmin_stats.csv
```

---

## API Keys & Accounts

| Service | Where to Get |
|---------|--------------|
| **Hevy API** | Hevy App → Settings → Account → API |
| **Gemini API** | https://aistudio.google.com/apikey |
| **Google Drive** | https://console.cloud.google.com (enable Drive API) |
| **Garmin** | Your existing Garmin Connect account |

---

## Tech Stack

- **Dashboard**: Streamlit + Plotly
- **Data**: Pandas, CSV storage
- **Garmin API**: garminconnect, garth
- **Hevy API**: REST API
- **AI**: Google Gemini (google-genai)
- **Scheduling**: Cron + systemd

---

## Contributing

Contributions welcome! Please check the [issues page](https://github.com/johnson4601/AI_Fitness/issues).

---

## License

MIT License - see [LICENSE](LICENSE)

---

**Built for the data-driven athlete**
