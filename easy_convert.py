import json
import os
from pathlib import Path
import re


def convert_bat_file(bat_file, output_folder):
    """
    Do not use function for convert variable config. 
    """
    with open(bat_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    variables = {}
    command_lines = []
    variables_text = [r"%GameFilter%=$LOCALCONDITION(useGameFilter==true ? 1024-65535 : 0)"]
    in_command = False

    for line in lines:
        line = line.strip()

        if not line or line.startswith('::') or line.lower().startswith('rem'):
            continue

        var_match = re.match(r'set\s+\"(\w+)=(.*?)\"', line, re.IGNORECASE)
        
        if var_match:
            var_name = var_match.group(1)
            var_value = var_match.group(2)
            var_value = var_value.replace('%~dp0', '$GETCURRENTDIR()/')
            var_value = var_value.strip('"')
            print(var_name, var_value)
            variables_text.append(f"%{var_name.upper()}%={var_value}")
            continue

        if line.lower().startswith('start'):
            in_command = True
            line = re.sub(
                r'start\s+".*?"\s+((/min+\s+".*?")|(\S*))\s*\^?', 
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

    def replace_vars(match):
        var_name = match.group(1)
        var_value = variables.get(var_name.upper(), '')
        return var_value

    # command = re.sub(r'%(\w+)%', replace_vars, command)

    command = command.replace(r'\\"', '').replace('"', '')
    command = command.replace("%~dp0..\\bin\\", "")

    command = command.replace('=', ' ')

    command = re.sub(r'\s+', ' ', command).strip()
    
    if command == '':
        raise KeyError("Empty startup parameters. The file is damaged or not compatible")

    name = f'$LOADSTRING(general) - {input("Enter config name [$LOADSTRING(general) - ...]")}'


    json_data = {
        "meta": "IC:v1.0",
        "name": name,
        "target": [
            "CSZTBN012", # Zapret
            "71.2"
        ],
        "params": {
            "useGameFilter": False 
        },
        "variables": variables_text,
        "startup_string": command
    }
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    bat_dir = os.path.dirname(os.path.abspath(bat_file))
    bat_name = os.path.splitext(os.path.basename(bat_file))[0].replace(" ", "").replace("(", "").replace(")", "")
    json_file = os.path.join(output_folder, f"{bat_name}.json")

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
        
    return json_file

file = input("Enter file path >>>")

print(convert_bat_file(file, Path(file).parent))