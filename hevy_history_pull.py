import requests
import csv
import os
import time
from datetime import datetime
from dotenv import load_dotenv  # <--- Loads the secret file

# --- CONFIGURATION VIA ENVIRONMENT ---
# 1. Load the secrets
load_dotenv()

# 2. Get variables safely
API_KEY = os.getenv("HEVY_API_KEY")
SAVE_PATH = os.getenv("SAVE_PATH")

# 3. Construct the path
if SAVE_PATH:
    CSV_FILE = os.path.join(SAVE_PATH, "hevy_stats.csv")
else:
    print("WARNING: SAVE_PATH not set in .env. Using current folder.")
    CSV_FILE = "hevy_stats.csv"

# Optional: You can change this here, or add START_YEAR to .env if you prefer
START_YEAR = 2023 
# -------------------------------------

def main():
    # Safety Check
    if not API_KEY:
        print("CRITICAL ERROR: 'HEVY_API_KEY' not found in .env file.")
        return

    headers = {
        "api-key": API_KEY,
        "Accept": "application/json"
    }
    
    print(f"--- STARTING HEVY HISTORY PULL (Since {START_YEAR}) ---")
    print(f"Target File: {CSV_FILE}")
    
    # 1. Create Folder if Missing (Robustness)
    folder_path = os.path.dirname(CSV_FILE)
    if folder_path and not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
            print(f"Created new folder: {folder_path}")
        except Exception as e:
            print(f"Error creating folder: {e}")
            # We continue anyway, in case it's a root drive issue
            
    # 2. Write Headers (if file is new)
    file_exists = os.path.isfile(CSV_FILE)
    if not file_exists:
        try:
            with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Workout", "Exercise", "Set", "Weight (lbs)", "Reps", "RPE", "Type"])
        except Exception as e:
            print(f"Error creating file: {e}")
            return

    page = 1
    total_sets = 0
    keep_going = True
    
    # 3. Fetch Loop
    while keep_going:
        print(f"Fetching Page {page}...", end="", flush=True)
        
        url = "https://api.hevyapp.com/v1/workouts"
        params = {"page": page, "pageSize": 10}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                print(f"\nCRITICAL ERROR: {response.status_code}")
                print(f"Server Message: {response.text}")
                break

            data = response.json()
            workouts = data.get('workouts', [])
            
            if not workouts:
                print(" No more workouts found. Done.")
                break
                
            new_rows = []
            
            for workout in workouts:
                w_date_str = workout.get('start_time')
                if not w_date_str: continue

                w_dt = datetime.fromisoformat(w_date_str).replace(tzinfo=None)
                
                # Check Year Limit
                if w_dt.year < START_YEAR:
                    print(f"\nReached {w_dt.year}. Stopping.")
                    keep_going = False
                    break
                
                w_date_clean = w_dt.strftime("%Y-%m-%d")
                w_title = workout.get('title', 'Unknown Workout')

                exercises = workout.get('exercises', [])
                for exercise in exercises:
                    ex_name = exercise.get('title', 'Unknown Exercise')
                    sets = exercise.get('sets', [])
                    
                    for i, s in enumerate(sets):
                        # SAFE GETS
                        weight_kg = s.get('weight_kg', 0)
                        weight_lbs = round(weight_kg * 2.20462, 1) if weight_kg else 0
                        s_type = s.get('set_type', 'normal') 
                        
                        row = [
                            w_date_clean, 
                            w_title, 
                            ex_name, 
                            i + 1, 
                            weight_lbs, 
                            s.get('reps_value', 0), 
                            s.get('rpe', ''), 
                            s_type
                        ]
                        new_rows.append(row)

            # 4. Save to CSV
            if new_rows:
                with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(new_rows)
                print(f" Saved {len(new_rows)} sets.")
                total_sets += len(new_rows)
            else:
                print(" (Page empty).")

            page += 1
            time.sleep(0.5) 
            
        except Exception as e:
            print(f"\nGlobal Error: {e}")
            break

    print(f"--- COMPLETE. Total Sets Saved: {total_sets} ---")

if __name__ == "__main__":
    main()