import os
import sys
import subprocess
import time
import requests
import shutil
import re

print("=" * 60)
print("🎭 AI Face Swap Studio - 1-Click Google Colab Runner")
print("=" * 60)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
MODELS_DIR = os.path.join(BACKEND_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def download_file_with_progress(urls, dest_path, min_size_bytes=50_000_000):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) >= min_size_bytes:
        print(f"✅ Already exists on disk: {os.path.basename(dest_path)} ({os.path.getsize(dest_path) // 1024 // 1024} MB)")
        return True

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for idx, url in enumerate(urls):
        print(f"📥 [{idx+1}/{len(urls)}] Downloading {os.path.basename(dest_path)} from: {url}")
        try:
            with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                temp_dest = dest_path + ".tmp"
                
                with open(temp_dest, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = int((downloaded / total_size) * 100)
                                mb_done = downloaded // (1024 * 1024)
                                mb_total = total_size // (1024 * 1024)
                                sys.stdout.write(f"\r   ⏳ Progress: [{mb_done}/{mb_total} MB] ({pct}%)")
                                sys.stdout.flush()
                
                sys.stdout.write("\n")
                if os.path.exists(temp_dest) and os.path.getsize(temp_dest) >= min_size_bytes:
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    os.rename(temp_dest, dest_path)
                    print(f"✅ Downloaded & Verified: {os.path.basename(dest_path)} ({os.path.getsize(dest_path) // 1024 // 1024} MB)\n")
                    return True
                else:
                    print("⚠️ Downloaded file size too small, trying next source...")
                    if os.path.exists(temp_dest):
                        os.remove(temp_dest)
        except Exception as e:
            print(f"⚠️ Source failed ({e}), trying fallback...")

    raise RuntimeError(f"❌ Failed to download model: {os.path.basename(dest_path)} from all sources.")

# 1. Download Required AI Models
inswapper_urls = [
    "https://huggingface.co/countfloyd/deepfake/resolve/main/inswapper_128.onnx",
    "https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/models/inswapper_128.onnx",
    "https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0/inswapper_128.onnx"
]

gfpgan_urls = [
    "https://huggingface.co/countfloyd/deepfake/resolve/main/GFPGANv1.4.onnx",
    "https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/models/GFPGANv1.4.onnx",
    "https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0/GFPGANv1.4.onnx"
]

download_file_with_progress(inswapper_urls, os.path.join(MODELS_DIR, "inswapper_128.onnx"), min_size_bytes=500_000_000)
download_file_with_progress(gfpgan_urls, os.path.join(MODELS_DIR, "gfpgan_1.4.onnx"), min_size_bytes=300_000_000)

alt_gfpgan = os.path.join(MODELS_DIR, "GFPGANv1.4.onnx")
main_gfpgan = os.path.join(MODELS_DIR, "gfpgan_1.4.onnx")
if os.path.exists(main_gfpgan) and not os.path.exists(alt_gfpgan):
    shutil.copyfile(main_gfpgan, alt_gfpgan)

# 2. Setup Cloudflared Tunnel
cloudflared_path = shutil.which("cloudflared") or os.path.join(BASE_DIR, "cloudflared")

if not os.path.exists(cloudflared_path) and not shutil.which("cloudflared"):
    print("🌐 Downloading Cloudflare Tunnel binary for Free Public HTTPS Link...")
    tunnel_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    try:
        r = requests.get(tunnel_url, headers={'User-Agent': 'Mozilla/5.0'}, stream=True)
        with open(cloudflared_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk: f.write(chunk)
        os.chmod(cloudflared_path, 0o777)
        print("✅ Cloudflare Tunnel binary ready!")
    except Exception as e:
        print(f"Tunnel download notice: {e}")

# 3. Start Backend Uvicorn Server in Background
print("🚀 Starting FastAPI Face Swap Server on Port 8000...")
server_cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
server_proc = subprocess.Popen(server_cmd, cwd=BACKEND_DIR)

time.sleep(2)

# 4. Start Cloudflare Tunnel
print("🔗 Launching Free Public HTTPS Tunnel...")
tunnel_cmd = [cloudflared_path, "tunnel", "--url", "http://localhost:8000"]
tunnel_proc = subprocess.Popen(tunnel_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

print("\n" + "=" * 60)
print("🌍 GENERATING YOUR LIVE PUBLIC URL...")
print("=" * 60)

tunnel_url_found = False
url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')

for line in tunnel_proc.stdout:
    match = url_pattern.search(line)
    if match:
        full_url = match.group(0)
        # Avoid the generic domain if matched
        if full_url != "https://trycloudflare.com" and "trycloudflare.com" in full_url:
            print("\n" + "🎉" * 28)
            print("✨ YOUR LIVE FACE SWAP STUDIO IS READY AT:")
            print(f"👉 {full_url}")
            print("🎉" * 28 + "\n")
            
            try:
                from IPython.display import display, HTML
                display(HTML(f'<div style="background:#1e1e38;padding:16px;border-radius:10px;border:2px solid #6366f1;text-align:center;"><h2 style="color:#fff;margin:0 0 10px;">✨ Live Face Swap Studio Ready!</h2><a href="{full_url}" target="_blank" style="display:inline-block;padding:12px 24px;background:linear-gradient(90deg,#6366f1,#ec4899);color:#fff;font-weight:bold;text-decoration:none;border-radius:8px;font-size:16px;">🚀 Open Face Swap App in New Tab</a><p style="color:#94a3b8;margin:8px 0 0;font-size:12px;">{full_url}</p></div>'))
            except Exception:
                pass
            
            tunnel_url_found = True
            break

try:
    server_proc.wait()
except KeyboardInterrupt:
    print("\n🛑 Shutting down server and tunnel...")
    server_proc.terminate()
    tunnel_proc.terminate()
