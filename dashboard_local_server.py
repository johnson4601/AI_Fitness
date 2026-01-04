import os
import sys
import time
import subprocess
import json
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

# Paths
DRIVE_PATH = os.getenv("DRIVE_MOUNT_PATH", "/home/pi/GDrive")
SAVE_PATH = os.getenv("SAVE_PATH", "/home/pi/GDrive/Gemini Gems/Personal trainer")
BACKUP_PATH = os.path.join(DRIVE_PATH, "Backups")

# Project paths (with sensible defaults)
PROJECT_DIR = os.getenv("PROJECT_DIR", os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.getenv("LOG_FILE", "/home/pi/cron_log.txt")
HEVY_API_KEY = os.getenv("HEVY_API_KEY")

# For prompt file
if os.path.exists(PROJECT_DIR):
    PROMPT_FILE = os.path.join(PROJECT_DIR, "MONTHLY_PROMPT_TEXT.txt")
else:
    PROMPT_FILE = os.path.join(os.getcwd(), "MONTHLY_PROMPT_TEXT.txt")

# CSV file paths
HEVY_STATS_FILE = os.path.join(SAVE_PATH, "hevy_stats.csv")
GARMIN_STATS_FILE = os.path.join(SAVE_PATH, "garmin_stats.csv")
GARMIN_RUNS_FILE = os.path.join(SAVE_PATH, "garmin_runs.csv")
HEVY_EXERCISES_FILE = os.path.join(SAVE_PATH, "HEVY APP exercises.csv")

# Tracked Files & Commands (using environment-based paths)
TRACKED_FILES = {
    "Garmin Health": {
        "path": os.path.join(SAVE_PATH, "garmin_stats.csv"),
        "interval": "hourly",
        "sched": {"minute": 30},
        "command": f"cd {PROJECT_DIR} && /usr/bin/python3 daily_garmin_health.py >> {LOG_FILE} 2>&1"
    },
    "Hevy Workouts": {
        "path": os.path.join(SAVE_PATH, "hevy_stats.csv"),
        "interval": "hourly",
        "sched": {"minute": 35},
        "command": f"cd {PROJECT_DIR} && /usr/bin/python3 daily_hevy_workouts.py >> {LOG_FILE} 2>&1"
    },
    "Garmin Runs": {
        "path": os.path.join(SAVE_PATH, "garmin_runs.csv"),
        "interval": "hourly",
        "sched": {"minute": 40},
        "command": f"cd {PROJECT_DIR} && /usr/bin/python3 daily_garmin_runs.py >> {LOG_FILE} 2>&1"
    },
    "Hevy Ticker": {
        "path": os.path.join(os.path.dirname(PROJECT_DIR), "Hevy_Ticker", "ticker.log"),
        "interval": "hourly",
        "sched": {"minute": 45},
        "command": f"cd {os.path.join(os.path.dirname(PROJECT_DIR), 'Hevy_Ticker')} && /usr/bin/python3 Hevy_Ticker.py >> {LOG_FILE} 2>&1"
    },
    "System Maint": {
        "path": os.path.join(PROJECT_DIR, "update.log"),
        "interval": "daily",
        "sched": {"hour": 4, "minute": 0},
        "command": f"{os.path.join(PROJECT_DIR, 'update.sh')} >> {LOG_FILE} 2>&1"
    },
    "System Backup": {
        "path": BACKUP_PATH,
        "interval": "weekly",
        "sched": {"dow": 0, "hour": 3, "minute": 0},
        "command": f"{os.path.join(os.path.dirname(PROJECT_DIR), 'system_backup.sh')} >> {LOG_FILE} 2>&1"
    },
    "Monthly AI Plan": {
        "path": os.path.join(PROJECT_DIR, "Gemini_Hevy.py"),
        "interval": "monthly",
        "sched": {"day": 1, "hour": 1, "minute": 0},
        "command": f"cd {PROJECT_DIR} && {os.path.join(PROJECT_DIR, 'venv', 'bin', 'python')} Gemini_Hevy.py >> {LOG_FILE} 2>&1"
    }
}

# Exercise to muscle group mapping
MUSCLE_GROUP_MAP = {
    # Shoulders
    'shoulder': 'Shoulders',
    'lateral raise': 'Shoulders',
    'rear delt': 'Shoulders',
    'front raise': 'Shoulders',
    'shrug': 'Shoulders',
    'face pull': 'Shoulders',
    # Chest
    'bench press': 'Chest',
    'chest': 'Chest',
    'pec': 'Chest',
    'fly': 'Chest',
    'push up': 'Chest',
    'pushup': 'Chest',
    # Back
    'row': 'Back',
    'lat pulldown': 'Back',
    'pull up': 'Back',
    'pullup': 'Back',
    'deadlift': 'Back',
    'back extension': 'Back',
    # Arms - Biceps
    'bicep': 'Biceps',
    'curl': 'Biceps',
    'hammer curl': 'Biceps',
    # Arms - Triceps
    'tricep': 'Triceps',
    'pushdown': 'Triceps',
    'skull crusher': 'Triceps',
    'dip': 'Triceps',
    # Legs - Quads
    'squat': 'Quads',
    'leg press': 'Quads',
    'leg extension': 'Quads',
    'lunge': 'Quads',
    # Legs - Hamstrings
    'leg curl': 'Hamstrings',
    'romanian deadlift': 'Hamstrings',
    'rdl': 'Hamstrings',
    # Legs - Glutes
    'hip thrust': 'Glutes',
    'glute': 'Glutes',
    'hip abduction': 'Glutes',
    'hip adduction': 'Glutes',
    # Calves
    'calf': 'Calves',
    # Core
    'ab': 'Core',
    'crunch': 'Core',
    'plank': 'Core',
    'core': 'Core',
}

# Cardio exercises to filter out of strength training charts
CARDIO_KEYWORDS = ['stair', 'treadmill', 'bike', 'elliptical', 'run', 'cardio', 'walk']


def get_muscle_group(exercise_name):
    """Map exercise name to muscle group"""
    name_lower = exercise_name.lower()
    for keyword, muscle in MUSCLE_GROUP_MAP.items():
        if keyword in name_lower:
            return muscle
    return 'Other'


def is_cardio_exercise(exercise_name):
    """Check if exercise is cardio-based"""
    name_lower = exercise_name.lower()
    return any(keyword in name_lower for keyword in CARDIO_KEYWORDS)


# --- DATA LOADING FUNCTIONS ---
@st.cache_data(ttl=300)
def load_hevy_data():
    """Load and prepare hevy workout data"""
    if not os.path.exists(HEVY_STATS_FILE):
        return None
    try:
        df = pd.read_csv(HEVY_STATS_FILE)
        df['Date'] = pd.to_datetime(df['Date'])
        df['primary_muscle_group'] = df['Exercise'].apply(get_muscle_group)
        df['is_cardio'] = df['Exercise'].apply(is_cardio_exercise)
        df['Volume'] = df['Weight (lbs)'].fillna(0) * df['Reps'].fillna(0)
        return df
    except Exception as e:
        st.error(f"Error loading Hevy data: {e}")
        return None


@st.cache_data(ttl=300)
def load_garmin_data():
    """Load and prepare garmin health data"""
    if not os.path.exists(GARMIN_STATS_FILE):
        return None
    try:
        df = pd.read_csv(GARMIN_STATS_FILE)
        # Handle mixed date formats (ISO and US format)
        df['Date'] = pd.to_datetime(df['Date'], format='mixed', dayfirst=False)
        # Remove duplicate dates, keeping the last entry
        df = df.drop_duplicates(subset=['Date'], keep='last')
        df = df.sort_values('Date').reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error loading Garmin data: {e}")
        return None


@st.cache_data(ttl=300)
def load_garmin_runs():
    """Load garmin running data"""
    if not os.path.exists(GARMIN_RUNS_FILE):
        return None
    try:
        df = pd.read_csv(GARMIN_RUNS_FILE)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        st.error(f"Error loading Garmin runs data: {e}")
        return None


# --- HEVY API FUNCTIONS ---
def get_or_create_hevy_folder(folder_name):
    headers = {"api-key": HEVY_API_KEY, "Content-Type": "application/json"}
    try:
        res = requests.get("https://api.hevyapp.com/v1/routine_folders", headers=headers)
        if res.status_code == 200:
            for folder in res.json().get('routine_folders', []):
                if folder['title'] == folder_name:
                    return folder['id']
        payload = {"routine_folder": {"title": folder_name}}
        res = requests.post("https://api.hevyapp.com/v1/routine_folders", headers=headers, json=payload)
        if res.status_code in [200, 201]:
            return res.json()['routine_folder']['id']
    except Exception as e:
        st.error(f"Hevy API Error: {e}")
    return None


def upload_routine_json(json_data, folder_name):
    if not HEVY_API_KEY:
        return "Error: HEVY_API_KEY missing in .env"
    try:
        data = json.loads(json_data)
        if isinstance(data, dict):
            routines = data.get('routines', [])
        elif isinstance(data, list):
            if data and isinstance(data[0], dict) and 'routine' in data[0]:
                routines = [item['routine'] for item in data]
            else:
                routines = data
        else:
            routines = []

        if not routines:
            return "Error: No routines found in JSON"

        folder_id = None
        if folder_name and folder_name.strip():
            folder_id = get_or_create_hevy_folder(folder_name)
            if not folder_id:
                return "Error: Could not create/access folder on Hevy."

        headers = {"api-key": HEVY_API_KEY, "Content-Type": "application/json"}
        success_count = 0
        errors = []

        for idx, routine in enumerate(routines):
            payload = {"routine": routine}
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

        msg = f"Uploaded {success_count}/{len(routines)} routines"
        if folder_name and folder_id and success_count > 0:
            msg += f" to '{folder_name}'"
        if errors:
            msg += f" | Issues: {'; '.join(errors[:3])}"
        return msg

    except json.JSONDecodeError as je:
        return f"Error: Invalid JSON - {str(je)}"
    except requests.exceptions.RequestException as re:
        return f"Network Error: {str(re)}"
    except Exception as e:
        return f"System Error: {str(e)}"


# --- SYSTEM MONITORING FUNCTIONS ---
def check_internet():
    try:
        subprocess.check_call(["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "ONLINE", "green"
    except:
        return "OFFLINE", "red"


def check_git_status():
    try:
        output = subprocess.check_output(["git", "describe", "--always", "--dirty"],
                                         cwd=PROJECT_DIR).decode().strip()
        if "dirty" in output:
            return f"{output} (Unsaved)", "orange"
        return output, "green"
    except:
        return "Git Error", "red"


def check_error_count():
    if not os.path.exists(LOG_FILE):
        return 0, "green"
    try:
        cmd = f"tail -n 2000 {LOG_FILE} | grep -c -i -E 'ERROR|Traceback'"
        count = int(subprocess.check_output(cmd, shell=True).decode().strip())
        if count == 0:
            return "0 Found", "green"
        else:
            return f"{count} ISSUES", "red"
    except subprocess.CalledProcessError:
        return "0 Found", "green"
    except:
        return "Scan Failed", "orange"


def get_logs():
    if not os.path.exists(LOG_FILE):
        return ["Log file not found."]
    try:
        lines = subprocess.check_output(['tail', '-n', '30', LOG_FILE]).decode('utf-8').splitlines()
        return lines[::-1]
    except:
        return ["Error reading log."]


def get_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            seconds = float(f.readline().split()[0])
        return str(timedelta(seconds=int(seconds)))
    except:
        return "Unknown"


def get_cpu_load():
    try:
        load1, load5, _ = os.getloadavg()
        return f"{load1:.2f} / {load5:.2f}"
    except:
        return "N/A"


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
    except:
        return "N/A"


def get_poe_fan():
    try:
        with open("/sys/class/thermal/cooling_device0/cur_state", "r") as f:
            speed = int(f.read())
        return "OFF" if speed == 0 else f"ON (Lvl {speed})"
    except:
        return "N/A"


def get_disk_usage(path):
    try:
        if not os.path.exists(path):
            return "N/A"
        st_fs = os.statvfs(path)
        total = st_fs.f_blocks * st_fs.f_frsize
        used = total - (st_fs.f_bavail * st_fs.f_frsize)
        return f"{int(used/(1024**3))}GB / {int(total/(1024**3))}GB ({int(used/total*100)}%)"
    except:
        return "Error"


def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read()) / 1000.0
    except:
        return 0


# --- SCHEDULING FUNCTIONS ---
def get_next_run(interval, sched):
    now = datetime.now()
    if interval == 'hourly':
        target = now.replace(minute=sched.get('minute', 0), second=0, microsecond=0)
        if target <= now:
            target += timedelta(hours=1)
    elif interval == 'daily':
        target = now.replace(hour=sched.get('hour', 0), minute=sched.get('minute', 0), second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
    elif interval == 'weekly':
        cron_dow = sched.get('dow', 0)
        target_dow = (cron_dow - 1) % 7
        target = now.replace(hour=sched.get('hour', 0), minute=sched.get('minute', 0), second=0, microsecond=0)
        days_ahead = target_dow - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        target += timedelta(days=days_ahead)
        if days_ahead == 0 and target <= now:
            target += timedelta(days=7)
    elif interval == 'monthly':
        target = now.replace(day=sched.get('day', 1), hour=sched.get('hour', 0),
                             minute=sched.get('minute', 0), second=0, microsecond=0)
        if target <= now:
            month = 1 if now.month == 12 else now.month + 1
            year = now.year + (1 if now.month == 12 else 0)
            target = target.replace(month=month, year=year)
    else:
        target = now
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
    color = "red"

    if exists:
        if interval == 'hourly':
            if seconds_ago < 172800:
                status, color = "UPDATED", "green"
        elif interval == 'daily':
            if seconds_ago < 259200:
                status, color = "UPDATED", "green"
        elif interval == 'weekly':
            if seconds_ago < 1209600:
                status, color = "UPDATED", "green"
        elif interval == 'monthly':
            if seconds_ago < 5184000:
                status, color = "UPDATED", "green"
    else:
        status = last_run_str
        color = "gray"

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
        "command": config.get('command', '')
    }


# --- PROMPT EDITOR FUNCTIONS ---
def load_prompt_content():
    try:
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return "ERROR: Prompt file not found at " + PROMPT_FILE
    except Exception as e:
        return f"ERROR: Could not read prompt file: {e}"


def save_prompt_content(content):
    try:
        with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, "Prompt saved successfully!"
    except Exception as e:
        return False, f"ERROR: Could not save prompt: {e}"


# --- STREAMLIT APP ---
st.set_page_config(
    page_title="Fitness Command Center",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    .stMetric {
        background-color: #1a1e28;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #282c34;
    }
    .status-updated { color: #4caf50; font-weight: bold; }
    .status-stale { color: #f44336; font-weight: bold; }
    .status-gray { color: #7f8c8d; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: Date Range Filter ---
st.sidebar.title("Filters")
st.sidebar.markdown("---")

# Date range filter
default_end = datetime.now().date()
default_start = default_end - timedelta(days=30)

date_range = st.sidebar.date_input(
    "Date Range",
    value=(default_start, default_end),
    max_value=default_end,
    key="date_range"
)

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, default_end

start_datetime = pd.Timestamp(start_date)
end_datetime = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

st.sidebar.markdown("---")
st.sidebar.info(f"Showing data from {start_date} to {end_date}")

# Chart options
st.sidebar.markdown("---")
st.sidebar.subheader("Chart Options")
show_trend_lines = st.sidebar.checkbox("Show Trend Lines", value=True, help="Overlay smooth average trend lines on charts")

# --- MAIN CONTENT ---
st.title("Fitness Command Center")

# Create tabs for fitness data
tab1, tab2, tab3 = st.tabs(["Training (Hevy)", "Recovery (Garmin)", "System & Tools"])

# --- TAB 1: Training (Hevy) ---
with tab1:
    hevy_df = load_hevy_data()

    if hevy_df is None:
        st.warning("Hevy workout data file not found. Please check the file path.")
    else:
        # Filter by date range
        mask = (hevy_df['Date'] >= start_datetime) & (hevy_df['Date'] <= end_datetime)
        filtered_hevy = hevy_df[mask].copy()

        if filtered_hevy.empty:
            st.warning("No workout data found for the selected date range.")
        else:
            # Metric Cards
            col1, col2, col3, col4 = st.columns(4)

            # Count unique workout sessions (unique Date + Workout combinations)
            total_workouts = filtered_hevy.groupby(['Date', 'Workout']).ngroups
            total_volume = filtered_hevy['Volume'].sum()
            total_sets = len(filtered_hevy)
            unique_exercises = filtered_hevy['Exercise'].nunique()

            with col1:
                st.metric("Total Workouts", total_workouts)
            with col2:
                st.metric("Total Volume", f"{total_volume:,.0f} lbs")
            with col3:
                st.metric("Total Sets", total_sets)
            with col4:
                st.metric("Unique Exercises", unique_exercises)

            st.markdown("---")

            # Charts Row
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.subheader("Volume Progression")
                # Calculate weekly volume
                weekly_volume = filtered_hevy.copy()
                weekly_volume['Week'] = weekly_volume['Date'].dt.to_period('W').dt.start_time
                weekly_agg = weekly_volume.groupby('Week')['Volume'].sum().reset_index()

                fig_volume = go.Figure()

                # Main line
                fig_volume.add_trace(go.Scatter(
                    x=weekly_agg['Week'],
                    y=weekly_agg['Volume'],
                    mode='lines+markers',
                    name='Weekly Volume',
                    line=dict(color='#61afef'),
                    marker=dict(color='#98c379')
                ))

                # Add trend line if enabled
                if show_trend_lines and len(weekly_agg) >= 3:
                    # Calculate rolling average for smooth trend
                    window = min(4, len(weekly_agg))
                    weekly_agg['Trend'] = weekly_agg['Volume'].rolling(window=window, center=True, min_periods=1).mean()
                    fig_volume.add_trace(go.Scatter(
                        x=weekly_agg['Week'],
                        y=weekly_agg['Trend'],
                        mode='lines',
                        name='Trend (4-week avg)',
                        line=dict(color='#e5c07b', dash='dash', width=2)
                    ))

                fig_volume.update_layout(
                    title="Weekly Training Volume (Weight x Reps)",
                    xaxis_title="Week",
                    yaxis_title="Volume (lbs)",
                    template="plotly_dark",
                    height=400,
                    legend=dict(x=0.5, y=1.1, xanchor='center', orientation='h')
                )
                st.plotly_chart(fig_volume, use_container_width=True)

            with chart_col2:
                st.subheader("Muscle Group Split")
                # Filter out cardio from muscle group analysis
                strength_only = filtered_hevy[~filtered_hevy['is_cardio']].copy()
                muscle_volume = strength_only.groupby('primary_muscle_group')['Volume'].sum().reset_index()
                muscle_volume = muscle_volume.sort_values('Volume', ascending=False)

                fig_muscle = px.pie(
                    muscle_volume,
                    values='Volume',
                    names='primary_muscle_group',
                    title="Volume per Muscle Group (lbs)",
                    hole=0.4
                )
                fig_muscle.update_layout(
                    template="plotly_dark",
                    height=400
                )
                st.plotly_chart(fig_muscle, use_container_width=True)

            # Additional muscle group bar chart
            st.subheader("Muscle Group Distribution")
            fig_bar = px.bar(
                muscle_volume,
                x='primary_muscle_group',
                y='Volume',
                title="Total Volume by Muscle Group (Strength Training Only)",
                color='Volume',
                color_continuous_scale='Blues'
            )
            fig_bar.update_layout(
                xaxis_title="Muscle Group",
                yaxis_title="Volume (lbs)",
                template="plotly_dark",
                height=350
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            # TODO: Muscle Heat Map Visualization (disabled - needs mannequin-style body map)
            # muscle_dict = dict(zip(muscle_volume['primary_muscle_group'], muscle_volume['Volume']))

            # --- CARDIO SECTION ---
            st.markdown("---")
            st.subheader("Cardio Training (Garmin Runs)")

            runs_df = load_garmin_runs()
            if runs_df is not None:
                # Filter by date range
                runs_mask = (runs_df['Date'] >= start_datetime) & (runs_df['Date'] <= end_datetime)
                filtered_runs = runs_df[runs_mask].copy()

                if not filtered_runs.empty:
                    # Cardio metrics
                    cardio_col1, cardio_col2, cardio_col3, cardio_col4 = st.columns(4)

                    total_runs = len(filtered_runs)
                    # Calculate distance from speed and duration if distance column doesn't exist
                    if 'distance' in filtered_runs.columns:
                        total_distance = filtered_runs['distance'].sum() / 1000  # Convert to km
                    elif 'averageSpeed' in filtered_runs.columns and 'duration' in filtered_runs.columns:
                        # distance = speed * time (speed in m/s, duration in seconds)
                        filtered_runs['distance_calc'] = filtered_runs['averageSpeed'] * filtered_runs['duration']
                        total_distance = filtered_runs['distance_calc'].sum() / 1000  # Convert to km
                    else:
                        total_distance = 0

                    avg_hr = filtered_runs['averageHR'].mean() if 'averageHR' in filtered_runs.columns else 0
                    avg_duration = filtered_runs['duration'].mean() / 60 if 'duration' in filtered_runs.columns else 0  # Convert to minutes

                    with cardio_col1:
                        st.metric("Total Runs", total_runs)
                    with cardio_col2:
                        st.metric("Total Distance", f"{total_distance:.1f} km")
                    with cardio_col3:
                        st.metric("Avg Heart Rate", f"{avg_hr:.0f} bpm" if pd.notna(avg_hr) else "N/A")
                    with cardio_col4:
                        st.metric("Avg Duration", f"{avg_duration:.1f} min" if pd.notna(avg_duration) else "N/A")

                    # Cardio charts
                    cardio_chart_col1, cardio_chart_col2 = st.columns(2)

                    with cardio_chart_col1:
                        # Distance over time
                        if 'averageSpeed' in filtered_runs.columns and 'duration' in filtered_runs.columns:
                            filtered_runs['distance_km'] = (filtered_runs['averageSpeed'] * filtered_runs['duration']) / 1000
                            fig_distance = px.bar(
                                filtered_runs,
                                x='Date',
                                y='distance_km',
                                title="Running Distance Over Time",
                                color='averageHR',
                                color_continuous_scale='Reds'
                            )
                            fig_distance.update_layout(
                                xaxis_title="Date",
                                yaxis_title="Distance (km)",
                                template="plotly_dark",
                                height=350
                            )
                            st.plotly_chart(fig_distance, use_container_width=True)

                    with cardio_chart_col2:
                        # Heart Rate Zones
                        zone_cols = ['hrTimeInZone_1', 'hrTimeInZone_2', 'hrTimeInZone_3', 'hrTimeInZone_4']
                        available_zones = [c for c in zone_cols if c in filtered_runs.columns]

                        if available_zones:
                            zone_sums = {col: filtered_runs[col].sum() / 60 for col in available_zones}  # Convert to minutes
                            zone_labels = ['Zone 1 (Easy)', 'Zone 2 (Fat Burn)', 'Zone 3 (Cardio)', 'Zone 4 (Peak)']
                            zone_data = pd.DataFrame({
                                'Zone': zone_labels[:len(available_zones)],
                                'Minutes': list(zone_sums.values())
                            })

                            fig_zones = px.pie(
                                zone_data,
                                values='Minutes',
                                names='Zone',
                                title="Heart Rate Zone Distribution (Total Minutes)",
                                hole=0.4,
                                color_discrete_sequence=['#4CAF50', '#FFC107', '#FF9800', '#F44336']
                            )
                            fig_zones.update_layout(
                                template="plotly_dark",
                                height=350
                            )
                            st.plotly_chart(fig_zones, use_container_width=True)

                    # Speed/Pace trend
                    if 'averageSpeed' in filtered_runs.columns:
                        # Convert m/s to min/km (pace)
                        filtered_runs['pace_min_km'] = 1000 / (filtered_runs['averageSpeed'] * 60)
                        fig_pace = px.line(
                            filtered_runs,
                            x='Date',
                            y='pace_min_km',
                            markers=True,
                            title="Running Pace Trend (lower is faster)"
                        )
                        fig_pace.update_layout(
                            xaxis_title="Date",
                            yaxis_title="Pace (min/km)",
                            template="plotly_dark",
                            height=300
                        )
                        fig_pace.update_traces(line_color='#e06c75', marker_color='#e5c07b')
                        st.plotly_chart(fig_pace, use_container_width=True)
                else:
                    st.info("No running data found for the selected date range.")
            else:
                st.info("Garmin runs data file not found.")


# --- TAB 2: Recovery (Garmin) ---
with tab2:
    garmin_df = load_garmin_data()

    if garmin_df is None:
        st.warning("Garmin health data file not found. Please check the file path.")
    else:
        # Filter by date range
        mask = (garmin_df['Date'] >= start_datetime) & (garmin_df['Date'] <= end_datetime)
        filtered_garmin = garmin_df[mask].copy()

        if filtered_garmin.empty:
            st.warning("No Garmin data found for the selected date range.")
        else:
            # Metric Cards
            col1, col2, col3, col4 = st.columns(4)

            avg_sleep = filtered_garmin['Sleep Score'].mean()

            # Calculate HRV properly - check if column exists and has any non-null values
            if 'HRV Avg' in filtered_garmin.columns:
                hrv_values = filtered_garmin['HRV Avg'].dropna()
                avg_hrv = hrv_values.mean() if not hrv_values.empty else None
            else:
                avg_hrv = None

            avg_rhr = filtered_garmin['RHR'].mean() if 'RHR' in filtered_garmin.columns else None
            avg_steps = filtered_garmin['Steps'].mean() if 'Steps' in filtered_garmin.columns else None

            with col1:
                st.metric("Avg Sleep Score", f"{avg_sleep:.1f}" if pd.notna(avg_sleep) else "N/A")
            with col2:
                st.metric("Avg HRV", f"{avg_hrv:.1f}" if avg_hrv is not None and pd.notna(avg_hrv) else "No data")
            with col3:
                st.metric("Avg RHR", f"{avg_rhr:.1f} bpm" if avg_rhr is not None and pd.notna(avg_rhr) else "N/A")
            with col4:
                st.metric("Avg Steps", f"{avg_steps:,.0f}" if avg_steps is not None and pd.notna(avg_steps) else "N/A")

            st.markdown("---")

            # Charts Row
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.subheader("Body Weight Trend")
                weight_data = filtered_garmin[filtered_garmin['Weight (lbs)'].notna()].copy()

                if not weight_data.empty:
                    fig_weight = go.Figure()

                    # Main weight line
                    fig_weight.add_trace(go.Scatter(
                        x=weight_data['Date'],
                        y=weight_data['Weight (lbs)'],
                        mode='lines+markers',
                        name='Weight',
                        line=dict(color='#e06c75'),
                        marker=dict(color='#e5c07b')
                    ))

                    # Add trend line if enabled
                    if show_trend_lines and len(weight_data) >= 3:
                        window = min(7, len(weight_data))
                        weight_data = weight_data.sort_values('Date')
                        weight_data['Trend'] = weight_data['Weight (lbs)'].rolling(window=window, center=True, min_periods=1).mean()
                        fig_weight.add_trace(go.Scatter(
                            x=weight_data['Date'],
                            y=weight_data['Trend'],
                            mode='lines',
                            name='Trend (7-day avg)',
                            line=dict(color='#c678dd', dash='dash', width=2)
                        ))

                    fig_weight.update_layout(
                        title="Body Weight Over Time",
                        xaxis_title="Date",
                        yaxis_title="Weight (lbs)",
                        template="plotly_dark",
                        height=400,
                        legend=dict(x=0.5, y=1.1, xanchor='center', orientation='h')
                    )
                    st.plotly_chart(fig_weight, use_container_width=True)
                else:
                    st.info("No weight data available for the selected period.")

            with chart_col2:
                st.subheader("Sleep & HRV")
                # Create multi-line chart for Sleep Score and HRV
                fig_recovery = go.Figure()

                if 'Sleep Score' in filtered_garmin.columns:
                    sleep_data = filtered_garmin[filtered_garmin['Sleep Score'].notna()].copy()
                    sleep_data = sleep_data.sort_values('Date')
                    fig_recovery.add_trace(go.Scatter(
                        x=sleep_data['Date'],
                        y=sleep_data['Sleep Score'],
                        mode='lines+markers',
                        name='Sleep Score',
                        line=dict(color='#98c379'),
                        yaxis='y'
                    ))

                    # Add sleep trend line
                    if show_trend_lines and len(sleep_data) >= 3:
                        window = min(7, len(sleep_data))
                        sleep_data['Sleep_Trend'] = sleep_data['Sleep Score'].rolling(window=window, center=True, min_periods=1).mean()
                        fig_recovery.add_trace(go.Scatter(
                            x=sleep_data['Date'],
                            y=sleep_data['Sleep_Trend'],
                            mode='lines',
                            name='Sleep Trend',
                            line=dict(color='#98c379', dash='dash', width=2),
                            yaxis='y'
                        ))

                if 'HRV Avg' in filtered_garmin.columns:
                    hrv_data = filtered_garmin[filtered_garmin['HRV Avg'].notna()].copy()
                    if not hrv_data.empty:
                        hrv_data = hrv_data.sort_values('Date')
                        fig_recovery.add_trace(go.Scatter(
                            x=hrv_data['Date'],
                            y=hrv_data['HRV Avg'],
                            mode='lines+markers',
                            name='HRV Avg',
                            line=dict(color='#61afef'),
                            yaxis='y2'
                        ))

                        # Add HRV trend line
                        if show_trend_lines and len(hrv_data) >= 3:
                            window = min(7, len(hrv_data))
                            hrv_data['HRV_Trend'] = hrv_data['HRV Avg'].rolling(window=window, center=True, min_periods=1).mean()
                            fig_recovery.add_trace(go.Scatter(
                                x=hrv_data['Date'],
                                y=hrv_data['HRV_Trend'],
                                mode='lines',
                                name='HRV Trend',
                                line=dict(color='#61afef', dash='dash', width=2),
                                yaxis='y2'
                            ))

                fig_recovery.update_layout(
                    title="Sleep Score vs HRV Average",
                    xaxis_title="Date",
                    yaxis=dict(title="Sleep Score", side='left', color='#98c379'),
                    yaxis2=dict(title="HRV Avg", side='right', overlaying='y', color='#61afef'),
                    template="plotly_dark",
                    height=400,
                    legend=dict(x=0.5, y=1.15, xanchor='center', orientation='h')
                )
                st.plotly_chart(fig_recovery, use_container_width=True)

            # Steps and RHR trends
            st.subheader("Daily Activity Metrics")
            steps_col, rhr_col = st.columns(2)

            with steps_col:
                if 'Steps' in filtered_garmin.columns:
                    steps_data = filtered_garmin[filtered_garmin['Steps'].notna()]
                    if not steps_data.empty:
                        fig_steps = px.bar(
                            steps_data,
                            x='Date',
                            y='Steps',
                            title="Daily Steps"
                        )
                        fig_steps.update_layout(
                            template="plotly_dark",
                            height=300
                        )
                        fig_steps.update_traces(marker_color='#c678dd')
                        st.plotly_chart(fig_steps, use_container_width=True)

            with rhr_col:
                if 'RHR' in filtered_garmin.columns:
                    rhr_data = filtered_garmin[filtered_garmin['RHR'].notna()]
                    if not rhr_data.empty:
                        fig_rhr = px.line(
                            rhr_data,
                            x='Date',
                            y='RHR',
                            markers=True,
                            title="Resting Heart Rate"
                        )
                        fig_rhr.update_layout(
                            template="plotly_dark",
                            height=300
                        )
                        fig_rhr.update_traces(line_color='#e06c75', marker_color='#e5c07b')
                        st.plotly_chart(fig_rhr, use_container_width=True)


# --- TAB 3: System & Tools ---
with tab3:
    # Create sub-sections
    st.header("Hevy JSON Uploader")

    with st.form("hevy_upload_form"):
        folder_name = st.text_input("Folder Name (optional)", value="Dashboard Uploads",
                                    help="Leave empty for no folder")
        json_data = st.text_area("Paste JSON Routine", height=200,
                                 placeholder='{"routines": [{"title": "Chest Day", "exercises": [...]}]}')

        col1, col2 = st.columns([1, 4])
        with col1:
            submitted = st.form_submit_button("Upload to Hevy", type="primary")

        if submitted:
            if json_data.strip():
                result = upload_routine_json(json_data, folder_name)
                if "Error" in result or "error" in result.lower():
                    st.error(result)
                else:
                    st.success(result)
            else:
                st.warning("Please paste JSON data before uploading.")

    st.markdown("---")

    # Mission Status
    st.header("Mission Status")

    tasks = [analyze_task(name, conf) for name, conf in TRACKED_FILES.items()]

    # Create task table
    task_cols = st.columns([2, 2, 2, 1, 1])
    task_cols[0].markdown("**Task**")
    task_cols[1].markdown("**Last Update**")
    task_cols[2].markdown("**Next Run**")
    task_cols[3].markdown("**Status**")
    task_cols[4].markdown("**Action**")

    for task in tasks:
        cols = st.columns([2, 2, 2, 1, 1])
        cols[0].write(task['name'])
        cols[1].write(task['last_run'])
        cols[2].write(task['next_run'])

        if task['color'] == 'green':
            cols[3].markdown(f"<span class='status-updated'>{task['status']}</span>",
                             unsafe_allow_html=True)
        elif task['color'] == 'red':
            cols[3].markdown(f"<span class='status-stale'>{task['status']}</span>",
                             unsafe_allow_html=True)
        else:
            cols[3].markdown(f"<span class='status-gray'>{task['status']}</span>",
                             unsafe_allow_html=True)

        if cols[4].button("Run", key=f"run_{task['name']}"):
            if task['command']:
                subprocess.Popen(task['command'], shell=True)
                st.toast(f"Started: {task['name']}")
                time.sleep(0.5)
                st.rerun()

    st.markdown("---")

    # System Vitals
    st.header("System Vitals")

    vitals_col1, vitals_col2, vitals_col3 = st.columns(3)

    with vitals_col1:
        internet_status, internet_color = check_internet()
        git_status, git_color = check_git_status()
        error_count, error_color = check_error_count()

        st.markdown(f"**Internet:** :{internet_color}[{internet_status}]")
        st.markdown(f"**Git Version:** :{git_color}[{git_status}]")
        st.markdown(f"**Log Errors:** :{error_color}[{error_count}]")

    with vitals_col2:
        st.markdown(f"**Uptime:** {get_uptime()}")
        cpu_temp = get_cpu_temp()
        temp_color = "red" if cpu_temp > 70 else "green"
        st.markdown(f"**CPU Temp:** :{temp_color}[{cpu_temp}C]")
        st.markdown(f"**CPU Load:** {get_cpu_load()}")

    with vitals_col3:
        st.markdown(f"**RAM:** {get_ram_usage()}")
        st.markdown(f"**Storage (SD):** {get_disk_usage('/')}")
        drive_online = os.path.ismount(DRIVE_PATH)
        drive_color = "green" if drive_online else "red"
        drive_text = "ONLINE" if drive_online else "OFFLINE"
        st.markdown(f"**Drive Mount:** :{drive_color}[{drive_text}]")

    st.markdown("---")

    # System Controls
    st.header("System Controls")

    # Initialize session state for restart confirmation
    if 'confirm_restart' not in st.session_state:
        st.session_state.confirm_restart = False
    if 'confirm_dashboard_restart' not in st.session_state:
        st.session_state.confirm_dashboard_restart = False

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(3)

    with ctrl_col1:
        if st.button("Restart Dashboard", type="secondary"):
            st.session_state.confirm_dashboard_restart = True

        if st.session_state.confirm_dashboard_restart:
            st.warning("Restart dashboard service?")
            confirm_col1, confirm_col2 = st.columns(2)
            with confirm_col1:
                if st.button("Yes, Restart Dashboard", type="primary", key="confirm_dash_restart"):
                    try:
                        subprocess.Popen(["sudo", "systemctl", "restart", "ai-fitness-dashboard.service"])
                        st.success("Dashboard restart initiated...")
                        st.session_state.confirm_dashboard_restart = False
                        time.sleep(2)
                    except Exception as e:
                        st.error(f"Error: {e}")
            with confirm_col2:
                if st.button("Cancel", key="cancel_dash_restart"):
                    st.session_state.confirm_dashboard_restart = False
                    st.rerun()

    with ctrl_col2:
        if st.button("Reboot System", type="secondary"):
            st.session_state.confirm_restart = True

        if st.session_state.confirm_restart:
            st.warning("Are you sure you want to reboot the Raspberry Pi?")
            confirm_col1, confirm_col2 = st.columns(2)
            with confirm_col1:
                if st.button("Yes, Reboot", type="primary", key="confirm_reboot"):
                    try:
                        subprocess.Popen(["sudo", "reboot"])
                        st.success("System reboot initiated...")
                        st.session_state.confirm_restart = False
                    except Exception as e:
                        st.error(f"Error: {e}")
            with confirm_col2:
                if st.button("Cancel", key="cancel_reboot"):
                    st.session_state.confirm_restart = False
                    st.rerun()

    with ctrl_col3:
        if st.button("Clear Streamlit Cache", type="secondary"):
            st.cache_data.clear()
            st.success("Cache cleared!")
            time.sleep(1)
            st.rerun()

    st.markdown("---")

    # Configuration Section
    st.header("Configuration")

    with st.expander("View/Edit Environment Settings (.env)", expanded=False):
        env_file = os.path.join(PROJECT_DIR, ".env")

        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    env_content = f.read()

                # Parse and display settings (hide passwords)
                st.markdown("**Current Settings:**")
                for line in env_content.split('\n'):
                    if line.strip() and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Mask sensitive values
                        if 'PASSWORD' in key.upper() or 'KEY' in key.upper() or 'SECRET' in key.upper():
                            if len(value) > 8:
                                display_value = value[:4] + "****" + value[-4:]
                            else:
                                display_value = "****"
                        else:
                            display_value = value
                        st.text(f"{key} = {display_value}")
            except Exception as e:
                st.error(f"Error reading .env: {e}")
        else:
            st.warning("No .env file found. Run setup.py to configure.")

        st.markdown("---")
        st.markdown("**Run Setup Script:**")
        st.code(f"cd {PROJECT_DIR} && python3 setup.py", language="bash")
        st.caption("Run this command in terminal to reconfigure settings interactively.")

    st.markdown("---")

    # Monthly Prompt Editor
    st.header("Monthly Prompt Editor")

    prompt_content = load_prompt_content()

    # Initialize session state for prompt editor
    if 'original_prompt' not in st.session_state:
        st.session_state.original_prompt = prompt_content
    if 'confirm_save' not in st.session_state:
        st.session_state.confirm_save = False

    edited_prompt = st.text_area("Edit AI Training Prompt", value=prompt_content, height=300, key="prompt_editor")

    # Check if content has changed
    has_changes = edited_prompt != st.session_state.original_prompt

    st.caption(f"File: MONTHLY_PROMPT_TEXT.txt | {len(edited_prompt)} characters" +
               (" | **Unsaved changes**" if has_changes else ""))

    col_save, col_reset = st.columns([1, 1])

    with col_save:
        if st.button("Save Prompt", type="primary", disabled=not has_changes):
            st.session_state.confirm_save = True

    with col_reset:
        if st.button("Reset Changes", disabled=not has_changes):
            st.session_state.original_prompt = prompt_content
            st.rerun()

    # Confirmation dialog
    if st.session_state.confirm_save:
        st.warning("Are you sure you want to save these changes?")
        confirm_col1, confirm_col2 = st.columns([1, 1])
        with confirm_col1:
            if st.button("Yes, Save", type="primary"):
                success, message = save_prompt_content(edited_prompt)
                if success:
                    st.session_state.original_prompt = edited_prompt
                    st.session_state.confirm_save = False
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        with confirm_col2:
            if st.button("Cancel"):
                st.session_state.confirm_save = False
                st.rerun()

    st.markdown("---")

    # System Logs
    st.header("System Logs (Newest First)")

    logs = get_logs()
    log_text = "\n".join(logs)
    st.code(log_text, language="text")

    if st.button("Refresh Logs"):
        st.rerun()
