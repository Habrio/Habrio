import os
import logging

merged_file = "merged_app.py"
included_files = set()
output = []

def collect_code_from(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
        lines = [line for line in lines if not line.startswith("from models") and not line.startswith("from services")]
        return lines

def walk_and_merge(folder):
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".py") and file not in ["merge_all.py", merged_file]:
                full_path = os.path.join(root, file)
                if full_path not in included_files:
                    included_files.add(full_path)
                    output.append(f"# === {full_path} ===\n")
                    output.extend(collect_code_from(full_path))
                    output.append("\n\n")

# Start merging
walk_and_merge("models")
walk_and_merge("services")
walk_and_merge("utils")
walk_and_merge("agent")

# Add main.py at the end
output.append("# === main.py ===\n")
output.extend(collect_code_from("main.py"))

# Write to merged file
with open(merged_file, "w") as f:
    f.writelines(output)

logging.info("✅ Merged into %s", merged_file)
