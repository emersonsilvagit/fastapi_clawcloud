from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import os
import time
import subprocess
from app.utils import extract_m3u8, download_m3u8

app = FastAPI()

class VideoRequest(BaseModel):
    id: str
    url: str

class TikTokRequest(BaseModel):
    id: str
    background: str  # e.g., "fut_bg.png"
    foreground: str  # e.g., "fut_fg_borda.png"
    font_1: str      # e.g., "SuperCreamy-OGAPp.ttf"
    font_2: str      # e.g., "JackportRegularNcv-BeY3.ttf"
    text_title: str  # e.g., "Sample Title"
    text_desc: str   # e.g., "Sample Result"

# Configuration for static file paths in the container
CONFIG_DIR = "/app/config"
DATA_DIR = "/tmp"

@app.post("/process")
async def process_video(req: VideoRequest):
    start_time = time.time()
    download_folder = f"{DATA_DIR}/downloads"
    os.makedirs(download_folder, exist_ok=True)

    m3u8_links = await extract_m3u8(req.url)

    if not m3u8_links:
        return {"status": "error", "message": "No m3u8 links found after retries."}

    output_file = os.path.join(download_folder, f"{req.id}_futebol.mp4")
    success = download_m3u8(m3u8_links[0], output_file)

    total_time = time.time() - start_time
    print(f"⏱ Total processing time: {total_time:.2f} seconds")

    if success:
        return {"status": "success", "file": output_file, "total_time": total_time}
    else:
        if os.path.exists(output_file):
            os.remove(output_file)
        return {"status": "error", "message": "Download failed. Check server logs for details."}

@app.api_route("/download/{video_id}", methods=["GET", "HEAD"])
async def download_video(request: Request, video_id: str):
    file_path = os.path.join(f"{DATA_DIR}/downloads", f"{video_id}_futebol.mp4")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    def iterfile():
        with open(file_path, mode="rb") as file:
            yield from file

    print(f"Serving file: {file_path}, size: {os.path.getsize(file_path)} bytes")
    return StreamingResponse(
        iterfile(),
        media_type='video/mp4',
        headers={
            "Content-Disposition": f"attachment; filename={video_id}_futebol.mp4",
            "Content-Length": str(os.path.getsize(file_path))
        }
    )

@app.post("/tiktok/process")
async def tiktok_process(req: TikTokRequest):
    start_time = time.time()
    download_folder = f"{DATA_DIR}/downloads"
    tiktok_folder = f"{DATA_DIR}/tiktok"
    os.makedirs(tiktok_folder, exist_ok=True)

    input_file = os.path.join(download_folder, f"{req.id}_futebol.mp4")
    if not os.path.exists(input_file):
        raise HTTPException(status_code=404, detail="Input video not found")

    output_file = os.path.join(tiktok_folder, f"tiktok_{req.id}_futebol.mp4")

    # Validate that the specified config files exist
    background_path = os.path.join(CONFIG_DIR, req.background)
    foreground_path = os.path.join(CONFIG_DIR, req.foreground)
    font_1_path = os.path.join(CONFIG_DIR, req.font_1)
    font_2_path = os.path.join(CONFIG_DIR, req.font_2)

    for file_path in [background_path, foreground_path, font_1_path, font_2_path]:
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Config file not found: {file_path}")

    try:
        # Construct FFmpeg command
        ffmpeg_command = [
            "ffmpeg",
            "-i", background_path,
            "-i", input_file,
            "-i", foreground_path,
            "-filter_complex",
            "[1:v]crop=iw/1.0:ih/1.0:(iw-iw/1.0)/2:(ih-ih/1.0)/2,scale=1280:1338[vid];"
            "[0:v][vid]overlay=-150:310[tmp];"
            "[tmp][2:v]overlay=0:0[base];"
            "[base]drawtext=text='GOOOOOOOL':fontfile='" + font_1_path + "':fontcolor=white:fontsize=80:x=(w-text_w)/2:y=320[txt1];"
            "[txt1]drawtext=text='" + req.text_title + "':fontfile='" + font_2_path + "':fontcolor=white:fontsize=80:x=(w-text_w)/2:y=420[txt2];"
            "[txt2]drawtext=text='" + req.text_desc + "':fontfile='" + font_2_path + "':fontcolor=white:fontsize=50:x=(w-text_w)/2:y=1600",
            "-c:a", "copy",
            output_file
        ]

        print(f"Executing FFmpeg command: {' '.join(ffmpeg_command)}")
        result = subprocess.run(ffmpeg_command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")

        total_time = time.time() - start_time
        print(f"✅ TikTok processing completed: {output_file}, time: {total_time:.2f} seconds")

        return {"status": "success", "file": output_file, "total_time": total_time}

    except Exception as e:
        if os.path.exists(output_file):
            os.remove(output_file)
        return {"status": "error", "message": f"Processing failed: {str(e)}"}

@app.api_route("/tiktok/{video_id}", methods=["GET", "HEAD"])
async def tiktok_video(request: Request, video_id: str):
    tiktok_folder = f"{DATA_DIR}/tiktok"
    os.makedirs(tiktok_folder, exist_ok=True)

    output_tiktok_file = os.path.join(tiktok_folder, f"tiktok_{video_id}_futebol.mp4")
    if not os.path.exists(output_tiktok_file):
        raise HTTPException(status_code=404, detail="File not found")

    def iterfile():
        with open(output_tiktok_file, mode="rb") as file:
            yield from file

    print(f"Serving file: {output_tiktok_file}, size: {os.path.getsize(output_tiktok_file)} bytes")
    return StreamingResponse(
        iterfile(),
        media_type='video/mp4',
        headers={
            "Content-Disposition": f"attachment; filename=tiktok_{video_id}_futebol.mp4",
            "Content-Length": str(os.path.getsize(output_tiktok_file))
        }
    )