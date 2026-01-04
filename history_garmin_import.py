import garth
from garminconnect import Garmin
from datetime import date, timedelta, datetime
import csv
import os
import time
import random

import os
import sys
import platform
from dotenv import load_dotenv

# 1. Load configuration immediately
load_dotenv()

# 2. Get the settings (with defaults for safety)
# On Raspberry Pi/Linux: Set CHECK_MOUNT_STATUS=True in .env to enable mount verification
# On Windows: Mount check is automatically skipped (unless explicitly enabled)
check_mount = os.getenv("CHECK_MOUNT_STATUS", "False").lower() == "true"
drive_path = os.getenv("DRIVE_MOUNT_PATH", "/home/pi/google_drive")

# 3. Platform-Aware Safety Check
is_windows = platform.system() == "Windows"

if check_mount and not is_windows:
    print(f"Safety Check: Verifying mount at {drive_path}...")

    if not os.path.ismount(drive_path):
        print(f"CRITICAL ERROR: Drive is not mounted at {drive_path}.")
        print("Stopping script to prevent writing to local storage.")
        sys.exit(1)
    else:
        print("Safety Check: PASSED. Drive is mounted.")
elif check_mount and is_windows:
    print("Note: Mount check skipped on Windows (not applicable).")

# ... rest of your code ...

# --- CONFIGURATION VIA ENVIRONMENT ---
SAVE_PATH = os.getenv("SAVE_PATH")

if SAVE_PATH:
    CSV_FILE = os.path.join(SAVE_PATH, "garmin_history.csv")
else:
    print("WARNING: SAVE_PATH not set in .env. Using current folder.")
    CSV_FILE = "garmin_history.csv"

TOKEN_DIR = ".garth"
START_DATE = "2025-12-12"       # <--- CHANGE THIS DATE to how far back you want to go
# ---------------------

def get_safe(data, *keys):
    try:
        for key in keys:
            data = data[key]
        return data
    except (KeyError, TypeError, AttributeError):
        return None

def main():
    # 1. Login
    try:
        garth.resume(TOKEN_DIR)
        api = Garmin("dummy", "dummy")
        api.garth = garth.client
        try:
            api.display_name = api.garth.profile['displayName']
        except:
            pass
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # 2. Setup Date Loop
    start = date.fromisoformat(START_DATE)
    end = date.today() - timedelta(days=1) # Stop at yesterday (daily script handles today)
    delta = timedelta(days=1)
    
    current_date = start
    
    print(f"--- STARTING HISTORY PULL ---")
    print(f"From {start} to {end}")
    print("Press Ctrl+C to stop at any time.")
    
    # 3. Create CSV Header
    headers = [
        "Date", 
        "Weight (lbs)", "Muscle Mass (lbs)", "Body Fat %", "Water %",
        "Sleep Total (hr)", "Sleep Deep (hr)", "Sleep REM (hr)", "Sleep Score",
        "RHR", "Min HR", "Max HR", "Avg Stress", "Respiration", "SpO2",
        "VO2 Max", "Training Status", "HRV Status", "HRV Avg",
        "Steps", "Step Goal", "Cals Total", "Cals Active",
        "Activities"
    ]
    
    # Only write header if file doesn't exist
    if not os.path.isfile(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    # 4. The Loop
    while current_date <= end:
        day_str = current_date.isoformat()
        print(f"Processing {day_str}...", end="", flush=True)

        try:
            # --- FETCH DATA (Same logic as Daily Script) ---
            # Core
            try:
                user_stats = api.get_user_summary(day_str)
                rhr = get_safe(user_stats, 'restingHeartRate')
                min_hr = get_safe(user_stats, 'minHeartRate')
                max_hr = get_safe(user_stats, 'maxHeartRate')
                stress = get_safe(user_stats, 'averageStressLevel')
                steps = get_safe(user_stats, 'totalSteps')
                vo2 = get_safe(user_stats, 'vo2Max')
                spo2 = get_safe(user_stats, 'averageSpO2')
                resp = get_safe(user_stats, 'averageRespirationValue')
                cals_tot = get_safe(user_stats, 'totalKilocalories')
                cals_act = get_safe(user_stats, 'activeKilocalories')
                cals_goal = get_safe(user_stats, 'dailyStepGoal')
            except:
                rhr, min_hr, max_hr, stress, steps, vo2, spo2, resp, cals_tot, cals_act, cals_goal = [None]*11

            # Sleep
            try:
                sleep_data = api.get_sleep_data(day_str)
                s_tot = get_safe(sleep_data, 'dailySleepDTO', 'sleepTimeSeconds')
                s_deep = get_safe(sleep_data, 'dailySleepDTO', 'deepSleepSeconds')
                s_rem = get_safe(sleep_data, 'dailySleepDTO', 'remSleepSeconds')
                s_score = get_safe(sleep_data, 'dailySleepDTO', 'sleepScores', 'overall', 'value')
                if s_tot: s_tot = round(s_tot / 3600, 2)
                if s_deep: s_deep = round(s_deep / 3600, 2)
                if s_rem: s_rem = round(s_rem / 3600, 2)
            except:
                s_tot, s_deep, s_rem, s_score = None, None, None, None

            # Training Status
            t_status = None
            try:
                if hasattr(api, 'get_training_status'):
                    ts = api.get_training_status(day_str)
                    t_status = get_safe(ts, 'mostRecentTerminatedTrainingStatus', 'status')
            except:
                pass

            # Body Comp
            wt, mus, fat, h2o = None, None, None, None
            try:
                bc = api.get_body_composition(day_str)
                if bc and 'totalAverage' in bc:
                    avg = bc['totalAverage']
                    if avg.get('weight'): wt = round(avg.get('weight')/453.592, 1)
                    if avg.get('muscleMass'): mus = round(avg.get('muscleMass')/453.592, 1)
                    fat = avg.get('bodyFat')
                    h2o = avg.get('bodyWater')
            except:
                pass

            # HRV
            hrv_s, hrv_a = None, None
            try:
                if hasattr(api, 'get_hrv_data'):
                    h = api.get_hrv_data(day_str)
                else:
                    h = api.connectapi(f"/hrv-service/hrv/daily/{day_str}")
                hrv_s = get_safe(h, 'hrvSummary', 'status')
                hrv_a = get_safe(h, 'hrvSummary', 'weeklyAverage')
            except:
                pass

            # Activities
            act_str = ""
            try:
                acts = api.get_activities_by_date(day_str, day_str)
                if acts:
                    names = [f"{a['activityName']} ({a['activityType']['typeKey']})" for a in acts]
                    act_str = "; ".join(names)
            except:
                pass

            # Write Row
            row = [
                day_str, wt, mus, fat, h2o, s_tot, s_deep, s_rem, s_score,
                rhr, min_hr, max_hr, stress, resp, spo2, vo2, t_status, hrv_s, hrv_a,
                steps, cals_goal, cals_tot, cals_act, act_str
            ]
            
            with open(CSV_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            print(" Done.")

        except Exception as e:
            print(f" Failed ({e})")

        # Increment Date & Sleep to be nice to API
        current_date += delta
        time.sleep(random.uniform(1.5, 3.0)) # Sleep 1.5 to 3 seconds

    print("--- HISTORY PULL COMPLETE ---")

if __name__ == "__main__":
    main()
