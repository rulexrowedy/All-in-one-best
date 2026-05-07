import streamlit as st
import time
import threading
import gc
import os
import sys
import random
from pathlib import Path
from collections import deque

# Allow imports from this directory
sys.path.insert(0, os.path.dirname(__file__))

from database import Session, SessionManager
from keepalive import get_keepalive_js, simulate_browser_activity

# ── Selenium imports ──────────────────────────────────────────────────────────
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

# ── Streamlit page config ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="Messenger Tools",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
* { font-family: 'Poppins', sans-serif; }
.stApp {
    background-image: url('https://i.postimg.cc/TYhXd0gG/d0a72a8cea5ae4978b21e04a74f0b0ee.jpg');
    background-size: cover; background-position: center; background-attachment: fixed;
}
.main .block-container {
    background: rgba(255,255,255,0.08); backdrop-filter: blur(8px);
    border-radius: 12px; padding: 20px; border: 1px solid rgba(255,255,255,0.12);
}
.main-header {
    background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
    padding: 1rem; border-radius: 12px; text-align: center; margin-bottom: 1rem;
}
.main-header h1 {
    background: linear-gradient(45deg, #667eea, #764ba2);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-size: 1.8rem; font-weight: 700; margin: 0;
}
.stButton>button {
    background: linear-gradient(45deg, #667eea, #764ba2);
    color: white; border: none; border-radius: 8px;
    padding: 0.6rem 1.5rem; font-weight: 600; width: 100%;
}
.stTextInput>div>div>input,
.stTextArea>div>div>textarea,
.stNumberInput>div>div>input {
    background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25);
    border-radius: 8px; color: white; padding: 0.6rem;
}
label { color: white !important; font-weight: 500 !important; font-size: 13px !important; }
.console-box {
    background: rgba(0,0,0,0.6); border: 1px solid rgba(102,126,234,0.5);
    border-radius: 8px; padding: 10px; font-family: 'Courier New', monospace;
    font-size: 11px; color: #a78bfa; max-height: 220px; overflow-y: auto; min-height: 80px;
}
.log-line { padding: 3px 6px; border-left: 2px solid #667eea; margin: 2px 0; background: rgba(0,0,0,0.3); }
.status-running {
    background: linear-gradient(135deg, #84fab0, #8fd3f4);
    padding: 8px; border-radius: 8px; color: #1a1a2e; text-align: center; font-weight: 700;
}
.status-stopped {
    background: linear-gradient(135deg, #fa709a, #fee140);
    padding: 8px; border-radius: 8px; color: white; text-align: center; font-weight: 600;
}
.online-indicator {
    display: inline-block; width: 10px; height: 10px; background: #00ff00;
    border-radius: 50%; margin-right: 6px; box-shadow: 0 0 6px #00ff00;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%   { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0,255,0,0.7); }
    70%  { transform: scale(1);    box-shadow: 0 0 0 6px rgba(0,255,0,0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0,255,0,0); }
}
.result-box {
    background: rgba(0,0,0,0.5); border: 1px solid rgba(102,126,234,0.4);
    border-radius: 8px; padding: 12px; margin-top: 10px;
}
.result-row {
    background: rgba(255,255,255,0.07); border-radius: 6px;
    padding: 8px 12px; margin: 4px 0; color: white; font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

st.markdown(get_keepalive_js(), unsafe_allow_html=True)

# ── Session manager ───────────────────────────────────────────────────────────
@st.cache_resource
def get_manager():
    return SessionManager()

manager = get_manager()

# ── Shared results store (for extractor) ─────────────────────────────────────
if 'extractor_results' not in st.session_state:
    st.session_state.extractor_results = []
if 'view_session' not in st.session_state:
    st.session_state.view_session = None

EXTRACT_RESULTS_FILE = "extractor_results.json"

# ═════════════════════════════════════════════════════════════════════════════
# BROWSER SETUP  (same logic as working original)
# ═════════════════════════════════════════════════════════════════════════════

def setup_browser(session):
    session.log('Setting up Chrome browser...')
    import shutil
    opts = Options()
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-setuid-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--disable-extensions')
    opts.add_argument('--window-size=1920,1080')
    opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

    for p in ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']:
        if Path(p).exists():
            opts.binary_location = p
            break

    drv_path = None
    for d in ['/usr/bin/chromedriver', '/usr/local/bin/chromedriver']:
        if Path(d).exists():
            drv_path = d
            break
    if not drv_path:
        drv_path = shutil.which('chromedriver') or shutil.which('chromium.chromedriver')
    if drv_path:
        session.log(f'Driver: {drv_path}')

    from selenium.webdriver.chrome.service import Service
    if drv_path:
        svc = Service(executable_path=drv_path)
        driver = webdriver.Chrome(service=svc, options=opts)
    else:
        driver = webdriver.Chrome(options=opts)

    driver.set_window_size(1920, 1080)
    session.log('Browser ready!')
    return driver


# ═════════════════════════════════════════════════════════════════════════════
# MESSENGER LOGIN  (cookies added to BOTH .messenger.com + .facebook.com)
# ═════════════════════════════════════════════════════════════════════════════

def login_messenger(driver, session, cookies):
    session.log('Opening Messenger...')
    driver.get('https://www.messenger.com/')
    time.sleep(8)

    if cookies:
        session.log('Adding cookies...')
        for c in cookies.split(';'):
            c = c.strip()
            if not c or '=' not in c:
                continue
            i = c.find('=')
            name = c[:i].strip()
            value = c[i+1:].strip()
            for domain in ['.messenger.com', '.facebook.com']:
                try:
                    driver.add_cookie({'name': name, 'value': value,
                                       'domain': domain, 'path': '/'})
                except:
                    pass

    driver.get('https://www.messenger.com/')
    time.sleep(10)
    session.log('Messenger loaded!')


def open_thread(driver, session, uid, e2e=False):
    """Navigate to a Messenger thread by UID."""
    if uid.startswith('http'):
        driver.get(uid)
    elif e2e:
        driver.get(f'https://www.messenger.com/e2ee/t/{uid}')
    else:
        driver.get(f'https://www.messenger.com/t/{uid}')
    time.sleep(10)
    session.log(f'Opened thread: {uid}')


# ═════════════════════════════════════════════════════════════════════════════
# ── FEATURE 1: SMART LOCK ────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

def get_current_group_name(driver):
    """Read the current group name from the Messenger chat header."""
    name = driver.execute_script("""
        var selectors = [
            'h1', 'h2', 'h4',
            '[data-testid="thread-title-text"]',
            '[data-testid="thread-title"]',
            'div[role="main"] header span',
            'header span[dir="auto"]'
        ];
        for (var i = 0; i < selectors.length; i++) {
            var el = document.querySelector(selectors[i]);
            if (el) {
                var t = el.textContent.trim();
                if (t.length > 1 && t !== 'Messenger') return t;
            }
        }
        var t = document.title.split('|')[0].trim().split('-')[0].trim();
        return (t && t !== 'Messenger' && t.length > 1) ? t : null;
    """)
    return (name or '').strip() or None


def restore_group_name(driver, session, target_name):
    """Attempt to rename the group back to target_name via Messenger UI."""
    session.log(f'Restoring group name → "{target_name}"')

    # Step 1: look for a settings / info button in the header
    opened_panel = driver.execute_script("""
        var labels = ['Customize chat','Chat info','More','Settings',
                      'Group info','Edit','Customize'];
        var btns = document.querySelectorAll('[role="button"],[aria-label]');
        for (var b of btns) {
            var lbl = (b.getAttribute('aria-label') || b.textContent || '').toLowerCase();
            for (var l of labels) {
                if (lbl.includes(l.toLowerCase())) { b.click(); return true; }
            }
        }
        return false;
    """)
    time.sleep(3)

    # Step 2: look for "Edit Group Name" or "Change name" inside panel/dialog
    found = driver.execute_script("""
        var keywords = ['edit group name','change name','group name','rename'];
        var all = document.querySelectorAll('[role="button"],[role="menuitem"],div,span,button');
        for (var el of all) {
            var t = (el.textContent || '').toLowerCase().trim();
            for (var k of keywords) {
                if (t === k || t.includes(k)) { el.click(); return true; }
            }
        }
        return false;
    """)
    time.sleep(2)

    # Step 3: find the rename input
    inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="text"],input:not([type])')
    for inp in inputs:
        try:
            if not inp.is_displayed():
                continue
            inp.triple_click = lambda: inp.send_keys(Keys.CONTROL + 'a')
            inp.send_keys(Keys.CONTROL + 'a')
            inp.send_keys(Keys.BACKSPACE)
            inp.clear()
            inp.send_keys(target_name)
            time.sleep(0.5)
            inp.send_keys(Keys.RETURN)
            time.sleep(2)
            session.log('✅ Group name restored!')
            return True
        except:
            continue

    # Fallback: try clicking on the group name text directly to enter edit mode
    driver.execute_script("""
        var h = document.querySelector('h1,h2,h4,[data-testid="thread-title-text"]');
        if (h) h.click();
    """)
    time.sleep(2)
    inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="text"],input:not([type])')
    for inp in inputs:
        try:
            if not inp.is_displayed():
                continue
            inp.send_keys(Keys.CONTROL + 'a')
            inp.send_keys(target_name)
            inp.send_keys(Keys.RETURN)
            time.sleep(2)
            session.log('✅ Group name restored (fallback)!')
            return True
        except:
            continue

    session.log('⚠️ Could not restore name via UI')
    return False


def set_member_nickname(driver, session, member_uid, nickname):
    """Set a member's nickname in the currently open Messenger group chat."""
    session.log(f'Setting nickname for UID {member_uid}: {nickname}')

    # Try opening members/people panel
    opened = driver.execute_script("""
        var labels = ['Members','People','View members','Participants'];
        var all = document.querySelectorAll('[role="button"],[aria-label]');
        for (var el of all) {
            var t = (el.getAttribute('aria-label') || el.textContent || '').trim();
            for (var l of labels) {
                if (t.toLowerCase().includes(l.toLowerCase())) { el.click(); return true; }
            }
        }
        return false;
    """)
    time.sleep(3)

    # Try clicking the specific member link/button (by uid in href or nearby text)
    clicked_member = driver.execute_script(f"""
        var uid = '{member_uid}';
        var links = document.querySelectorAll('a[href*="' + uid + '"]');
        if (links.length > 0) {{ links[0].click(); return true; }}
        return false;
    """)
    time.sleep(3)

    if not clicked_member:
        session.log(f'Member {member_uid} not found in panel')
        return False

    # Look for "Edit Nickname" or "Set Nickname" button
    found = driver.execute_script("""
        var kw = ['nickname','edit nickname','set nickname'];
        var all = document.querySelectorAll('[role="button"],[role="menuitem"],div,span');
        for (var el of all) {
            var t = (el.textContent || '').toLowerCase().trim();
            for (var k of kw) {
                if (t.includes(k)) { el.click(); return true; }
            }
        }
        return false;
    """)
    time.sleep(2)

    inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="text"],input:not([type])')
    for inp in inputs:
        try:
            if not inp.is_displayed():
                continue
            inp.send_keys(Keys.CONTROL + 'a')
            inp.send_keys(Keys.BACKSPACE)
            inp.clear()
            inp.send_keys(nickname)
            inp.send_keys(Keys.RETURN)
            time.sleep(2)
            session.log(f'✅ Nickname set: {nickname}')
            return True
        except:
            continue

    session.log(f'⚠️ Could not set nickname for {member_uid}')
    return False


def run_smart_lock(session, cookies, group_uid, target_name, nicknames_map, check_interval, e2e):
    """
    nicknames_map: dict {member_uid: nickname}
    Polls the group every check_interval seconds and restores name/nicknames.
    """
    driver = None
    retries = 0

    while session.running and retries < 8:
        try:
            if driver is None:
                driver = setup_browser(session)
                session.driver = driver
                login_messenger(driver, session, cookies)

            open_thread(driver, session, group_uid, e2e=e2e)

            # Set all nicknames once at the start of each browser session
            if nicknames_map:
                session.log(f'Setting {len(nicknames_map)} nickname(s)...')
                for muid, nick in nicknames_map.items():
                    if not session.running:
                        break
                    open_thread(driver, session, group_uid, e2e=e2e)
                    set_member_nickname(driver, session, muid, nick)
                open_thread(driver, session, group_uid, e2e=e2e)

            session.log('🔒 Smart Lock active — monitoring...')
            retries = 0

            while session.running:
                try:
                    # Re-navigate to get fresh state
                    open_thread(driver, session, group_uid, e2e=e2e)
                    current = get_current_group_name(driver)
                    session.log(f'Check → name: "{current}"')

                    if current and current != target_name:
                        session.log(f'⚠️ Name changed! "{current}" → restoring "{target_name}"')
                        restore_group_name(driver, session, target_name)

                    # Check nicknames
                    if nicknames_map and session.running:
                        for muid, nick in nicknames_map.items():
                            if not session.running:
                                break
                            # Re-open thread for each check to stay fresh
                            open_thread(driver, session, group_uid, e2e=e2e)
                            # Simple check: try to set nickname (will overwrite if changed)
                            set_member_nickname(driver, session, muid, nick)

                    session.count += 1
                    manager.update_count(session.id, session.count)

                    # Wait for next check
                    session.log(f'Sleeping {check_interval}s until next check...')
                    for _ in range(check_interval):
                        if not session.running:
                            break
                        time.sleep(1)

                except Exception as inner_e:
                    err = str(inner_e)[:60]
                    session.log(f'Inner error: {err}')
                    if 'session' in err.lower() or 'disconn' in err.lower():
                        session.log('Browser lost, restarting...')
                        try:
                            driver.quit()
                        except:
                            pass
                        driver = None
                        retries += 1
                        time.sleep(5)
                        break
                    time.sleep(10)

        except Exception as e:
            session.log(f'Fatal: {str(e)[:60]}')
            retries += 1
            try:
                driver.quit()
            except:
                pass
            driver = None
            time.sleep(10)

    session.running = False
    session.log('Smart Lock stopped.')
    manager._save_registry()
    if driver:
        try:
            driver.quit()
        except:
            pass
    gc.collect()


def start_smart_lock(session, cookies, group_uid, target_name, nicknames_raw, check_interval, e2e):
    session.running = True
    session.logs = deque(maxlen=50)
    session.count = 0
    session.idx = 0
    session.start_time = time.strftime("%H:%M:%S")
    try:
        open(f"messenger_logs/{session.id}.log", 'w').close()
    except:
        pass

    # Parse nicknames: each line is "UID=Nickname"
    nicknames_map = {}
    for line in nicknames_raw.splitlines():
        line = line.strip()
        if '=' in line:
            parts = line.split('=', 1)
            uid_part = parts[0].strip()
            nick_part = parts[1].strip()
            if uid_part and nick_part:
                nicknames_map[uid_part] = nick_part

    session.log(f'Smart Lock starting | Group: {group_uid} | Name: "{target_name}" | '
                f'Nicknames: {len(nicknames_map)} | Interval: {check_interval}s')
    manager._save_registry()

    threading.Thread(
        target=run_smart_lock,
        args=(session, cookies, group_uid, target_name, nicknames_map, check_interval, e2e),
        daemon=True
    ).start()


# ═════════════════════════════════════════════════════════════════════════════
# ── FEATURE 2: AUTO MESSAGE SENDER ──────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

def find_message_input(driver, session):
    session.log('Finding message input...')
    time.sleep(5)
    selectors = [
        'div[role="textbox"][aria-label*="message" i]',
        'div[contenteditable="true"][aria-label*="message" i]',
        'div[role="textbox"][aria-label*="Message" i]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[contenteditable="true"]',
        '[role="textbox"]',
    ]
    for sel in selectors:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elems:
                try:
                    ok = driver.execute_script(
                        "return arguments[0].contentEditable === 'true' || "
                        "arguments[0].tagName === 'TEXTAREA';", el)
                    if ok and el.is_displayed():
                        el.click()
                        time.sleep(0.3)
                        session.log('Message input found!')
                        return el
                except:
                    continue
        except:
            continue
    return None


def send_message(driver, session, msg_input, text):
    """Type text and send via Enter."""
    driver.execute_script("""
        const el = arguments[0];
        const txt = arguments[1];
        el.scrollIntoView({block:'center'});
        el.focus();
        el.click();
        if (el.tagName === 'DIV') {
            el.textContent = txt;
        } else {
            el.value = txt;
        }
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new InputEvent('input', {bubbles:true, data:txt}));
    """, msg_input, text)
    time.sleep(0.8)

    driver.execute_script("""
        const el = arguments[0];
        el.focus();
        ['keydown','keypress','keyup'].forEach(type => {
            el.dispatchEvent(new KeyboardEvent(type, {
                key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true
            }));
        });
    """, msg_input)
    time.sleep(1)
    session.log(f'Message sent: {text[:30]}...')


def run_auto_message(session, cookies, recipient_uids, messages, prefix, delay, e2e):
    driver = None
    retries = 0

    while session.running and retries < 8:
        try:
            if driver is None:
                driver = setup_browser(session)
                session.driver = driver
                login_messenger(driver, session, cookies)

            session.log(f'Starting auto-message | {len(recipient_uids)} recipient(s)')
            retries = 0

            while session.running:
                for uid in recipient_uids:
                    if not session.running:
                        break

                    uid = uid.strip()
                    session.log(f'Opening: {uid}')
                    open_thread(driver, session, uid, e2e=e2e)

                    msg_input = find_message_input(driver, session)
                    if not msg_input:
                        session.log(f'❌ Input not found for {uid}, skipping')
                        continue

                    base_msg = messages[session.idx % len(messages)]
                    session.idx += 1
                    full_msg = f"{prefix} {base_msg}".strip() if prefix else base_msg

                    send_message(driver, session, msg_input, full_msg)
                    session.count += 1
                    manager.update_count(session.id, session.count)
                    session.log(f'✅ Msg #{session.count} sent to {uid}')

                    jitter = int(delay + random.uniform(-5, 5))
                    jitter = max(5, jitter)
                    session.log(f'Waiting {jitter}s...')
                    for _ in range(jitter):
                        if not session.running:
                            break
                        time.sleep(1)

                if session.running:
                    simulate_browser_activity(driver)

        except Exception as e:
            err = str(e)[:60]
            session.log(f'Fatal: {err}')
            retries += 1
            try:
                driver.quit()
            except:
                pass
            driver = None
            time.sleep(8)

    session.running = False
    session.log('Auto Message stopped.')
    manager._save_registry()
    if driver:
        try:
            driver.quit()
        except:
            pass
    gc.collect()


def start_auto_message(session, cookies, recipient_uids, messages, prefix, delay, e2e):
    session.running = True
    session.logs = deque(maxlen=50)
    session.count = 0
    session.idx = 0
    session.start_time = time.strftime("%H:%M:%S")
    try:
        open(f"messenger_logs/{session.id}.log", 'w').close()
    except:
        pass
    session.log(f'Auto Message session starting...')
    manager._save_registry()
    threading.Thread(
        target=run_auto_message,
        args=(session, cookies, recipient_uids, messages, prefix, delay, e2e),
        daemon=True
    ).start()


# ═════════════════════════════════════════════════════════════════════════════
# ── FEATURE 3: GROUP UID EXTRACTOR ──────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

def extract_groups_from_messenger(session, cookies, result_holder):
    """
    Scrapes all group conversations from messenger.com sidebar.
    result_holder is a list; we append dicts {name, uid, members} to it.
    """
    driver = None
    try:
        driver = setup_browser(session)
        session.driver = driver
        login_messenger(driver, session, cookies)

        session.log('Scanning conversations...')
        driver.get('https://www.messenger.com/')
        time.sleep(12)

        # Scroll sidebar to load more conversations
        driver.execute_script("""
            var sidebar = document.querySelector('[role="navigation"]') ||
                          document.querySelector('[aria-label*="conversation" i]') ||
                          document.querySelector('div[role="list"]');
            if (sidebar) {
                for (var i = 0; i < 10; i++) {
                    sidebar.scrollTop += 600;
                }
            }
        """)
        time.sleep(4)

        # Extract all conversation links and titles
        convs = driver.execute_script("""
            var results = [];
            var seen = new Set();

            // Method 1: links with /t/ or /e2ee/t/ in href
            var links = document.querySelectorAll('a[href*="/t/"]');
            links.forEach(function(link) {
                var href = link.getAttribute('href') || '';
                var uid = href.replace(/.*\\/t\\//, '').replace(/[?#].*/, '').trim();
                if (!uid || seen.has(uid)) return;
                seen.add(uid);

                // Get conversation name
                var nameEl = link.querySelector('span[dir="auto"],span,div[dir="auto"]');
                var name = nameEl ? nameEl.textContent.trim() : uid;

                // Get member count hint (often shown as "You, Name, ...")
                var subEl = link.querySelector('div:nth-child(2) span, div:last-child span');
                var subtitle = subEl ? subEl.textContent.trim() : '';

                results.push({uid: uid, name: name, subtitle: subtitle, href: href});
            });

            return results;
        """)

        # Filter to likely group conversations (has subtitle mentioning multiple people
        # or has a name that's not a single person)
        all_found = []
        for c in (convs or []):
            uid = (c.get('uid') or '').strip()
            name = (c.get('name') or uid).strip()
            subtitle = (c.get('subtitle') or '').strip()
            if uid:
                all_found.append({'uid': uid, 'name': name, 'subtitle': subtitle})

        session.log(f'Found {len(all_found)} conversation(s)')

        # For each conversation, visit it to check if it's a group and get member count
        for idx, conv in enumerate(all_found[:30]):  # limit to 30
            if not session.running:
                break
            uid = conv['uid']
            session.log(f'Checking {idx+1}/{min(len(all_found),30)}: {conv["name"][:20]}')

            try:
                driver.get(f'https://www.messenger.com/t/{uid}')
                time.sleep(8)

                info = driver.execute_script("""
                    // Get group name from header
                    var nameEl = document.querySelector(
                        'h1,h2,h4,[data-testid="thread-title-text"],[data-testid="thread-title"]');
                    var name = nameEl ? nameEl.textContent.trim() : null;

                    // Member count: look for "X members" text
                    var memberCount = null;
                    var allText = document.body.innerText || '';
                    var m = allText.match(/(\\d+) (members|people|participants)/i);
                    if (m) memberCount = m[1] + ' ' + m[2];

                    // Is it a group? Look for "Members" label or multiple names in header subtitle
                    var isGroup = false;
                    var spans = document.querySelectorAll('span,div');
                    spans.forEach(function(el) {
                        var t = (el.textContent || '').toLowerCase().trim();
                        if (t === 'members' || t.includes('member') || t.includes('participant')) {
                            isGroup = true;
                        }
                    });

                    return {name: name, memberCount: memberCount, isGroup: isGroup};
                """)

                g_name = (info.get('name') or conv['name']).strip()
                m_count = info.get('memberCount') or 'N/A'
                is_group = info.get('isGroup') or (',' in conv['subtitle'])

                result_holder.append({
                    'uid': uid,
                    'name': g_name,
                    'members': m_count,
                    'is_group': is_group,
                })
                session.log(f'✅ {g_name[:20]} | {m_count} | Group: {is_group}')
                session.count += 1
                manager.update_count(session.id, session.count)

            except Exception as e:
                session.log(f'Error on {uid}: {str(e)[:40]}')

        session.log(f'Extraction done! {len(result_holder)} conversations found.')

    except Exception as e:
        session.log(f'Fatal: {str(e)[:60]}')
    finally:
        session.running = False
        manager._save_registry()
        if driver:
            try:
                driver.quit()
            except:
                pass
        gc.collect()


def start_extractor(session, cookies):
    session.running = True
    session.logs = deque(maxlen=50)
    session.count = 0
    session.start_time = time.strftime("%H:%M:%S")
    try:
        open(f"messenger_logs/{session.id}.log", 'w').close()
    except:
        pass
    session.log('Group UID Extractor starting...')
    manager._save_registry()
    result_holder = st.session_state.extractor_results
    result_holder.clear()
    threading.Thread(
        target=extract_groups_from_messenger,
        args=(session, cookies, result_holder),
        daemon=True
    ).start()


# ═════════════════════════════════════════════════════════════════════════════
# ── UI ───────────────────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="main-header"><h1>🔒 Messenger Tools</h1></div>', unsafe_allow_html=True)

all_sessions = manager.get_all_sessions()
active_sessions = manager.get_active_sessions()

c1, c2, c3 = st.columns(3)
c1.metric("Active Sessions", len(active_sessions))
c2.metric("Total Actions", sum(s.count for s in all_sessions))
with c3:
    if st.button("Refresh"):
        st.rerun()

st.markdown("---")

# ── Session viewer ─────────────────────────────────────────────────────────
if st.session_state.view_session:
    sid = st.session_state.view_session
    session = manager.get_session(sid)

    st.markdown(f"### Session: `{sid}`")

    if session:
        if session.running:
            st.markdown(
                f'<div class="status-running"><span class="online-indicator"></span>'
                f'RUNNING — {session.count} actions | {session.session_type.upper()}</div>',
                unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-stopped">STOPPED</div>', unsafe_allow_html=True)

        logs = manager.get_logs(sid, 30)
        logs_html = '<div class="console-box">'
        for line in logs:
            logs_html += f'<div class="log-line">{line.strip()}</div>'
        logs_html += '</div>'
        st.markdown(logs_html, unsafe_allow_html=True)

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("STOP", disabled=not session.running):
                manager.stop_session(sid)
                st.rerun()
        with b2:
            if st.button("Delete"):
                manager.delete_session(sid)
                st.session_state.view_session = None
                st.rerun()
        with b3:
            if st.button("↻ Refresh Logs"):
                st.rerun()
        with b4:
            if st.button("← Back"):
                st.session_state.view_session = None
                st.rerun()
    else:
        st.error("Session not found")
        if st.button("← Back"):
            st.session_state.view_session = None
            st.rerun()

else:
    # ── 3 feature tabs ────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["🔒 Smart Lock", "💬 Auto Message", "🔍 Group UID Extractor"])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — Smart Lock
    # ══════════════════════════════════════════════════════════════════════
    with tab1:
        st.markdown("### 🔒 Smart Lock — Group Name & Nickname Guard")
        st.info(
            "Enter the group E2E UID, the name you want to lock, "
            "and optional member nicknames. The tool will monitor the group "
            "and restore any changes automatically."
        )

        sl1, sl2 = st.columns(2)
        with sl1:
            sl_group_uid = st.text_input(
                "Group E2E UID", placeholder="e.g. 6158586340685", key="sl_gid")
            sl_target_name = st.text_input(
                "Group Name to Lock", placeholder="My Group", key="sl_name")
            sl_interval = st.number_input(
                "Check Interval (seconds)", 30, 3600, 60, key="sl_interval")
            sl_e2e = st.checkbox("E2E Encrypted Thread?", value=True, key="sl_e2e")
        with sl2:
            sl_cookies = st.text_area(
                "Cookies", height=110, placeholder="Paste Facebook/Messenger cookies...",
                key="sl_cookies")
            sl_nicknames = st.text_area(
                "Member Nicknames (optional)\nFormat: UID=Nickname  one per line",
                height=110,
                placeholder="61585863406851=Bhai\n100072345678=Dost",
                key="sl_nicks")

        if st.button("🔒 START SMART LOCK", key="btn_smartlock", use_container_width=True):
            if not sl_cookies.strip():
                st.error("Cookies required!")
            elif not sl_group_uid.strip():
                st.error("Group UID required!")
            elif not sl_target_name.strip():
                st.error("Group name to lock required!")
            else:
                new_s = manager.create_session('lock')
                start_smart_lock(
                    new_s,
                    sl_cookies.strip(),
                    sl_group_uid.strip(),
                    sl_target_name.strip(),
                    sl_nicknames,
                    int(sl_interval),
                    sl_e2e
                )
                st.success(f"✅ Smart Lock started! Session: `{new_s.id}`")
                time.sleep(1)
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — Auto Message
    # ══════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("### 💬 Auto Message Sender — Inbox / Group Chat")
        st.info(
            "Enter recipient E2E UIDs (one per line). "
            "Upload a msg.txt with one message per line. "
            "The tool opens each inbox, types the message with prefix, and sends it."
        )

        am1, am2 = st.columns(2)
        with am1:
            am_uids = st.text_area(
                "Recipient E2E UIDs (one per line)",
                height=120,
                placeholder="61585863406851\n100072345678\nhttps://messenger.com/t/xxx",
                key="am_uids")
            am_prefix = st.text_input(
                "Prefix (optional)", placeholder="Hello!", key="am_prefix")
            am_delay = st.number_input(
                "Delay between messages (seconds)", 10, 3600, 30, key="am_delay")
            am_e2e = st.checkbox("E2E Encrypted Thread?", value=True, key="am_e2e")
        with am2:
            am_cookies = st.text_area(
                "Cookies", height=110, placeholder="Paste cookies...", key="am_cookies")
            am_txt_file = st.file_uploader(
                "Upload msg.txt (one message per line)", type=['txt'], key="am_txt")
            am_manual = st.text_area(
                "Or type messages here (one per line)",
                height=80,
                placeholder="Hello!\nHow are you?\nCheck this out!",
                key="am_manual")

        messages_list = []
        if am_txt_file:
            raw = am_txt_file.read().decode('utf-8', errors='ignore')
            messages_list = [l.strip() for l in raw.splitlines() if l.strip()]
            st.success(f"✅ {len(messages_list)} message(s) loaded from file")
        elif am_manual.strip():
            messages_list = [l.strip() for l in am_manual.splitlines() if l.strip()]

        if messages_list:
            st.code(f"First message: {messages_list[0][:80]}", language=None)

        if st.button("💬 START AUTO MESSAGE", key="btn_automsg", use_container_width=True):
            uids_list = [u.strip() for u in am_uids.splitlines() if u.strip()]
            if not am_cookies.strip():
                st.error("Cookies required!")
            elif not uids_list:
                st.error("Add at least one recipient UID!")
            elif not messages_list:
                st.error("Add messages (file or manual)!")
            else:
                new_s = manager.create_session('message')
                start_auto_message(
                    new_s,
                    am_cookies.strip(),
                    uids_list,
                    messages_list,
                    am_prefix.strip(),
                    int(am_delay),
                    am_e2e
                )
                st.success(f"✅ Auto Message started! Session: `{new_s.id}`")
                time.sleep(1)
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — Group UID Extractor
    # ══════════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown("### 🔍 Group UID Extractor")
        st.info(
            "Add your cookies — the tool opens Messenger, scans all your "
            "conversations, and extracts Group Name, Member Count, and UID."
        )

        ex_cookies = st.text_area(
            "Cookies", height=110,
            placeholder="Paste Facebook/Messenger cookies...",
            key="ex_cookies")

        if st.button("🔍 EXTRACT GROUP UIDs", key="btn_extract", use_container_width=True):
            if not ex_cookies.strip():
                st.error("Cookies required!")
            else:
                new_s = manager.create_session('extractor')
                start_extractor(new_s, ex_cookies.strip())
                st.success(f"✅ Extraction started! Session: `{new_s.id}`")
                st.info("Click 'Refresh' button above to update results as they come in.")
                time.sleep(2)
                st.rerun()

        # Show results
        results = st.session_state.extractor_results
        if results:
            st.markdown(f"#### Found {len(results)} conversation(s)")

            # Export CSV
            import io
            csv_lines = ["UID,Name,Members,IsGroup"]
            for r in results:
                csv_lines.append(
                    f'"{r["uid"]}","{r["name"]}","{r["members"]}","{r["is_group"]}"')
            csv_data = "\n".join(csv_lines)
            st.download_button(
                "⬇ Download CSV",
                data=csv_data.encode(),
                file_name="messenger_groups.csv",
                mime="text/csv"
            )

            st.markdown('<div class="result-box">', unsafe_allow_html=True)
            for r in results:
                flag = "👥" if r.get('is_group') else "👤"
                st.markdown(
                    f'<div class="result-row">'
                    f'{flag} <b>{r["name"]}</b> &nbsp;|&nbsp; '
                    f'UID: <code>{r["uid"]}</code> &nbsp;|&nbsp; '
                    f'Members: {r["members"]}'
                    f'</div>',
                    unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No results yet — start extraction above.")

# ── Active sessions panel ──────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Active Sessions")

active = manager.get_active_sessions()
if active:
    for s in active:
        c1, c2, c3, c4, c5 = st.columns([1, 2, 1, 1, 1])
        with c1:
            badge = {"lock": "🔒", "message": "💬", "extractor": "🔍"}.get(s.session_type, "⚙️")
            st.write(f"{badge} `{s.id}`")
        with c2:
            st.write(f"Actions: {s.count} | {s.session_type}")
        with c3:
            if st.button("View", key=f"v_{s.id}"):
                st.session_state.view_session = s.id
                st.rerun()
        with c4:
            if st.button("Stop", key=f"s_{s.id}"):
                manager.stop_session(s.id)
                st.rerun()
        with c5:
            if st.button("Del", key=f"d_{s.id}"):
                manager.delete_session(s.id)
                st.rerun()
else:
    st.info("No active sessions")

stopped = [s for s in all_sessions if not s.running]
if stopped:
    with st.expander("Stopped Sessions"):
        for s in stopped[-8:]:
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                badge = {"lock": "🔒", "message": "💬", "extractor": "🔍"}.get(s.session_type, "⚙️")
                st.write(f"{badge} `{s.id}`")
            with c2:
                st.write(f"Actions: {s.count}")
            with c3:
                if st.button("Logs", key=f"lg_{s.id}"):
                    st.session_state.view_session = s.id
                    st.rerun()
            with c4:
                if st.button("Del", key=f"dl_{s.id}"):
                    manager.delete_session(s.id)
                    st.rerun()

# ── Session lookup ─────────────────────────────────────────────────────────
st.markdown("---")
lookup = st.text_input("Session ID lookup:", placeholder="XXXXXXXX", key="lookup")
if lookup and st.button("Find"):
    if manager.get_session(lookup.upper()):
        st.session_state.view_session = lookup.upper()
        st.rerun()
    else:
        st.error("Session not found")
