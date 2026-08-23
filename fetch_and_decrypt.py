import os
import subprocess
import sys
import time
import requests
import json

# ---------- Configurazione ----------
ANDROID_HOME = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
if not ANDROID_HOME:
    print("Errore: ANDROID_HOME non è impostato.")
    sys.exit(1)

# API level dell'emulatore (modifica se necessario)
API_LEVEL = "33"
ANDROID_JAR = os.path.join(ANDROID_HOME, "platforms", f"android-{API_LEVEL}", "android.jar")

# Percorso del file Decryptor.java e del jar risultante
DECRYPTOR_JAVA = "Decryptor.java"
DECRYPTOR_JAR = "Decryptor.jar"

# ---------- Funzioni ----------
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

def run_decryptor():
    """Esegue Decryptor.jar tramite adb shell."""
    print("Esecuzione di Decryptor.jar sull'emulatore...")
    # Copia il jar sul dispositivo
    subprocess.run(["adb", "push", DECRYPTOR_JAR, "/data/local/tmp/"], check=True)
    subprocess.run(["adb", "shell", "app_process", "-Djava.class.path=/data/local/tmp/Decryptor.jar", "/data/local/tmp", "Decryptor"], check=True)
    # Nota: il nome della classe principale potrebbe essere diverso; adatta se necessario

def fetch_data():
    """Scarica i dati decifrati dall'emulatore o da un endpoint."""
    print("Recupero dei dati decifrati...")
    # Esempio: esegui un comando adb per estrarre file, oppure fai una richiesta HTTP
    # Qui dovresti implementare la logica effettiva di scraping/decifratura.
    # Per esempio, potresti usare adb pull per ottenere file decifrati.
    subprocess.run(["adb", "pull", "/sdcard/decrypted_data.json", "./public_decrypted/"], check=True)

def save_config():
    """Crea o aggiorna config.json."""
    config = {
        "last_update": time.time(),
        "source": "dudetv_3.2v.apk"
    }
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    print("config.json aggiornato.")

# ---------- Main ----------
def main():
    print("Attendo che l'emulatore sia pronto...")
    subprocess.run(["adb", "wait-for-device"], check=True)
    time.sleep(5)  # ulteriore attesa per la piena accensione

    ensure_decryptor_jar()
    run_decryptor()
    fetch_data()
    save_config()
    print("Operazioni completate con successo.")

if __name__ == "__main__":
    main()
