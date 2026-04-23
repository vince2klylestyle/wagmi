"""Detect spongmonkeys.fun API by monitoring network requests."""
import asyncio
import tempfile
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed")
    exit(1)


async def detect_api():
    """Monitor network requests to find the API endpoint."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Monitor all requests/responses
        requests_made = []
        responses = []

        page.on("request", lambda req: requests_made.append({
            "url": req.url,
            "method": req.method,
            "headers": dict(req.headers) if hasattr(req, 'headers') else {},
        }))

        page.on("response", lambda resp: responses.append({
            "url": resp.url,
            "status": resp.status,
            "headers": dict(resp.headers) if hasattr(resp, 'headers') else {},
        }))

        # Create a test image
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (200, 200), color='#ffdbac')
        draw = ImageDraw.Draw(img)
        draw.ellipse([70, 70, 90, 90], fill='white')
        draw.ellipse([110, 70, 130, 90], fill='white')

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            img.save(f.name)
            test_image = f.name

        print("Navigating to spongmonkeys.fun...")
        await page.goto("https://spongmonkeys.fun", wait_until="networkidle")
        print(f"  {len(requests_made)} requests so far")

        # Upload image and watch for API calls
        print("\nUploading image...")
        file_input = page.locator("#fileIn").first
        await file_input.set_input_files(test_image)

        # Wait a bit for any follow-up requests
        print("Waiting for generation requests...")
        for i in range(10):
            await asyncio.sleep(1)
            print(f"  {len(requests_made)} total requests, {len(responses)} responses")

        # Look for API calls (likely POST to /api/* or similar)
        print("\n=== API Candidates ===")
        api_requests = [r for r in requests_made if '/api' in r['url'].lower() or 'generate' in r['url'].lower()]

        if api_requests:
            for req in api_requests:
                print(f"\n{req['method']} {req['url']}")
                for h in ['content-type', 'authorization', 'x-api-key']:
                    if h in req['headers']:
                        print(f"  {h}: {req['headers'][h]}")
        else:
            print("No obvious API endpoints found")

        print("\n=== All POST/PUT Requests ===")
        for req in requests_made:
            if req['method'] in ('POST', 'PUT'):
                print(f"{req['method']} {req['url']}")

        await browser.close()
        Path(test_image).unlink()


if __name__ == "__main__":
    asyncio.run(detect_api())
