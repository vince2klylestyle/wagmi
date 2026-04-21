#!/usr/bin/env python3
"""Quick health check for memegine backends."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from memegine import image_gen, local_assets, reference_lib, projects, raid_parser
from memegine.config import settings


def check_image_gen():
    """Check image generation backend."""
    print("\n=== Image Generation ===")
    available = image_gen.available_backends()
    if available:
        print(f"[OK] Backends available: {', '.join(available)}")
        active = image_gen._backend()
        print(f"     Active: {active}")
    else:
        print("[!!] NO IMAGE GENERATION CONFIGURED")
        print("     Set one of: MEMEGINE_FAL_KEY, MEMEGINE_XAI_API_KEY, MEMEGINE_OPENAI_KEY in .env")
        return False
    return True


def check_local_assets():
    """Check local TG media discovery."""
    print("\n=== Local TG Assets ===")
    found = local_assets.scan_local_tg_downloads()
    total = sum(len(v) for v in found.values())
    if total == 0:
        print("[..] No local TG media found")
        print("     Tip: Create folders like:")
        print("       C:\\Users\\vince\\Downloads\\TG_kilroy\\")
        print("       C:\\Users\\vince\\Downloads\\TG_spong\\")
        return False
    for brand, entries in found.items():
        if entries:
            print(f"[OK] {brand}: {len(entries)} items")
    return True


def check_reference_libs():
    """Check reference library size per brand."""
    print("\n=== Reference Libraries ===")
    for brand in ("kilroy", "motion", "spong"):
        try:
            projects.set_active(brand)
            settings.refresh_project(brand)
            entries = reference_lib.search()
            status = "[OK]" if entries else "[..]"
            print(f"{status} {brand}: {len(entries)} items")
        except Exception as e:
            print(f"[!!] {brand}: {e}")


def main():
    print("=" * 50)
    print("MEMEGINE HEALTH CHECK")
    print("=" * 50)

    img_ok = check_image_gen()
    local_ok = check_local_assets()
    check_reference_libs()

    print("\n" + "=" * 50)
    if img_ok:
        print("[OK] Ready for image generation")
    else:
        print("[..] Image generation not configured — no API images will be generated")
        print("     You can still use /gallery to browse local reference media")
        print("     And use spongify with manual Grok Imagine uploads")

    print("=" * 50)


if __name__ == "__main__":
    main()
