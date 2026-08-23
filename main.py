import os
import json
import base64
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

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

def replace_sportzx_with_dudetv(data):
    if isinstance(data, dict):
        return {k: replace_sportzx_with_dudetv(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_sportzx_with_dudetv(i) for i in data]
    elif isinstance(data, str):
        return data.replace("SportzX", "DUDE Tv").replace("sportzx", "dudetv")
    return data

def decrypt_cbc(ciphertext_bytes, key, iv):
    if len(ciphertext_bytes) % 16 != 0:
        ciphertext_bytes = ciphertext_bytes[:len(ciphertext_bytes) - (len(ciphertext_bytes) % 16)]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext_bytes) + decryptor.finalize()

def decrypt_payload(enc_bytes, key, hardcoded_iv):
    # 1. DEADBEEF format (magic 0xdeadbeef at byte 0 or byte 1)
    if len(enc_bytes) >= 20 and enc_bytes[:4] == b'\xde\xad\xbe\xef':
        iv = enc_bytes[4:20]
        ciphertext = enc_bytes[20:]
        decrypted_bytes = decrypt_cbc(ciphertext, key, iv)
    elif len(enc_bytes) >= 21 and enc_bytes[1:5] == b'\xde\xad\xbe\xef':
        iv = enc_bytes[5:21]
        ciphertext = enc_bytes[21:]
        decrypted_bytes = decrypt_cbc(ciphertext, key, iv)
    # 2. Dynamic IV Format starting with 0x02 (1 byte flag + 16 bytes IV + ciphertext)
    elif len(enc_bytes) >= 17 and enc_bytes[0] == 2:
        iv = enc_bytes[1:17]
        ciphertext = enc_bytes[17:]
        decrypted_bytes = decrypt_cbc(ciphertext, key, iv)
    # 3. Static IV Format
    else:
        decrypted_bytes = decrypt_cbc(enc_bytes, key, hardcoded_iv)
        
    dec_str = decrypted_bytes.decode("utf-8", errors="ignore").strip().rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10').strip()
    
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
        raise

def main():
    with open("config.json", "r") as f:
        config = json.load(f)
    
    key_var = config["aes_credentials"]["key_env_var"]
    iv_var = config["aes_credentials"]["iv_env_var"]
    
    key = os.environ.get(key_var, "6ayJ7jo@ao#pxVc%")
    iv = os.environ.get(iv_var, "HsjJTCA7jJztpL2w")
    
    key_bytes = key.encode("utf-8")
    iv_bytes = iv.encode("utf-8")
    
    out_dir = config.get("output_directory", "public_decrypted")
    os.makedirs(out_dir, exist_ok=True)
    
    endpoints = config["endpoints"]
    
    for name, ep_info in endpoints.items():
        url = ep_info["url"]
        format_type = ep_info.get("format", "b5cdbd48")
        
        print(f"Processing {name} from {url}...")
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            
            response_json = r.json()
            encrypted_payload = response_json.get("data")
            
            if not encrypted_payload:
                print(f"Skipping {name}: 'data' key not found.")
                continue
                
            enc_bytes = clean_and_decode_b64(encrypted_payload)
            decrypted_json = decrypt_payload(enc_bytes, key_bytes, iv_bytes)
            
            decrypted_json = replace_sportzx_with_dudetv(decrypted_json)
            output_file = os.path.join(out_dir, f"{name}.json")
            with open(output_file, "w", encoding="utf-8") as out_f:
                json.dump(decrypted_json, out_f, indent=2, ensure_ascii=False)
            print(f"Successfully saved decrypted output: {output_file}")
            
        except Exception as e:
            print(f"Failed to process {name}: {e}")

if __name__ == "__main__":
    main()
