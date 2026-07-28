import csv
import os
import re
import subprocess
import sys
import time
import types
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import distutils.version  # noqa: F401
except ModuleNotFoundError:
    from setuptools._distutils.version import LooseVersion

    distutils_module = types.ModuleType("distutils")
    version_module = types.ModuleType("distutils.version")
    version_module.LooseVersion = LooseVersion
    distutils_module.version = version_module
    sys.modules["distutils"] = distutils_module
    sys.modules["distutils.version"] = version_module

import undetected_chromedriver as uc  # noqa: E402

from tiktok_comments_scraper import (  # noqa: E402
    click_view_more_buttons,
    extract_all_comment_blocks,
    find_comment_scroll_target,
    get_total_comment_count,
    is_valid_comment,
    scroll_comments,
    scroll_to_last_comment,
    wait_for_more_blocks,
)


def _find_chrome_executable():
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _detect_chrome_major_version(chrome_path):
    env_version = os.environ.get("CHROME_VERSION_MAIN", "").strip()
    if env_version.isdigit():
        return int(env_version)

    if not chrome_path:
        return None

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [chrome_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=creationflags,
        )
        match = re.search(r"(\d+)\.", result.stdout or result.stderr or "")
        if match:
            return int(match.group(1))
    except Exception:
        pass

    app_dir = os.path.dirname(chrome_path)
    try:
        versions = []
        for name in os.listdir(app_dir):
            if re.match(r"^\d+\.\d+\.\d+\.\d+$", name):
                versions.append(name)
        if versions:
            latest = sorted(versions, key=lambda value: [int(part) for part in value.split(".")])[-1]
            return int(latest.split(".", 1)[0])
    except Exception:
        pass

    return None


def build_driver_for_web(profile_dir, headless=False):
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=id-ID")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    if profile_dir:
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")

    if headless:
        options.add_argument("--headless=new")

    chrome_path = _find_chrome_executable()
    chrome_major = _detect_chrome_major_version(chrome_path)
    kwargs = {"options": options}
    if chrome_path:
        kwargs["browser_executable_path"] = chrome_path
    if chrome_major:
        kwargs["version_main"] = chrome_major

    driver = uc.Chrome(**kwargs)
    print(f"Chrome berhasil dibuka dengan version_main={chrome_major or 'auto'}")
    return driver


def save_scraped_comments(data, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(output_dir, f"scraping_tiktok_{timestamp}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["no", "tanggal", "username", "komentar"])
        for i, row in enumerate(data, 1):
            writer.writerow([i, row["date"], row["username"], row["comment"]])

    return csv_path


def scrape_tiktok_for_web(
    url,
    output_dir,
    profile_dir,
    manual_wait=20,
    max_comments=300,
    max_empty_scroll=8,
    delay=2.0,
    headless=False,
):
    driver = build_driver_for_web(profile_dir=profile_dir, headless=headless)
    seen = set()
    all_data = []
    total_target = None

    try:
        driver.get(url)
        time.sleep(max(3, int(manual_wait)))

        total_target = get_total_comment_count(driver)
        scroll_target = find_comment_scroll_target(driver)
        empty_scroll_count = 0

        while empty_scroll_count < max_empty_scroll and len(all_data) < max_comments:
            click_view_more_buttons(driver)
            blocks = extract_all_comment_blocks(driver)
            new_count = 0

            for block in blocks:
                key = (block["username"], block["comment"])
                if key not in seen and is_valid_comment(block["comment"]):
                    seen.add(key)
                    all_data.append(block)
                    new_count += 1
                    if len(all_data) >= max_comments:
                        break

            if new_count == 0:
                empty_scroll_count += 1
            else:
                empty_scroll_count = 0

            if total_target and len(all_data) >= total_target:
                break

            prev_total = len(blocks)
            if not scroll_to_last_comment(driver, scroll_target):
                scroll_comments(driver, scroll_target)
            scroll_comments(driver, scroll_target)
            if not wait_for_more_blocks(driver, prev_total, timeout=delay + 2):
                time.sleep(delay)

        csv_path = save_scraped_comments(all_data, output_dir) if all_data else None
        return {
            "csv_path": csv_path,
            "total_comments": len(all_data),
            "target_comments": total_target,
            "max_comments": int(max_comments),
        }
    finally:
        try:
            driver.quit()
        except Exception:
            pass
