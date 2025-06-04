import subprocess
import os
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import ffmpeg

async def extract_m3u8(url):
    """
    Extract m3u8 links from a URL using Playwright Async API with retry on timeout.
    
    Args:
        url (str): Website URL to scrape.
    
    Returns:
        list: List of m3u8 URLs.
    """
    async def try_navigate(url, timeout_ms, attempt):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    bypass_csp=True,
                    no_viewport=True  # Disable video rendering
                )
                page = await context.new_page()

                m3u8_links = []

                def handle_response(response):
                    if ".m3u8" in response.url:
                        print(f"✅ Found m3u8 link: {response.url}")
                        m3u8_links.append(response.url)

                page.on("response", handle_response)

                print(f"➡️ Attempt {attempt}: Navigating to {url} with {timeout_ms/1000}s timeout")
                await page.goto(url, timeout=timeout_ms)

                await page.wait_for_timeout(3000)  # Reduced from 5s

                await page.evaluate("""
                    const overlay = document.querySelector('.poster__background-overlay');
                    if (overlay) {
                        overlay.style.pointerEvents = 'none';
                        overlay.style.opacity = '0';
                    }
                """)

                play_button_selector = "button[aria-label='Play'], button.play"
                play_button = await page.query_selector(play_button_selector)
                if play_button:
                    print(f"▶️ Attempt {attempt}: Clicking play button...")
                    try:
                        await play_button.click(timeout=3000)  # Reduced from 5s
                    except PlaywrightTimeoutError:
                        print(f"⚠️ Attempt {attempt}: Timeout clicking play button, continuing...")
                else:
                    print(f"ℹ️ Attempt {attempt}: Play button not found")

                await page.wait_for_timeout(5000)  # Reduced from 10s

                await context.close()
                await browser.close()
                return m3u8_links

        except PlaywrightTimeoutError:
            print(f"❌ Attempt {attempt}: Timeout navigating to URL: {url}")
            return None
        except Exception as e:
            print(f"❌ Attempt {attempt}: Error extracting m3u8 links: {e}")
            return None

    result = await try_navigate(url, 60000, 1)
    if result is not None and result:
        return result

    print("🔄 Retrying with extended timeout...")
    result = await try_navigate(url, 90000, 2)
    return result if result is not None else []

def download_m3u8(m3u8_url, output_file):
    """
    Download an m3u8 video using FFmpeg.
    
    Args:
        m3u8_url (str): URL of the m3u8 stream.
        output_file (str): Path to save the downloaded video.
    
    Returns:
        bool: True if download succeeds, False otherwise.
    """
    output_file = os.path.abspath(output_file)
    command = [
        "ffmpeg",
        "-y",
        "-timeout", "30000000",  # 30s timeout (microseconds)
        "-i", m3u8_url,
        "-c", "copy",
        output_file
    ]
    print(f"⬇️ Downloading video to {output_file} ...")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(f"✅ Download completed: {output_file}")
        print(f"📜 FFmpeg stdout: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Download failed:\nStderr: {e.stderr}\nStdout: {e.stdout}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during download: {e}")
        return False

def get_video_duration(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        duration = float(probe['format']['duration'])
        print(f"⏱ Video duration: {duration:.2f} seconds")
        return duration
    except ffmpeg.Error as e:
        print(f"❌ Error probing duration: {e.stderr.decode() if e.stderr else 'No stderr'}")
        return None

def compress_video(input_path, output_path):
    """
    Compress a video to 720p with CRF 23 and capped bitrate using FFmpeg.
    
    Args:
        input_path (str): Path to the input video.
        output_path (str): Path to save the compressed video.
    
    Returns:
        bool: True if compression succeeds, False otherwise.
    """
    try:
        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        if not os.path.exists(input_path):
            print(f"❌ Input file not found: {input_path}")
            return False
        
        input_size = os.path.getsize(input_path) / (1024 * 1024)
        print(f"📥 Input file size: {input_size:.2f} MB")
        
        duration = get_video_duration(input_path)
        if duration is None:
            print("❌ Skipping compression due to invalid input file")
            return False
        
        command = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vcodec", "libx264",
            "-crf", "23",
            "-preset", "veryfast",
            "-b:v", "2000k",
            "-maxrate", "2000k",
            "-bufsize", "4000k",
            "-vf", "scale=-2:720",
            "-acodec", "aac",
            "-ab", "128k",
            "-movflags", "+faststart",
            "-tune", "fastdecode",
            "-threads", "2",
            output_path
        ]
        
        print(f"🔧 FFmpeg command: {' '.join(command)}")
        
        start_time = time.time()
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Compression failed:\nStderr: {result.stderr}\nStdout: {result.stdout}")
            return False
        
        output_size = os.path.getsize(output_path) / (1024 * 1024)
        compression_time = time.time() - start_time
        print(f"✅ Compression completed: {output_path}")
        print(f"📤 Output file size: {output_size:.2f} MB")
        print(f"⏱ Compression time: {compression_time:.2f} seconds")
        
        if os.path.exists(input_path):
            os.remove(input_path)
        
        if output_size >= input_size:
            print(f"⚠️ Warning: Output file size ({output_size:.2f} MB) is not smaller than input ({input_size:.2f} MB)")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Unexpected error during compression: {e}")
        return False