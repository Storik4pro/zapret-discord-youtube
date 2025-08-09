#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
from pathlib import Path
import re
import sys

def convert_bat_file(bat_file: str, output_folder: str):
    """
    Convert a single .bat into the json format used by your app.
    Non-interactive: name is derived from file name.
    """
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
            # remove start "title" and possible /min "..." and trailing caret
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
    command = command.replace(r'\\"', '').replace('"', '')
    command = command.replace("%~dp0..\\bin\\", "")
    command = re.sub(r'\s+', ' ', command).strip()

    if command == '':
        raise KeyError(f"Empty startup parameters for {bat_file}. The file may be damaged or not compatible")

    bat_name = Path(bat_file).stem
    name = f'$LOADSTRING(general) - {bat_name}'

    json_data = {
        "meta": "IC:v1.0",
        "name": name,
        "target": [
            "CSZTBN012",
            "71.2"
        ],
        "jparams": {
            "useGameFilter": False
        },
        "variables": variables_text,
        "startup_string": command
    }

    os.makedirs(output_folder, exist_ok=True)
    out_name = Path(output_folder) / f"{bat_name}.json"
    with open(out_name, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    return out_name

def main():
    if len(sys.argv) < 3:
        print("Usage: convert.py <source_root> <output_folder> [exclude_csv]")
        sys.exit(2)

    src_root = sys.argv[1]
    output_folder = sys.argv[2]
    excludes = sys.argv[3].split(',') if len(sys.argv) > 3 and sys.argv[3].strip() != '' else []
    excludes = [e.strip().lower() for e in excludes]

    p = Path(src_root)
    if not p.exists():
        print("Source root does not exist:", src_root)
        sys.exit(1)

    bat_files = list(p.rglob("*.bat"))
    print(f"Found {len(bat_files)} .bat files under {src_root}")
    converted = []
    for b in bat_files:
        name = b.name.lower()
        if name in excludes:
            print("Skipping excluded:", b)
            continue
        try:
            out = convert_bat_file(str(b), output_folder)
            converted.append(str(out))
            print("Converted:", b, "->", out)
        except Exception as e:
            print("Failed to convert", b, ":", e)

    if not converted:
        print("No files converted.")
        sys.exit(1)

    print(f"Converted {len(converted)} files. Output folder:", output_folder)

if __name__ == "__main__":
    main()
