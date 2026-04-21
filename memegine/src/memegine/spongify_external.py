"""Spongify via spongmonkeys.fun web interface.

Instead of prompting Grok, automate the actual spongmonkeys.fun generator
which is already perfect. Use Playwright to:
  1. Navigate to spongmonkeys.fun
  2. Upload profile picture
  3. Wait for generation
  4. Download spongified image
  5. Return bytes

This bypasses all the prompt engineering — we use the real thing.
"""
from __future__ import annotations

import asyncio
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None


@dataclass
class SpongifyResult:
    image_bytes: bytes
    image_path: Optional[Path] = None
    error: Optional[str] = None


async def spongify_via_web(
    image_path: Path,
    *,
    headless: bool = True,
    timeout_sec: float = 120,
) -> SpongifyResult:
    """Upload image to spongmonkeys.fun, generate, download result.

    Args:
      image_path: Path to input image (JPG/PNG)
      headless: Run browser headless (no UI)
      timeout_sec: Max wait for generation

    Returns:
      SpongifyResult with image_bytes or error message
    """
    if not async_playwright:
        return SpongifyResult(
            image_bytes=b"",
            error="Playwright not installed. Run: pip install playwright && playwright install"
        )

    if not image_path.exists():
        return SpongifyResult(
            image_bytes=b"",
            error=f"Image not found: {image_path}"
        )

    try:
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            # Navigate to generator
            await page.goto("https://spongmonkeys.fun", wait_until="networkidle")

            # Wait for upload input to appear
            await page.wait_for_selector("input[type='file']", timeout=10000)

            # Upload image
            input_locator = page.locator("input[type='file']")
            await input_locator.set_input_files(str(image_path))

            # Wait for generation UI to appear (submit button, etc.)
            # This varies — may be auto-submit or need a button click
            try:
                # Try to find and click a "Generate" button
                gen_button = page.locator("button:has-text('Generate'), button:has-text('Spongify')")
                if await gen_button.count() > 0:
                    await gen_button.click()
            except Exception:
                pass

            # Wait for result image to load
            # Usually appears in an <img> or <canvas>
            start_time = time.time()
            result_image = None
            while time.time() - start_time < timeout_sec:
                try:
                    # Look for output image — could be in different selectors
                    candidates = [
                        page.locator("img.result"),
                        page.locator("img[alt*='spong']"),
                        page.locator("[class*='result'] img"),
                        page.locator("[class*='output'] img"),
                    ]

                    for candidate in candidates:
                        if await candidate.count() > 0:
                            src = await candidate.get_attribute("src")
                            if src and ("data:" in src or "http" in src):
                                result_image = candidate
                                break

                    if result_image:
                        break
                except Exception:
                    pass

                await asyncio.sleep(0.5)

            if not result_image:
                await browser.close()
                return SpongifyResult(
                    image_bytes=b"",
                    error="Generation timeout or UI not found"
                )

            # Download the image
            src = await result_image.get_attribute("src")
            if not src:
                await browser.close()
                return SpongifyResult(
                    image_bytes=b"",
                    error="Could not find result image source"
                )

            image_bytes = b""

            if src.startswith("data:"):
                # Data URI — extract base64
                try:
                    import base64
                    data_part = src.split(",", 1)[1]
                    image_bytes = base64.b64decode(data_part)
                except Exception as e:
                    await browser.close()
                    return SpongifyResult(
                        image_bytes=b"",
                        error=f"Failed to decode data URI: {e}"
                    )
            else:
                # HTTP URL — fetch it
                try:
                    async with page.context.request as req:
                        resp = await req.get(src)
                        image_bytes = await resp.body()
                except Exception as e:
                    await browser.close()
                    return SpongifyResult(
                        image_bytes=b"",
                        error=f"Failed to fetch image: {e}"
                    )

            await browser.close()
            return SpongifyResult(image_bytes=image_bytes)

    except Exception as e:
        return SpongifyResult(
            image_bytes=b"",
            error=f"Browser automation failed: {e}"
        )


def spongify_sync(image_path: Path, **kwargs) -> SpongifyResult:
    """Synchronous wrapper for spongify_via_web."""
    try:
        return asyncio.run(spongify_via_web(image_path, **kwargs))
    except Exception as e:
        return SpongifyResult(
            image_bytes=b"",
            error=f"Async runtime error: {e}"
        )


if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) < 2:
        print("Usage: python spongify_external.py <image_path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    result = spongify_sync(path, headless=False)  # Show browser for debugging
    if result.error:
        print(f"Error: {result.error}")
    else:
        print(f"Success! {len(result.image_bytes)} bytes")
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(result.image_bytes)
            print(f"Saved to: {f.name}")
