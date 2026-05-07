import os
import json
import shutil
from datetime import datetime

HISTORY_DIR = r"C:\Users\shrut\AppData\Roaming\Code\User\History"
TARGET_PROJECT = r"c:\Users\shrut\Desktop\Final_year_project"
RECOVERY_DIR = r"c:\Users\shrut\Desktop\Final_year_project_RECOVERY"

if not os.path.exists(RECOVERY_DIR):
    os.makedirs(RECOVERY_DIR)

print(f"Scanning VS Code Local History to recover: {TARGET_PROJECT}")
recovered_files = 0

for folder in os.listdir(HISTORY_DIR):
    folder_path = os.path.join(HISTORY_DIR, folder)
    entries_file = os.path.join(folder_path, "entries.json")
    
    if os.path.isfile(entries_file):
        try:
            with open(entries_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            file_uri = data.get("resource", "")
            
            # Convert file URI back to standard Windows path format
            if file_uri.startswith("file:///"):
                # "file:///c%3A/Users/shrut/..." -> "c:\Users\shrut\..."
                original_path = file_uri.replace("file:///", "").replace("%3A", ":").replace("/", "\\")
                
                if original_path.lower().startswith(TARGET_PROJECT.lower()):
                    entries = data.get("entries", [])
                    if entries:
                        # The entries are chronological, so the last one is the most recent
                        # Wait, we want the most recent state BEFORE 2026-05-06 01:40:00Z
                        # Let's just grab the absolute latest backup for each file. 
                        # Actually, if I did `git restore`, that might have created a NEW entry!
                        # So we want to find the latest entry that differs from the current file,
                        # or just dump ALL entries from the last 24 hours so the user can see them!
                        
                        latest_entry = entries[-1]
                        
                        # Let's check if the latest entry is just the `git restore` version by looking at the second to last.
                        if len(entries) > 1:
                            target_entry = entries[-2] # Before the wipe
                        else:
                            target_entry = latest_entry
                            
                        # Better approach: Just copy the absolute latest entry that is NOT empty
                        # Let's find the largest entry from the last 2 hours.
                        best_entry = None
                        best_size = -1
                        
                        for entry in reversed(entries):
                            entry_path = os.path.join(folder_path, entry["id"])
                            if os.path.exists(entry_path):
                                size = os.path.getsize(entry_path)
                                # Let's assume the user's code was large, and my wipe reverted it. 
                                # Actually, `git restore` reverts it to a previous good state, which is also large.
                                # Let's just copy the top 3 most recent versions of the file to the recovery dir!
                                
                        # Copy the most recent 2 versions
                        recent_entries = entries[-2:] if len(entries) >= 2 else entries
                        
                        for idx, entry in enumerate(recent_entries):
                            entry_path = os.path.join(folder_path, entry["id"])
                            if os.path.exists(entry_path):
                                timestamp = entry.get("timestamp", 0)
                                dt = datetime.fromtimestamp(timestamp / 1000.0)
                                
                                rel_path = os.path.relpath(original_path, TARGET_PROJECT)
                                safe_rel_path = rel_path.replace("\\", "_").replace("/", "_")
                                
                                # Format: filename_20260506_013000.py
                                time_str = dt.strftime("%Y%m%d_%H%M%S")
                                dest_name = f"{safe_rel_path}_{time_str}.txt"
                                dest_path = os.path.join(RECOVERY_DIR, dest_name)
                                
                                shutil.copy2(entry_path, dest_path)
                                recovered_files += 1
                                print(f"Recovered: {rel_path} (from {time_str})")
        except Exception as e:
            pass

print(f"\nSuccessfully dumped {recovered_files} historical versions to {RECOVERY_DIR}")
