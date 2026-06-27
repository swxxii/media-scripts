#!/usr/bin/env python3
import sys
import requests
import yaml
from pathlib import Path

# --- CONFIGURATION ---
CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config.yml'

try:
    with open(CONFIG_PATH, 'r') as file:
        config = yaml.safe_load(file)
    PLEX_URL = config.get('plex_url', 'http://localhost:32400')
    PLEX_TOKEN = config.get('plex_token', '')
except FileNotFoundError:
    print(f"Error: Configuration file not found at {CONFIG_PATH}")
    sys.exit(1)
except yaml.YAMLError as e:
    print(f"Error parsing configuration file: {e}")
    sys.exit(1)
# ---------------------

def change_plex_setting(scan_value):
    headers = {'X-Plex-Token': PLEX_TOKEN, 'Accept': 'application/json'}
    payload = {
        'scheduledLibraryUpdateEnabled': scan_value,
        'scheduledLibraryUpdatesInterval': 0,
    }
    try:
        r = requests.put(f"{PLEX_URL}/:/prefs", headers=headers, params=payload)
        if r.status_code == 200:
            print(f"Successfully toggled Plex background scans. (Status: {scan_value})")
        else:
            print(f"Failed to update Plex settings. Status code: {r.status_code}")
    except Exception as e:
        print(f"Error communicating with Plex API: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
        if action == "start":
            change_plex_setting("0")
        elif action == "stop":
            change_plex_setting("1")
