import os
import sys
import json
import base64
import urllib.request
import subprocess
import re
from Crypto.Cipher import AES
import time

# Set terminal encoding to UTF-8
sys.stdout.reconfigure(encoding="utf-8")

CONFIG_FILE = "config.json"
STATIC_KEY = b"6ayJ7jo@ao#pxVc%"

def replace_sportzx_with_dudetv(data):
    if isinstance(data, dict):
        return {k: replace_sportzx_with_dudetv(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_sportzx_with_dudetv(item) for item in data]
    elif isinstance(data, str):
        return data.replace("SportzX", "DUDE Tv").replace("sportzx", "dudetv")
    return data

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def check_adb_devices():
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True)
        lines = res.stdout.strip().split("\n")[1:]
        devices = [line.split()[0] for line in lines if line.strip() and "device" in line]
        return devices
    except Exception as e:
        print(f"ADB is not installed or not in PATH: {e}")
        return []

def get_device_paths():
    try:
        apk_path_cmd = subprocess.run(["adb", "shell", "pm", "path", "com.sportzx.live"], capture_output=True, text=True, check=True)
        apk_path = apk_path_cmd.stdout.strip().replace("package:", "")
        if not apk_path:
            raise ValueError("DUDEtv app package (com.sportzx.live) is not installed on the emulator.")
            
        base_dir = apk_path.replace("base.apk", "")
        lib_list_cmd = subprocess.run(["adb", "shell", f"ls {base_dir}lib/"], capture_output=True, text=True, check=True)
        arch = lib_list_cmd.stdout.strip().split()[0]
        lib_path = f"{base_dir}lib/{arch}/libnative-lib.so"
        
        return apk_path, lib_path
    except Exception as e:
        print(f"Error resolving emulator paths: {e}")
        print("Please make sure the DUDEtv app is installed and the emulator is fully booted.")
        return None, None

def ensure_decryptor_jar():
    jar_name = "Decryptor.jar"
    local_jar_path = os.path.join("..", jar_name) if os.path.exists(os.path.join("..", jar_name)) else jar_name
    
    if not os.path.exists(local_jar_path):
        print("Decryptor.jar not found. Re-building...")
        try:
            java_file = "../Decryptor.java" if os.path.exists("../Decryptor.java") else "Decryptor.java"
            android_jar = "C:/Users/mdjam/AppData/Local/Android/Sdk/platforms/android-35/android.jar"
            d8_bat = "C:/Users/mdjam/AppData/Local/Android/Sdk/build-tools/34.0.0/d8.bat"
            
            subprocess.run(["javac", "--release", "8", "-cp", android_jar, java_file], check=True)
            subprocess.run([d8_bat, "--lib", android_jar, "--output", ".", "Decryptor.class"], check=True)
            
            import zipfile
            with zipfile.ZipFile(jar_name, "w") as z:
                z.write("classes.dex")
            
            # Clean up temporary files
            for temp in ["classes.dex", "Decryptor.class"]:
                if os.path.exists(temp):
                    os.remove(temp)
            local_jar_path = jar_name
            print("Successfully built Decryptor.jar")
        except Exception as e:
            print(f"Failed to build Decryptor.jar: {e}")
            sys.exit(1)
            
    try:
        subprocess.run(["adb", "push", local_jar_path, "/data/local/tmp/Decryptor.jar"], check=True, capture_output=True)
        print("Decryptor.jar verified and pushed to emulator.")
    except Exception as e:
        print(f"Failed to push Decryptor.jar: {e}")
        sys.exit(1)

def clean_and_decode_b64(encrypted_b64):
    clean_str = "".join(encrypted_b64.split())
    std_b64 = clean_str.replace("-", "+").replace("_", "/")
    padding = len(std_b64) % 4
    if padding:
        std_b64 += "=" * (4 - padding)
    try:
        return base64.b64decode(std_b64)
    except Exception:
        return base64.urlsafe_b64decode(std_b64)

def decrypt_cbc(ciphertext_bytes, key, iv):
    if len(ciphertext_bytes) % 16 != 0:
        ciphertext_bytes = ciphertext_bytes[:len(ciphertext_bytes) - (len(ciphertext_bytes) % 16)]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext_bytes)
    if len(decrypted) > 0:
        pad_len = decrypted[-1]
        if 1 <= pad_len <= 16 and all(x == pad_len for x in decrypted[-pad_len:]):
            decrypted = decrypted[:-pad_len]
    return decrypted

def decrypt_local_b5cdbd48(enc_bytes, iv_str):
    dec = decrypt_cbc(enc_bytes, STATIC_KEY, iv_str.encode("utf-8"))
    dec_str = dec.decode("utf-8", errors="ignore")
    return json.loads(dec_str)

def decrypt_via_emulator(payload, apk_path, lib_path):
    temp_file = "temp_payload.txt"
    device_file = "/data/local/tmp/payload.txt"
    try:
        # Try running adb root to see if we can get native root shell access
        subprocess.run(["adb", "root"], capture_output=True)
        subprocess.run(["adb", "wait-for-device"], capture_output=True)
        whoami_res = subprocess.run(["adb", "shell", "whoami"], capture_output=True)
        whoami_out = whoami_res.stdout.decode("utf-8", errors="ignore")
        is_root = "root" in whoami_out
        
        def run_root_cmd(cmd):
            if is_root:
                subprocess.run(["adb", "shell", cmd], capture_output=True)
            else:
                res = subprocess.run(["adb", "shell", f"su -c '{cmd}'"], capture_output=True)
                res_err = res.stderr.decode("utf-8", errors="ignore")
                res_out = res.stdout.decode("utf-8", errors="ignore")
                if "invalid uid/gid" in res_err or "invalid uid/gid" in res_out:
                    subprocess.run(["adb", "shell", f"su root {cmd}"], capture_output=True)

        def run_root_cmd_bytes(cmd):
            if is_root:
                return subprocess.run(["adb", "shell", cmd], capture_output=True).stdout
            else:
                res = subprocess.run(["adb", "shell", f"su -c '{cmd}'"], capture_output=True)
                res_err = res.stderr.decode("utf-8", errors="ignore")
                res_out = res.stdout.decode("utf-8", errors="ignore")
                if "invalid uid/gid" in res_err or "invalid uid/gid" in res_out:
                    return subprocess.run(["adb", "shell", f"su root {cmd}"], capture_output=True).stdout
                return res.stdout

        # 1. Make sure App is running and SELinux is Permissive
        pid_check = subprocess.run(["adb", "shell", "pidof com.sportzx.live"], capture_output=True)
        pid_out = pid_check.stdout.decode("utf-8", errors="ignore").strip()
        if not pid_out:
            print("      [Frida Fallback] App is not running. Launching SportzX...")
            run_root_cmd("setenforce 0")
            subprocess.run(["adb", "shell", "am start -n com.sportzx.live/com.sportzx.live.activities.SplashActivity"], capture_output=True)
            # Wait up to 12 seconds for the process to register
            for _ in range(12):
                pid_check = subprocess.run(["adb", "shell", "pidof com.sportzx.live"], capture_output=True)
                pid_out = pid_check.stdout.decode("utf-8", errors="ignore").strip()
                if pid_out:
                    break
                time.sleep(1)
            time.sleep(12)
        
        # 2. Write payload and push it
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(payload)
        subprocess.run(["adb", "push", temp_file, device_file], check=True, capture_output=True)
        
        # Remove old output file
        run_root_cmd("rm -f /data/user/0/com.sportzx.live/cache/decrypted_raw.bin")
        
        # 3. Start frida-server in mount master namespace if not running
        frida_ps = subprocess.run(["adb", "shell", "ps -A | grep frida-server"], capture_output=True)
        frida_ps_out = frida_ps.stdout.decode("utf-8", errors="ignore")
        if "frida-server" not in frida_ps_out:
            # Check if frida-server exists on the device
            check_fs = subprocess.run(["adb", "shell", "ls /data/local/tmp/frida-server"], capture_output=True)
            check_fs_err = check_fs.stderr.decode("utf-8", errors="ignore")
            check_fs_out = check_fs.stdout.decode("utf-8", errors="ignore")
            if "No such file" in check_fs_err or "frida-server" not in check_fs_out:
                print("      [Frida Fallback] frida-server not found on device. Preparing push...")
                if os.path.exists("frida-server"):
                    subprocess.run(["adb", "push", "frida-server", "/data/local/tmp/frida-server"], check=True)
                elif os.path.exists("frida-server.xz"):
                    print("      [Frida Fallback] Extracting frida-server.xz on host...")
                    import lzma
                    with lzma.open("frida-server.xz", "rb") as f_in:
                        with open("frida-server", "wb") as f_out:
                            f_out.write(f_in.read())
                    subprocess.run(["adb", "push", "frida-server", "/data/local/tmp/frida-server"], check=True)
                else:
                    print("      [Frida Fallback] Warning: frida-server binary or xz archive not found locally.")
                run_root_cmd("chmod 755 /data/local/tmp/frida-server")

            print("      [Frida Fallback] Starting frida-server...")
            if is_root:
                subprocess.Popen(["adb", "shell", "nohup /data/local/tmp/frida-server > /dev/null 2>&1 &"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                test_mm = subprocess.run(["adb", "shell", "su -mm -c 'id'"], capture_output=True)
                test_mm_err = test_mm.stderr.decode("utf-8", errors="ignore")
                test_mm_out = test_mm.stdout.decode("utf-8", errors="ignore")
                if "invalid uid/gid" in test_mm_err or "invalid uid/gid" in test_mm_out:
                    subprocess.Popen(["adb", "shell", "su root nohup /data/local/tmp/frida-server > /dev/null 2>&1 &"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(["adb", "shell", "su -mm -c 'nohup /data/local/tmp/frida-server > /dev/null 2>&1 &'"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Wait up to 10 seconds for frida-server to start up and respond
            for _ in range(10):
                res = subprocess.run(["frida-ps", "-U"], capture_output=True)
                if res.returncode == 0:
                    break
                time.sleep(1.5)
            
        # 4. Get the PID of com.sportzx.live and run Frida
        pid_res = subprocess.run(["adb", "shell", "pidof com.sportzx.live"], capture_output=True)
        pid = pid_res.stdout.decode("utf-8", errors="ignore").strip()
        if not pid:
            # Try parsing from ps
            ps_cmd = subprocess.run(["adb", "shell", "ps | grep com.sportzx.live"], capture_output=True)
            ps_out = ps_cmd.stdout.decode("utf-8", errors="ignore")
            match = re.search(r'\s+(\d+)\s+', ps_out)
            if match:
                pid = match.group(1)
        
        if pid:
            frida_cmd = ["frida", "-U", "-p", pid, "-l", "decrypt_script.js"]
        else:
            # Fallback to process/package name
            frida_cmd = ["frida", "-U", "-n", "com.sportzx.live", "-l", "decrypt_script.js"]
        output = ""
        stderr_output = ""
        try:
            # Run frida and let it time out after 15 seconds
            res = subprocess.run(frida_cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=15)
            output = res.stdout.decode("utf-8", errors="ignore") if res.stdout else ""
            stderr_output = res.stderr.decode("utf-8", errors="ignore") if res.stderr else ""
        except subprocess.TimeoutExpired as te:
            output = te.stdout.decode("utf-8", errors="ignore") if te.stdout else ""
            stderr_output = te.stderr.decode("utf-8", errors="ignore") if te.stderr else ""
        except Exception as fe:
            print(f"      [Frida Fallback] process error: {fe}")
                
        success = False
        saved_path = None
        for line in output.splitlines():
            if "SUCCESS!" in line:
                success = True
                parts = line.split("saved to:")
                if len(parts) > 1:
                    saved_path = parts[1].strip()
                break
            
        if not success or not saved_path:
            print("      [Frida Fallback] Frida decryption failed or output path not parsed.")
            print(f"      [Frida Debug] stdout: {output}")
            print(f"      [Frida Debug] stderr: {stderr_output}")
            saved_path = "/data/user/0/com.sportzx.live/cache/decrypted_raw.bin" # fallback
            
        # 5. Retrieve output bytes directly from private folder using binary-safe adb pull
        local_temp = os.path.join(os.getcwd(), "temp_decrypted.bin")
        if os.path.exists(local_temp):
            os.remove(local_temp)
            
        if is_root:
            subprocess.run(["adb", "shell", f"cp {saved_path} /data/local/tmp/decrypted_raw.bin"], capture_output=True)
            subprocess.run(["adb", "shell", "chmod 666 /data/local/tmp/decrypted_raw.bin"], capture_output=True)
        else:
            res = subprocess.run(["adb", "shell", f"su -c 'cp {saved_path} /data/local/tmp/decrypted_raw.bin && chmod 666 /data/local/tmp/decrypted_raw.bin'"], capture_output=True)
            res_err = res.stderr.decode("utf-8", errors="ignore")
            res_out = res.stdout.decode("utf-8", errors="ignore")
            if "invalid uid/gid" in res_err or "invalid uid/gid" in res_out:
                subprocess.run(["adb", "shell", f"su root 'cp {saved_path} /data/local/tmp/decrypted_raw.bin && chmod 666 /data/local/tmp/decrypted_raw.bin'"], capture_output=True)
                
        subprocess.run(["adb", "pull", "/data/local/tmp/decrypted_raw.bin", local_temp], capture_output=True)
        
        raw_bytes = b""
        if os.path.exists(local_temp):
            with open(local_temp, "rb") as lf:
                raw_bytes = lf.read()
            os.remove(local_temp)
        subprocess.run(["adb", "shell", "rm -f /data/local/tmp/decrypted_raw.bin"], capture_output=True)
        
        if len(raw_bytes) == 0:
            print("      [Frida Fallback] Decrypted file is empty or not readable.")
            return None
            
        # 6. Decode UTF-16BE directly from raw_bytes
        try:
            text = raw_bytes.decode("utf-16be", errors="ignore").strip()
        except Exception:
            low_bytes = bytes(raw_bytes[i+1] for i in range(0, len(raw_bytes)-1, 2))
            text = low_bytes.decode("utf-8", errors="ignore").strip()

        # Clean JSON boundaries
        start_idx = -1
        first_bracket = text.find('[')
        first_brace = text.find('{')
        if first_bracket != -1 and first_brace != -1:
            start_idx = min(first_bracket, first_brace)
        elif first_bracket != -1:
            start_idx = first_bracket
        elif first_brace != -1:
            start_idx = first_brace

        if start_idx != -1:
            text = text[start_idx:]

        last_bracket = text.rfind(']')
        last_brace = text.rfind('}')
        end_idx = max(last_bracket, last_brace)
        if end_idx != -1:
            text = text[:end_idx + 1]

        if not text:
            print("      [Frida Fallback] Output does not contain valid JSON boundaries.")
            return None

        try:
            return json.loads(text, strict=False)
        except Exception as je:
            print(f"      [Frida Fallback] json.loads initial attempt failed: {je}")
            if last_bracket != -1 and text.startswith('['):
                try:
                    return json.loads(text[:last_bracket + 1], strict=False)
                except Exception:
                    pass
            if last_brace != -1 and text.startswith('{'):
                try:
                    return json.loads(text[:last_brace + 1], strict=False)
                except Exception:
                    pass
            cleaned_text = re.sub(r',(\s*[\]}])', r'\1', text)
            try:
                return json.loads(cleaned_text, strict=False)
            except Exception as final_e:
                print(f"      [Frida Fallback] JSON parsing recovery failed: {final_e}")
                return None
            
    except Exception as e:
        print(f"      [Frida Fallback] Unexpected error: {e}")
        return None
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

def decrypt_data(payload, apk_path=None, lib_path=None):
    try:
        enc_bytes = clean_and_decode_b64(payload)
        
        # 1. DEADBEEF format (magic 0xdeadbeef at byte 0 or byte 1)
        if len(enc_bytes) >= 20 and enc_bytes[:4] == b'\xde\xad\xbe\xef':
            iv = enc_bytes[4:20]
            ciphertext = enc_bytes[20:]
            dec = decrypt_cbc(ciphertext, STATIC_KEY, iv)
        elif len(enc_bytes) >= 21 and enc_bytes[1:5] == b'\xde\xad\xbe\xef':
            iv = enc_bytes[5:21]
            ciphertext = enc_bytes[21:]
            dec = decrypt_cbc(ciphertext, STATIC_KEY, iv)
            
        # 2. Dynamic IV Format starting with 0x02 (1 byte flag + 16 bytes IV + ciphertext)
        elif len(enc_bytes) >= 17 and enc_bytes[0] == 2:
            iv = enc_bytes[1:17]
            ciphertext = enc_bytes[17:]
            dec = decrypt_cbc(ciphertext, STATIC_KEY, iv)
            
        # 3. Static IV Format
        else:
            dec = decrypt_cbc(enc_bytes, STATIC_KEY, b"HsjJTCA7jJztpL2w")
            
        dec_str = dec.decode("utf-8", errors="ignore").strip().rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10').strip()
        
        # Clean JSON string boundary
        if dec_str.startswith('[') and not dec_str.endswith(']'):
            last_bracket = dec_str.rfind(']')
            if last_bracket >= 0:
                dec_str = dec_str[:last_bracket + 1]

        try:
            return json.loads(dec_str, strict=False)
        except Exception:
            last_bracket = dec_str.rfind(']')
            if last_bracket >= 0:
                clean_json = dec_str[:last_bracket + 1]
                return json.loads(clean_json, strict=False)
                
    except Exception as e:
        print(f"      Decryption attempt failed: {e}")
        if apk_path and lib_path:
            try:
                print("      Trying emulator JNI fallback...")
                return decrypt_via_emulator(payload, apk_path, lib_path)
            except Exception as jnie:
                print(f"      JNI fallback failed: {jnie}")
        return None

def write_api_specification(out_dir):
    spec = {
        "api_name": "DUDE TV Decrypted API",
        "base_url": "https://mdjamsad9.github.io/dudetvapi/public_decrypted",
        "description": "This is a clean, decrypted static JSON API database for DUDE TV, generated automatically every 6 hours via GitHub Actions.",
        "endpoints": {
            "categories_menu": {
                "path": "/cats.json",
                "description": "Main category menu list. Contains the category names, images, and links.",
                "fields": {
                    "id": "Unique category identifier",
                    "title": "Category display name",
                    "image": "Category thumbnail URL",
                    "catLink": "The path to the subcategory channels list (e.g. 'cats/bangla.json') OR a direct M3U playlist URL (starts with http/https)"
                },
                "usage_flow": "Step 1: Fetch this file to render the menu. When user clicks a category: if 'catLink' starts with 'http', stream the M3U. If it points to a local file, fetch it from 'base_url + /cats/{catLink}'."
            },
            "sports_tv_channels": {
                "path": "/sports.json",
                "description": "List of standard sports TV channels.",
                "fields": {
                    "id": "Unique TV channel identifier (e.g., '1')",
                    "title": "Channel display name",
                    "image": "Channel logo URL",
                    "formats": "Array of stream server format names"
                },
                "usage_flow": "To play a TV channel: Fetch its stream links using '/channels/{id}.json' (e.g., '/channels/1.json')."
            },
            "live_events": {
                "path": "/events.json",
                "description": "List of live and upcoming sports matches and events.",
                "fields": {
                    "id": "Unique event identifier (e.g. 50002)",
                    "title": "Event title",
                    "eventInfo": "Object containing teams, logos, event name, start and end times",
                    "formats": "Available stream quality/server names"
                },
                "usage_flow": "To play a live match/event: Fetch its stream links using '/channels/{id}.json' (e.g., '/channels/50002.json')."
            },
            "live_events_combined": {
                "path": "/events_with_channels.json",
                "description": "A consolidated central database combining all live events directly with their decrypted channel links. Recommended for web and single-page apps to avoid multiple fetch requests.",
                "fields": {
                    "id": "Event identifier",
                    "title": "Event title",
                    "decoded_channels": "Array of stream objects containing 'api', 'link', 'logo', and 'title'"
                }
            },
            "highlights": {
                "path": "/highlights.json",
                "description": "List of completed matches highlights and replays.",
                "fields": {
                    "id": "Unique highlight identifier (e.g. 100035)",
                    "title": "Match title",
                    "eventInfo": "Teams and start/end time metadata",
                    "formats": "Available highlight categories (e.g., HIGHLIGHTS, FULL MATCH)"
                },
                "usage_flow": "To play highlights: Fetch its stream links using '/channels/{id}.json' (e.g., '/channels/100035.json')."
            },
            "event_categories": {
                "path": "/eventcats.json",
                "description": "Filter categories for live events (e.g. Football, Cricket, Badminton)."
            }
        },
        "sub_directories": {
            "subcategory_details": {
                "path_pattern": "/cats/{catLink}.json",
                "description": "Contains list of channels inside a specific category (e.g. `/cats/bangla.json`).",
                "fields": {
                    "id": "Channel identifier (use this to fetch stream links from /channels/{id}.json)",
                    "title": "Channel display name",
                    "image": "Channel logo URL"
                }
            },
            "decrypted_stream_links": {
                "path_pattern": "/channels/{id}.json",
                "description": "Contains decrypted playback streams for any specific live event, highlight, or TV channel.",
                "fields": {
                    "title": "Stream title/quality/server name (e.g. beIN Sports HD)",
                    "link": "The playback stream URL (DASH/MPD or HLS/M3U8). Note: Some URLs contain headers like '|user-agent=...' or '|Cookie=...' which MUST be parsed and set as custom request headers in your player.",
                    "api": "ClearKey decryption keys in the format 'kid:key' for encrypted DASH streams (if applicable)."
                },
                "player_decryption_handling": "If 'api' is present (e.g. '385ceb97...:18dce92...'), it represents a DRM protected stream. Split the 'api' string by ':' to get the Key ID (left) and Key (right), and pass them to your player's DRM ClearKey configuration."
            }
        }
    }
    spec_file = os.path.join(out_dir, "api_specification.json")
    with open(spec_file, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    print(f"  [SUCCESS] API Specification JSON saved to: {spec_file}")

def main():
    config = load_config()
    out_dir = config.get("output_directory", "public_decrypted")
    os.makedirs(out_dir, exist_ok=True)
    
    # Parse base domain from config cats endpoint (default fallback)
    import urllib.parse
    cats_url = config["endpoints"]["cats"]["url"]
    parsed_url = urllib.parse.urlparse(cats_url)
    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    devices = check_adb_devices()
    emulator_available = False
    apk_path, lib_path = None, None
    
    if not devices:
        print("WARNING: No emulator/device detected via ADB.")
        print("Continuing with local decryption only. 'deadbeef' format files (events, cats, highlights) will be skipped.")
    else:
        print(f"Connected devices: {devices}")
        print("Ensuring adb runs as root...")
        subprocess.run(["adb", "root"], capture_output=True)
        subprocess.run(["adb", "wait-for-device"], capture_output=True)
        apk_path, lib_path = get_device_paths()
        if apk_path and lib_path:
            emulator_available = True
            ensure_decryptor_jar()
            print("Emulator decryption engine is READY!")
            
            # --- Dynamic Domain Resolution ---
            print("\n=== Resolving Active API Domain from Emulator ===")
            try:
                # 1. Force stop and restart app to force Remote Config fetch
                print("    Launching SportzX on emulator to trigger Remote Config fetch...")
                subprocess.run(["adb", "shell", "am force-stop com.sportzx.live"], capture_output=True)
                subprocess.run(["adb", "shell", "am start -n com.sportzx.live/com.sportzx.live.activities.SplashActivity"], capture_output=True)
                time.sleep(12)
                subprocess.run(["adb", "shell", "am force-stop com.sportzx.live"], capture_output=True)
                
                # 2. Copy and pull appPref.xml binary-safely
                local_xml = os.path.join(os.getcwd(), "temp_appPref.xml")
                if os.path.exists(local_xml):
                    os.remove(local_xml)
                    
                # Clean up any stale files on device first
                subprocess.run(["adb", "shell", "rm -f /data/local/tmp/appPref.xml"], capture_output=True)
                
                # Force adb root state again just in case
                subprocess.run(["adb", "root"], capture_output=True)
                subprocess.run(["adb", "wait-for-device"], capture_output=True)
                    
                whoami_res = subprocess.run(["adb", "shell", "whoami"], capture_output=True)
                whoami_out = whoami_res.stdout.decode("utf-8", errors="ignore")
                is_root = "root" in whoami_out
                
                shared_prefs_path = "/data/data/com.sportzx.live/shared_prefs/appPref.xml"
                if is_root:
                    subprocess.run(["adb", "shell", f"cp {shared_prefs_path} /data/local/tmp/appPref.xml"], capture_output=True)
                    subprocess.run(["adb", "shell", "chmod 666 /data/local/tmp/appPref.xml"], capture_output=True)
                else:
                    res = subprocess.run(["adb", "shell", f"su -c 'cp {shared_prefs_path} /data/local/tmp/appPref.xml && chmod 666 /data/local/tmp/appPref.xml'"], capture_output=True)
                    res_err = res.stderr.decode("utf-8", errors="ignore")
                    res_out = res.stdout.decode("utf-8", errors="ignore")
                    if "invalid uid/gid" in res_err or "invalid uid/gid" in res_out:
                        subprocess.run(["adb", "shell", f"su root 'cp {shared_prefs_path} /data/local/tmp/appPref.xml && chmod 666 /data/local/tmp/appPref.xml'"], capture_output=True)
                
                pull_res = subprocess.run(["adb", "pull", "/data/local/tmp/appPref.xml", local_xml], capture_output=True)
                subprocess.run(["adb", "shell", "rm -f /data/local/tmp/appPref.xml"], capture_output=True)
                
                if os.path.exists(local_xml):
                    with open(local_xml, "r", encoding="utf-8", errors="ignore") as xf:
                        xml_content = xf.read()
                    os.remove(local_xml)
                    
                    import re
                    match = re.search(r'<string name="last_success_api_url">(https?://[^<]+)</string>', xml_content)
                    if match:
                        detected_url = match.group(1).strip()
                        if detected_url.endswith("/"):
                            detected_url = detected_url[:-1]
                        print(f"    [Auto Domain] Detected active API base domain: {detected_url}")
                        
                        # Update base_domain
                        base_domain = detected_url
                        
                        # Update config endpoints dynamically
                        for ep_name in config["endpoints"]:
                            old_url = config["endpoints"][ep_name]["url"]
                            parsed_ep = urllib.parse.urlparse(old_url)
                            new_url = f"{base_domain}{parsed_ep.path}"
                            config["endpoints"][ep_name]["url"] = new_url
                            
                        # Save updated config.json
                        with open("config.json", "w", encoding="utf-8") as f:
                            json.dump(config, f, indent=2, ensure_ascii=False)
                        print("    [Auto Domain] Updated config.json with active domain URLs.")
                    else:
                        print("    [Auto Domain] last_success_api_url not found in appPref.xml.")
                else:
                    print("    [Auto Domain] Failed to pull appPref.xml from emulator.")
                    print("                  Make sure you have granted Superuser (root) permission to 'Shell' in your emulator's GUI.")
            except Exception as ade:
                print(f"    [Auto Domain] Error resolving domain: {ade}")
            
    for name, ep_info in config["endpoints"].items():
        url = ep_info["url"]
        format_type = ep_info["format"]
        print(f"\nProcessing endpoint '{name}' ({url})...")
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as response:
                response_json = json.loads(response.read().decode("utf-8"))
                
            payload = response_json.get("data")
            if not payload:
                print(f"  Skipping {name}: 'data' field is empty.")
                continue
                
            enc_bytes = clean_and_decode_b64(payload)
            decrypted_json = None
            
            if format_type == "b5cdbd48":
                iv_str = "HsjJTCA7jJztpL2w"
                print(f"  Decrypting locally using static key and IV '{iv_str}'...")
                decrypted_json = decrypt_local_b5cdbd48(enc_bytes, iv_str)
                
            elif format_type == "deadbeef":
                print(f"  Decrypting {name}...")
                decrypted_json = decrypt_data(payload, apk_path, lib_path)
                
            if not decrypted_json:
                output_file = os.path.join(out_dir, f"{name}.json")
                cats_file = os.path.join(out_dir, "cats", f"{name}.json")
                target = output_file if os.path.exists(output_file) else (cats_file if os.path.exists(cats_file) else None)
                if target:
                    try:
                        with open(target, "r", encoding="utf-8") as cached_f:
                            decrypted_json = json.load(cached_f)
                        print(f"  [CACHED FALLBACK] Loaded existing decrypted data for '{name}' ({len(decrypted_json)} items)")
                    except Exception as ce:
                        print(f"  [CACHED FAIL] Could not read cached file for '{name}': {ce}")

            if decrypted_json:
                # Add 100000 offset to highlight IDs for compatibility
                if name == "highlights" and isinstance(decrypted_json, list):
                    for item in decrypted_json:
                        if "id" in item:
                            try:
                                item["id"] = int(item["id"]) + 100000
                            except Exception:
                                pass
                decrypted_json = replace_sportzx_with_dudetv(decrypted_json)
                output_file = os.path.join(out_dir, f"{name}.json")
                with open(output_file, "w", encoding="utf-8") as out_f:
                    json.dump(decrypted_json, out_f, indent=2, ensure_ascii=False)
                print(f"  [SUCCESS] Saved output: {output_file} ({len(decrypted_json)} items)")
                
                # If this is sports.json, also mirror it into subcategory directory (cats/sports.json)
                if name == "sports":
                    sub_dir = os.path.join(out_dir, "cats")
                    os.makedirs(sub_dir, exist_ok=True)
                    sports_sub_file = os.path.join(sub_dir, "sports.json")
                    with open(sports_sub_file, "w", encoding="utf-8") as sf:
                        json.dump(decrypted_json, sf, indent=2, ensure_ascii=False)
                    print(f"  [SUCCESS] Mirrored sports.json to: {sports_sub_file}")

                # If this is cats.json, process individual subcategory files
                if name == "cats":
                    print("  Processing individual subcategories...")
                    sub_dir = os.path.join(out_dir, "cats")
                    os.makedirs(sub_dir, exist_ok=True)
                    updated_cats = []
                    
                    for i, cat in enumerate(decrypted_json):
                        cat_id = cat.get("id")
                        title = cat.get("title", f"Category {cat_id}")
                        cat_link = cat.get("catLink")
                        
                        cat_copy = dict(cat)
                        if cat_link and not cat_link.startswith("http"):
                            # Normalize slug to avoid paths like 'cats/cats/bangla.json.json' or case mismatches like 'Sports'
                            clean_slug = cat_link.strip()
                            if clean_slug.startswith("cats/"):
                                clean_slug = clean_slug[5:]
                            if clean_slug.endswith(".json"):
                                clean_slug = clean_slug[:-5]
                            clean_slug = clean_slug.lower()

                            print(f"    [{i+1}/{len(decrypted_json)}] Fetching subcategory: {title} ({clean_slug})...")
                            sub_fetched = False
                            try:
                                relative_path = f"cats/{clean_slug}.json"
                                sub_url = f"{base_domain}/{relative_path}"
                                sub_req = urllib.request.Request(sub_url, headers={"User-Agent": "Mozilla/5.0"})
                                with urllib.request.urlopen(sub_req, timeout=15) as sub_res:
                                    sub_json = json.loads(sub_res.read().decode("utf-8"))
                                
                                sub_payload = sub_json.get("data")
                                if sub_payload:
                                    sub_data = decrypt_data(sub_payload, apk_path, lib_path)
                                                
                                    if sub_data:
                                        sub_data = replace_sportzx_with_dudetv(sub_data)
                                        sub_out_file = os.path.join(sub_dir, f"{clean_slug}.json")
                                        with open(sub_out_file, "w", encoding="utf-8") as sub_f:
                                            json.dump(sub_data, sub_f, indent=2, ensure_ascii=False)
                                        print(f"      Saved: {sub_out_file} ({len(sub_data)} channels)")
                                        cat_copy["catLink"] = f"cats/{clean_slug}.json"
                                        sub_fetched = True
                                        
                                        # If sports subcategory, also sync root sports.json
                                        if clean_slug == "sports":
                                            root_sports_file = os.path.join(out_dir, "sports.json")
                                            with open(root_sports_file, "w", encoding="utf-8") as rsf:
                                                json.dump(sub_data, rsf, indent=2, ensure_ascii=False)
                                            print(f"      Synced root sports file: {root_sports_file}")
                                    else:
                                        print(f"      Failed to parse decrypted JSON for {clean_slug}")
                            except Exception as ce:
                                print(f"      Failed to process subcategory {clean_slug}: {ce}")

                            if not sub_fetched:
                                sub_out_file = os.path.join(sub_dir, f"{clean_slug}.json")
                                root_file = os.path.join(out_dir, f"{clean_slug}.json")
                                if os.path.exists(sub_out_file) or os.path.exists(root_file):
                                    cat_copy["catLink"] = f"cats/{clean_slug}.json"
                                    print(f"      [CACHED LINK] Preserved subcategory catLink: cats/{clean_slug}.json")
                                
                        updated_cats.append(cat_copy)
                        
                    with open(output_file, "w", encoding="utf-8") as out_f:
                        json.dump(updated_cats, out_f, indent=2, ensure_ascii=False)
                    print(f"  [SUCCESS] Updated {output_file} with hosted API links.")
                
                # If this is events.json, process individual channels
                if name == "events":
                    print("  Processing individual channels for each event (merging main and fallback)...")
                    ch_dir = os.path.join(out_dir, "channels")
                    os.makedirs(ch_dir, exist_ok=True)
                    events_with_channels = []
                    
                    for i, event in enumerate(decrypted_json):
                        event_id = event.get("id")
                        title = event.get("title", f"Event {event_id}")
                        print(f"    [{i+1}/{len(decrypted_json)}] Fetching channels for: {title} (ID: {event_id})...")
                        
                        event_channels = []
                        ch_out_file = os.path.join(ch_dir, f"{event_id}.json")
                        channel_status = "unavailable"  # default
                        
                        channels1 = []
                        channels2 = []
                        fetched_successfully = False

                        # 1. Fetch main ID channels
                        try:
                            ch_url = f"{base_domain}/channels/{event_id}.json"
                            ch_req = urllib.request.Request(ch_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(ch_req, timeout=15) as ch_res:
                                ch_json = json.loads(ch_res.read().decode("utf-8"))
                            
                            ch_payload = ch_json.get("data")
                            if ch_payload:
                                dec_ch = decrypt_data(ch_payload, apk_path, lib_path)
                                if dec_ch:
                                    channels1 = replace_sportzx_with_dudetv(dec_ch)
                                    fetched_successfully = True
                                    print(f"      Fetched {event_id}.json ({len(channels1)} channels)")
                        except Exception as ce:
                            print(f"      Main attempt failed for {event_id}: {ce}")

                        # 2. Fetch fallback ID 'e' channels
                        try:
                            ch_url = f"{base_domain}/channels/{event_id}e.json"
                            ch_req = urllib.request.Request(ch_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(ch_req, timeout=15) as ch_res:
                                ch_json = json.loads(ch_res.read().decode("utf-8"))
                            
                            ch_payload = ch_json.get("data")
                            if ch_payload:
                                dec_ch = decrypt_data(ch_payload, apk_path, lib_path)
                                if dec_ch:
                                    channels2 = replace_sportzx_with_dudetv(dec_ch)
                                    fetched_successfully = True
                                    print(f"      Fetched fallback {event_id}e.json ({len(channels2)} channels)")
                        except Exception as ce2:
                            print(f"      Fallback attempt failed for {event_id}e: {ce2}")

                        # 3. Merge and deduplicate channels if we fetched anything
                        if fetched_successfully:
                            seen_links = set()
                            merged_channels = []
                            for ch in (channels1 + channels2):
                                # Clean link comparison by ignoring query params or request headers after '|'
                                link = ch.get("link", "").split("|")[0].strip()
                                if link and link not in seen_links:
                                    seen_links.add(link)
                                    merged_channels.append(ch)
                            
                            event_channels = merged_channels
                            channel_status = "live"
                            with open(ch_out_file, "w", encoding="utf-8") as ch_f:
                                json.dump(event_channels, ch_f, indent=2, ensure_ascii=False)
                            print(f"      Saved merged: {ch_out_file} ({len(event_channels)} channels) [LIVE]")

                        # If both attempts failed to fetch live data, use cache if available
                        if not fetched_successfully:
                            if os.path.exists(ch_out_file):
                                try:
                                    with open(ch_out_file, "r", encoding="utf-8") as cached_f:
                                        event_channels = json.load(cached_f)
                                    event_channels = replace_sportzx_with_dudetv(event_channels)
                                    channel_status = "cached"  # using last known good
                                    print(f"      [CACHED] Using last known data for {event_id} ({len(event_channels)} channels)")
                                except Exception as cached_err:
                                    channel_status = "unavailable"
                                    print(f"      [UNAVAILABLE] Cache read error for {event_id}: {cached_err}")
                            else:
                                channel_status = "unavailable"
                                print(f"      [UNAVAILABLE] No data or cache available for {event_id}")
                            
                        # Add channels metadata to event object
                        event_copy = dict(event)
                        event_copy["decoded_channels"] = event_channels
                        event_copy["channel_status"] = channel_status  # live / cached / unavailable
                        events_with_channels.append(event_copy)
                        
                    # Save combined file
                    combined_file = os.path.join(out_dir, "events_with_channels.json")
                    with open(combined_file, "w", encoding="utf-8") as comb_f:
                        json.dump(events_with_channels, comb_f, indent=2, ensure_ascii=False)
                    print(f"  [SUCCESS] Saved combined channels mapping to: {combined_file}")
            else:
                print(f"  [FAILED] Failed to decrypt {name}")
                
        except Exception as e:
            print(f"  [ERROR] Failed to process {name}: {e}")

    # Collect and process all unique TV channel stream links from all subcategories
    # We run this even if emulator is not available because we have local decryption fallback
    print("\n=== Harvesting TV Channel Streams from Subcategories ===")
    ch_dir = os.path.join(out_dir, "channels")
    os.makedirs(ch_dir, exist_ok=True)
    
    tv_channel_ids = set()
    
    # Read subcategory files from public_decrypted/cats/
    sub_dir = os.path.join(out_dir, "cats")
    if os.path.exists(sub_dir):
        for file_name in os.listdir(sub_dir):
            if file_name.endswith(".json"):
                sub_path = os.path.join(sub_dir, file_name)
                try:
                    with open(sub_path, "r", encoding="utf-8") as sf:
                        channels_list = json.load(sf)
                    if isinstance(channels_list, list):
                        for ch in channels_list:
                            ch_id = ch.get("id")
                            if ch_id:
                                tv_channel_ids.add(str(ch_id))
                except Exception as e:
                    print(f"Error reading subcategory file {file_name}: {e}")
                    
    # Read channels from sports.json (main category file)
    sports_path = os.path.join(out_dir, "sports.json")
    if os.path.exists(sports_path):
        try:
            with open(sports_path, "r", encoding="utf-8") as sf:
                channels_list = json.load(sf)
            if isinstance(channels_list, list):
                for ch in channels_list:
                    ch_id = ch.get("id")
                    if ch_id:
                        tv_channel_ids.add(str(ch_id))
        except Exception as e:
            print(f"Error reading sports.json: {e}")
            
    # Read channels from highlights.json
    highlights_path = os.path.join(out_dir, "highlights.json")
    if os.path.exists(highlights_path):
        try:
            with open(highlights_path, "r", encoding="utf-8") as sf:
                channels_list = json.load(sf)
            if isinstance(channels_list, list):
                for ch in channels_list:
                    ch_id = ch.get("id")
                    if ch_id:
                        tv_channel_ids.add(str(ch_id))
        except Exception as e:
            print(f"Error reading highlights.json: {e}")
            
    print(f"Found {len(tv_channel_ids)} unique TV channel/highlight IDs in subcategories.")
    
    import hashlib
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Load payload hash cache (to skip unchanged channels)
    cache_file = os.path.join(out_dir, ".payload_cache.json")
    payload_cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as cf:
                payload_cache = json.load(cf)
        except Exception:
            payload_cache = {}
    
    # ── Phase 1: Parallel HTTP Fetch (all channels at once) ──────────────────────
    print(f"\n  [Phase 1] Fetching {len(tv_channel_ids)} channel payloads in parallel...")
    
    def fetch_channel_payload(ch_id):
        """Fetch encrypted payload for a single channel. Returns (ch_id, payload_str or None, error)."""
        try:
            # Map highlight ID (>= 100000) to actual server ID (id - 100000)
            server_id = ch_id
            try:
                val = int(ch_id)
                if val >= 100000:
                    server_id = str(val - 100000)
            except Exception:
                pass
                
            ch_url = f"{base_domain}/channels/{server_id}.json"
            ch_req = urllib.request.Request(ch_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(ch_req, timeout=12) as ch_res:
                ch_json = json.loads(ch_res.read().decode("utf-8"))
            payload = ch_json.get("data")
            return (ch_id, payload, None)
        except Exception as e:
            return (ch_id, None, str(e))
    
    fetched_payloads = {}   # ch_id → payload string
    fetch_errors = {}       # ch_id → error message
    
    sorted_ids = sorted(list(tv_channel_ids))
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(fetch_channel_payload, ch_id): ch_id for ch_id in sorted_ids}
        done_count = 0
        for future in as_completed(futures):
            ch_id, payload, err = future.result()
            done_count += 1
            if payload:
                fetched_payloads[ch_id] = payload
            elif err:
                fetch_errors[ch_id] = err
            # Print progress every 20 channels
            if done_count % 20 == 0 or done_count == len(sorted_ids):
                print(f"    Downloaded {done_count}/{len(sorted_ids)} channels...")
    
    print(f"  [Phase 1 done] {len(fetched_payloads)} payloads fetched, {len(fetch_errors)} errors.")
    
    # ── Phase 2 & 3: Cache check + Sequential JNI decrypt ────────────────────────
    print(f"\n  [Phase 2&3] Checking cache and decrypting changed channels...")
    
    new_cache = dict(payload_cache)  # start with old cache, update as we go
    skipped = 0
    decrypted_count = 0
    
    for idx, ch_id in enumerate(sorted_ids):
        ch_out_file = os.path.join(ch_dir, f"{ch_id}.json")
        
        if ch_id not in fetched_payloads:
            # Fetch failed — use cached file if it exists
            if ch_id in fetch_errors:
                err = fetch_errors[ch_id]
                if not any(skip_kw in err for skip_kw in ["404", "Not Found"]):
                    print(f"    [{idx+1}/{len(sorted_ids)}] Channel {ch_id}: fetch error — {err}")
            continue
        
        ch_payload = fetched_payloads[ch_id]
        
        # Phase 2: Hash check
        payload_hash = hashlib.sha256(ch_payload.encode("utf-8", errors="ignore")).hexdigest()
        
        if (payload_cache.get(ch_id) == payload_hash) and os.path.exists(ch_out_file):
            # Payload unchanged — skip decryption
            skipped += 1
            continue
        
        # Phase 3: Payload changed → decrypt
        print(f"    [{idx+1}/{len(sorted_ids)}] Decrypting channel {ch_id} (payload changed)...")
        try:
            dec_ch = decrypt_data(ch_payload, apk_path, lib_path)
            if dec_ch:
                dec_ch = replace_sportzx_with_dudetv(dec_ch)
                with open(ch_out_file, "w", encoding="utf-8") as ch_f:
                    json.dump(dec_ch, ch_f, indent=2, ensure_ascii=False)
                new_cache[ch_id] = payload_hash
                decrypted_count += 1
                print(f"      Saved: {ch_out_file} ({len(dec_ch)} channels)")
        except Exception as ce:
            print(f"      Failed to decrypt channel {ch_id}: {ce}")
    
    # Save updated cache
    try:
        with open(cache_file, "w", encoding="utf-8") as cf:
            json.dump(new_cache, cf, ensure_ascii=False)
    except Exception:
        pass
    
    print(f"\n  [Done] Decrypted: {decrypted_count} | Cached (skipped): {skipped} | Errors: {len(fetch_errors)}")


    # Write the API specification JSON file
    write_api_specification(out_dir)

    print("\nProcessing complete!")

if __name__ == "__main__":
    main()
