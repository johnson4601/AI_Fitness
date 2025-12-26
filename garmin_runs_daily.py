import garth
from garminconnect import Garmin
from datetime import date, timedelta
import csv
import os
from dotenv import load_dotenv

# --- CONFIGURATION VIA ENVIRONMENT ---
load_dotenv()
SAVE_PATH = os.getenv("SAVE_PATH")

if SAVE_PATH:
    CSV_FILE = os.path.join(SAVE_PATH, "garmin_runs.csv")
else:
    print("WARNING: SAVE_PATH not set in .env. Using current folder.")
    CSV_FILE = "garmin_runs.csv"

TOKEN_DIR = ".garth"
# -------------------------------------

def format_pace(speed_mps):
    if not speed_mps or speed_mps <= 0: return None
    mins_per_mile = 26.8224 / speed_mps
    minutes = int(mins_per_mile)
    seconds = int((mins_per_mile - minutes) * 60)
    return f"{minutes}:{seconds:02d}"

def main():
    # 1. Load Existing Data
    existing_ids = set()
    
    # Ensure folder exists
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

                title = act.get('activityName', 'Run')
                dist_m = act.get('distance', 0)
                dist_mi = round(dist_m * 0.000621371, 2)
                dur_s = act.get('duration', 0)
                dur_min = round(dur_s / 60, 2)
                speed_mps = act.get('averageSpeed', 0)
                avg_pace = format_pace(speed_mps)
                hr = act.get('averageHR')
                max_hr = act.get('maxHR')
                cadence = act.get('averageRunningCadenceInStepsPerMinute')
                elev_m = act.get('totalElevationGain', 0)
                elev_ft = round(elev_m * 3.28084, 0) if elev_m else 0
                aero_te = act.get('aerobicTrainingEffect')
                ana_te = act.get('anaerobicTrainingEffect')
                cal = act.get('calories')

                new_rows.append([
                    date_str, time_str, title, dist_mi, dur_min, 
                    avg_pace, hr, max_hr, cadence, elev_ft, aero_te, ana_te, cal
                ])
        
        if new_rows:
            is_new = not os.path.isfile(CSV_FILE)
            with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if is_new:
                     writer.writerow(["Date", "Time", "Title", "Distance (mi)", "Duration (min)", "Avg Pace", "Avg HR", "Max HR", "Cadence", "Elevation Gain (ft)", "Aerobic TE", "Anaerobic TE", "Calories"])
                writer.writerows(new_rows)
            print(f"SUCCESS: Added {len(new_rows)} new runs.")
        else:
            print("No new runs found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()