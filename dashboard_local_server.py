import os
import sys
import time
import subprocess
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, flash
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-fallback-key-change-in-production') # Needed for flashing messages

# Paths
DRIVE_PATH = os.getenv("DRIVE_MOUNT_PATH", "/home/pi/google_drive")
SAVE_PATH = os.getenv("SAVE_PATH", "/home/pi/google_drive/Gemini Gems/Personal trainer")
BACKUP_PATH = os.path.join(DRIVE_PATH, "Backups")

LOG_FILE = "/home/pi/cron_log.txt"
PROJECT_DIR = "/home/pi/Documents/AI_Fitness"
HEVY_API_KEY = os.getenv("HEVY_API_KEY")

# Debug Print
print(f"--- DASHBOARD STARTUP ---")
print(f"Save Path: {SAVE_PATH}")

# Tracked Files & Commands
TRACKED_FILES = {
    "Garmin Health": {
        "path": os.path.join(SAVE_PATH, "garmin_stats.csv"),
        "interval": "hourly",
        "sched": {"minute": 30},
        "command": "cd /home/pi/Documents/AI_Fitness && /usr/bin/python3 daily_garmin_health.py >> /home/pi/cron_log.txt 2>&1"
    },
    "Hevy Workouts": {
        "path": os.path.join(SAVE_PATH, "hevy_stats.csv"),
        "interval": "hourly",
        "sched": {"minute": 35},
        "command": "cd /home/pi/Documents/AI_Fitness && /usr/bin/python3 daily_hevy_workouts.py >> /home/pi/cron_log.txt 2>&1"
    },
    "Garmin Runs": {
        "path": os.path.join(SAVE_PATH, "garmin_runs.csv"),
        "interval": "hourly",
        "sched": {"minute": 40},
        "command": "cd /home/pi/Documents/AI_Fitness && /usr/bin/python3 daily_garmin_runs.py >> /home/pi/cron_log.txt 2>&1"
    },
    "Hevy Ticker": {
        "path": "/home/pi/Documents/Hevy_Ticker/ticker.log", 
        "interval": "hourly",
        "sched": {"minute": 45},
        "command": "cd /home/pi/Documents/Hevy_Ticker && /usr/bin/python3 Hevy_Ticker.py >> /home/pi/cron_log.txt 2>&1"
    },
    "System Maint": {
        "path": "/home/pi/Documents/AI_Fitness/update.log",
        "interval": "daily",
        "sched": {"hour": 4, "minute": 0},
        "command": "/home/pi/Documents/AI_Fitness/update.sh >> /home/pi/cron_log.txt 2>&1"
    },
    "System Backup": {
        "path": BACKUP_PATH,
        "interval": "weekly",
        "sched": {"dow": 0, "hour": 3, "minute": 0},
        "command": "/home/pi/Documents/system_backup.sh >> /home/pi/cron_log.txt 2>&1"
    },
    "Monthly AI Plan": {
        "path": "/home/pi/Documents/AI_Fitness/Gemini_Hevy.py",
        "interval": "monthly",
        "sched": {"day": 1, "hour": 1, "minute": 0},
        "command": "cd /home/pi/Documents/AI_Fitness && /home/pi/Documents/AI_Fitness/venv/bin/python Gemini_Hevy.py >> /home/pi/cron_log.txt 2>&1"
    }
}

# --- HEVY HELPER FUNCTIONS ---
def get_or_create_hevy_folder(folder_name):
    headers = {"api-key": HEVY_API_KEY, "Content-Type": "application/json"}
    # List existing
    try:
        res = requests.get("https://api.hevyapp.com/v1/routine_folders", headers=headers)
        if res.status_code == 200:
            for folder in res.json().get('routine_folders', []):
                if folder['title'] == folder_name:
                    return folder['id']
        # Create new
        payload = {"routine_folder": {"title": folder_name}}
        res = requests.post("https://api.hevyapp.com/v1/routine_folders", headers=headers, json=payload)
        if res.status_code in [200, 201]:
            return res.json()['routine_folder']['id']
    except Exception as e:
        print(f"Hevy API Error: {e}")
    return None

def upload_routine_json(json_data, folder_name):
    if not HEVY_API_KEY:
        return "Error: HEVY_API_KEY missing in .env"

    try:
        data = json.loads(json_data)

        # Handle different JSON formats:
        # 1. {"routines": [{...}, {...}]}
        # 2. [{"routine": {...}}, {"routine": {...}}]
        # 3. [{...}, {...}] (direct array of routines)
        if isinstance(data, dict):
            routines = data.get('routines', [])
        elif isinstance(data, list):
            # Check if items have a "routine" wrapper
            if data and isinstance(data[0], dict) and 'routine' in data[0]:
                routines = [item['routine'] for item in data]
            else:
                routines = data
        else:
            routines = []

        if not routines:
            return "Error: No routines found in JSON"

        # Get or create folder if folder_name is provided
        folder_id = None
        if folder_name and folder_name.strip():
            folder_id = get_or_create_hevy_folder(folder_name)
            if not folder_id:
                return "Error: Could not create/access folder on Hevy. Check API key permissions."

        headers = {"api-key": HEVY_API_KEY, "Content-Type": "application/json"}
        success_count = 0
        errors = []

        for idx, routine in enumerate(routines):
            # Build the payload - keep the routine structure as-is
            payload = {"routine": routine}

            # Add folder_id if we have one (correct field name!)
            if folder_id:
                payload["routine"]["folder_id"] = folder_id

            res = requests.post("https://api.hevyapp.com/v1/routines", headers=headers, json=payload)

            if res.status_code in [200, 201]:
                success_count += 1
            else:
                try:
                    error_detail = res.json() if res.headers.get('content-type') == 'application/json' else res.text
                except:
                    error_detail = res.text
                errors.append(f"#{idx+1} '{routine.get('title', 'Unknown')}': {error_detail}")

        # Build result message
        msg = f"✓ Uploaded {success_count}/{len(routines)} routines"
        if folder_name and folder_id and success_count > 0:
            msg += f" to '{folder_name}'"
        if errors:
            msg += f" | Issues: {'; '.join(errors[:3])}"  # Show first 3 errors

        return msg

    except json.JSONDecodeError as je:
        return f"Error: Invalid JSON format - {str(je)}"
    except requests.exceptions.RequestException as re:
        return f"Network Error: {str(re)}"
    except Exception as e:
        return f"System Error: {str(e)}"

# --- MONITORING FUNCTIONS ---
def check_internet():
    try:
        subprocess.check_call(["ping", "-c", "1", "-W", "2", "8.8.8.8"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "ONLINE", "#4caf50"
    except:
        return "OFFLINE", "#f44336"

def check_git_status():
    try:
        output = subprocess.check_output(["git", "describe", "--always", "--dirty"], cwd=PROJECT_DIR).decode().strip()
        if "dirty" in output:
             return f"{output} (Unsaved)", "#ff9800"
        return output, "#98c379"
    except:
        return "Git Error", "#f44336"

def check_error_count():
    if not os.path.exists(LOG_FILE): return 0, "#98c379"
    try:
        cmd = f"tail -n 2000 {LOG_FILE} | grep -c -i -E 'ERROR|Traceback'"
        count = int(subprocess.check_output(cmd, shell=True).decode().strip())
        if count == 0:
            return "0 Found", "#98c379"
        else:
            return f"{count} ISSUES", "#f44336"
    except subprocess.CalledProcessError:
        return "0 Found", "#98c379"
    except:
        return "Scan Failed", "#ff9800"

def get_logs():
    if not os.path.exists(LOG_FILE): return ["Log file not found."]
    try:
        lines = subprocess.check_output(['tail', '-n', '30', LOG_FILE]).decode('utf-8').splitlines()
        return lines[::-1]
    except: return ["Error reading log."]

# --- HARDWARE UTILS ---
def get_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            seconds = float(f.readline().split()[0])
        return str(timedelta(seconds=int(seconds)))
    except: return "Unknown"

def get_cpu_load():
    try:
        load1, load5, _ = os.getloadavg()
        return f"{load1:.2f} / {load5:.2f}" 
    except: return "N/A"

def get_ram_usage():
    try:
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split()
                meminfo[parts[0].strip(':')] = int(parts[1])
        total = meminfo.get('MemTotal', 1)
        used = total - meminfo.get('MemAvailable', 1)
        return f"{int(used/1024)}MB / {int(total/1024)}MB ({int(used/total*100)}%)"
    except: return "N/A"

def get_poe_fan():
    try:
        with open("/sys/class/thermal/cooling_device0/cur_state", "r") as f:
            speed = int(f.read())
        return "OFF" if speed == 0 else f"ON (Lvl {speed})"
    except: return "N/A"

def get_disk_usage(path):
    try:
        if not os.path.exists(path): return "N/A"
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        used = total - (st.f_bavail * st.f_frsize)
        return f"{int(used/(1024**3))}GB / {int(total/(1024**3))}GB ({int(used/total*100)}%)"
    except: return "Error"

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read()) / 1000.0
    except: return 0

# --- SCHEDULING CORE ---
def get_next_run(interval, sched):
    now = datetime.now()
    if interval == 'hourly':
        target = now.replace(minute=sched.get('minute', 0), second=0, microsecond=0)
        if target <= now: target += timedelta(hours=1)
    elif interval == 'daily':
        target = now.replace(hour=sched.get('hour', 0), minute=sched.get('minute', 0), second=0, microsecond=0)
        if target <= now: target += timedelta(days=1)
    elif interval == 'weekly':
        cron_dow = sched.get('dow', 0)
        target_dow = (cron_dow - 1) % 7 
        target = now.replace(hour=sched.get('hour', 0), minute=sched.get('minute', 0), second=0, microsecond=0)
        days_ahead = target_dow - now.weekday()
        if days_ahead < 0: days_ahead += 7
        target += timedelta(days=days_ahead)
        if days_ahead == 0 and target <= now: target += timedelta(days=7)
    elif interval == 'monthly':
        target = now.replace(day=sched.get('day', 1), hour=sched.get('hour', 0), minute=sched.get('minute', 0), second=0, microsecond=0)
        if target <= now:
            month = 1 if now.month == 12 else now.month + 1
            year = now.year + (1 if now.month == 12 else 0)
            target = target.replace(month=month, year=year)
    return target

def analyze_task(name, config):
    filepath = config['path']
    interval = config['interval']
    
    if filepath and os.path.exists(filepath):
        mod_ts = os.path.getmtime(filepath)
        dt_mod = datetime.fromtimestamp(mod_ts)
        last_run_str = dt_mod.strftime("%b %d %H:%M")
        seconds_ago = (datetime.now() - dt_mod).total_seconds()
        exists = True
    else:
        if filepath and os.path.exists(os.path.dirname(filepath)):
            last_run_str = "NO FILE"
        else:
            last_run_str = "BAD FOLDER"
        seconds_ago = 999999999
        exists = False

    status = "STALE"
    color = "#f44336" 

    if exists:
        if interval == 'hourly':
            if seconds_ago < 172800: status, color = "UPDATED", "#4caf50"
        elif interval == 'daily':
            if seconds_ago < 259200: status, color = "UPDATED", "#4caf50"
        elif interval == 'weekly':
            if seconds_ago < 1209600: status, color = "UPDATED", "#4caf50"
        elif interval == 'monthly':
            if seconds_ago < 5184000: status, color = "UPDATED", "#4caf50"
    else:
        status = last_run_str 
        color = "#7f8c8d"

    next_dt = get_next_run(interval, config['sched'])
    if next_dt.date() == datetime.now().date():
        next_run_str = f"Today {next_dt.strftime('%H:%M')}"
    else:
        next_run_str = next_dt.strftime("%b %d %H:%M")

    return {
        "name": name,
        "last_run": last_run_str,
        "next_run": next_run_str,
        "status": status,
        "color": color,
        "debug_path": filepath
    }

# --- ROUTES ---
@app.route('/')
def home():
    internet_status, internet_color = check_internet()
    git_hash, git_color = check_git_status()
    error_count, error_color = check_error_count()

    hw = {
        "temp": get_cpu_temp(),
        "load": get_cpu_load(),
        "ram": get_ram_usage(),
        "uptime": get_uptime(),
        "fan": get_poe_fan(),
        "sd_space": get_disk_usage("/"),
        "drive_space": get_disk_usage(DRIVE_PATH),
        "internet": internet_status,
        "internet_color": internet_color,
        "git": git_hash,
        "git_color": git_color,
        "errors": error_count,
        "error_color": error_color
    }

    drive_online = os.path.ismount(DRIVE_PATH)
    drive_status = {"status": "ONLINE", "color": "#4caf50"} if drive_online else {"status": "OFFLINE", "color": "#f44336"}

    projects = [analyze_task(name, conf) for name, conf in TRACKED_FILES.items()]
    logs = get_logs()

    # Capture Flashed Messages (Success/Error alerts)
    messages = []

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pi Command Deck</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { background-color: #0f111a; color: #a0aab5; font-family: 'Courier New', monospace; padding: 15px; margin: 0;}
            h1 { text-align: center; color: #61afef; letter-spacing: 2px; margin-bottom: 20px; font-weight: bold;}
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 15px; }
            .card { background-color: #1a1e28; padding: 15px; border-radius: 8px; border: 1px solid #282c34; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            .card h2 { color: #e06c75; margin-top: 0; border-bottom: 1px solid #3e4451; padding-bottom: 10px; font-size: 1.1em; text-transform: uppercase;}
            
            .hw-row { display: flex; justify-content: space-between; margin-bottom: 8px; align-items: center; border-bottom: 1px solid #232730; padding-bottom: 4px;}
            .val { color: #98c379; font-weight: bold; }
            
            table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
            th { text-align: left; color: #5c6370; padding-bottom: 8px; border-bottom: 1px solid #3e4451; }
            td { padding: 8px 0; border-bottom: 1px solid #232730; vertical-align: middle;}
            .status-badge { padding: 2px 6px; border-radius: 4px; color: #1a1e28; font-weight: bold; font-size: 0.8em; cursor: help;}
            
            .run-btn { 
                background-color: #3e4451; color: #fff; border: none; padding: 4px 10px; 
                border-radius: 3px; cursor: pointer; font-family: inherit; font-size: 0.8em; 
                transition: background 0.2s;
            }
            .run-btn:hover { background-color: #61afef; }

            .log-box { 
                background: #0b0d12; color: #abb2bf; padding: 10px; border-radius: 4px; font-size: 0.75em; 
                height: 350px; overflow-y: auto; border: 1px solid #282c34;
                display: flex; flex-direction: column; 
            }
            .log-line { margin-bottom: 4px; border-bottom: 1px solid #1c2129; padding-bottom: 2px; }
            .temp-gauge { color: {{ '#f44336' if hw.temp > 70 else '#98c379' }}; }
            
            /* Form Styles */
            input[type=text], textarea {
                width: 100%; background: #0b0d12; border: 1px solid #3e4451; color: #fff; 
                padding: 8px; border-radius: 4px; box-sizing: border-box; margin-bottom: 10px; font-family: inherit;
            }
            .upload-btn {
                background-color: #98c379; color: #1a1e28; width: 100%; font-weight: bold; padding: 10px;
                border: none; border-radius: 4px; cursor: pointer;
            }
            .upload-btn:hover { background-color: #7da560; }
        </style>
    </head>
    <body>
        <h1>COMMAND LINE // PI DASHBOARD</h1>
        
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div style="background: #21252b; border: 1px solid #61afef; color: #61afef; padding: 10px; margin-bottom: 15px; border-radius: 4px; text-align: center;">
              {% for message in messages %}
                {{ message }}<br>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}
        
        <div class="grid">
            <div class="card">
                <h2>System Vitals</h2>
                <div class="hw-row">
                    <span>Internet</span> 
                    <span style="color: {{ hw.internet_color }}; font-weight: bold;">{{ hw.internet }}</span>
                </div>
                <div class="hw-row">
                    <span>Git Version</span> 
                    <span style="color: {{ hw.git_color }}; font-weight: bold;">{{ hw.git }}</span>
                </div>
                <div class="hw-row">
                    <span>Log Errors (24h)</span> 
                    <span style="color: {{ hw.error_color }}; font-weight: bold;">{{ hw.errors }}</span>
                </div>
                <hr style="border: 0; border-top: 1px solid #333; margin: 10px 0;">
                <div class="hw-row"><span>Uptime</span> <span class="val">{{ hw.uptime }}</span></div>
                <div class="hw-row"><span>CPU Temp</span> <span class="val temp-gauge">{{ hw.temp }}°C</span></div>
                <div class="hw-row"><span>CPU Load</span> <span class="val">{{ hw.load }}</span></div>
                <div class="hw-row"><span>RAM</span> <span class="val">{{ hw.ram }}</span></div>
                <div class="hw-row"><span>Storage (SD)</span> <span class="val">{{ hw.sd_space }}</span></div>
                <div class="hw-row">
                    <span>Drive Mount</span> 
                    <span style="color: {{ drive_status.color }}; font-weight: bold;">{{ drive_status.status }}</span>
                </div>
            </div>

            <div class="card">
                <h2>Mission Status</h2>
                <table>
                    <thead>
                        <tr>
                            <th>TASK</th>
                            <th>LAST FILE UPDATE</th>
                            <th style="text-align: right;">STATUS</th>
                            <th style="text-align: right;">ACTION</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in projects %}
                        <tr>
                            <td style="color: #e5c07b;">
                                {{ p.name }}<br>
                                <span style="font-size: 0.8em; opacity: 0.5;">Next: {{ p.next_run }}</span>
                            </td>
                            <td>{{ p.last_run }}</td>
                            <td style="text-align: right;">
                                <span class="status-badge" style="background-color: {{ p.color }};" title="Path: {{ p.debug_path }}">{{ p.status }}</span>
                            </td>
                            <td style="text-align: right;">
                                <form action="/run_task" method="POST" style="display: inline;">
                                    <input type="hidden" name="task_name" value="{{ p.name }}">
                                    <button type="submit" class="run-btn">RUN</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h2>Hevy JSON Uploader</h2>
                <form action="/upload_hevy" method="POST" onsubmit="return validateJSON()">
                    <label style="font-size: 0.9em; color: #abb2bf;">Folder Name (optional):</label>
                    <input type="text" name="folder_name" id="folder_name" value="Dashboard Uploads" placeholder="Leave empty for no folder">

                    <label style="font-size: 0.9em; color: #abb2bf;">Paste JSON Routine:</label>
                    <textarea name="json_data" id="json_data" rows="10" placeholder='{"routines": [{"title": "Chest Day", "exercises": [...]}]}' required oninput="updateCharCount()"></textarea>

                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <span id="char_count" style="font-size: 0.8em; color: #5c6370;">0 characters</span>
                        <span id="validation_msg" style="font-size: 0.8em; color: #e06c75;"></span>
                    </div>

                    <button type="button" onclick="insertExample()" style="background: #3e4451; color: #fff; border: none; padding: 6px 12px; border-radius: 3px; cursor: pointer; margin-bottom: 10px; width: 100%;">Insert Example JSON</button>

                    <button type="submit" class="upload-btn">UPLOAD TO HEVY</button>
                </form>

                <script>
                    function updateCharCount() {
                        const text = document.getElementById('json_data').value;
                        document.getElementById('char_count').textContent = text.length + ' characters';

                        // Clear validation message while typing
                        document.getElementById('validation_msg').textContent = '';
                    }

                    function validateJSON() {
                        const jsonText = document.getElementById('json_data').value;
                        const validationMsg = document.getElementById('validation_msg');

                        try {
                            const data = JSON.parse(jsonText);
                            let routines = [];

                            // Handle different formats
                            if (typeof data === 'object' && !Array.isArray(data)) {
                                routines = data.routines || [];
                            } else if (Array.isArray(data)) {
                                // Check for {routine: {...}} wrapper
                                if (data.length > 0 && data[0].routine) {
                                    routines = data.map(item => item.routine);
                                } else {
                                    routines = data;
                                }
                            }

                            if (routines.length === 0) {
                                validationMsg.textContent = 'Error: No routines found';
                                validationMsg.style.color = '#e06c75';
                                return false;
                            }

                            validationMsg.textContent = '✓ Valid JSON - ' + routines.length + ' routine(s)';
                            validationMsg.style.color = '#98c379';
                            return true;

                        } catch (e) {
                            validationMsg.textContent = 'Invalid JSON: ' + e.message;
                            validationMsg.style.color = '#e06c75';
                            return false;
                        }
                    }

                    function insertExample() {
                        const example = {
                            "routines": [
                                {
                                    "title": "Example Workout",
                                    "exercises": [
                                        {
                                            "title": "Bench Press",
                                            "sets": [
                                                {"weight_kg": 60, "reps": 10},
                                                {"weight_kg": 70, "reps": 8},
                                                {"weight_kg": 80, "reps": 6}
                                            ]
                                        }
                                    ]
                                }
                            ]
                        };
                        document.getElementById('json_data').value = JSON.stringify(example, null, 2);
                        updateCharCount();
                    }
                </script>
            </div>

            <div class="card" style="grid-column: 1 / -1;">
                <h2>System Logs (Newest First)</h2>
                <div class="log-box">
                    {% for line in logs %}
                    <div class="log-line">{{ line }}</div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, hw=hw, drive_status=drive_status, projects=projects, logs=logs)

@app.route('/run_task', methods=['POST'])
def run_task():
    task_name = request.form.get('task_name')
    if task_name in TRACKED_FILES:
        cmd = TRACKED_FILES[task_name].get('command')
        if cmd:
            subprocess.Popen(cmd, shell=True)
            time.sleep(0.5)
    return redirect(url_for('home'))

@app.route('/upload_hevy', methods=['POST'])
def upload_hevy():
    folder_name = request.form.get('folder_name')
    json_data = request.form.get('json_data')
    
    result_msg = upload_routine_json(json_data, folder_name)
    flash(result_msg) # Send message to home page
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)