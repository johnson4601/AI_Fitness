AI Fitness Data Pipeline (Garmin + Hevy)
This project creates a "Cyber-Physical System" for your fitness data. It automatically pulls your biometrics (Garmin) and weightlifting data (Hevy), aggregates them into CSV files, and syncs them to a location of your choice (like Google Drive) for analysis by AI tools like Gemini or ChatGPT.

🚀 Features
Garmin Biometrics: Tracks Weight, Sleep Score, HRV, Stress, and Body Battery hourly.

Garmin Runs: detailed run analysis including Splits, Pace, HR Zones, and Elevation.

Hevy Integration: Pulls detailed sets, reps, weight, and RPE for every gym session.

Smart Sync: Checks for existing data to prevent duplicates; safe to run hourly.

Secure: Uses environment variables to keep your passwords safe.

🛠️ Prerequisites
Before you start, you need three things installed on your computer:

Python 3.12+: Download Here

Crucial: When installing, check the box "Add Python to PATH" at the bottom of the installer.

Google Drive for Desktop (Optional): If you want the files to automatically sync to the cloud for your AI agent.

Git (Optional): To easily download updates.

📥 Installation
1. Download the Code
Open your terminal (PowerShell or Command Prompt) and run:

PowerShell

git clone https://github.com/johnson4601/Fitness-Bot-V1.git
cd Fitness-Bot-V1
(Or just download the ZIP file from GitHub and unzip it).

2. Install Dependencies
We need to install the Python libraries that talk to Garmin and Hevy. Run this command in your project folder:

PowerShell

pip install -r requirements.txt
⚙️ Configuration (The Important Part)
We do not hardcode passwords. We use a special secure file.

Find the file named .env.example in the folder.

Rename it to .env (remove the .example).

Note: If you don't see file extensions, just rename it so it looks like just .env.

Open .env with Notepad.

Fill in your details:

Ini, TOML

# Garmin Credentials
GARMIN_EMAIL=your_email@example.com
GARMIN_PASSWORD=your_password

# Hevy API Key (Requires Hevy Pro)
# Get this from: https://hevy.com/settings (Developer tab)
HEVY_API_KEY=your_long_api_key_here

# Where should the CSV files be saved?
# Example for Google Drive users:
SAVE_PATH=G:\My Drive\Gemini Gems\Personal trainer
# Example for local users:
# SAVE_PATH=C:\Users\Brian\Documents\FitnessData
🏃‍♂️ First Run & Authentication
1. Login to Garmin
Garmin requires a one-time secure login to generate session tokens. Run this command:

PowerShell

python direct_login.py
If successful, it will save a hidden .garth folder. You won't need to log in again for about a year.

2. Backfill Your History
Let's pull all your past data so your database isn't empty.

PowerShell

# Pull lifting history (Since 2023)
python hevy_history_pull.py

# Pull run history (Since 2023)
python garmin_runs_daily.py
Check your SAVE_PATH folder. You should see hevy_stats.csv and garmin_runs.csv full of data.

🤖 Automation (Set it and Forget it)
To have this run automatically every hour, we use Windows Task Scheduler.

The Easy Way (PowerShell Script)
Open PowerShell as Administrator and copy/paste these blocks to create the tasks instantly.

Task 1: Garmin Biometrics (Hourly)

PowerShell

$Action = New-ScheduledTaskAction -Execute "python.exe" -Argument "garmin_daily_report.py" -WorkingDirectory "C:\Path\To\Fitness-Bot-V1"
$Trigger = New-ScheduledTaskTrigger -Once -At "11:30PM" -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 36500)
$Trigger.Repetition.Duration = $null
Register-ScheduledTask -TaskName "Garmin Daily Pull" -Action $Action -Trigger $Trigger -Force
(Make sure to replace C:\Path\To\Fitness-Bot-V1 with the actual folder location on your PC).

Task 2: Hevy Lifts (Hourly) Repeat the command above, but change:

Argument: hevy_pull.py

TaskName: "Hevy Daily Pull"

❓ Troubleshooting
"python is not recognized" You didn't check "Add to PATH" when installing Python. Re-install Python and check that box.

Garmin Login Fails Garmin security is strict. If direct_login.py fails:

Delete the .garth folder if it exists.

Wait 15 minutes.

Try logging in again.

Files not updating Check the logs. Open the .env file and ensure SAVE_PATH points to a folder that actually exists.

Disclaimer: This tool is for personal use. Be mindful of API rate limits. Running scripts more frequently than once every 15-30 minutes may get your IP temporarily restricted by Garmin.