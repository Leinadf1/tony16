import os
import sys
import time
import json
import hashlib
import lzma
import shutil
import subprocess
import urllib.request
import requests
from pathlib import Path

# ---------- Configurazione ----------
ANDROID_HOME = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
if not ANDROID_HOME:
    print("Errore: ANDROID_HOME non impostato.")
    sys.exit(1)

API_LEVEL = "33"
ANDROID_JAR = os.path.join(ANDROID_HOME, "platforms", f"android-{API_LEVEL}", "android.jar")

DECRYPTOR_JAVA = "Decryptor.java"
DECRYPTOR_JAR = "Decryptor.jar"

# URL diretto del frida-server.xz nella repo originale
FRIDA_DOWNLOAD_URL = "https://raw.githubusercontent.com/mdjamsad9/dudetvapi/main/frida-server.xz"
FRIDA_SERVER_BIN = "frida-server"
FRIDA_SERVER_XZ = "frida-server.xz"

# Endpoints principali da decifrare
ENDPOINTS = ["cats", "sports", "eventcats", "events", "highlights"]

# Template URL per i payload dei singoli canali
# ⚠️ ADATTA questo in base all'endpoint reale usato dall'app
CHANNEL_PAYLOAD_URL_TEMPLATE = "{base_url}/channel/{channel_id}.json"

# Cartelle di output
PUBLIC_DECRYPTED_DIR = Path("public_decrypted")
CHANNELS_DIR = PUBLIC_DECRYPTED_DIR / "channels"
CHANNELS_DIR.mkdir(parents=True, exist_ok=True)

# File di cache
CACHE_FILE = PUBLIC_DECRYPTED_DIR / ".payload_cache.json"
if CACHE_FILE.exists():
    with open(CACHE_FILE, "r") as f:
        PAYLOAD_CACHE = json.load(f)
else:
    PAYLOAD_CACHE = {}

# ---------- Funzioni base ----------

def run_adb(args, check=True, timeout=None):
    cmd = ["adb"] + args
    print(f"ADB: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        print(f"Errore ADB: {result.stderr}")
        sys.exit(1)
    return result

def ensure_frida_server():
    """Scarica ed estrae frida-server se non è già presente."""
    if os.path.exists(FRIDA_SERVER_BIN):
        print("frida-server già presente.")
        return

    if not os.path.exists(FRIDA_SERVER_XZ):
        print(f"Scaricamento di {FRIDA_DOWNLOAD_URL} ...")
        urllib.request.urlretrieve(FRIDA_DOWNLOAD_URL, FRIDA_SERVER_XZ)
        print("Download completato.")
    else:
        print("Archivio frida-server.xz già presente.")

    print("Decompressione di frida-server...")
    with lzma.open(FRIDA_SERVER_XZ, 'rb') as f_in:
        with open(FRIDA_SERVER_BIN, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.chmod(FRIDA_SERVER_BIN, 0o755)
    print("frida-server pronto.")

def ensure_decryptor_jar():
    """Compila Decryptor.java se il jar non esiste o se il sorgente è più recente."""
    if not os.path.exists(DECRYPTOR_JAVA):
        print(f"Errore: {DECRYPTOR_JAVA} non trovato nella directory corrente.")
        sys.exit(1)

    need_compile = False
    if not os.path.exists(DECRYPTOR_JAR):
        need_compile = True
    elif os.path.getmtime(DECRYPTOR_JAVA) > os.path.getmtime(DECRYPTOR_JAR):
        need_compile = True

    if need_compile:
        print("Compilazione di Decryptor.java...")
        cmd = [
            "javac",
            "--release", "8",
            "-cp", ANDROID_JAR,
            DECRYPTOR_JAVA
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Compilazione fallita:\n{result.stderr}")
            sys.exit(1)
        print("Compilazione completata.")
    else:
        print("Decryptor.jar già aggiornato.")

def start_frida_server():
    """Avvia frida-server sull'emulatore."""
    print("Avvio di frida-server sull'emulatore...")
    run_adb(["push", FRIDA_SERVER_BIN, "/data/local/tmp/frida-server"])
    run_adb(["shell", "chmod", "755", "/data/local/tmp/frida-server"])
    subprocess.Popen(["adb", "shell", "/data/local/tmp/frida-server", "&"])
    time.sleep(3)
    print("frida-server avviato.")

def launch_sportzx():
    """Lancia l'app SportzX per attivare il Remote Config."""
    print("Lancio SportzX sull'emulatore...")
    run_adb(["shell", "monkey", "-p", "com.sportzx.live", "1"])
    time.sleep(8)

def get_active_api_domain():
    """Legge il dominio API attivo dal logcat o usa il fallback."""
    print("Individuazione del dominio API attivo...")
    try:
        logcat = subprocess.check_output(["adb", "logcat", "-d", "-s", "SportzX", "RemoteConfig"], text=True)
        import re
        match = re.search(r'https?://[^\s"]+', logcat)
        if match:
            domain = match.group(0).rstrip('",')
            print(f"[Auto Domain] Rilevato: {domain}")
            return domain
    except Exception as e:
        print(f"Lettura logcat fallita: {e}")

    fallback_domain = "https://app.modijitop.top"
    print(f"[Auto Domain] Uso dominio predefinito: {fallback_domain}")
    return fallback_domain

# ---------- Decifratura ----------

def decrypt_with_jar(payload: str) -> str:
    """Tenta la decifratura usando Decryptor.jar tramite app_process."""
    print("Tentativo decifratura con Decryptor.jar...")
    temp_file = "temp_encrypted.txt"
    with open(temp_file, "w") as f:
        f.write(payload)

    run_adb(["push", temp_file, "/data/local/tmp/temp_encrypted.txt"])
    cmd = [
        "adb", "shell",
        "app_process",
        "-Djava.class.path=/data/local/tmp/Decryptor.jar",
        "/data/local/tmp",
        "Decryptor",
        "/data/local/tmp/temp_encrypted.txt",
        "/data/local/tmp/temp_decrypted.txt"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"Decryptor fallito: {result.stderr}")
        return None

    run_adb(["pull", "/data/local/tmp/temp_decrypted.txt", "temp_decrypted.txt"])
    with open("temp_decrypted.txt", "r") as f:
        decrypted = f.read()

    os.remove(temp_file)
    os.remove("temp_decrypted.txt")
    return decrypted

def decrypt_with_frida(payload: str) -> str:
    """
    Usa Frida per decifrare il payload agganciando l'app SportzX.
    Questo è un placeholder: va adattato alla classe reale dell'app.
    """
    print("Tentativo decifratura con Frida...")
    frida_script = """
import frida
import sys

def on_message(message, data):
    if message['type'] == 'send':
        print("[FRIDA]", message['payload'])
    elif message['type'] == 'error':
        print("[FRIDA ERROR]", message['stack'])

device = frida.get_usb_device(timeout=10)
session = device.attach("com.sportzx.live")
script = session.create_script(\"\"\"
Java.perform(function () {
    var Decryptor = Java.use('com.sportzx.live.utils.Decryptor');
    Decryptor.decrypt.overload('java.lang.String').implementation = function (encrypted) {
        var result = this.decrypt(encrypted);
        send({encrypted: encrypted, decrypted: result});
        return result;
    };
});
\"\"\")
script.on('message', on_message)
script.load()
sys.stdin.read()
"""
    frida_script_file = "frida_hook.py"
    with open(frida_script_file, "w") as f:
        f.write(frida_script)

    proc = subprocess.Popen(["python", frida_script_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(10)
    proc.terminate()

    stdout, _ = proc.communicate()
    decrypted = None
    import re
    for line in stdout.splitlines():
        if "decrypted" in line:
            match = re.search(r'"decrypted": "(.*)"', line)
            if match:
                decrypted = match.group(1)
                break
    os.remove(frida_script_file)
    return decrypted

def decrypt_payload(payload: str) -> str:
    """Prova prima con JAR, poi con Frida."""
    decrypted = decrypt_with_jar(payload)
    if decrypted is None:
        decrypted = decrypt_with_frida(payload)
    return decrypted

# ---------- Harvesting ----------

def extract_channel_ids(json_data):
    """
    Estrae ricorsivamente tutti gli ID numerici di 5 cifre (o qualsiasi campo
    che contenga 'id' nel nome) da un JSON decifrato.
    Restituisce un set di stringhe.
    """
    ids = set()

    def _extract(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Se la chiave contiene 'id' (case-insensitive) e il valore è un numero o stringa numerica
                if 'id' in key.lower():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        ids.add(str(int(value)))
                    elif isinstance(value, str) and value.isdigit():
                        ids.add(value)
                # Ricorsione su valori annidati
                _extract(value)
        elif isinstance(obj, list):
            for item in obj:
                _extract(item)

    _extract(json_data)
    # Filtra solo ID di 5 cifre (come 50002) – rimuovi questo filtro se non serve
    return {i for i in ids if len(i) == 5 and i.isdigit()}

def fetch_channel_payload(channel_id: str, base_url: str) -> str:
    """Scarica il payload cifrato del canale."""
    url = CHANNEL_PAYLOAD_URL_TEMPLATE.format(base_url=base_url, channel_id=channel_id)
    print(f"  Scaricamento payload per {channel_id}: {url}")
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.text
        else:
            print(f"  Errore HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  Errore download: {e}")
        return None

def process_channel(channel_id: str, base_url: str):
    """Scarica e decifra un singolo canale, aggiornando la cache."""
    payload = fetch_channel_payload(channel_id, base_url)
    if payload is None:
        return False

    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    # ⚠️ NOTA: forziamo l'aggiornamento per questo run, quindi commentiamo il salto cache
    # if channel_id in PAYLOAD_CACHE and PAYLOAD_CACHE[channel_id] == payload_hash:
    #     print(f"  {channel_id}: invariato, uso cache.")
    #     channel_file = CHANNELS_DIR / f"{channel_id}.json"
    #     if channel_file.exists():
    #         return True

    print(f"  Decifratura payload per {channel_id}...")
    decrypted = decrypt_payload(payload)
    if decrypted is None:
        print(f"  [FAILED] Decifratura canale {channel_id} fallita.")
        return False

    # Salva il JSON decifrato
    channel_file = CHANNELS_DIR / f"{channel_id}.json"
    with open(channel_file, "w") as f:
        f.write(decrypted)

    # Aggiorna cache
    PAYLOAD_CACHE[channel_id] = payload_hash
    print(f"  Salvato {channel_file}")
    return True

def harvest_channels(base_url: str):
    """Esegue l'harvesting degli ID canale dai JSON decifrati principali."""
    print("\n=== Harvesting TV Channel Streams from Subcategories ===")
    all_ids = set()

    for endpoint in ENDPOINTS:
        json_file = PUBLIC_DECRYPTED_DIR / f"{endpoint}.json"
        if not json_file.exists():
            print(f"  {json_file} non trovato, salto.")
            continue
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            ids = extract_channel_ids(data)
            print(f"  {endpoint}: trovati {len(ids)} ID")
            all_ids.update(ids)
        except Exception as e:
            print(f"  Errore lettura {json_file}: {e}")

    print(f"  Totale ID unici: {len(all_ids)}")
    if all_ids:
        print("  ID trovati (primi 20):", sorted(all_ids)[:20])
    else:
        print("  Nessun ID trovato. Verifica la struttura dei JSON decifrati.")
        # Stampa la struttura del primo file disponibile per debug
        for endpoint in ENDPOINTS:
            json_file = PUBLIC_DECRYPTED_DIR / f"{endpoint}.json"
            if json_file.exists():
                with open(json_file, "r") as f:
                    data = json.load(f)
                print(f"  Struttura di {endpoint}.json (prime chiavi):",
                      list(data.keys()) if isinstance(data, dict) else type(data))
                break
        return

    # Fase 1: download e decifratura (sequenziale per semplicità)
    print("  [Phase 1] Fetching payloads...")
    success = 0
    errors = 0
    for channel_id in sorted(all_ids):
        if process_channel(channel_id, base_url):
            success += 1
        else:
            errors += 1

    print(f"  [Done] Decrypted: {success} | Errors: {errors}")

    # Salva la cache aggiornata
    with open(CACHE_FILE, "w") as f:
        json.dump(PAYLOAD_CACHE, f, indent=2)

# ---------- Main ----------

def main():
    print("Attendo che l'emulatore sia pronto...")
    run_adb(["wait-for-device"])
    time.sleep(5)

    ensure_decryptor_jar()
    ensure_frida_server()
    start_frida_server()
    launch_sportzx()

    base_url = get_active_api_domain()
    print(f"Dominio API attivo: {base_url}")

    # Salva config.json
    config = {
        "last_update": time.time(),
        "active_api_base": base_url,
        "source": "dudetv_3.2v.apk"
    }
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Processa gli endpoint principali
    for endpoint in ENDPOINTS:
        url = f"{base_url}/{endpoint}.json"
        print(f"\nProcesso endpoint '{endpoint}' ({url})...")
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"  Errore HTTP {resp.status_code}")
                continue
            payload = resp.text
        except Exception as e:
            print(f"  Errore download: {e}")
            continue

        print(f"  Decifratura di {endpoint}...")
        decrypted = decrypt_payload(payload)
        if decrypted is None:
            print(f"  [FAILED] Decifratura {endpoint} fallita.")
            continue

        output_file = PUBLIC_DECRYPTED_DIR / f"{endpoint}.json"
        with open(output_file, "w") as f:
            f.write(decrypted)
        print(f"  Salvato {output_file}")

    # Esegue l'harvesting dei canali
    harvest_channels(base_url)

    print("\nProcessing completo!")

if __name__ == "__main__":
    main()
