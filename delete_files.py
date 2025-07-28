from pathlib import Path
import shutil
import os

archive_root = Path("C:/Users/pratikhegde/OneDrive - Nagarro/Desktop/Pratik/short-trade-assistant/backend/backtesting/ohlcv_archive")

deleted = 0
skipped = []

for folder in archive_root.iterdir():
    if folder.is_dir():
        try:
            # Check if empty
            if not any(folder.iterdir()):
                os.chmod(folder, 0o777)  # reset permissions just in case
                folder.rmdir()
                print(f"🧹 Deleted: {folder.name}")
                deleted += 1
        except Exception as e:
            skipped.append((folder.name, str(e)))

print(f"\n✅ Deleted {deleted} empty folders.")
if skipped:
    print(f"⚠️ Skipped {len(skipped)} folders due to errors:")
    for name, err in skipped[:10]:
        print(f" - {name}: {err}")
