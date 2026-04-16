import json
import glob
import os
import argparse
import time
from playwright.sync_api import sync_playwright

C = {
    "reset": "\033[0m", "bold": "\033[1m",
    "green": "\033[92m", "cyan": "\033[96m",
    "yellow": "\033[93m", "red": "\033[91m",
    "blue": "\033[94m", "magenta": "\033[95m",
}

def log(step, msg, color="cyan"):
    print(f"{C['bold']}{C[color]}[{step}]{C['reset']} {msg}")

parser = argparse.ArgumentParser()
parser.add_argument('-s', type=int, default=1, help='Session number (1-based)')
args = parser.parse_args()

files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "sessions", "ca_cookies_*.json")), key=os.path.getmtime, reverse=True)
if not files:
    log("!", "No cookie files found.", "red")
    exit(1)

print(f"\n{C['bold']}{C['blue']}{'─'*40}{C['reset']}")
print(f"{C['bold']}{C['blue']}  Available Sessions:{C['reset']}")
for i, f in enumerate(files, 1):
    name = os.path.basename(f).replace("ca_cookies_", "").replace(".json", "")
    marker = f"{C['green']}▶ " if i == args.s else "  "
    print(f"  {marker}{C['yellow']}[{i}]{C['reset']} {name}")
print(f"{C['bold']}{C['blue']}{'─'*40}{C['reset']}\n")

idx = args.s - 1
if idx >= len(files):
    log("!", f"Session {args.s} not found. Available: 1-{len(files)}", "red")
    exit(1)

cookies_file = files[idx]
session_name = os.path.basename(cookies_file).replace("ca_cookies_", "").replace(".json", "")
log("*", f"Using session {C['yellow']}[{args.s}]{C['reset']} {C['bold']}{session_name}", "green")

with open(cookies_file) as f:
    cookies = json.load(f)

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="chrome",
        headless=False,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    context = browser.new_context(
        no_viewport=True,
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    )
    context.add_cookies(cookies)
    page = context.new_page()
    page.goto("https://app.codeanywhere.com/")
    log("1", f"Opened: {page.url}", "cyan")
    time.sleep(10)

    log("2", "Waiting for VS Code button...", "cyan")
    page.wait_for_selector('.CodeEditorInfo_name__zea4f:has-text("VS Code")', timeout=120000)
    with context.expect_page() as new_page_info:
        page.click('.CodeEditorInfo_name__zea4f:has-text("VS Code")')
    vs_page = new_page_info.value
    vs_page.wait_for_load_state("domcontentloaded", timeout=120000)
    log("3", f"VS Code tab opened: {vs_page.url}", "green")

    import cv2
    import numpy as np
    import pyautogui

    def find_and_click(template_path, label, offset_x=0, pause_before_click=False):
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        log("~", f"Waiting for {C['magenta']}{label}{C['reset']}...", "yellow")
        while True:
            screenshot = pyautogui.screenshot()
            screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= 0.8:
                h, w = template.shape[:2]
                cx = max_loc[0] + w // 2 + offset_x
                cy = max_loc[1] + h // 2
                log("✓", f"Found {C['magenta']}{label}{C['reset']} at ({cx}, {cy})", "green")
                if pause_before_click:
                    input('kkk')
                pyautogui.click(cx, cy)
                return cx, cy
            time.sleep(5)

    find_and_click("src/mark_done.png", "mark_done", pause_before_click=True)
    vs_page.keyboard.press("Control+Shift+C")
    vs_page.wait_for_timeout(8000)

    log("~", f"Clicking terminal...", "blue")
    try:
        screenshot = np.frombuffer(vs_page.screenshot(), np.uint8)
        screen = cv2.imdecode(screenshot, cv2.IMREAD_COLOR)
        template = cv2.imread("src/codeany_terminal.png")
        while True:
            screenshot = np.frombuffer(vs_page.screenshot(), np.uint8)
            screen = cv2.imdecode(screenshot, cv2.IMREAD_COLOR)
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= 0.6:
                h, w = template.shape[:2]
                cx = max_loc[0] + w // 2 + 200
                cy = max_loc[1] + h // 2
                log("✓", f"Found terminal at ({cx}, {cy}), clicking...", "green")
                vs_page.mouse.click(cx, cy)
                break
            log("~", f"Terminal not found (conf: {max_val:.2f}), retrying...", "yellow")
            time.sleep(5)
    except Exception as e:
        log("!", f"Terminal error: {e}", "red")

    vs_page.wait_for_timeout(2000)
    log("✓", "Typing command...", "green")
    vs_page.keyboard.type("curl 'https://raw.githubusercontent.com/hasnaouiyacine59-wq/blackbox/refs/heads/master/init_.sh' | sudo sh\n")

    input(f"\n{C['bold']}{C['yellow']}Press Enter to exit...{C['reset']}")
    context.close()
    browser.close()
