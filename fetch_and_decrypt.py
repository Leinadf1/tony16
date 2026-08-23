import os
import sys
import time
import json
import lzma
import shutil
import subprocess
import urllib.request
import requests

# ---------- Configurazione ----------
ANDROID_HOME = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
if not ANDROID_HOME:
    print("Errore: ANDROID_HOME non è impostato.")
    sys.exit(1)

API_LEVEL = "33"
ANDROID_JAR = os.path.join(ANDROID_HOME, "platforms", f"android-{API_LEVEL}", "android.jar")

DECRYPTOR_JAVA = "Decryptor.java"
DECRYPTOR_JAR = "Decryptor.jar"

FRIDA_VERSION = "17.17.0"
FRIDA_ARCH = "x86_64"
FRIDA_SERVER_FILENAME = f"frida-server-{FRIDA_VERSION}-android-{FRIDA_ARCH}.xz"
FRIDA_SERVER_XZ_PATH = os.path.join(os.getcwd(), FRIDA_SERVER_FILENAME)
FRIDA_SERVER_BIN_PATH = os.path.join(os.getcwd(), "frida-server")

# Endpoints da processare
ENDPOINTS = ["cats", "sports", "eventcats", "events", "highlights"]

# ---------- Funzioni ----------

def ensure_frida_server():
    """Scarica ed estrae frida-server se non è già presente."""
    if os.path.exists(FRIDA_SERVER_BIN_PATH):
        print("frida-server già presente.")
        return

    if not os.path.exists(FRIDA_SERVER_XZ_PATH):
        url = f"https://github.com/frida/frida/releases/download/{FRIDA_VERSION}/{FRIDA_SERVER_FILENAME}"
        print(f"Scaricamento di {url} ...")
        urllib.request.urlretrieve(url, FRIDA_SERVER_XZ_PATH)
        print("Download completato.")
    else:
        print("Archivio frida-server.xz già presente.")

    print("Estrazione di frida-server...")
    with lzma.open(FRIDA_SERVER_XZ_PATH, 'rb') as f_in:
        with open(FRIDA_SERVER_BIN_PATH, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.chmod(FRIDA_SERVER_BIN_PATH, 0o755)
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
    subprocess.run(["adb", "push", FRIDA_SERVER_BIN_PATH, "/data/local/tmp/frida-server"], check=True)
    subprocess.run(["adb", "shell", "chmod", "755", "/data/local/tmp/frida-server"], check=True)
    # Avvia in background
    subprocess.Popen(["adb", "shell", "/data/local/tmp/frida-server", "&"])
    time.sleep(3)
    print("frida-server avviato.")

def launch_sportzx():
    """Lancia l'app SportzX per attivare il Remote Config."""
    print("Lancio SportzX sull'emulatore...")
    subprocess.run(["adb", "shell", "monkey", "-p", "com.sportzx.live", "1"], check=True)
    time.sleep(8)  # attesa per il fetch del remote config

def get_active_api_domain():
    """Legge il dominio API attivo dal logcat o da un file remoto."""
    # Metodo semplice: cerca nel logcat una riga contenente 'base_url' o simili
    print("Individuazione del dominio API attivo...")
    try:
        logcat = subprocess.check_output(["adb", "logcat", "-d", "-s", "SportzX", "RemoteConfig"], text=True)
        # Cerca l'URL nel log
        import re
        match = re.search(r'https?://[^\s"]+', logcat)
        if match:
            domain = match.group(0).rstrip('",')
            print(f"[Auto Domain] Rilevato: {domain}")
            return domain
    except Exception as e:
        print(f"Lettura logcat fallita: {e}")

    # Fallback: dominio predefinito
    fallback_domain = "https://app.modijitop.top"
    print(f"[Auto Domain] Uso dominio predefinito: {fallback_domain}")
    return fallback_domain

def decrypt_with_jar(payload: str) -> str:
    """Tenta la decifratura usando Decryptor.jar tramite app_process."""
    print("Tentativo decifratura con Decryptor.jar...")
    # Scrivi il payload su un file temporaneo sull'host
    temp_file = "temp_encrypted.txt"
    with open(temp_file, "w") as f:
        f.write(payload)
    # Copia sul dispositivo
    subprocess.run(["adb", "push", temp_file, "/data/local/tmp/temp_encrypted.txt"], check=True)
    # Esegui Decryptor
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
    # Leggi il risultato
    subprocess.run(["adb", "pull", "/data/local/tmp/temp_decrypted.txt", "temp_decrypted.txt"], check=True)
    with open("temp_decrypted.txt", "r") as f:
        decrypted = f.read()
    os.remove(temp_file)
    os.remove("temp_decrypted.txt")
    return decrypted

def decrypt_with_frida(payload: str) -> str:
    """Usa Frida per decifrare il payload agganciando l'app SportzX."""
    print("Tentativo decifratura con Frida...")
    # Assicurati che frida-server sia in esecuzione
    # Esegui uno script Frida inline che intercetta la funzione di decifratura
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
script = session.create_script("""
Java.perform(function () {
    // Cerca la classe di decifratura (da adattare al nome reale)
    var Decryptor = Java.use('com.sportzx.live.utils.Decryptor');
    Decryptor.decrypt.overload('java.lang.String').implementation = function (encrypted) {
        var result = this.decrypt(encrypted);
        send({encrypted: encrypted, decrypted: result});
        return result;
    };
});
""")
script.on('message', on_message)
script.load()
sys.stdin.read()
"""
    # Salva lo script Frida in un file temporaneo
    frida_script_file = "frida_hook.py"
    with open(frida_script_file, "w") as f:
        f.write(frida_script)

    # Esegui lo script Frida in background
    proc = subprocess.Popen(["python", frida_script_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Invia il payload all'app tramite broadcast o altro metodo? Qui simuliamo: non è necessario,
    # lo script Frida aggancerà la decifratura quando l'app la chiama.
    # Per questo esempio, assumiamo che il payload venga decifrato internamente e che lo script invii il risultato.
    # Dovresti implementare la logica reale di comunicazione.
    time.sleep(10)
    proc.terminate()

    # Leggi l'output di Frida e cerca il valore decifrato
    stdout, _ = proc.communicate()
    # Estrai il JSON decifrato (supponendo che Frida l'abbia inviato)
    decrypted = None
    for line in stdout.splitlines():
        if "decrypted" in line:
            # Estrai il valore decifrato (semplificato)
            import re
            match = re.search(r'"decrypted": "(.*)"', line)
            if match:
                decrypted = match.group(1)
                break
    os.remove(frida_script_file)
    return decrypted

def process_endpoint(name: str, base_url: str):
    """Scarica l'endpoint cifrato e tenta la decifratura."""
    url = f"{base_url}/{name}.json"
    print(f"Processo endpoint '{name}' ({url})...")
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"  Errore HTTP {resp.status_code}")
            return None
        payload = resp.text
    except Exception as e:
        print(f"  Errore durante il download: {e}")
        return None

    print(f"  Decifratura di {name}...")
    decrypted = decrypt_with_jar(payload)
    if decrypted is None:
        print("  Decifratura JNI fallita, uso Frida...")
        decrypted = decrypt_with_frida(payload)
        if decrypted is None:
            print(f"  [FAILED] Decifratura {name} fallita.")
            return None

    # Salva il JSON decifrato
    output_file = os.path.join("public_decrypted", f"{name}.json")
    with open(output_file, "w") as f:
        f.write(decrypted)
    print(f"  Salvato {output_file}")
    return decrypted

def save_config(base_url: str):
    """Crea o aggiorna config.json."""
    config = {
        "last_update": time.time(),
        "active_api_base": base_url,
        "source": "dudetv_3.2v.apk"
    }
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    print("config.json aggiornato.")

def main():
    print("Attendo che l'emulatore sia pronto...")
    subprocess.run(["adb", "wait-for-device"], check=True)
    time.sleep(5)

    ensure_decryptor_jar()
    ensure_frida_server()
    start_frida_server()
    launch_sportzx()

    base_url = get_active_api_domain()
    save_config(base_url)

    os.makedirs("public_decrypted", exist_ok=True)

    total_success = 0
    for endpoint in ENDPOINTS:
        result = process_endpoint(endpoint, base_url)
        if result is not None:
            total_success += 1

    print(f"\nDecifrati con successo: {total_success}/{len(ENDPOINTS)}")
    print("Processing completo!")

if __name__ == "__main__":
    main()
