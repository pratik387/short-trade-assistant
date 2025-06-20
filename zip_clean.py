import zipfile, os

EXCLUDE_FOLDERS = {"__pycache__", ".venv", "node_modules", ".git", ".mypy_cache", ".vscode"}
EXCLUDE_FILES = {".env.production", ".env.development"}
EXCLUDE_EXTENSIONS = {".log", ".pyc"}

def zip_without_excluded(zip_name, folder_path):
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            # Clean folders
            dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]

            for file in files:
                if file in EXCLUDE_FILES or any(file.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                    continue
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, folder_path)
                zipf.write(filepath, arcname)

# Example usage:
zip_without_excluded(
    "C:/Users/pratikhegde/Downloads/short-trade-assistant.zip",
    "C:/Users/pratikhegde/OneDrive - Nagarro/Desktop/Pratik/short-trade-assistant"
)
