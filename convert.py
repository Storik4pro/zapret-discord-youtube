#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert.py
Usage:
  python convert.py <source_root> <output_json_folder> <package_dir> <zip_output_path> [exclude_bat_csv] [exclude_ext_csv]
Or set environment variable EXCLUDE_EXTS for exclude_ext_csv.

Behavior:
- Converts .bat files under <source_root> into json files in <output_json_folder>.
- Builds a package in <package_dir> with all files/folders from source_root,
  excluding: .service (folder), .github (folder), .gitignore (file), LICENSE.txt (file).
- In each directory, if both "name" and "name.backup" exist (e.g. ipset-all.txt and ipset-all.txt.backup),
  prefer the backup file and copy it renamed to the original name — unless the base extension is excluded.
- Apply extension filter: files whose extension (case-insensitive) is in excluded_exts are NOT copied.
- Puts generated .json files into the package root.
- Creates zip at <zip_output_path> containing the package content (no extra top-level folder).
"""
import json
import os
import shutil
from pathlib import Path
import re
import sys

EXCLUDE_DIR_NAMES = {'.service', '.github'}
EXCLUDE_FILE_NAMES = {'.gitignore', 'LICENSE.txt'}
DEFAULT_EXCLUDED_EXTS = {'.exe', '.dll', '.sys', '.bat'}  
DEFAULT_TARGET_VERSION = "71.2"

def normalize_exts(ext_csv: str):
    """Return set of normalized extensions starting with dot and lowercased."""
    if not ext_csv:
        return set()
    parts = [p.strip().lower() for p in ext_csv.split(',') if p.strip() != '']
    normalized = set()
    for p in parts:
        if p == '':
            continue
        if not p.startswith('.'):
            p = '.' + p
        normalized.add(p)
    return normalized

def convert_bat_file(bat_file: str, output_folder: str):
    with open(bat_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    variables_text = [r"%GameFilter%=$LOCALCONDITION(useGameFilter==true ? 1024-65535 : 0)"]
    command_lines = []
    in_command = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith('::') or line.lower().startswith('rem'):
            continue

        var_match = re.match(r'set\s+\"?(\w+)=(.*?)\"?$', line, re.IGNORECASE)
        if var_match:
            var_name = var_match.group(1)
            var_value = var_match.group(2)
            var_value = var_value.replace('%~dp0', '$GETCURRENTDIR()/')
            var_value = var_value.strip('"')
            variables_text.append(f"%{var_name.upper()}%={var_value}")
            continue

        if line.lower().startswith('start'):
            in_command = True
            line = re.sub(
                r'start\s+\".*?\"\s+((/min+\s+\".*?\")|(\S*))\s*\^?',
                '',
                line,
                flags=re.IGNORECASE
            )
            line = line.strip()
            if line:
                command_lines.append(line)
            continue

        if in_command:
            if line.endswith('^'):
                line = line[:-1].strip()
                command_lines.append(line)
            else:
                command_lines.append(line)
                in_command = False
            continue

    command = ' '.join(command_lines)
    command = command.replace('^', '').replace('\n', '').strip()
    command = command.replace('%~dp0', '').replace("POPD", '')
    command = command.replace("%~dp0..\\bin\\", "")
    command = re.sub(r'\s+', ' ', command).strip()

    if command == '':
        raise KeyError(f"Empty startup parameters for {bat_file}. The file may be damaged or not compatible")

    bat_name = Path(bat_file).stem
    loc_name = bat_name.replace("general", "$LOADSTRING(general) ").replace("(ALT", "$LOADSTRING(alt) ").replace(")", "").replace("(", "")
    name = loc_name

    json_data = {
        "meta": "IC:v1.0",
        "name": name,
        "target": [
            "CSZTBN012",
            TARGET_VERSION
        ],
        "jparams": {
            "useGameFilter": False
        },
        "variables": variables_text,
        "startup_string": command
    }

    os.makedirs(output_folder, exist_ok=True)
    rdname = bat_name.replace("(", "").replace(")", "").replace(" ", "")
    out_name = Path(output_folder) / f"{rdname}.json"
    with open(out_name, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    return out_name

def convert_all_bats(src_root: Path, out_json_folder: Path, excludes_csv: str):
    excludes = [e.strip().lower() for e in excludes_csv.split(',')] if excludes_csv else []
    bat_files = list(src_root.rglob("*.bat"))
    print(f"Found {len(bat_files)} .bat files under {src_root}")
    converted = []
    for b in bat_files:
        name = b.name.lower()
        if name in excludes:
            print("Skipping excluded:", b)
            continue
        try:
            out = convert_bat_file(str(b), str(out_json_folder))
            converted.append(str(out))
            print("Converted:", b, "->", out)
        except Exception as e:
            print("Failed to convert", b, ":", e)
    return converted

def copy_package_with_backup_policy(src_root: Path, package_dir: Path, excluded_exts: set):
    """
    Copy files and dirs from src_root -> package_dir applying:
    - skip directories with names in EXCLUDE_DIR_NAMES
    - skip files in EXCLUDE_FILE_NAMES
    - skip any file whose extension is in excluded_exts
    - in each folder, if both file and file.backup exist, copy only backup as file (rename)
      unless base extension is excluded (in which case skip)
    - if only backup exists, copy backup renamed (unless excluded)
    """
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    for src_dir, dirnames, filenames in os.walk(src_root):
        rel_dir = os.path.relpath(src_dir, src_root)
        if rel_dir == '.':
            rel_dir = ''

        dirnames[:] = [d for d in dirnames if d.lower() not in EXCLUDE_DIR_NAMES]

        target_dir = package_dir.joinpath(rel_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        files_set = set(filenames)
        handled = set()

        for fname in list(files_set):
            if fname.endswith('.backup'):
                base = fname[:-7] 
                base_ext = Path(base).suffix.lower()
                if base_ext in excluded_exts:
                    print(f"Skipping backup for excluded extension: {Path(src_dir)/fname} -> (base {base_ext} excluded)")
                    handled.add(fname)
                    handled.add(base)
                    continue

                if base in files_set:
                    src_file = Path(src_dir) / fname
                    dst_file = target_dir / base
                    shutil.copy2(src_file, dst_file)
                    handled.add(base)
                    handled.add(fname)
                    print(f"Copied (backup replaces original): {src_file} -> {dst_file}")
                else:
                    src_file = Path(src_dir) / fname
                    dst_file = target_dir / base
                    shutil.copy2(src_file, dst_file)
                    handled.add(base)
                    handled.add(fname)
                    print(f"Copied (backup->base): {src_file} -> {dst_file}")

        for fname in files_set:
            if fname in handled:
                continue
            if fname.lower() in EXCLUDE_FILE_NAMES:
                print(f"Skipping excluded file: {Path(src_dir)/fname}")
                continue
            base_ext = Path(fname).suffix.lower()
            if base_ext in excluded_exts:
                print(f"Skipping file with excluded extension: {Path(src_dir)/fname}")
                continue

            src_file = Path(src_dir) / fname
            dst_file = target_dir / fname
            shutil.copy2(src_file, dst_file)
            print(f"Copied: {src_file} -> {dst_file}")

    for excl in EXCLUDE_DIR_NAMES:
        excl_path = package_dir.joinpath(excl)
        if excl_path.exists():
            if excl_path.is_dir():
                shutil.rmtree(excl_path)
            else:
                excl_path.unlink()

def merge_jsons_into_package(json_folder: Path, package_dir: Path):
    if not json_folder.exists():
        return
    for jf in json_folder.glob("*.json"):
        dst = package_dir / jf.name
        shutil.copy2(jf, dst)
        print(f"Included JSON: {jf} -> {dst}")

def make_zip_from_package(package_dir: Path, zip_output_path: Path):
    zip_base = str(zip_output_path.with_suffix(''))
    shutil.make_archive(zip_base, 'zip', root_dir=str(package_dir))
    produced = Path(zip_base + '.zip')
    if produced.resolve() != zip_output_path.resolve():
        shutil.move(str(produced), str(zip_output_path))
    print(f"Created zip: {zip_output_path}")

def main():
    global TARGET_VERSION
     
    if len(sys.argv) < 5:
        print("Usage: convert.py <source_root> <output_json_folder> <package_dir> <zip_output_path> [exclude_bat_csv] [exclude_ext_csv]")
        sys.exit(2)

    src_root = Path(sys.argv[1])
    out_json = Path(sys.argv[2])
    package_dir = Path(sys.argv[3])
    zip_output = Path(sys.argv[4])
    exclude_bat_csv = sys.argv[5] if len(sys.argv) > 5 else ''
    exclude_ext_csv = sys.argv[6] if len(sys.argv) > 6 else os.environ.get('EXCLUDE_EXTS', '')
    arg_target_version = sys.argv[7] if len(sys.argv) > 7 else os.environ.get('TARGET_VERSION', '')

    excluded_exts = normalize_exts(exclude_ext_csv)
    if not excluded_exts:
        excluded_exts = set(DEFAULT_EXCLUDED_EXTS)
    print("Excluded extensions:", excluded_exts)

    if arg_target_version:
        TARGET_VERSION = str(arg_target_version)
    else:
        TARGET_VERSION = os.environ.get('TARGET_VERSION', DEFAULT_TARGET_VERSION)
    print("Using target version for JSON:", TARGET_VERSION)

    if not src_root.exists():
        print("Source root does not exist:", src_root)
        sys.exit(1)

    converted = convert_all_bats(src_root, out_json, exclude_bat_csv)
    print(f"Converted {len(converted)} .bat files to JSON in {out_json}")

    copy_package_with_backup_policy(src_root, package_dir, excluded_exts)

    merge_jsons_into_package(out_json, package_dir)

    make_zip_from_package(package_dir, zip_output)

    print("Done. Zip path:", zip_output)
    print("Converted files count:", len(converted))

if __name__ == "__main__":
    main()
