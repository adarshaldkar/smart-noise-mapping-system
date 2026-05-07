import os
import json
import shutil

HISTORY_DIR = r"C:\Users\shrut\AppData\Roaming\Code\User\History"
TARGET_PROJECT = r"c:\Users\shrut\Desktop\Final_year_project"

print(f"Restoring latest files from VS Code History directly to: {TARGET_PROJECT}")
restored_files = 0

for folder in os.listdir(HISTORY_DIR):
    folder_path = os.path.join(HISTORY_DIR, folder)
    entries_file = os.path.join(folder_path, "entries.json")
    
    if os.path.isfile(entries_file):
        try:
            with open(entries_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            file_uri = data.get("resource", "")
            
            if file_uri.startswith("file:///"):
                original_path = file_uri.replace("file:///", "").replace("%3A", ":").replace("/", "\\")
                
                if original_path.lower().startswith(TARGET_PROJECT.lower()):
                    entries = data.get("entries", [])
                    if entries:
                        # Grab the second-to-last if available (which is right before my git restore)
                        # Actually, wait, when I did `git restore .`, it might have created a new entry in VS Code history!
                        # Let's get the absolute latest entry that is from BEFORE my wipe (which happened around 2026-05-06 01:40:00Z)
                        # 01:40:00Z on May 6 is timestamp 1778031600000 approx
                        
                        wipe_timestamp_ms = 1778031600000 
                        
                        valid_entries = []
                        for entry in entries:
                            if entry.get("timestamp", 0) < wipe_timestamp_ms:
                                valid_entries.append(entry)
                        
                        if not valid_entries:
                            continue
                            
                        # Get the absolute latest entry before the wipe
                        latest_entry = valid_entries[-1]
                        
                        entry_path = os.path.join(folder_path, latest_entry["id"])
                        if os.path.exists(entry_path):
                            # Ensure the directory exists
                            os.makedirs(os.path.dirname(original_path), exist_ok=True)
                            
                            shutil.copy2(entry_path, original_path)
                            restored_files += 1
                            print(f"Restored: {original_path}")
        except Exception as e:
            pass

print(f"\nSuccessfully RESTORED {restored_files} historical files to your project folder!")
