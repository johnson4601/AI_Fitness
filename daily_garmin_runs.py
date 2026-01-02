import garth
from garminconnect import Garmin
from datetime import date, timedelta
import csv
import os
import sys
import json
from dotenv import load_dotenv

# 1. Load configuration
load_dotenv()

# 2. Safety Check
check_mount = os.getenv("CHECK_MOUNT_STATUS", "False").lower() == "true"
drive_path = os.getenv("DRIVE_MOUNT_PATH", "/home/pi/google_drive")

if check_mount:
    print(f"Safety Check: Verifying mount at {drive_path}...")
    if not os.path.ismount(drive_path):
        print(f"CRITICAL ERROR: Drive is not mounted at {drive_path}.")
        sys.exit(1)

# --- CONFIGURATION ---
SAVE_PATH = os.getenv("SAVE_PATH")
CSV_FILE = os.path.join(SAVE_PATH, "garmin_runs.csv") if SAVE_PATH else "garmin_runs.csv"
TOKEN_DIR = ".garth"
# ---------------------

def safe_get(data, key, default=None):
    return data.get(key, default)

def main():
    # 1. Load Existing IDs
    existing_ids = set()
    folder_path = os.path.dirname(CSV_FILE)
    if folder_path and not os.path.exists(folder_path):
        os.makedirs(folder_path)

    if os.path.isfile(CSV_FILE):
        try:
            with open(CSV_FILE, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) > 1:
                        existing_ids.add(f"{row[0]}_{row[1]}")
        except:
            pass

    # 2. Login
    try:
        garth.resume(TOKEN_DIR)
        api = Garmin("dummy", "dummy")
        api.garth = garth.client
    except Exception as e:
        print(f"Login Error: {e}")
        return

    # 3. Check Last 3 Days
    today = date.today()
    start_check = today - timedelta(days=3)
    
    print(f"Checking runs from {start_check}...")

    try:
        # Note: If you want Strength stats too, change "running" to None or check your filters
        activities = api.get_activities_by_date(start_check.isoformat(), today.isoformat(), "running")
        
        new_rows = []
        if activities:
            for act in activities:
                start_local = act.get('startTimeLocal', '')
                date_str = start_local[:10]
                time_str = start_local[11:]
                
                sig = f"{date_str}_{time_str}"
                if sig in existing_ids:
                    continue

                # --- 4. DEEP DIVE (Daily Only) ---
                # Some fields like hrTimeInZone or sets might be missing from the summary.
                # We fetch the full activity details for these few new items.
                activity_id = act.get('activityId')
                full_details = {}
                try:
                    # Attempt to fetch full details if needed (warning: adds API time)
                    # For simple runs, summary is often enough, but for zones we might need more.
                    # We will rely on summary first, if missing and critical, you could enable:
                    # full_details = api.get_activity_details(activity_id) 
                    pass 
                except:
                    pass

                # --- FIELD EXTRACTION ---
                # Basic
                title = act.get('activityName', 'Run')
                atype_key = act.get('activityType', {}).get('typeKey', 'running')
                
                # Time & Dist
                dur = act.get('duration', 0)
                elapsed = act.get('elapsedDuration', 0)
                moving = act.get('movingDuration', 0)
                
                # Speed / HR / Steps
                avg_spd = act.get('averageSpeed', 0)
                avg_hr = act.get('averageHR')
                max_hr = act.get('maxHR')
                steps = act.get('steps')
                
                # Strength / Reps (Likely 0 for runs)
                # summaries often come as a list of dicts. We JSON stringify it to fit in CSV.
                summ_sets_raw = act.get('summarizedExerciseSets')
                summ_sets_str = json.dumps(summ_sets_raw) if summ_sets_raw else ""
                
                total_sets = act.get('totalSets')
                active_sets = act.get('activeSets')
                total_reps = act.get('totalReps')
                
                # Training Load / Effect
                te_label = act.get('trainingEffectLabel')
                load = act.get('activityTrainingLoad')
                min_lap = act.get('minActivityLapDuration')

                # HR Zones (This usually requires specific extraction logic)
                # If these keys exist directly in your export data, we grab them.
                # Otherwise, we might need to look into 'userSettings' or specific zone arrays.
                # For now, we try direct access as requested:
                z1 = act.get('hrTimeInZone_1')
                z2 = act.get('hrTimeInZone_2')
                z3 = act.get('hrTimeInZone_3')
                z4 = act.get('hrTimeInZone_4')

                new_rows.append([
                    date_str, time_str, title, atype_key,
                    dur, elapsed, moving, avg_spd, avg_hr, max_hr, steps,
                    summ_sets_str, total_sets, active_sets, total_reps,
                    te_label, load, min_lap, z1, z2, z3, z4
                ])
        
        if new_rows:
            # Check if file exists to determine if we write headers
            is_new = not os.path.isfile(CSV_FILE)
            
            with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if is_new:
                     writer.writerow([
                         "Date", "Time", "activityName", "activityType_typeKey", 
                         "duration", "elapsedDuration", "movingDuration", 
                         "averageSpeed", "averageHR", "maxHR", "steps", 
                         "summarizedExerciseSets", "totalSets", "activeSets", "totalReps", 
                         "trainingEffectLabel", "activityTrainingLoad", "minActivityLapDuration", 
                         "hrTimeInZone_1", "hrTimeInZone_2", "hrTimeInZone_3", "hrTimeInZone_4"
                     ])
                writer.writerows(new_rows)
            print(f"SUCCESS: Added {len(new_rows)} new activities.")
        else:
            print("No new activities found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()