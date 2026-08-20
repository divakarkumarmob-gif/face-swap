# 🎭 Studio AI Face Swap (Photo & Video)

High-Fidelity, Movie-Grade AI Face Swapping Web Studio powered by **FastAPI**, **InSwapper 128**, **GFPGAN 1.4 HD**, and **InsightFace (Buffalo_L)**.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/divakarkumarmob-gif/face-swap/blob/main/face_swap_colab.ipynb)

---

## ⚡ 1-Click Free Google Colab Deployment (NVIDIA T4 GPU)

Click the badge above or open this link in your browser:
👉 **[Open in Google Colab](https://colab.research.google.com/github/divakarkumarmob-gif/face-swap/blob/main/face_swap_colab.ipynb)**

1. In Colab, select **Runtime > Change runtime type > T4 GPU**.
2. Run the 3 code cells.
3. Click the generated **`https://xxxx.trycloudflare.com`** live link to use your web app with free GPU speed from anywhere!

---

## ⚡ System Requirements

### 1. Hardware Requirements

| Component | Minimum (CPU Mode) | Recommended (GPU Mode - 5x-10x Faster) |
|---|---|---|
| **Processor** | Intel Core i5 (8th Gen+) / AMD Ryzen 5 (4+ Cores) | Intel Core i7/i9 or AMD Ryzen 7/9 / 8+ vCPU |
| **RAM** | 8 GB RAM | 16 GB - 32 GB RAM |
| **GPU / VRAM** | Not Required (runs on CPU) | NVIDIA GPU with CUDA (GTX 1660, RTX 3060, RTX 4070, T4, A10G) with 4GB-12GB+ VRAM |
| **Storage** | 5 GB Free SSD space | 10 GB+ NVMe SSD |

---

### 2. Software Requirements

- **Operating System**: Windows 10/11, Ubuntu 20.04/22.04 LTS, Debian, or macOS
- **Python**: Python `3.10`, `3.11`, `3.12`, or `3.13`
- **Git**: Installed for version control

---

## 🚀 Quick Setup & Run (Local PC / Laptop)

### Step 1: Clone Repository
```bash
git clone https://github.com/divakarkumarmob-gif/face-swap.git
cd face-swap
```

### Step 2: Create Python Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

*(Note for GPU acceleration with NVIDIA CUDA: `pip install onnxruntime-gpu`)*

### Step 4: Download AI Models
Ensure the following models exist in `backend/models/`:
1. `backend/models/inswapper_128.onnx` (~528 MB)
2. `backend/models/gfpgan_1.4.onnx` (~330 MB)

*(InsightFace `buffalo_l` models download automatically on first run)*

### Step 5: Start Local Server
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
Open your browser at: **`http://localhost:8000`**

---

## ☁️ Deploying to Cloud Server (AWS / DigitalOcean / RunPod / GCP / VPS)

### Production Deployment via Systemd or PM2 / Gunicorn:
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Reverse Proxy via Nginx (Optional with SSL):
```nginx
server {
    listen 80;
    server_name your-domain.com;
    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
