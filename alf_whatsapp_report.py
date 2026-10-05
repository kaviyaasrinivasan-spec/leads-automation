# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', write_through=True)

"""
ALF Daily Lead Report - WhatsApp Automation
==========================================
- Fetches today's lead data via PHP API (akngroups.in/lead_api.php)
- Sends report to personal number (+91 80157 36601) and group (WB AI)
- Runs daily at 10:00 AM
- Saves WhatsApp session (no QR scan every day after first time)

Usage:
  python alf_whatsapp_report.py --setup   ← First time: scan QR & save session
  python alf_whatsapp_report.py --test    ← Send report immediately (test)
  python alf_whatsapp_report.py           ← Start daily 10:00 AM scheduler
"""

import schedule
import time
import os
import sys
import json
import urllib.request
from datetime import datetime, date, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
# ============================================================
# ⚙️  CONFIGURATION
# ============================================================

# PHP API endpoint (fetches data from alf_leads DB)
# Token is read from the LEAD_API_TOKEN environment variable (never hardcode it)
API_URL = "https://akngroups.in/lead_api.php?token=" + os.environ.get("LEAD_API_TOKEN", "")

# Target group name exactly as it appears in WhatsApp
GROUP_NAME = "TBA - DM"           # WhatsApp group name

# Paths
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
CHROME_PROFILE = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
SESSION_DIR    = os.path.join(SCRIPT_DIR, "whatsapp_session")  # fallback if Chrome profile busy

# Daily report time
REPORT_TIME = "10:30"

# ============================================================


def get_lead_data(report_date=None):
    """
    Fetch YESTERDAY's lead counts from PHP API.
    Categories: Family, General, NRI, Unknown (from ad_name column)
    """
    try:
        url = API_URL
        if report_date:
            url += f"&date={report_date}"
        # No date param = API defaults to yesterday automatically

        print(f"[DB] Fetching data from API: {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "ALF-Report-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")

        data = json.loads(raw)

        if "error" in data:
            print(f"[DB] API Error: {data['error']}")
            return None

        total   = int(data.get("total",   0))
        family  = int(data.get("family",  0))
        general = int(data.get("general", 0))
        nri     = int(data.get("nri",     0))
        unknown = int(data.get("unknown", 0))

        print(f"[DB] OK | Date: {data['date']} | Total:{total} | "
              f"Family:{family} General:{general} NRI:{nri} Unknown:{unknown}")

        return {
            "date":    data.get("date", ""),
            "total":   total,
            "family":  family,
            "general": general,
            "nri":     nri,
            "unknown": unknown,
        }

    except Exception as e:
        print(f"[DB] Error: {e}")
        return None


def build_message(data, spend=None):
    """
    Build WhatsApp message matching the screenshot format, including Ad Spend if available.
    """
    d = data

    if not spend:
        # Fallback if spend failed to fetch
        spend = {"family": 0, "general": 0, "nri": 0, "unknown": 0, "total": 0}

    lines = [
        "*ALF Daily Lead Report*",
        f"*{d['date']}*",
        "",
        "```",
        "Lead Type | Leads | Spend (₹)",
        "-----------------------------",
        f"Family    | {d['family']:<5} | {spend['family']}",
        f"General   | {d['general']:<5} | {spend['general']}",
        f"NRI       | {d['nri']:<5} | {spend['nri']}",
        f"Unknown   | {d['unknown']:<5} | 0",
        "-----------------------------",
        f"Total     | {d['total']:<5} | {spend['total']}",
        "```",
        "_Send automatically from Work Booster Ai_",
    ]
    return "\n".join(lines)


def init_driver():
    """Launch Chrome with saved WhatsApp session (separate profile - no conflict)."""
    os.makedirs(SESSION_DIR, exist_ok=True)

    opts = Options()
    opts.add_argument(f"--user-data-dir={SESSION_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage") # Very important for Linux Server

    # Automatically use headless mode if running on a Linux Server
    import platform
    if platform.system() == "Linux":
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument("--start-maximized")

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=opts)
    return driver


def wait_for_whatsapp_login(driver, qr_wait=90):
    """Wait until WhatsApp Web/Business is ready."""
    print("[WA] Opening WhatsApp Web...")
    driver.get("https://web.whatsapp.com")

    print("[WA] Waiting 12s for page to fully load...")
    time.sleep(12)

    # Take a screenshot to see what's loaded
    ss_path = os.path.join(SCRIPT_DIR, "wa_loading.png")
    driver.save_screenshot(ss_path)
    print(f"[WA] Screenshot saved: {ss_path}")

    # Check page source - if 'id="side"' exists = logged in
    try:
        page_src = driver.page_source
        if 'id="side"' in page_src or '"side"' in page_src:
            print("[WA] Logged in! (detected via page source)")
            print("[WA] Waiting an extra 30 seconds for chats to finish syncing...")
            time.sleep(30) # Extra wait time to ensure syncing is done
            return True
    except Exception:
        pass

    # Try Selenium selectors
    LOGIN_SELECTORS = [
        (By.CSS_SELECTOR, "#side"),
        (By.CSS_SELECTOR, "#side > div.x1c4vz4f.x2lah0s.xdl72j9.xk0lpn4 > div.x1n2onr6.x11uqc5h.x9f619.x78zum5.x1okw0bk.xl2dz39.xexx8yu.x18d9i69.x1280gxy.x73uwhe.x1qhh985.x1sy0etr.x1phvje8.xcldk2z.x7a106z.x4tpdpg > div > div > div > div > div"),
        (By.XPATH, '//div[@id="side"]'),
        (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]'),
        (By.CSS_SELECTOR, 'div[data-testid="chat-list-search"]'),
    ]
    for sel in LOGIN_SELECTORS:
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located(sel))
            print("[WA] Logged in! (detected via element)")
            time.sleep(2)
            return True
        except Exception:
            continue

    # Not logged in - show QR
    print("[WA] Not logged in. Please scan QR...")
    qr_path = os.path.join(SCRIPT_DIR, "whatsapp_qr.png")
    print(f"[WA] QR screenshot is refreshed every 5s at: {qr_path}")
    print(f"[WA] Waiting {qr_wait} seconds for QR scan...")

    # WhatsApp rotates the QR code every ~20s, so keep re-saving the screenshot
    # and re-printing the ASCII QR (the code lives in the data-ref of the div wrapping the canvas)
    last_ref = None
    deadline = time.time() + qr_wait
    while time.time() < deadline:
        try:
            driver.save_screenshot(qr_path)
        except Exception:
            pass

        try:
            qr_ref = driver.find_element(By.XPATH, '//div[@data-ref]').get_attribute("data-ref")
        except Exception:
            qr_ref = None
        if qr_ref and qr_ref != last_ref:
            last_ref = qr_ref
            try:
                import qrcode
                print("\n" + "="*40)
                print(" SCAN THIS QR CODE IN YOUR TERMINAL / MOBILE:")
                print("="*40)
                qr = qrcode.QRCode()
                qr.add_data(qr_ref)
                qr.print_ascii(invert=True)
                print("="*40 + "\n")
            except Exception as err:
                print(f"[WA] Could not render ASCII QR ({err}). Please view {qr_path}.")

        for sel in LOGIN_SELECTORS:
            if driver.find_elements(*sel):
                print("[WA] QR scanned! Session saved.")
                time.sleep(3)
                return True

        time.sleep(5)

    print("[WA] Login timeout.")
    return False


def send_to_target(driver, target_name, message, is_phone=False):
    """Open chat and send message to contact or group"""
    wait = WebDriverWait(driver, 60)

    # Search box selectors - user's EXACT inspected CSS path first
    SEARCH_SELECTORS = [
        # New exact path from user browser inspect
        (By.CSS_SELECTOR, "#side > div.x1c4vz4f.x2lah0s.xdl72j9.xk0lpn4 > div.x1n2onr6.x11uqc5h.x9f619.x78zum5.x1okw0bk.xl2dz39.xexx8yu.x18d9i69.x1280gxy.x73uwhe.x1qhh985.x1sy0etr.x1phvje8.xcldk2z.x7a106z.x4tpdpg > div > div > div > div > div"),
        # Previous exact path (slightly different classes)
        (By.CSS_SELECTOR, "#side > div.x1c4vz4f.x2lah0s.xdl72j9.xk0lpn4 > div.x1n2onr6.x11uqc5h.x9f619.x78zum5.x1okw0bk.xl2dz39.xexx8yu.x18d9i69.x73uwhe.x1qhh985.x1sy0etr.x1280gxy.x1gnnqk1.x1phvje8.xcldk2z.x7a106z.x4tpdpg > div > div > div > div > div"),
        (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]'),
        (By.XPATH, '//div[@data-testid="chat-list-search"]//div[@contenteditable]'),
        (By.CSS_SELECTOR, 'div[data-testid="chat-list-search"] div[contenteditable]'),
        (By.XPATH, '//div[contains(@aria-label,"Search")][@contenteditable="true"]'),
    ]

    # Message box selectors
    MSG_SELECTORS = [
        (By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]'),
        (By.XPATH, '//div[@data-testid="conversation-compose-box-input"]'),
        (By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="10"]'),
        (By.XPATH, '//footer//div[@contenteditable="true"]'),
        (By.XPATH, '//div[contains(@class,"copyable-area")]//div[@contenteditable="true"]'),
    ]

    try:
        if is_phone:
            phone_clean = target_name.replace("+", "").replace(" ", "")
            url = f"https://web.whatsapp.com/send?phone={phone_clean}"
            driver.get(url)
            time.sleep(8)
        else:
            from selenium.webdriver.common.action_chains import ActionChains

            # Method: Click the search icon at top, then type
            # First try clicking the visible search icon/area
            try:
                # Click on an empty area first to deselect any chat
                body = driver.find_element(By.TAG_NAME, "body")
                
                # Try clicking user's specific close button path
                try:
                    close_btn = driver.find_element(By.CSS_SELECTOR, "#_r_4m_ > div > div > button > div > div > div:nth-child(1) > span")
                    close_btn.click()
                    time.sleep(0.5)
                except:
                    pass

                body.send_keys(Keys.ESCAPE)  # Dismiss 'What's new' popups
                time.sleep(0.5)
                body.click()
                time.sleep(1)

                # Try finding search box with any available selector
                search_box = None
                for sel in SEARCH_SELECTORS:
                    try:
                        el = driver.find_element(*sel)
                        # Check if element is displayed
                        if el.is_displayed():
                            search_box = el
                            break
                    except Exception:
                        continue

                if search_box:
                    # Use ActionChains for reliable interaction
                    actions = ActionChains(driver)
                    actions.move_to_element(search_box).click().perform()
                    time.sleep(1)
                    actions = ActionChains(driver)
                    actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
                    time.sleep(0.3)
                    actions = ActionChains(driver)
                    actions.send_keys(target_name).perform()
                    time.sleep(2)
                else:
                    # Fallback: use keyboard shortcut Ctrl+F to open search
                    body = driver.find_element(By.TAG_NAME, "body")
                    body.send_keys(Keys.CONTROL + "f")
                    time.sleep(1)
                    body.send_keys(target_name)
                    time.sleep(2)

            except Exception as e:
                print(f"[WA] Search approach failed: {e}")
                driver.save_screenshot(os.path.join(SCRIPT_DIR, "search_fail.png"))
                return False

            # Click the matching group/contact
            clicked = False
            click_selectors = [
                (By.XPATH, f'//span[@title="{target_name}"]'),
                (By.XPATH, f'//div[@aria-label="{target_name}"]'),
            ]
            
            # Use a shorter wait so it doesn't hang for 60s per selector
            short_wait = WebDriverWait(driver, 5)
            for sel in click_selectors:
                try:
                    result = short_wait.until(EC.element_to_be_clickable(sel))
                    result.click()
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                print(f"[WA] Could not find '{target_name}'")
                driver.save_screenshot(os.path.join(SCRIPT_DIR, "notfound.png"))
                return False

            time.sleep(3)

        msg_box = None
        for sel in MSG_SELECTORS:
            try:
                msg_box = wait.until(EC.element_to_be_clickable(sel))
                if msg_box:
                    break
            except Exception:
                continue

        if not msg_box:
            print(f"[WA] Could not find message input box for '{target_name}'")
            driver.save_screenshot(os.path.join(SCRIPT_DIR, f"nomsgbox.png"))
            return False

        msg_box.click()
        time.sleep(1)

        # Type message - SHIFT+ENTER for newlines
        lines = message.split('\n')
        for i, line in enumerate(lines):
            msg_box.send_keys(line)
            if i < len(lines) - 1:
                msg_box.send_keys(Keys.SHIFT + Keys.ENTER)
            time.sleep(0.05)

        time.sleep(2)
        msg_box.send_keys(Keys.ENTER)  # SEND
        time.sleep(6)

        # Save confirmation screenshot
        conf_name = target_name.replace("+", "").replace(" ", "_")
        conf_path = os.path.join(SCRIPT_DIR, f"sent_{conf_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.png")
        driver.save_screenshot(conf_path)
        print(f"[WA] Message sent to '{target_name}' | Screenshot: {conf_path}")
        return True

    except Exception as e:
        print(f"[WA] Error sending to '{target_name}': {e}")
        err_path = os.path.join(SCRIPT_DIR, f"error_{target_name.replace('+','').replace(' ','_')}.png")
        try:
            driver.save_screenshot(err_path)
        except Exception:
            pass
        return False


def send_daily_report():
    """Main: fetch data → build message → send via WhatsApp"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*55}")
    print(f"  ALF Daily Report - {now_str}")
    print(f"{'='*55}")

    # 1. Fetch data
    data = get_lead_data()
    if not data:
        print("[!] Skipping - could not fetch lead data.")
        return

    # 1.5 Fetch Google Ads Spend Data
    print("[DB] Fetching Google Ads spend data...")
    spend_data = None
    try:
        yaml_path = os.path.join(SCRIPT_DIR, "google_ads.yaml")
        client = GoogleAdsClient.load_from_storage(yaml_path)
        ga_service = client.get_service("GoogleAdsService")
        # Customer ID without hyphens
        CUSTOMER_ID = "6549489566"
        query = "SELECT campaign.name, metrics.cost_micros FROM campaign WHERE segments.date DURING YESTERDAY AND metrics.cost_micros > 0"
        response = ga_service.search(customer_id=CUSTOMER_ID, query=query)
        
        spend_data = {"family": 0, "general": 0, "nri": 0, "unknown": 0}
        total_cost = 0
        for row in response:
            campaign_name = row.campaign.name.lower()
            cost = row.metrics.cost_micros / 1000000.0
            total_cost += cost
            if "family" in campaign_name:
                spend_data["family"] += cost
            elif "general" in campaign_name or "chennai advocate alf" in campaign_name:
                spend_data["general"] += cost
            elif "nri" in campaign_name:
                spend_data["nri"] += cost
            # Unknown spend is intentionally ignored as requested by the user

        for k in spend_data:
            spend_data[k] = round(spend_data[k])
            
        # Total cost now only reflects Family + General + NRI
        spend_data["total"] = spend_data["family"] + spend_data["general"] + spend_data["nri"]
        print(f"[DB] OK | Spend: {spend_data}")
    except Exception as e:
        print(f"[!] Error fetching Ads spend: {e}")

    # 2. Build message
    message = build_message(data, spend_data)
    print(f"\n[MSG] Message preview:\n{message}\n")

    # 3. Launch browser
    driver = None
    try:
        driver = init_driver()
        logged_in = wait_for_whatsapp_login(driver)

        if not logged_in:
            print("[!] WhatsApp login failed. Aborting.")
            return

        # Send to WB AI group only
        print(f"\n[SEND] Sending to group: {GROUP_NAME}")
        ok = send_to_target(driver, GROUP_NAME, message, is_phone=False)

        if ok:
            print(f"\n[OK] Report sent to '{GROUP_NAME}' successfully!")
        else:
            print(f"\n[FAIL] Group send failed. Check screenshots.")

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        if driver:
            try:
                driver.save_screenshot(os.path.join(SCRIPT_DIR, "fatal_error.png"))
            except Exception:
                pass
    finally:
        if driver:
            print("[WA] Waiting 60 seconds for message sync before closing...")
            time.sleep(60)
            driver.quit()
            print("[WA] Browser closed.")


def start_scheduler():
    """Schedule daily report at REPORT_TIME"""
    schedule.every().day.at(REPORT_TIME).do(send_daily_report)

    next_run = schedule.next_run()

    print(f"\n{'='*55}")
    print(f"  ALF WhatsApp Report Scheduler")
    print(f"{'='*55}")
    print(f"  Time     : {REPORT_TIME} AM daily")
    print(f"  Group    : {GROUP_NAME}")
    print(f"  Session  : {SESSION_DIR}")
    print(f"  Next Run : {next_run}")
    print(f"{'='*55}")
    print(f"\n  Press Ctrl+C to stop.\n")

    while True:
        schedule.run_pending()
        time.sleep(30)


# ============================================================
if __name__ == "__main__":

    if "--setup" in sys.argv:
        # One-time setup: open browser, scan QR, save session
        print("=" * 55)
        print("  SETUP MODE - WhatsApp QR Scan")
        print("=" * 55)
        print("  Chrome will open. Scan the QR code with your phone.")
        print("  After scanning, session will be saved permanently.")
        print("=" * 55)
        driver = init_driver()
        try:
            success = wait_for_whatsapp_login(driver, qr_wait=300)
            if success:
                print("\n[OK] Session saved! Run without --setup to start scheduler.")
                time.sleep(20)  # let the new session finish writing to the profile
            else:
                time.sleep(5)
        finally:
            driver.quit()

    elif "--test" in sys.argv:
        # Test: send report immediately
        print("=" * 55)
        print("  TEST MODE - Sending report now")
        print("=" * 55)
        send_daily_report()

    else:
        # Normal: start daily scheduler
        start_scheduler()
