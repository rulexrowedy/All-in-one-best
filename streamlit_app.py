import streamlit as st
import time
import threading
import gc
import json
import os
import uuid
import random
from pathlib import Path
from collections import deque
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

st.set_page_config(
    page_title="FB Comment Tool",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

KEEP_ALIVE_JS = """
<script>
    setInterval(function() { fetch(window.location.href, {method: 'HEAD'}).catch(function(){}); }, 25000);
    setInterval(function() { document.dispatchEvent(new MouseEvent('mousemove', {bubbles: true, clientX: Math.random()*200, clientY: Math.random()*200})); }, 60000);
</script>
"""

custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    * { font-family: 'Poppins', sans-serif; }
    .stApp {
        background-image: url('https://i.postimg.cc/TYhXd0gG/d0a72a8cea5ae4978b21e04a74f0b0ee.jpg');
        background-size: cover; background-position: center; background-attachment: fixed;
    }
    .main .block-container {
        background: rgba(255, 255, 255, 0.08); backdrop-filter: blur(8px);
        border-radius: 12px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .main-header {
        background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px);
        padding: 1rem; border-radius: 12px; text-align: center; margin-bottom: 1rem;
    }
    .main-header h1 {
        background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-size: 1.8rem; font-weight: 700; margin: 0;
    }
    .stButton>button {
        background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
        color: white; border: none; border-radius: 8px; padding: 0.6rem 1.5rem;
        font-weight: 600; width: 100%;
    }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stNumberInput>div>div>input {
        background: rgba(255, 255, 255, 0.15); border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 8px; color: white; padding: 0.6rem;
    }
    label { color: white !important; font-weight: 500 !important; font-size: 13px !important; }
    .console-box {
        background: rgba(0, 0, 0, 0.6); border: 1px solid rgba(78, 205, 196, 0.5);
        border-radius: 8px; padding: 10px; font-family: 'Courier New', monospace;
        font-size: 11px; color: #00ff88; max-height: 200px; overflow-y: auto;
        min-height: 100px;
    }
    .log-line { padding: 3px 6px; border-left: 2px solid #4ecdc4; margin: 2px 0; background: rgba(0,0,0,0.3); }
    .status-running { background: linear-gradient(135deg, #84fab0, #8fd3f4); padding: 8px; border-radius: 8px; color: white; text-align: center; font-weight: 600; }
    .status-stopped { background: linear-gradient(135deg, #fa709a, #fee140); padding: 8px; border-radius: 8px; color: white; text-align: center; font-weight: 600; }
    .online-indicator {
        display: inline-block; width: 10px; height: 10px; background-color: #00ff00;
        border-radius: 50%; margin-right: 5px; box-shadow: 0 0 5px #00ff00;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 5px rgba(0, 255, 0, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }
    }
    [data-testid="stMetricValue"] { color: #4ecdc4; font-weight: 700; }
    .session-id-box { background: linear-gradient(45deg, #667eea, #764ba2); padding: 10px 15px; border-radius: 8px; color: white; font-weight: 600; font-family: monospace; text-align: center; margin: 10px 0; }
    .active-sessions { background: rgba(0,0,0,0.4); border: 1px solid rgba(78, 205, 196, 0.5); border-radius: 10px; padding: 15px; margin-top: 20px; }
    .session-row { background: rgba(255,255,255,0.1); padding: 10px; border-radius: 6px; margin: 5px 0; display: flex; justify-content: space-between; align-items: center; }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)
st.markdown(KEEP_ALIVE_JS, unsafe_allow_html=True)

SESSIONS_FILE = "sessions_registry.json"
LOGS_DIR = "session_logs"
MAX_LOGS = 30
TEMP_IMAGES_DIR = "temp_images"

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_IMAGES_DIR, exist_ok=True)

class Session:
    __slots__ = ['id', 'running', 'count', 'logs', 'idx', 'driver', 'start_time', 'profile_id', 'img_idx', 'session_type']
    def __init__(self, sid, session_type='comment'):
        self.id = sid
        self.running = False
        self.count = 0
        self.logs = deque(maxlen=MAX_LOGS)
        self.idx = 0
        self.img_idx = 0
        self.driver = None
        self.start_time = None
        self.profile_id = None
        self.session_type = session_type
    
    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        profile_str = f" {self.profile_id}" if self.profile_id else ""
        log_entry = f"[{ts}]{profile_str} {msg}"
        self.logs.append(log_entry)
        try:
            with open(f"{LOGS_DIR}/{self.id}.log", "a") as f:
                f.write(log_entry + "\n")
        except:
            pass

@st.cache_resource
def get_session_manager():
    return SessionManager()

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()
        self._load_registry()
    
    def _load_registry(self):
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE, 'r') as f:
                    data = json.load(f)
                    for sid, info in data.items():
                        if sid not in self.sessions:
                            s = Session(sid, info.get('session_type', 'comment'))
                            s.count = info.get('count', 0)
                            s.running = False
                            s.start_time = info.get('start_time')
                            self.sessions[sid] = s
            except:
                pass
    
    def _save_registry(self):
        try:
            data = {}
            for sid, s in self.sessions.items():
                data[sid] = {
                    'count': s.count,
                    'running': s.running,
                    'start_time': s.start_time,
                    'session_type': s.session_type
                }
            with open(SESSIONS_FILE, 'w') as f:
                json.dump(data, f)
        except:
            pass
    
    def create_session(self, session_type='comment'):
        with self.lock:
            sid = uuid.uuid4().hex[:8].upper()
            s = Session(sid, session_type)
            self.sessions[sid] = s
            self._save_registry()
            return s
    
    def get_session(self, sid):
        return self.sessions.get(sid)
    
    def get_all_sessions(self):
        return list(self.sessions.values())
    
    def get_active_sessions(self):
        return [s for s in self.sessions.values() if s.running]
    
    def stop_session(self, sid):
        s = self.sessions.get(sid)
        if s:
            s.running = False
            if s.driver:
                try:
                    s.driver.quit()
                except:
                    pass
                s.driver = None
            self._save_registry()

    def delete_session(self, sid):
        with self.lock:
            s = self.sessions.get(sid)
            if s:
                s.running = False
                if s.driver is not None:
                    try: s.driver.quit()
                    except: pass
                    s.driver = None
                del self.sessions[sid]
                try:
                    os.remove(f"{LOGS_DIR}/{sid}.log")
                except:
                    pass
                self._save_registry()
                gc.collect()
    
    def get_logs(self, sid, limit=30):
        log_file = f"{LOGS_DIR}/{sid}.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    return lines[-limit:]
            except:
                pass
        s = self.sessions.get(sid)
        if s:
            return list(s.logs)[-limit:]
        return []
    
    def update_count(self, sid, count):
        s = self.sessions.get(sid)
        if s:
            s.count = count
            self._save_registry()
    
    def cleanup_stopped(self):
        with self.lock:
            to_remove = [sid for sid, s in self.sessions.items() if not s.running and s.count == 0]
            for sid in to_remove:
                del self.sessions[sid]
                try:
                    os.remove(f"{LOGS_DIR}/{sid}.log")
                except:
                    pass
            self._save_registry()

manager = get_session_manager()

def extract_fb_profile_name(cookies):
    try:
        cookie_dict = {}
        if cookies:
            for c in cookies.split(';'):
                c = c.strip()
                if c and '=' in c:
                    i = c.find('=')
                    name = c[:i].strip()
                    value = c[i+1:].strip()
                    cookie_dict[name] = value
        
        if 'c_user' in cookie_dict:
            return cookie_dict['c_user']
        elif 'uid' in cookie_dict:
            return cookie_dict['uid']
        return "Unknown"
    except:
        return "Unknown"

def fetch_profile_name_from_fb(driver, c_user_id):
    try:
        driver.get(f'https://www.facebook.com/{c_user_id}')
        time.sleep(8)
        profile_name = driver.execute_script("""
            try {
                let name = null;
                let h1 = document.querySelector('h1');
                if (h1) name = h1.textContent?.trim();
                if (!name) {
                    let title_elem = document.querySelector('[data-content-scope-id] h1') || 
                                    document.querySelector('h2 span') ||
                                    document.evaluate("//h1/span", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (title_elem) name = title_elem.textContent?.trim();
                }
                return (name && name.length > 1) ? name : 'Unknown';
            } catch (e) { return 'Unknown'; }
        """)
        return profile_name.strip() if profile_name else "Unknown"
    except:
        return "Unknown"

def setup_browser(session):
    session.log('Setting up Chrome browser...')
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
    
    import shutil
    drv_path = None
    for d in ['/usr/bin/chromedriver', '/usr/local/bin/chromedriver']:
        if Path(d).exists():
            drv_path = d
            break
    if not drv_path:
        drv_path = shutil.which('chromedriver') or shutil.which('chromium.chromedriver')
    if drv_path:
        session.log(f'Chromedriver: {drv_path}')
    
    from selenium.webdriver.chrome.service import Service
    if drv_path:
        svc = Service(executable_path=drv_path)
        driver = webdriver.Chrome(service=svc, options=opts)
    else:
        driver = webdriver.Chrome(options=opts)
    
    driver.set_window_size(1920, 1080)
    session.log('Browser ready!')
    return driver

def simulate_human(driver):
    try:
        # Frequent background activity to stay online
        driver.execute_script("""
            window.scrollBy(0, Math.random() * 200 - 100);
            document.dispatchEvent(new MouseEvent('mousemove', {
                bubbles: true,
                clientX: Math.random() * window.innerWidth,
                clientY: Math.random() * window.innerHeight
            }));
            // Occasionally click to signal active session
            if (Math.random() > 0.7) {
                const body = document.querySelector('body');
                if (body) body.click();
            }
        """)
        # Touch home page or notification to keep session fresh
        if random.random() > 0.9:
            driver.execute_script("fetch('/home').catch(e => {});")
    except:
        pass

def find_comment_input(driver, session):
    session.log('Finding comment input...')
    time.sleep(10)
    
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
    except:
        pass
    
    selectors = [
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[aria-label*="comment" i][contenteditable="true"]',
        'div[aria-label*="Comment" i][contenteditable="true"]',
        'div[aria-label*="Write a comment" i][contenteditable="true"]',
        'div[contenteditable="true"][spellcheck="true"]',
        '[role="textbox"][contenteditable="true"]',
        '[contenteditable="true"]'
    ]
    
    for idx, selector in enumerate(selectors):
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                try:
                    is_editable = driver.execute_script("""
                        return arguments[0].contentEditable === 'true' || 
                               arguments[0].tagName === 'TEXTAREA' || 
                               arguments[0].tagName === 'INPUT';
                    """, element)
                    if is_editable:
                        try:
                            element.click()
                            time.sleep(0.5)
                        except:
                            pass
                        session.log(f'Found input with selector #{idx+1}')
                        return element
                except:
                    continue
        except:
            continue
    return None

def run_session(session, post_id, cookies, comments_list, prefix, delay):
    retries = 0
    driver = None
    fb_id = extract_fb_profile_name(cookies)
    
    while session.running and retries < 10:
        try:
            if driver is None:
                driver = setup_browser(session)
                session.driver = driver
            
            session.log('Navigating to Facebook...')
            driver.get('https://www.facebook.com/')
            time.sleep(8)
            
            if cookies:
                session.log('Adding cookies...')
                for c in cookies.split(';'):
                    c = c.strip()
                    if c and '=' in c:
                        i = c.find('=')
                        try:
                            driver.add_cookie({'name': c[:i].strip(), 'value': c[i+1:].strip(), 'domain': '.facebook.com', 'path': '/'})
                        except:
                            pass
            
            profile_name = fetch_profile_name_from_fb(driver, fb_id)
            session.profile_id = f"📌{profile_name}"
            session.log(f'Profile: {profile_name}')
            
            session.log(f'Opening post...')
            if post_id.startswith('http'):
                driver.get(post_id)
            else:
                driver.get(f'https://www.facebook.com/{post_id}')
            
            time.sleep(15)
            session.log('ID Online - Browser Active!')
            
            input_not_found_count = 0
            while session.running:
                try:
                    comment_input = find_comment_input(driver, session)
                    
                    if not comment_input:
                        input_not_found_count += 1
                        if input_not_found_count >= 3:
                            session.log('❌ Comment input not found - stopping session as requested')
                            session.running = False
                            break
                        session.log(f'Comment input not found ({input_not_found_count}/3), refreshing...')
                        driver.get(driver.current_url)
                        time.sleep(15)
                        continue
                    
                    input_not_found_count = 0
                    
                    base_comment = comments_list[session.idx % len(comments_list)]
                    session.idx += 1
                    
                    comment_to_send = f"{prefix} {base_comment}" if prefix else base_comment
                    
                    session.log(f'Typing: {comment_to_send[:25]}...')
                    
                    driver.execute_script("""
                        const element = arguments[0];
                        const message = arguments[1];
                        element.scrollIntoView({behavior: 'smooth', block: 'center'});
                        element.focus();
                        element.click();
                        if (element.tagName === 'DIV') {
                            element.textContent = message;
                            element.innerHTML = message;
                        } else {
                            element.value = message;
                        }
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                        element.dispatchEvent(new InputEvent('input', { bubbles: true, data: message }));
                    """, comment_input, comment_to_send)
                    
                    time.sleep(1)
                    
                    session.log('Sending...')
                    driver.execute_script("""
                        const element = arguments[0];
                        element.focus();
                        const events = [
                            new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }),
                            new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }),
                            new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true })
                        ];
                        events.forEach(event => element.dispatchEvent(event));
                    """, comment_input)
                    
                    time.sleep(1)
                    session.count += 1
                    manager.update_count(session.id, session.count)
                    session.log(f'Comment #{session.count} sent!')
                    retries = 0
                    
                    # Jitter delay
                    jitter_delay = int(delay + random.uniform(-10, 10))
                    jitter_delay = max(10, jitter_delay)
                    session.log(f'Waiting {jitter_delay}s (with jitter)...')
                    for i in range(jitter_delay):
                        if not session.running:
                            break
                        if i > 0 and i % 15 == 0:
                            simulate_human(driver)
                        time.sleep(1)
                    
                    if session.count % 2 == 0:
                        gc.collect()
                        try:
                            driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
                        except:
                            pass
                        
                except Exception as e:
                    err = str(e)[:50]
                    session.log(f'Error: {err}')
                    if 'session' in err.lower() or 'disconnect' in err.lower():
                        session.log('Restarting browser...')
                        try: driver.quit()
                        except: pass
                        driver = None
                        retries += 1
                        time.sleep(5)
                        break
                    time.sleep(10)
                    
        except Exception as e:
            session.log(f'Fatal: {str(e)[:50]}')
            retries += 1
            try: driver.quit()
            except: pass
            driver = None
            time.sleep(10)
    
    session.running = False
    session.log('Stopped.')
    manager._save_registry()
    if driver:
        try: driver.quit()
        except: pass
    gc.collect()

def start_session(session, post_id, cookies, comments, prefix, delay):
    session.running = True
    session.logs = deque(maxlen=MAX_LOGS)
    session.count = 0
    session.idx = 0
    session.start_time = time.strftime("%H:%M:%S")
    
    try:
        open(f"{LOGS_DIR}/{session.id}.log", 'w').close()
    except:
        pass
    
    session.log(f'Session {session.id} starting...')
    manager._save_registry()
    
    comments_list = [c.strip() for c in comments.split('\n') if c.strip()] or ['Nice post!']
    threading.Thread(target=run_session, args=(session, post_id, cookies, comments_list, prefix, delay), daemon=True).start()

# =============================================================================
# NEW AUTO-POST FUNCTIONS (added below — original code above is unchanged)
# =============================================================================

def get_uid_display_name(driver, uid_or_url):
    """Visit Facebook profile and return the display name for mention autocomplete."""
    try:
        if uid_or_url.startswith('http'):
            driver.get(uid_or_url)
        else:
            uid = uid_or_url.lstrip('@')
            driver.get(f'https://www.facebook.com/profile.php?id={uid}')
        time.sleep(8)
        name = driver.execute_script("""
            try {
                var h1 = document.querySelector('h1');
                if (h1 && h1.textContent.trim().length > 1) return h1.textContent.trim();
                var spans = document.querySelectorAll('h1 span');
                for (var i = 0; i < spans.length; i++) {
                    var t = spans[i].textContent.trim();
                    if (t.length > 1) return t;
                }
                return null;
            } catch(e) { return null; }
        """)
        return (name or '').strip() or uid_or_url
    except:
        return uid_or_url

def add_fb_mention(driver, session, composer, name):
    """
    Type @+name chars in the composer via keyboard to trigger Facebook
    mention autocomplete, then click the first suggestion (blue mention).
    Returns True if a blue mention was inserted, False if plain text fallback.
    """
    from selenium.webdriver.common.keys import Keys
    try:
        session.log(f'Mentioning: {name[:20]}...')
        composer.click()
        time.sleep(0.5)
        composer.send_keys(' @')
        time.sleep(0.8)

        # Type first word of name (at most 6 chars) to trigger autocomplete
        query = name.split()[0][:6] if name.split() else name[:6]
        for ch in query:
            composer.send_keys(ch)
            time.sleep(0.15)
        time.sleep(3)

        # Try multiple selectors for the suggestion dropdown
        suggestion_selectors = [
            '[role="option"]',
            '[role="listbox"] [role="option"]',
            'ul[role="listbox"] li',
            '[data-testid="typeahead-item"]',
            '[class*="mention"] li',
        ]
        clicked = False
        for sel in suggestion_selectors:
            try:
                opts = driver.find_elements(By.CSS_SELECTOR, sel)
                if opts:
                    opts[0].click()
                    time.sleep(0.8)
                    session.log(f'✅ Blue mention added: {name[:15]}')
                    clicked = True
                    break
            except:
                continue

        if not clicked:
            # Also try clicking via JS on any visible suggestion item
            clicked = driver.execute_script("""
                var opts = document.querySelectorAll('[role="option"],[data-testid="typeahead-item"]');
                if (opts.length > 0) { opts[0].click(); return true; }
                return false;
            """)
            if clicked:
                session.log(f'✅ Blue mention added (JS): {name[:15]}')
                time.sleep(0.8)

        if not clicked:
            # Fallback: type rest of name and leave as plain text
            rest = name.split()[0][6:] if len(name.split()[0]) > 6 else ''
            if rest:
                composer.send_keys(rest)
            session.log(f'⚠️ No dropdown - plain text fallback: @{name[:15]}')
        return clicked
    except Exception as e:
        session.log(f'Mention error: {str(e)[:35]}')
        return False

def save_uploaded_images(uploaded_files, session_id):
    d = os.path.join(TEMP_IMAGES_DIR, session_id)
    os.makedirs(d, exist_ok=True)
    paths = []
    for i, f in enumerate(uploaded_files):
        ext = Path(f.name).suffix or '.jpg'
        path = os.path.abspath(os.path.join(d, f"{i:03d}{ext}"))
        with open(path, 'wb') as fp:
            fp.write(f.read())
        paths.append(path)
    return paths

def find_post_composer(driver, session):
    session.log('Going to home feed...')
    driver.get('https://www.facebook.com/')
    time.sleep(12)
    
    try:
        driver.execute_script("window.scrollTo(0, 200);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
    except:
        pass
    
    session.log('Looking for composer button...')
    clicked = driver.execute_script("""
        var all = document.querySelectorAll('[role="button"]');
        for (var i = 0; i < all.length; i++) {
            var t = (all[i].textContent || all[i].getAttribute('aria-label') || '').toLowerCase();
            if ((t.includes('what') && t.includes('mind')) ||
                 t.includes('write something') || t.includes('create post')) {
                all[i].click(); return true;
            }
        }
        return false;
    """)
    
    if not clicked:
        for sel in [
            'div[aria-label*="mind" i]',
            'div[aria-label*="Write something" i]',
            'div[aria-label*="Create post" i]',
            'div[aria-label*="on your mind" i]',
        ]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    elems[0].click()
                    clicked = True
                    break
            except:
                pass
    
    if clicked:
        session.log('Composer opened, waiting...')
        time.sleep(5)
    else:
        session.log('Composer button not found, trying direct textbox...')
    
    selectors = [
        'div[role="dialog"] div[contenteditable="true"][role="textbox"]',
        'div[role="dialog"] div[contenteditable="true"]',
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[contenteditable="true"][spellcheck="true"]',
        '[role="textbox"][contenteditable="true"]',
        '[contenteditable="true"]',
    ]
    for idx, selector in enumerate(selectors):
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                try:
                    is_editable = driver.execute_script("""
                        return arguments[0].contentEditable === 'true' || 
                               arguments[0].tagName === 'TEXTAREA' || 
                               arguments[0].tagName === 'INPUT';
                    """, element)
                    if is_editable:
                        try:
                            element.click()
                            time.sleep(0.5)
                        except:
                            pass
                        session.log(f'Composer textbox found (selector #{idx+1})')
                        return element
                except:
                    continue
        except:
            continue
    return None

def attach_image(driver, session, img_abs_path):
    session.log(f'Attaching: {Path(img_abs_path).name}')
    try:
        driver.execute_script("""
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.display = 'block';
                el.style.visibility = 'visible';
                el.style.opacity = '1';
                el.style.position = 'fixed';
                el.style.top = '0'; el.style.left = '0';
            });
        """)
        time.sleep(1)
        inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
        if inputs:
            inputs[0].send_keys(img_abs_path)
            time.sleep(6)
            session.log('Image attached!')
            return True
        for sel in ['div[aria-label*="Photo" i]', 'div[aria-label*="photo" i]']:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            if btns:
                try:
                    btns[0].click()
                    time.sleep(3)
                    inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                    if inputs:
                        inputs[0].send_keys(img_abs_path)
                        time.sleep(6)
                        session.log('Image attached via photo button!')
                        return True
                except:
                    pass
        session.log('File input not found, posting without image.')
        return False
    except Exception as e:
        session.log(f'Image error: {str(e)[:40]}')
        return False

def click_post_button(driver, session):
    session.log('Clicking POST...')
    clicked = driver.execute_script("""
        var all = document.querySelectorAll('[role="button"]');
        for (var i = 0; i < all.length; i++) {
            var t = (all[i].textContent || all[i].getAttribute('aria-label') || '').trim().toLowerCase();
            if (t === 'post' || t === 'share now' || t === 'publish' || t === 'share') {
                all[i].click(); return true;
            }
        }
        return false;
    """)
    if clicked:
        time.sleep(5)
        session.log('Post submitted!')
        return True
    for sel in ['div[aria-label="Post"][role="button"]', 'button[type="submit"]']:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                elems[0].click()
                time.sleep(5)
                session.log('Post submitted (fallback)!')
                return True
        except:
            pass
    session.log('POST button not found!')
    return False

def run_post_session(session, cookies, text_lines, prefix, mention_uids_raw, image_paths, delay):
    retries = 0
    driver = None
    fb_id = extract_fb_profile_name(cookies)
    mention_names = {}  # uid_or_url → display name (fetched once)
    
    while session.running and retries < 10:
        try:
            if driver is None:
                driver = setup_browser(session)
                session.driver = driver
            
            session.log('Navigating to Facebook...')
            driver.get('https://www.facebook.com/')
            time.sleep(8)
            
            if cookies:
                session.log('Adding cookies...')
                for c in cookies.split(';'):
                    c = c.strip()
                    if c and '=' in c:
                        i = c.find('=')
                        try:
                            driver.add_cookie({'name': c[:i].strip(), 'value': c[i+1:].strip(), 'domain': '.facebook.com', 'path': '/'})
                        except:
                            pass
            
            profile_name = fetch_profile_name_from_fb(driver, fb_id)
            session.profile_id = f"📌{profile_name}"
            session.log(f'Profile: {profile_name}')
            
            # Fetch display names for all mention UIDs once (per browser session)
            if mention_uids_raw and not mention_names:
                session.log(f'Fetching names for {len(mention_uids_raw)} mention UID(s)...')
                for uid_raw in mention_uids_raw:
                    uid_raw = uid_raw.strip()
                    if not uid_raw:
                        continue
                    name = get_uid_display_name(driver, uid_raw)
                    mention_names[uid_raw] = name
                    session.log(f'UID {uid_raw[:15]} → {name[:20]}')
                # Go back to home after fetching names
                driver.get('https://www.facebook.com/')
                time.sleep(6)
            
            session.log('ID Online - Browser Active!')
            
            not_found_count = 0
            while session.running:
                try:
                    line = text_lines[session.idx % len(text_lines)] if text_lines else ''
                    session.idx += 1

                    # Build post text WITHOUT mentions (mentions added via keyboard below)
                    parts = []
                    if prefix.strip():
                        parts.append(prefix.strip())
                    if line.strip():
                        parts.append(line.strip())
                    post_text = ' '.join(parts)
                    
                    session.log(f'Post #{session.count+1}...')
                    
                    composer = find_post_composer(driver, session)
                    
                    if not composer:
                        not_found_count += 1
                        if not_found_count >= 3:
                            session.log('❌ Composer not found 3x - stopping')
                            session.running = False
                            break
                        session.log(f'Composer not found ({not_found_count}/3), refreshing...')
                        driver.get(driver.current_url)
                        time.sleep(15)
                        continue
                    
                    not_found_count = 0
                    
                    # Type prefix + post line via JS
                    if post_text.strip():
                        session.log(f'Typing: {post_text[:25]}...')
                        driver.execute_script("""
                            const element = arguments[0];
                            const message = arguments[1];
                            element.scrollIntoView({behavior: 'smooth', block: 'center'});
                            element.focus();
                            element.click();
                            if (element.tagName === 'DIV') {
                                element.textContent = message;
                                element.innerHTML = message;
                            } else {
                                element.value = message;
                            }
                            element.dispatchEvent(new Event('input', { bubbles: true }));
                            element.dispatchEvent(new Event('change', { bubbles: true }));
                            element.dispatchEvent(new InputEvent('input', { bubbles: true, data: message }));
                        """, composer, post_text)
                        time.sleep(1)
                    
                    # Add blue mentions via keyboard (one by one)
                    for uid_raw, name in mention_names.items():
                        add_fb_mention(driver, session, composer, name)
                    
                    time.sleep(1)
                    
                    if image_paths:
                        img = image_paths[session.img_idx % len(image_paths)]
                        session.img_idx += 1
                        attach_image(driver, session, img)
                        time.sleep(2)
                    
                    ok = click_post_button(driver, session)
                    if ok:
                        session.count += 1
                        manager.update_count(session.id, session.count)
                        session.log(f'✅ Post #{session.count} done!')
                        retries = 0
                    else:
                        session.log('Submit may have failed, closing composer...')
                        try:
                            driver.execute_script(
                                "var c=document.querySelector('[aria-label=\"Close\"]');if(c)c.click();")
                        except:
                            pass
                        time.sleep(5)
                    
                    session.log(f'Waiting {delay}s...')
                    for i in range(int(delay)):
                        if not session.running:
                            break
                        if i > 0 and i % 20 == 0:
                            simulate_human(driver)
                        time.sleep(1)
                    
                    if session.count % 3 == 0:
                        gc.collect()
                        try:
                            driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
                        except:
                            pass
                    
                except Exception as e:
                    err = str(e)[:50]
                    session.log(f'Error: {err}')
                    if 'session' in err.lower() or 'disconnect' in err.lower():
                        session.log('Restarting browser...')
                        try: driver.quit()
                        except: pass
                        driver = None
                        mention_names = {}  # re-fetch names on new browser
                        retries += 1
                        time.sleep(5)
                        break
                    time.sleep(10)
                    
        except Exception as e:
            session.log(f'Fatal: {str(e)[:50]}')
            retries += 1
            try: driver.quit()
            except: pass
            driver = None
            mention_names = {}
            time.sleep(10)
    
    session.running = False
    session.log('Stopped.')
    manager._save_registry()
    if driver:
        try: driver.quit()
        except: pass
    gc.collect()

def start_post_session(session, cookies, text_lines, prefix, mention_ids_raw, image_paths, delay):
    session.running = True
    session.logs = deque(maxlen=MAX_LOGS)
    session.count = 0
    session.idx = 0
    session.img_idx = 0
    session.start_time = time.strftime("%H:%M:%S")
    
    try:
        open(f"{LOGS_DIR}/{session.id}.log", 'w').close()
    except:
        pass
    
    session.log(f'Session {session.id} starting (auto-post)...')
    manager._save_registry()
    
    # Pass raw UIDs/URLs directly — run_post_session will fetch display names
    clean_uids = [m.strip().lstrip('@') for m in mention_ids_raw if m.strip()]
    
    threading.Thread(
        target=run_post_session,
        args=(session, cookies, text_lines, prefix, clean_uids, image_paths, delay),
        daemon=True
    ).start()

# =============================================================================
# UI — original comment UI inside Tab 1, new post UI in Tab 2
# =============================================================================

st.markdown('<div class="main-header"><h1>FB Comment Tool</h1></div>', unsafe_allow_html=True)

all_sessions = manager.get_all_sessions()
active_sessions = manager.get_active_sessions()
total_comments = sum(s.count for s in all_sessions)

col1, col2, col3 = st.columns(3)
col1.metric("Total Comments", total_comments)
col2.metric("Active Sessions", len(active_sessions))
with col3:
    if st.button("+ New Session"):
        manager.create_session('comment')
        st.rerun()

if 'view_session' not in st.session_state:
    st.session_state.view_session = None

st.markdown("---")

if st.session_state.view_session:
    sid = st.session_state.view_session
    session = manager.get_session(sid)
    
    st.markdown(f"### Viewing Session: `{sid}`")
    
    if session:
        if session.running:
            st.markdown(f'<div class="status-running"><span class="online-indicator"></span>RUNNING - {session.count} comments (ID: {session.profile_id if session.profile_id else "..."})</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-stopped">STOPPED</div>', unsafe_allow_html=True)
        
        logs = manager.get_logs(sid, 25)
        if logs:
            logs_html = '<div class="console-box">'
            for log in logs:
                logs_html += f'<div class="log-line">{log.strip()}</div>'
            logs_html += '</div>'
            st.markdown(logs_html, unsafe_allow_html=True)
        else:
            st.markdown('<div class="console-box">No logs yet</div>', unsafe_allow_html=True)
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("STOP Session", disabled=not session.running):
                manager.stop_session(sid)
                st.rerun()
        with c2:
            if st.button("Delete Session"):
                manager.delete_session(sid)
                st.session_state.view_session = None
                st.rerun()
        with c3:
            if st.button("Refresh Logs"):
                st.rerun()
        with c4:
            if st.button("Back"):
                st.session_state.view_session = None
                st.rerun()
    else:
        st.error("Session not found")
        if st.button("Back"):
            st.session_state.view_session = None
            st.rerun()

else:
    tab1, tab2 = st.tabs(["💬 Auto Comment", "📸 Auto Post"])

    # ── Tab 1: original comment UI — exact same as original ───────────────────
    with tab1:
        st.markdown("### Start New Automation")
        
        c1, c2 = st.columns(2)
        with c1:
            post_id = st.text_input("Post ID/URL", placeholder="https://facebook.com/...")
            prefix = st.text_input("Prefix (optional)", placeholder="@username")
            delay = st.number_input("Delay (seconds)", 10, 3600, 30)
        with c2:
            cookies = st.text_area("Cookies", height=100, placeholder="Paste cookies here...")
        
        uploaded = st.file_uploader("Upload Comments TXT", type=['txt'])
        if uploaded:
            comments = uploaded.read().decode('utf-8')
        else:
            comments = st.text_area("Comments (one per line)", height=70, placeholder="Nice!\nGreat post!")
        
        if st.button("START NEW SESSION", use_container_width=True):
            if not cookies:
                st.error("Add cookies!")
            elif not post_id:
                st.error("Add Post ID!")
            elif not comments:
                st.error("Add comments!")
            else:
                new_session = manager.create_session('comment')
                start_session(new_session, post_id, cookies, comments, prefix, delay)
                st.success(f"Session Started! ID: {new_session.id}")
                time.sleep(1)
                st.rerun()

    # ── Tab 2: new auto-post UI ───────────────────────────────────────────────
    with tab2:
        st.markdown("### Auto Post on Your Profile")

        p1, p2 = st.columns(2)
        with p1:
            prefix_p = st.text_input("Prefix (optional)", placeholder="e.g. 🔥 Check this!", key="post_prefix")
            delay_p = st.number_input("Delay Between Posts (seconds)", 30, 7200, 120, key="post_delay")
        with p2:
            cookies_p = st.text_area("Cookies", height=100, placeholder="Paste cookies here...", key="post_cookies")

        mention_raw = st.text_area(
            "Mention IDs/UIDs (one per line)",
            height=70,
            placeholder="123456789\n@friend.name\nhttps://facebook.com/username",
            key="post_mention"
        )

        uploaded_txt = st.file_uploader("Upload Post Text TXT (one line = one post)", type=['txt'], key="post_txt")
        text_lines = []
        if uploaded_txt:
            raw = uploaded_txt.read().decode('utf-8')
            text_lines = [l.strip() for l in raw.splitlines() if l.strip()]
            st.success(f"Loaded {len(text_lines)} post lines")
        else:
            manual_txt = st.text_area("Post Lines (one line = one post)", height=70,
                                      placeholder="First post text\nSecond post text", key="post_manual")
            if manual_txt.strip():
                text_lines = [l.strip() for l in manual_txt.splitlines() if l.strip()]

        uploaded_imgs = st.file_uploader(
            "Upload Images (cycle: img1→post1, img2→post2 ...)",
            type=['jpg', 'jpeg', 'png', 'gif', 'webp'],
            accept_multiple_files=True,
            key="post_imgs"
        )
        if uploaded_imgs:
            st.info(f"✅ {len(uploaded_imgs)} image(s) loaded")
            pcols = st.columns(min(len(uploaded_imgs), 5))
            for i, img in enumerate(uploaded_imgs[:5]):
                with pcols[i]:
                    st.image(img, width=70, caption=f"#{i+1}")

        mention_ids_raw = [m.strip() for m in mention_raw.splitlines() if m.strip()]
        preview_parts = []
        if prefix_p.strip(): preview_parts.append(prefix_p.strip())
        for m in mention_ids_raw:
            preview_parts.append(m if m.startswith('http') else f'@{m.lstrip("@")}')
        preview_parts.append(text_lines[0] if text_lines else "(no text yet)")
        st.markdown("**First post preview:**")
        st.code(' '.join(preview_parts)[:200], language=None)

        if st.button("START AUTO POST SESSION", use_container_width=True, key="btn_post"):
            if not cookies_p.strip():
                st.error("Add cookies!")
            elif not text_lines:
                st.error("Add post text (TXT file or manual)!")
            else:
                new_session = manager.create_session('post')
                img_paths = []
                if uploaded_imgs:
                    img_paths = save_uploaded_images(uploaded_imgs, new_session.id)
                start_post_session(new_session, cookies_p, text_lines, prefix_p,
                                   mention_ids_raw, img_paths, delay_p)
                st.success(f"Auto-Post Session Started! ID: {new_session.id}")
                time.sleep(1)
                st.rerun()

st.markdown("---")
st.markdown("### Active Sessions")

active = manager.get_active_sessions()
if active:
    st.markdown('<div class="active-sessions">', unsafe_allow_html=True)
    for s in active:
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            st.code(s.id, language=None)
        with col2:
            st.write(f"Comments: {s.count}")
        with col3:
            if st.button("View", key=f"view_{s.id}"):
                st.session_state.view_session = s.id
                st.rerun()
        with col4:
            if st.button("Stop", key=f"stop_{s.id}"):
                manager.stop_session(s.id)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("No active sessions")

stopped = [s for s in all_sessions if not s.running and s.count >= 0]
if stopped:
    with st.expander("Stopped Sessions"):
        for s in stopped[-10:]:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.code(s.id, language=None)
            with col2:
                st.write(f"Comments: {s.count}")
            with col3:
                if st.button("Logs", key=f"logs_{s.id}"):
                    st.session_state.view_session = s.id
                    st.rerun()
            with col4:
                if st.button("Delete", key=f"del_{s.id}"):
                    manager.delete_session(s.id)
                    st.rerun()

st.markdown("---")
st.markdown("### Session ID Lookup")
lookup_id = st.text_input("Enter Session ID to view:", placeholder="XXXXXXXX")
if lookup_id and st.button("Find Session"):
    if manager.get_session(lookup_id.upper()):
        st.session_state.view_session = lookup_id.upper()
        st.rerun()
    else:
        st.error("Session not found")
