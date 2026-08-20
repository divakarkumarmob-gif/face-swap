import os
import cv2
import numpy as np

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
os.makedirs(SAMPLES_DIR, exist_ok=True)

def create_sample_assets():
    # 1. Download a couple of high-quality sample portrait faces
    import urllib.request
    
    sample_faces = {
        "avatar_man.jpg": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=800&auto=format&fit=crop&q=80",
        "avatar_woman.jpg": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=800&auto=format&fit=crop&q=80"
    }

    sample_target_photos = {
        "target_model_portrait.jpg": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=800&auto=format&fit=crop&q=80",
        "target_businessman.jpg": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&auto=format&fit=crop&q=80"
    }
    
    for filename, url in {**sample_faces, **sample_target_photos}.items():
        filepath = os.path.join(SAMPLES_DIR, filename)
        if not os.path.exists(filepath):
            try:
                print(f"Downloading {filename}...")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(filepath, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception as e:
                print(f"Could not download {filename}: {e}")

    # 2. Download sample test video clips (small royalty-free video clips)
    sample_videos = {
        "cinematic_walk.mp4": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "action_clip.mp4": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyBlazes.mp4"
    }

    for filename, url in sample_videos.items():
        filepath = os.path.join(SAMPLES_DIR, filename)
        if not os.path.exists(filepath):
            try:
                print(f"Downloading {filename}...")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(filepath, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception as e:
                print(f"Could not download {filename}: {e}")

if __name__ == "__main__":
    create_sample_assets()

