#!/usr/bin/env python3
# -------------------------------------------------------------------------
# plexmeta.py
#
# Description:  Exports Plex library metadata via the Tautulli API.
#               - Ensure OUTPUT_DIR exists and Tautulli is reachable.
#               - Remove any stale exports from the server.
#               - Query Tautulli to get library sections.
#               - Trigger CSV/JSON exports for each section.
#               - Poll until each export completes or fails.
#               - Download completed files to disk.
#               - Clean up exports from the server.
#
# Dependency:   `pip install requests`
#
# -------------------------------------------------------------------------
import time
import requests
from pathlib import Path

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
# base URL of the Tautulli server (including port).
TAUTULLI    = "http://192.168.1.3:8181"
# Tautulli API key (get from Tautulli settings > web interface).
API_KEY     = "CHANGE TO YOUR KEY"
# folder where export files will be saved
OUTPUT_DIR  = Path("/mnt/sync/Google/Backups/plexmeta")

# number of seconds to wait before checking export is complete
POLL_SECS   = 5
# number of seconds to wait before bailing on an export
TIMEOUT     = 300

# -------------------------------------------------------------------------
# Call Tautulli API and return parsed data
# -------------------------------------------------------------------------
def api(cmd, **params):
    r = requests.get(
        f"{TAUTULLI}/api/v2",
        params={"apikey": API_KEY, "cmd": cmd, **params},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()["response"]
    if body["result"] != "success":
        raise RuntimeError(f"{cmd} failed: {body.get('message')}")
    return body["data"]


# -----------------------------------------------------------------------------
# Get list of Plex libraries (section_id, section_name)
# -----------------------------------------------------------------------------
def get_libraries():
    return [(lib["section_id"], lib["section_name"]) for lib in api("get_libraries")]


# -----------------------------------------------------------------------------
# Delete all export jobs from Tautulli
# -----------------------------------------------------------------------------
def delete_all_exports():
    try:
        exports_before = api("get_exports_table", length=1000).get("data", [])
        count_before = len(exports_before)
    except Exception:
        count_before = 0
    api("delete_export", delete_all=1)
    try:
        exports_after = api("get_exports_table", length=1000).get("data", [])
        count_after = len(exports_after)
    except Exception:
        count_after = 0
    deleted = max(count_before - count_after, 0)
    return deleted


# -----------------------------------------------------------------------------
# Trigger export for a library section in CSV or JSON
# -----------------------------------------------------------------------------
def trigger_export(section_id, file_format="csv"):
    data = api("export_metadata", section_id=section_id, file_format=file_format)
    return data["export_id"]


# -----------------------------------------------------------------------------
# Wait until export job completes or times out
# -----------------------------------------------------------------------------
def wait_until_ready(export_id, section_id):
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_SECS)
        rows = api("get_exports_table", section_id=section_id, length=50)
        for row in rows.get("data", []):
            if row.get("export_id") == export_id:
                if row.get("complete") == 1:
                    return
                if row.get("complete") == -1:
                    raise RuntimeError(f"Export {export_id} failed on Tautulli server")
                break
    raise TimeoutError(f"Export {export_id} did not complete within {TIMEOUT}s")


# -----------------------------------------------------------------------------
# Download completed export file to disk
# -----------------------------------------------------------------------------
def download(export_id, path):
    r = requests.get(
        f"{TAUTULLI}/api/v2",
        params={"apikey": API_KEY, "cmd": "download_export", "export_id": export_id},
        stream=True,
        timeout=120,
    )
    r.raise_for_status()
    content = b"".join(r.iter_content(8192))
    if not content:
        raise RuntimeError("Downloaded file was empty")
    path.write_bytes(content)
    return len(content)


# -----------------------------------------------------------------------------
# Make a library name safe for filesystem
# -----------------------------------------------------------------------------
def safe_filename(name):
    return name.replace(" ", "_").replace("/", "-").replace(":", "")


# -----------------------------------------------------------------------------
# Wait for Tautulli server to become reachable
# -----------------------------------------------------------------------------
def wait_for_tautulli(timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(f"{TAUTULLI}/api/v2", params={"apikey": API_KEY, "cmd": "arnold"}, timeout=5)
            return
        except requests.exceptions.ConnectionError:
            time.sleep(5)
    raise TimeoutError(f"Tautulli did not become reachable within {timeout}s")


# -----------------------------------------------------------------------------
# Run the full export workflow
# -----------------------------------------------------------------------------
def main():
    print("Starting Plex metadata export...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wait_for_tautulli()
    deleted_initial = delete_all_exports()
    print(f"Cleaned up {deleted_initial} exports before starting.")
    libraries = get_libraries()
    print(f"Found {len(libraries)} libraries")

    ok, failed = [], []
    total_start = time.time()
    results = []
    print("-" * 62)
    print("{:<14} {:<6} {:>12} {:>12} {:>10}".format("Library", "Status", "CSV Size", "JSON Size", "Time"))
    print("-" * 62)
    for section_id, name in libraries:
        start = time.time()
        status = "OK"
        csv_size = json_size = "-"
        error = ""
        try:
            sizes = []
            for fmt in ("csv", "json"):
                export_id = trigger_export(section_id, fmt)
                wait_until_ready(export_id, section_id)
                out_path = OUTPUT_DIR / f"{safe_filename(name)}.{fmt}"
                sizes.append(download(export_id, out_path))
            csv_size = f"{int(sizes[0] / 1024)} KB"
            json_size = f"{int(sizes[1] / 1024)} KB"
            ok.append(name)
        except Exception as e:
            status = "FAIL"
            error = str(e)
            failed.append((name, error))
        end = time.time()
        elapsed = round(end - start, 1)
        results.append((name, status, csv_size, json_size, f"{elapsed:.1f}", error))
        print("{:<14} {:<6} {:>12} {:>12} {:>10}".format(name, status, csv_size, json_size, f"{elapsed:.1f}s"))
    deleted_final = delete_all_exports()
    print(f"\nCleaned up {deleted_final} exports after export.")
    total_end = time.time()
    print(f"\n{len(ok)} succeeded, {len(failed)} failed")
    if failed:
        print("\nFailed libraries:")
        for name, err in failed:
            print(f"  ✗ {name}: {err}")
    print(f"\nTotal export time: {round(total_end - total_start, 1):.1f}s")


if __name__ == "__main__":
    main()