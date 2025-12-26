import requests
import csv
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv  # <--- New Import

# --- CONFIGURATION VIA ENVIRONMENT ---
# 1. Load the .env file
load_dotenv()

# 2. Get variables safely
API_KEY = os.getenv("HEVY_API_KEY")
SAVE_PATH = os.getenv("SAVE_PATH")

# 3. Construct the full file path
# This joins the folder path from .env with the filename
if SAVE_PATH:
    CSV_FILE = os.path.join(SAVE_PATH, "hevy_stats.csv")
else:
    # Fallback if someone forgets to set the .env
    print("WARNING: SAVE_PATH not found in .env. Using current directory.")
    CSV_FILE = "hevy_stats.csv"
# -------------------------------------

def main():
    # Safety Check: Did the user actually set the key?
    if not API_KEY:
        print("CRITICAL ERROR: 'HEVY_API_KEY' not found. Please create a .env file.")
        return

    headers = {
        "api-key": API_KEY,
        "Accept": "application/json"
    }
    
    # 1. READ EXISTING DATA (Smart Deduplication)
    existing_sets = set()
    
    # Check if directory exists first
    folder = os.path.dirname(CSV_FILE)
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
            print(f"Created directory: {folder}")
        except OSError:
            pass # Drive might not be mounted yet

    if os.path.isfile(CSV_FILE):
        try:
            with open(CSV_FILE, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None) # Skip header
                for row in reader:
                    if len(row) > 3:
                        # Signature: Date_Workout_Exercise_Set
                        signature = f"{row[0]}_{row[1]}_{row[2]}_{row[3]}"
                        existing_sets.add(signature)
        except Exception as e:
            print(f"Warning reading file: {e}")

    # 2. FETCH RECENT WORKOUTS
    cutoff_date = datetime.now() - timedelta(days=2)
    print(f"Checking Hevy for workouts since {cutoff_date.date()}...")
    
    url = "https://api.hevyapp.com/v1/workouts"
    params = {"page": 1, "pageSize": 10}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return

        data = response.json()
        workouts = data.get('workouts', [])
        
        if not workouts:
            print("No workouts found.")
            return

        new_rows = []
        skipped_count = 0
        
        for workout in workouts:
            w_date_str = workout.get('start_time')
            if not w_date_str: continue

            w_dt = datetime.fromisoformat(w_date_str).replace(tzinfo=None)
            
            if w_dt < cutoff_date:
                continue
            
            w_date_clean = w_dt.strftime("%Y-%m-%d")
            w_title = workout.get('title', 'Unknown Workout')

            for exercise in workout.get('exercises', []):
                ex_name = exercise.get('title', 'Unknown')
                
                for i, s in enumerate(exercise.get('sets', [])):
                    set_num = str(i + 1)
                    
                    signature = f"{w_date_clean}_{w_title}_{ex_name}_{set_num}"
                    
                    if signature in existing_sets:
                        skipped_count += 1
                        continue 
                    
                    weight_kg = s.get('weight_kg', 0)
                    weight_lbs = round(weight_kg * 2.20462, 1) if weight_kg else 0
                    
                    row = [
                        w_date_clean,
                        w_title,
                        ex_name,
                        set_num,
                        weight_lbs,
                        s.get('reps_value', 0),
                        s.get('rpe', ''),
                        s.get('set_type', 'normal')
                    ]
                    new_rows.append(row)

        # 3. SAVE ONLY NEW ROWS
        if new_rows:
            # Ensure headers exist if new file
            is_new_file = not os.path.isfile(CSV_FILE)
            
            with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if is_new_file:
                     writer.writerow(["Date", "Workout", "Exercise", "Set", "Weight (lbs)", "Reps", "RPE", "Type"])
                writer.writerows(new_rows)
            print(f"SUCCESS: Added {len(new_rows)} new sets. (Skipped {skipped_count} duplicates)")
        else:
            print(f"No *new* sets found. (Skipped {skipped_count} duplicates)")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()