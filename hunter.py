import requests
import time
import json
import os

# --- SETTINGS (SINSTA EDITION - ONE RUN MODE) ---
SAFE_DELAY = 5 
BATCH_SIZE = 200 

STATE_FILE = "state.json"
USERNAMES_FILE = "usernames.txt"
AVAILABLE_FILE = "available_usernames.txt"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading state.json: {e}. Resetting state.")
    return {"last_checked_index": -1}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving state.json: {e}")

def load_usernames():
    if not os.path.exists(USERNAMES_FILE):
        print(f"Warning: {USERNAMES_FILE} does not exist!")
        return []
    
    usernames = []
    with open(USERNAMES_FILE, "r") as f:
        for line in f:
            uname = line.strip()
            if uname and not uname.startswith("#"):
                usernames.append(uname)
    return usernames

def log_available_username(username, reason):
    try:
        with open(AVAILABLE_FILE, "a") as f:
            f.write(f"{username}\n")
    except Exception as e:
        print(f"Error writing to {AVAILABLE_FILE}: {e}")

def check_availability(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        # Step 1: URL HTTP GET Probe
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return False, "Taken (Profile active)"
            
    except Exception as e:
        return False, f"Connection Error (GET): {str(e)}"
        
    # Step 2: Strict Signup API Check with Retries for rate limiting
    api_url = "https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/"
    max_retries = 3
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            session = requests.Session()
            session.get("https://www.instagram.com/accounts/emailsignup/", headers=headers, timeout=10)
            
            api_headers = {
                "User-Agent": headers["User-Agent"],
                "X-IG-App-ID": "936619743392459",
                "X-ASBD-ID": "129477",
                "X-CSRFToken": session.cookies.get("csrftoken", "missing"),
                "Referer": "https://www.instagram.com/accounts/emailsignup/",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            data = {
                "email": f"sinsta_{int(time.time())}@gmail.com",
                "username": username,
                "first_name": "Sinsta",
                "opt_into_hashtags": "false"
            }
            
            api_resp = session.post(api_url, data=data, headers=api_headers, timeout=10)
            
            # Handle rate limiting or blocking
            if api_resp.status_code == 429:
                print(f"[Rate Limited (429) on {username}, retrying in {retry_delay}s...]", end="", flush=True)
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
                
            if api_resp.status_code != 200:
                # If we get a bad status code, it's highly likely a temporary block or a rate limit
                # We will wait and retry
                print(f"[HTTP {api_resp.status_code} on {username}, retrying in {retry_delay}s...]", end="", flush=True)
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            
            try:
                result = api_resp.json()
            except Exception:
                # If it's not JSON, Instagram probably redirected us to a login page or error block page
                print(f"[Bad JSON Response on {username}, retrying in {retry_delay}s...]", end="", flush=True)
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            
            # Parse API Response
            if "errors" in result and result["errors"]:
                errors = result["errors"]
                error_msg = "Taken / Deactivated"
                if "username" in errors:
                    error_msg = errors["username"][0].get("message", "Taken")
                return False, f"Not Registerable ({error_msg})"
                
            if result.get("status") != "ok":
                return False, f"Not Registerable (Status: {result.get('status')})"
                
            return True, "Available (Truly Registerable)"
            
        except Exception as e:
            if attempt == max_retries - 1:
                return False, f"API Connection/Parsing Error: {str(e)}"
            time.sleep(retry_delay)
            retry_delay *= 2
            
    # If all retries failed, log it as an error to allow manual check or skip
    return False, "Rate Limited / Connection Blocked"

def run_batch():
    state = load_state()
    usernames = load_usernames()
    
    total_names = len(usernames)
    start_idx = state["last_checked_index"] + 1
    
    if start_idx >= total_names:
        print(f"All {total_names} usernames in {USERNAMES_FILE} have already been checked. Done!")
        return
        
    print(f"Starting Sinsta single-run batch | Total targets = {total_names}")
    print(f"Checking usernames from index {start_idx} up to {min(start_idx + BATCH_SIZE - 1, total_names - 1)}")
    print("=" * 60)
    
    checked_count = 0
    current_idx = start_idx
    
    available_usernames = []
    taken_count = 0
    error_count = 0
    
    if start_idx == 0 and os.path.exists(AVAILABLE_FILE):
        try:
            os.remove(AVAILABLE_FILE)
        except Exception as e:
            print(f"Could not reset {AVAILABLE_FILE}: {e}")
            
    while checked_count < BATCH_SIZE and current_idx < total_names:
        username = usernames[current_idx]
        print(f"[{current_idx + 1}/{total_names}] Checking: {username:15} -> ", end="", flush=True)
        
        is_avail, reason = check_availability(username)
        if is_avail:
            print("AVAILABLE! [SUCCESS]")
            available_usernames.append(username)
            log_available_username(username, reason)
        else:
            print(f"TAKEN ({reason})")
            if "Error" in reason or "Limited" in reason or "Blocked" in reason:
                error_count += 1
            else:
                taken_count += 1
            
        checked_count += 1
        current_idx += 1
        
        state["last_checked_index"] = current_idx - 1
        save_state(state)
        
        if checked_count < BATCH_SIZE and current_idx < total_names:
            time.sleep(SAFE_DELAY)
            
    print("\n" + "=" * 60)
    print("SINSTA RUN COMPLETED SUMMARY")
    print("=" * 60)
    print(f"Total Checked:        {checked_count}")
    print(f"Truly Available:      {len(available_usernames)}")
    print(f"Taken/Unregisterable: {taken_count}")
    print(f"API/Network Errors:   {error_count}")
    print("-" * 60)
    
    if available_usernames:
        print("TRULY AVAILABLE USERNAMES DISCOVERED:")
        for name in available_usernames:
            print(f"  * {name}")
        print(f"\nSaved successfully to: {AVAILABLE_FILE}")
    else:
        print("[!] No available/registerable usernames discovered in this run.")
    print("=" * 60)

if __name__ == "__main__":
    run_batch()
