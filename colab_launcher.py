import os
import sys
import subprocess
import time
import urllib.request
import shutil

print("=" * 60)
print("🎭 AI Face Swap Studio - 1-Click Google Colab Runner")
print("=" * 60)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
MODELS_DIR = os.path.join(BACKEND_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# 1. Download Required AI Models if not present
models = {
    "inswapper_128.onnx": "https://huggingface.co/ezioroz/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
    "gfpgan_1.4.onnx": "https://huggingface.co/ezioroz/inswapper_128.onnx/resolve/main/gfpgan_1.4.onnx"
}

for name, url in models.items():
    dest = os.path.join(MODELS_DIR, name)
    if not os.path.exists(dest) or os.path.getsize(dest) < 1000000:
        print(f"📥 Downloading AI Model: {name}...")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"✅ {name} downloaded successfully! ({os.path.getsize(dest) // 1024 // 1024} MB)")
        except Exception as e:
            print(f"⚠️ Primary URL failed, trying fallback for {name}...")
            fallback = f"https://github.com/facefusion/facefusion-assets/releases/download/models/{name}"
            urllib.request.urlretrieve(fallback, dest)
            print(f"✅ {name} downloaded from fallback!")

# 2. Setup Cloudflared Tunnel for instant 100% Free Public HTTPS URL (No signup/tokens needed)
cloudflared_path = shutil.which("cloudflared") or os.path.join(BASE_DIR, "cloudflared")

if not os.path.exists(cloudflared_path) and not shutil.which("cloudflared"):
    print("🌐 Downloading Cloudflare Tunnel binary for Free Public HTTPS Link...")
    tunnel_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    urllib.request.urlretrieve(tunnel_url, cloudflared_path)
    os.chmod(cloudflared_path, 0o777)

# 3. Start Backend Uvicorn Server in Background
print("🚀 Starting FastAPI Face Swap Server on Port 8000...")
server_cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
server_proc = subprocess.Popen(server_cmd, cwd=BACKEND_DIR)

time.sleep(3)

# 4. Start Cloudflare Tunnel
print("🔗 Launching Free Public Tunnel...")
tunnel_cmd = [cloudflared_path, "tunnel", "--url", "http://localhost:8000"]
tunnel_proc = subprocess.Popen(tunnel_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

print("\n" + "=" * 60)
print("🌍 GENERATING YOUR LIVE PUBLIC URL...")
print("=" * 60)

tunnel_url_found = False
for line in tunnel_proc.stdout:
    if "trycloudflare.com" in line:
        for word in line.split():
            if "trycloudflare.com" in word:
                clean_url = word.strip().rstrip("/.")
                if not clean_url.startswith("http"):
                    clean_url = f"https://{clean_url}"
                print("\n" + "🎉" * 25)
                print(f"✨ YOUR LIVE FACE SWAP STUDIO IS READY AT:")
                print(f"👉 {clean_url}")
                print("🎉" * 25 + "\n")
                tunnel_url_found = True
                break
    if tunnel_url_found:
        break

try:
    server_proc.wait()
except KeyboardInterrupt:
    print("\n🛑 Shutting down server and tunnel...")
    server_proc.terminate()
    tunnel_proc.terminate()
