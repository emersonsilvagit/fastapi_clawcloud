import subprocess
import os
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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