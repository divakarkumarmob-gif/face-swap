import os
import urllib.request
import sys
from tqdm import tqdm

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

MODEL_URLS = {
    "inswapper_128.onnx": [
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
        "https://huggingface.co/deepinsight/inswapper/resolve/main/inswapper_128.onnx"
    ],
    "gfpgan_1.4.onnx": [
        "https://huggingface.co/hacksider/deep-live-cam/resolve/main/GFPGANv1.4.onnx",
        "https://huggingface.co/Neus/GFPGANv1.4/resolve/main/GFPGANv1.4.onnx",
        "https://huggingface.co/facefusion/models-3.0.0/resolve/main/models-3.0.0/gfpgan_1.4.onnx"
    ]
}

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

def ensure_models_dir():
    os.makedirs(MODELS_DIR, exist_ok=True)
    return MODELS_DIR

def download_model(model_name: str, progress_callback=None) -> str:
    ensure_models_dir()
    target_path = os.path.join(MODELS_DIR, model_name)
    
    if os.path.exists(target_path) and os.path.getsize(target_path) > 10 * 1024 * 1024:
        return target_path
    
    urls = MODEL_URLS.get(model_name, [])
    if not urls:
        raise ValueError(f"No download URL registered for model {model_name}")
    
    success = False
    last_error = None
    
    for url in urls:
        try:
            print(f"Downloading {model_name} from {url}...")
            
            def reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, int(block_num * block_size * 100 / total_size))
                    if progress_callback:
                        progress_callback(percent, f"Downloading AI Model {model_name} ({percent}%)...")
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                total_size = int(response.info().get('Content-Length', 0))
                with open(target_path, 'wb') as out_file, DownloadProgressBar(
                    unit='B', unit_scale=True, miniters=1, desc=model_name, total=total_size
                ) as t:
                    block_num = 0
                    block_size = 1024 * 1024 # 1MB chunks
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        out_file.write(buffer)
                        block_num += 1
                        t.update(len(buffer))
                        if total_size > 0 and progress_callback:
                            percent = min(100, int((block_num * block_size / total_size) * 100))
                            progress_callback(percent, f"Downloading {model_name} ({percent}%)...")
                
            if os.path.exists(target_path) and os.path.getsize(target_path) > 10 * 1024 * 1024:
                print(f"Successfully downloaded {model_name} ({os.path.getsize(target_path) / (1024*1024):.1f} MB)")
                success = True
                break
        except Exception as e:
            last_error = e
            print(f"Failed to download {model_name} from {url}: {e}")
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except:
                    pass
    
    if not success:
        print(f"Warning: Could not download {model_name}: {last_error}")
        return None
    
    return target_path

if __name__ == "__main__":
    download_model("inswapper_128.onnx")
    download_model("gfpgan_1.4.onnx")
