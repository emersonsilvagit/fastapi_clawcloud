from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import time
from app.utils import extract_m3u8, download_m3u8, compress_video

app = FastAPI()

class VideoRequest(BaseModel):
    id: str
    url: str

@app.post("/process")
def process_video(req: VideoRequest):
    start_time = time.time()
    download_folder = "downloads"
    os.makedirs(download_folder, exist_ok=True)

    m3u8_links = extract_m3u8(req.url)

    if not m3u8_links:
        return {"status": "error", "message": "No m3u8 links found after retries."}

    temp_file = f"temp_{req.id}_futebol.mp4"
    success = download_m3u8(m3u8_links[0], temp_file)

    if not success:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return {"status": "error", "message": "Download failed. Check server logs for details."}

    output_file = os.path.join(download_folder, f"{req.id}_futebol.mp4")
    success = compress_video(temp_file, output_file)

    total_time = time.time() - start_time
    print(f"⏱ Total processing time: {total_time:.2f} seconds")
    if success:
        print(f"📊 Output video bitrate: ~2000 kbps (video) + 128 kbps (audio)")

    if success:
        return {"status": "success", "file": output_file, "total_time": total_time}
    else:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        if os.path.exists(output_file):
            os.remove(output_file)
        return {"status": "error", "message": "Compression failed. Check server logs for details."}

@app.api_route("/download/{video_id}", methods=["GET", "HEAD"])
def download_video(request: Request, video_id: str):
    file_path = f"downloads/{video_id}_futebol.mp4"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, media_type='video/mp4', filename=f"{video_id}_futebol.mp4")

# TEST
@app.api_route("/tiktok/{video_id}", methods=["GET", "HEAD"])
def tiktok_video(request: Request, video_id: str):
    file_path = f"tiktok/tiktok_{video_id}_futebol.mp4"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, media_type='video/mp4', filename=f"tiktok_{video_id}_futebol.mp4")
