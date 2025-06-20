"""
Warmup Script — primes the assistant's memory with project structure and usage.
"""

import os

# Load project map
try:
    from project_map import PROJECT_MAP
except ImportError:
    raise RuntimeError("project_map.py not found or not in path.")

def run_warmup(verbose=True, check_tags=True):
    print("🔁 Running warmup...")

    total = len(PROJECT_MAP)
    missing_roles = []
    missing_tags = []

    for path, meta in PROJECT_MAP.items():
        role = meta.get("role", "").strip()
        tags = meta.get("tags", [])

        if verbose:
            print(f"📄 {path} → role: {role or '❓'}, tags: {tags or ['❓']}")

        if check_tags:
            if not role or role == "TBD":
                missing_roles.append(path)
            if not tags:
                missing_tags.append(path)

    print(f"✅ Warmup complete. {total} files scanned.")
    if check_tags:
        print(f"⚠️  Missing roles: {len(missing_roles)}")
        print(f"⚠️  Missing tags: {len(missing_tags)}")

    # Folder tree cross-check
    tree_file = "folder_tree.txt"
    if os.path.exists(tree_file):
        print("\n📁 Verifying folder tree against project map...")
        with open(tree_file, "r") as f:
            lines = f.readlines()

        listed_files = [line.strip()[2:] for line in lines if line.strip().startswith("📄")]
        missing_in_map = [f for f in listed_files if f not in PROJECT_MAP]

        if missing_in_map:
            print(f"⚠️  {len(missing_in_map)} files found in tree but missing in map:")
            for f in missing_in_map:
                print(f"    🔸 {f}")
        else:
            print("✅ All files in tree are accounted for in project map.")

    return {
        "total_files": total,
        "missing_roles": missing_roles,
        "missing_tags": missing_tags
    }

if __name__ == "__main__":
    run_warmup()
