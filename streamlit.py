import streamlit as st
import time
import threading
import gc
import json
import os
import uuid
import random
import shutil
from pathlib import Path
from collections import deque
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

# ═════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="FB & Messenger Tools",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═════════════════════════════════════════════════════════════════════════════
# CSS + KEEP-ALIVE
# ═════════════════════════════════════════════════════════════════════════════
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
    background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #667eea);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-size: 1.8rem; font-weight: 700; margin: 0;
}
.stButton>button {
    background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
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
    background: rgba(0,0,0,0.6); border: 1px solid rgba(78,205,196,0.5);
    border-radius: 8px; padding: 10px; font-family: 'Courier New', monospace;
    font-size: 11px; color: #00ff88; max-height: 220px; overflow-y: auto; min-height: 80px;
}
.log-line { padding: 3px 6px; border-left: 2px solid #4ecdc4; margin: 2px 0; background: rgba(0,0,0,0.3); }
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
[data-testid="stMetricValue"] { color: #4ecdc4; font-weight: 700; }
.result-box {
    background: rgba(0,0,0,0.5); border: 1px solid rgba(78,205,196,0.4);
    border-radius: 8px; padding: 12px; margin-top: 10px;
}
.result-row {
    background: rgba(255,255,255,0.07); border-radius: 6px;
    padding: 8px 12px; margin: 4px 0; color: white; font-size: 13px;
}
</style>
<script>
    setInterval(function(){fetch(window.location.href,{method:'HEAD'}).catch(function(){});},25000);
    setInterval(function(){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:Math.random()*200,clientY:Math.random()*200}));},60000);
</script>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# CONSTANTS & DIRS
# ═════════════════════════════════════════════════════════════════════════════
SESSIONS_FILE  = "sessions_registry.json"
LOGS_DIR       = "session_logs"
TEMP_IMAGES_DIR = "temp_images"
MAX_LOGS       = 50

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_IMAGES_DIR, exist_ok=True)

# ═════════════════════════════════════════════════════════════════════════════
# SESSION MODEL
# ═════════════════════════════════════════════════════════════════════════════
class Session:
    __slots__ = ['id','running','count','logs','idx','driver',
                 'start_time','profile_id','img_idx','session_type']

    def __init__(self, sid, session_type='comment'):
        self.id           = sid
        self.running      = False
        self.count        = 0
        self.logs         = deque(maxlen=MAX_LOGS)
        self.idx          = 0
        self.img_idx      = 0
        self.driver       = None
        self.start_time   = None
        self.profile_id   = None
        self.session_type = session_type

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        pid = f" {self.profile_id}" if self.profile_id else ""
        entry = f"[{ts}]{pid} {msg}"
        self.logs.append(entry)
        try:
            with open(f"{LOGS_DIR}/{self.id}.log", "a") as f:
                f.write(entry + "\n")
        except:
            pass


# ═════════════════════════════════════════════════════════════════════════════
# SESSION MANAGER
# ═════════════════════════════════════════════════════════════════════════════
class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()
        self._load_registry()

    def _load_registry(self):
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE) as f:
                    data = json.load(f)
                for sid, info in data.items():
                    if sid not in self.sessions:
                        s = Session(sid, info.get('session_type', 'comment'))
                        s.count      = info.get('count', 0)
                        s.running    = False
                        s.start_time = info.get('start_time')
                        self.sessions[sid] = s
            except:
                pass

    def _save_registry(self):
        try:
            data = {sid: {'count': s.count, 'running': s.running,
                          'start_time': s.start_time, 'session_type': s.session_type}
                    for sid, s in self.sessions.items()}
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
                try: s.driver.quit()
                except: pass
                s.driver = None
            self._save_registry()

    def delete_session(self, sid):
        with self.lock:
            s = self.sessions.get(sid)
            if s:
                s.running = False
                if s.driver:
                    try: s.driver.quit()
                    except: pass
                    s.driver = None
                del self.sessions[sid]
                try: os.remove(f"{LOGS_DIR}/{sid}.log")
                except: pass
                self._save_registry()
                gc.collect()

    def get_logs(self, sid, limit=35):
        log_file = f"{LOGS_DIR}/{sid}.log"
        if os.path.exists(log_file):
            try:
                with open(log_file) as f:
                    return f.readlines()[-limit:]
            except:
                pass
        s = self.sessions.get(sid)
        return list(s.logs)[-limit:] if s else []

    def update_count(self, sid, count):
        s = self.sessions.get(sid)
        if s:
            s.count = count
            self._save_registry()


@st.cache_resource
def get_manager():
    return SessionManager()

manager = get_manager()

# ═════════════════════════════════════════════════════════════════════════════
# BROWSER SETUP  (identical to working original)
# ═════════════════════════════════════════════════════════════════════════════
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
    opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/121.0.0.0 Safari/537.36')

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
    driver = webdriver.Chrome(service=Service(drv_path), options=opts) \
             if drv_path else webdriver.Chrome(options=opts)
    driver.set_window_size(1920, 1080)
    session.log('Browser ready!')
    return driver


# ═════════════════════════════════════════════════════════════════════════════
# FACEBOOK HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def extract_fb_profile_name(cookies):
    try:
        for c in cookies.split(';'):
            c = c.strip()
            if c and '=' in c:
                i = c.find('=')
                k, v = c[:i].strip(), c[i+1:].strip()
                if k == 'c_user': return v
                if k == 'uid':    return v
    except:
        pass
    return "Unknown"


def fetch_profile_name_from_fb(driver, c_user_id):
    try:
        driver.get(f'https://www.facebook.com/{c_user_id}')
        time.sleep(8)
        name = driver.execute_script("""
            try {
                var h1 = document.querySelector('h1');
                if (h1) { var t = h1.textContent.trim(); if (t.length>1) return t; }
                var sp = document.evaluate("//h1/span",document,null,
                         XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;
                if (sp) return sp.textContent.trim();
            } catch(e) {}
            return 'Unknown';
        """)
        return (name or 'Unknown').strip()
    except:
        return 'Unknown'


def add_fb_cookies(driver, cookies):
    for c in cookies.split(';'):
        c = c.strip()
        if c and '=' in c:
            i = c.find('=')
            try:
                driver.add_cookie({'name': c[:i].strip(), 'value': c[i+1:].strip(),
                                   'domain': '.facebook.com', 'path': '/'})
            except:
                pass


def simulate_human(driver):
    try:
        driver.execute_script("""
            window.scrollBy(0, Math.random()*200-100);
            document.dispatchEvent(new MouseEvent('mousemove',{
                bubbles:true,
                clientX:Math.random()*window.innerWidth,
                clientY:Math.random()*window.innerHeight
            }));
        """)
        if random.random() > 0.9:
            driver.execute_script("fetch('/home').catch(()=>{});")
    except:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# MESSENGER HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def login_messenger(driver, session, cookies):
    session.log('Opening Messenger...')
    driver.get('https://www.messenger.com/')
    time.sleep(8)
    if cookies:
        session.log('Adding cookies...')
        for c in cookies.split(';'):
            c = c.strip()
            if not c or '=' not in c: continue
            i = c.find('=')
            n, v = c[:i].strip(), c[i+1:].strip()
            for domain in ['.messenger.com', '.facebook.com']:
                try:
                    driver.add_cookie({'name': n, 'value': v, 'domain': domain, 'path': '/'})
                except:
                    pass
    driver.get('https://www.messenger.com/')
    time.sleep(10)
    session.log('Messenger loaded!')


def open_thread(driver, session, uid, e2e=False):
    if uid.startswith('http'):
        driver.get(uid)
    elif e2e:
        driver.get(f'https://www.messenger.com/e2ee/t/{uid}')
    else:
        driver.get(f'https://www.messenger.com/t/{uid}')
    time.sleep(10)
    session.log(f'Thread opened: {uid}')


# ═════════════════════════════════════════════════════════════════════════════
# ── TAB 1: AUTO COMMENT ──────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════
def find_comment_input(driver, session):
    session.log('Finding comment input...')
    time.sleep(10)
    try:
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0,0);")
        time.sleep(2)
    except:
        pass
    selectors = [
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[aria-label*="comment" i][contenteditable="true"]',
        'div[aria-label*="Write a comment" i][contenteditable="true"]',
        'div[contenteditable="true"][spellcheck="true"]',
        '[role="textbox"][contenteditable="true"]',
        '[contenteditable="true"]',
    ]
    for idx, sel in enumerate(selectors):
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    ok = driver.execute_script(
                        "return arguments[0].contentEditable==='true'||"
                        "arguments[0].tagName==='TEXTAREA'||"
                        "arguments[0].tagName==='INPUT';", el)
                    if ok:
                        try: el.click()
                        except: pass
                        time.sleep(0.3)
                        session.log(f'Comment input found (sel #{idx+1})')
                        return el
                except:
                    continue
        except:
            continue
    return None


def run_comment_session(session, post_id, cookies, comments_list, prefix, delay):
    retries = 0
    driver  = None
    fb_id   = extract_fb_profile_name(cookies)

    while session.running and retries < 10:
        try:
            if driver is None:
                driver = setup_browser(session)
                session.driver = driver
            session.log('Navigating to Facebook...')
            driver.get('https://www.facebook.com/')
            time.sleep(8)
            add_fb_cookies(driver, cookies)
            profile_name = fetch_profile_name_from_fb(driver, fb_id)
            session.profile_id = f"📌{profile_name}"
            session.log(f'Profile: {profile_name}')
            session.log('Opening post...')
            driver.get(post_id if post_id.startswith('http')
                       else f'https://www.facebook.com/{post_id}')
            time.sleep(15)
            session.log('ID Online - Browser Active!')
            miss = 0
            while session.running:
                try:
                    inp = find_comment_input(driver, session)
                    if not inp:
                        miss += 1
                        if miss >= 3:
                            session.log('❌ Input not found 3x — stopping')
                            session.running = False; break
                        session.log(f'Input not found ({miss}/3), refreshing...')
                        driver.get(driver.current_url); time.sleep(15); continue
                    miss = 0
                    base = comments_list[session.idx % len(comments_list)]
                    session.idx += 1
                    text = f"{prefix} {base}".strip() if prefix else base
                    session.log(f'Typing: {text[:25]}...')
                    driver.execute_script("""
                        var el=arguments[0], msg=arguments[1];
                        el.scrollIntoView({behavior:'smooth',block:'center'});
                        el.focus(); el.click();
                        if(el.tagName==='DIV'){el.textContent=msg;el.innerHTML=msg;}
                        else el.value=msg;
                        el.dispatchEvent(new Event('input',{bubbles:true}));
                        el.dispatchEvent(new Event('change',{bubbles:true}));
                        el.dispatchEvent(new InputEvent('input',{bubbles:true,data:msg}));
                    """, inp, text)
                    time.sleep(1)
                    session.log('Sending...')
                    driver.execute_script("""
                        var el=arguments[0]; el.focus();
                        ['keydown','keypress','keyup'].forEach(function(t){
                            el.dispatchEvent(new KeyboardEvent(t,{
                                key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
                        });
                    """, inp)
                    time.sleep(1)
                    session.count += 1
                    manager.update_count(session.id, session.count)
                    session.log(f'✅ Comment #{session.count} sent!')
                    retries = 0
                    jd = max(10, int(delay + random.uniform(-10, 10)))
                    session.log(f'Waiting {jd}s...')
                    for i in range(jd):
                        if not session.running: break
                        if i and i % 15 == 0: simulate_human(driver)
                        time.sleep(1)
                    if session.count % 2 == 0:
                        gc.collect()
                        try: driver.execute_script("window.localStorage.clear();window.sessionStorage.clear();")
                        except: pass
                except Exception as e:
                    err = str(e)[:50]
                    session.log(f'Error: {err}')
                    if 'session' in err.lower() or 'disconnect' in err.lower():
                        session.log('Restarting browser...')
                        try: driver.quit()
                        except: pass
                        driver = None; retries += 1; time.sleep(5); break
                    time.sleep(10)
        except Exception as e:
            session.log(f'Fatal: {str(e)[:50]}')
            retries += 1
            try: driver.quit()
            except: pass
            driver = None; time.sleep(10)

    session.running = False
    session.log('Stopped.')
    manager._save_registry()
    if driver:
        try: driver.quit()
        except: pass
    gc.collect()


def start_comment_session(session, post_id, cookies, comments, prefix, delay):
    session.running = True
    session.logs    = deque(maxlen=MAX_LOGS)
    session.count   = 0
    session.idx     = 0
    session.start_time = time.strftime("%H:%M:%S")
    try: open(f"{LOGS_DIR}/{session.id}.log", 'w').close()
    except: pass
    session.log(f'Comment session {session.id} starting...')
    manager._save_registry()
    comments_list = [c.strip() for c in comments.split('\n') if c.strip()] or ['Nice!']
    threading.Thread(target=run_comment_session,
                     args=(session, post_id, cookies, comments_list, prefix, delay),
                     daemon=True).start()


# ═════════════════════════════════════════════════════════════════════════════
# ── TAB 2: AUTO POST ─────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════
def get_uid_display_name(driver, uid_or_url):
    try:
        if uid_or_url.startswith('http'):
            driver.get(uid_or_url)
        else:
            driver.get(f'https://www.facebook.com/profile.php?id={uid_or_url.lstrip("@")}')
        time.sleep(8)
        name = driver.execute_script("""
            var h1=document.querySelector('h1');
            if(h1&&h1.textContent.trim().length>1) return h1.textContent.trim();
            var spans=document.querySelectorAll('h1 span');
            for(var i=0;i<spans.length;i++){
                var t=spans[i].textContent.trim(); if(t.length>1) return t;
            }
            return null;
        """)
        return (name or '').strip() or uid_or_url
    except:
        return uid_or_url


def add_fb_mention(driver, session, composer, name):
    try:
        session.log(f'Mentioning: {name[:20]}...')
        composer.click(); time.sleep(0.5)
        composer.send_keys(' @'); time.sleep(0.8)
        query = name.split()[0][:6] if name.split() else name[:6]
        for ch in query:
            composer.send_keys(ch); time.sleep(0.15)
        time.sleep(3)
        for sel in ['[role="option"]','[role="listbox"] [role="option"]',
                    'ul[role="listbox"] li','[data-testid="typeahead-item"]']:
            try:
                opts = driver.find_elements(By.CSS_SELECTOR, sel)
                if opts:
                    opts[0].click(); time.sleep(0.8)
                    session.log(f'✅ Blue mention: {name[:15]}')
                    return True
            except:
                continue
        clicked = driver.execute_script(
            "var o=document.querySelectorAll('[role=\"option\"],[data-testid=\"typeahead-item\"]');"
            "if(o.length>0){o[0].click();return true;}return false;")
        if clicked:
            session.log(f'✅ Blue mention (JS): {name[:15]}')
            time.sleep(0.8); return True
        session.log(f'⚠️ Plain text fallback: @{name[:15]}')
        return False
    except Exception as e:
        session.log(f'Mention err: {str(e)[:30]}')
        return False


def save_uploaded_images(uploaded_files, session_id):
    d = os.path.join(TEMP_IMAGES_DIR, session_id)
    os.makedirs(d, exist_ok=True)
    paths = []
    for i, f in enumerate(uploaded_files):
        ext  = Path(f.name).suffix or '.jpg'
        path = os.path.abspath(os.path.join(d, f"{i:03d}{ext}"))
        with open(path, 'wb') as fp: fp.write(f.read())
        paths.append(path)
    return paths


def find_post_composer(driver, session):
    session.log('Going to home feed...')
    driver.get('https://www.facebook.com/')
    time.sleep(12)
    try:
        driver.execute_script("window.scrollTo(0,200);"); time.sleep(1)
        driver.execute_script("window.scrollTo(0,0);"); time.sleep(1)
    except: pass
    session.log('Looking for composer...')
    clicked = driver.execute_script("""
        var all=document.querySelectorAll('[role="button"]');
        for(var i=0;i<all.length;i++){
            var t=(all[i].textContent||all[i].getAttribute('aria-label')||'').toLowerCase();
            if((t.includes('what')&&t.includes('mind'))||
               t.includes('write something')||t.includes('create post')){
                all[i].click();return true;
            }
        }
        return false;
    """)
    if not clicked:
        for sel in ['div[aria-label*="mind" i]','div[aria-label*="Write something" i]',
                    'div[aria-label*="Create post" i]','div[aria-label*="on your mind" i]']:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                if elems: elems[0].click(); clicked = True; break
            except: pass
    if clicked:
        session.log('Composer opened!'); time.sleep(5)
    for sel in ['div[role="dialog"] div[contenteditable="true"][role="textbox"]',
                'div[role="dialog"] div[contenteditable="true"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[contenteditable="true"][data-lexical-editor="true"]',
                'div[contenteditable="true"][spellcheck="true"]',
                '[role="textbox"][contenteditable="true"]',
                '[contenteditable="true"]']:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    ok = driver.execute_script(
                        "return arguments[0].contentEditable==='true'||"
                        "arguments[0].tagName==='TEXTAREA'||"
                        "arguments[0].tagName==='INPUT';", el)
                    if ok:
                        try: el.click()
                        except: pass
                        time.sleep(0.4)
                        session.log('Composer textbox found!')
                        return el
                except: continue
        except: continue
    return None


def attach_image(driver, session, img_path):
    session.log(f'Attaching: {Path(img_path).name}')
    try:
        driver.execute_script("""
            document.querySelectorAll('input[type="file"]').forEach(function(el){
                el.style.display='block';el.style.visibility='visible';
                el.style.opacity='1';el.style.position='fixed';el.style.top='0';el.style.left='0';
            });
        """)
        time.sleep(1)
        inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
        if inputs:
            inputs[0].send_keys(img_path); time.sleep(6)
            session.log('Image attached!'); return True
        for sel in ['div[aria-label*="Photo" i]','div[aria-label*="photo" i]']:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            if btns:
                try:
                    btns[0].click(); time.sleep(3)
                    inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                    if inputs:
                        inputs[0].send_keys(img_path); time.sleep(6)
                        session.log('Image attached via photo btn!'); return True
                except: pass
        session.log('File input not found, skipping image.'); return False
    except Exception as e:
        session.log(f'Image err: {str(e)[:40]}'); return False


def click_post_button(driver, session):
    session.log('Clicking POST...')
    ok = driver.execute_script("""
        var all=document.querySelectorAll('[role="button"]');
        for(var i=0;i<all.length;i++){
            var t=(all[i].textContent||all[i].getAttribute('aria-label')||'').trim().toLowerCase();
            if(t==='post'||t==='share now'||t==='publish'||t==='share'){all[i].click();return true;}
        }
        return false;
    """)
    if ok:
        time.sleep(5); session.log('Post submitted!'); return True
    for sel in ['div[aria-label="Post"][role="button"]','button[type="submit"]']:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                elems[0].click(); time.sleep(5)
                session.log('Post submitted (fallback)!'); return True
        except: pass
    session.log('POST button not found!'); return False


def run_post_session(session, cookies, text_lines, prefix, mention_uids_raw, image_paths, delay):
    retries = 0; driver = None
    fb_id   = extract_fb_profile_name(cookies)
    mention_names = {}

    while session.running and retries < 10:
        try:
            if driver is None:
                driver = setup_browser(session)
                session.driver = driver
            session.log('Navigating to Facebook...')
            driver.get('https://www.facebook.com/'); time.sleep(8)
            add_fb_cookies(driver, cookies)
            profile_name = fetch_profile_name_from_fb(driver, fb_id)
            session.profile_id = f"📌{profile_name}"
            session.log(f'Profile: {profile_name}')
            if mention_uids_raw and not mention_names:
                session.log(f'Fetching names for {len(mention_uids_raw)} UIDs...')
                for uid in mention_uids_raw:
                    if not uid: continue
                    name = get_uid_display_name(driver, uid)
                    mention_names[uid] = name
                    session.log(f'UID {uid[:15]} → {name[:20]}')
                driver.get('https://www.facebook.com/'); time.sleep(6)
            session.log('ID Online - Browser Active!')
            miss = 0
            while session.running:
                try:
                    line = text_lines[session.idx % len(text_lines)] if text_lines else ''
                    session.idx += 1
                    parts = []
                    if prefix.strip(): parts.append(prefix.strip())
                    if line.strip():   parts.append(line.strip())
                    post_text = ' '.join(parts)
                    session.log(f'Post #{session.count+1}...')
                    composer = find_post_composer(driver, session)
                    if not composer:
                        miss += 1
                        if miss >= 3:
                            session.log('❌ Composer not found 3x — stopping')
                            session.running = False; break
                        session.log(f'Composer not found ({miss}/3), refreshing...')
                        driver.get(driver.current_url); time.sleep(15); continue
                    miss = 0
                    if post_text.strip():
                        session.log(f'Typing: {post_text[:25]}...')
                        driver.execute_script("""
                            var el=arguments[0],msg=arguments[1];
                            el.scrollIntoView({behavior:'smooth',block:'center'});
                            el.focus();el.click();
                            if(el.tagName==='DIV'){el.textContent=msg;el.innerHTML=msg;}
                            else el.value=msg;
                            el.dispatchEvent(new Event('input',{bubbles:true}));
                            el.dispatchEvent(new Event('change',{bubbles:true}));
                            el.dispatchEvent(new InputEvent('input',{bubbles:true,data:msg}));
                        """, composer, post_text)
                        time.sleep(1)
                    for uid, name in mention_names.items():
                        add_fb_mention(driver, session, composer, name)
                    time.sleep(1)
                    if image_paths:
                        img = image_paths[session.img_idx % len(image_paths)]
                        session.img_idx += 1
                        attach_image(driver, session, img); time.sleep(2)
                    ok = click_post_button(driver, session)
                    if ok:
                        session.count += 1
                        manager.update_count(session.id, session.count)
                        session.log(f'✅ Post #{session.count} done!')
                        retries = 0
                    else:
                        try: driver.execute_script(
                            "var c=document.querySelector('[aria-label=\"Close\"]');if(c)c.click();")
                        except: pass
                        time.sleep(5)
                    session.log(f'Waiting {delay}s...')
                    for i in range(int(delay)):
                        if not session.running: break
                        if i and i % 20 == 0: simulate_human(driver)
                        time.sleep(1)
                    if session.count % 3 == 0:
                        gc.collect()
                        try: driver.execute_script("window.localStorage.clear();window.sessionStorage.clear();")
                        except: pass
                except Exception as e:
                    err = str(e)[:50]; session.log(f'Error: {err}')
                    if 'session' in err.lower() or 'disconnect' in err.lower():
                        session.log('Restarting browser...')
                        try: driver.quit()
                        except: pass
                        driver = None; mention_names = {}; retries += 1; time.sleep(5); break
                    time.sleep(10)
        except Exception as e:
            session.log(f'Fatal: {str(e)[:50]}'); retries += 1
            try: driver.quit()
            except: pass
            driver = None; mention_names = {}; time.sleep(10)

    session.running = False; session.log('Stopped.')
    manager._save_registry()
    if driver:
        try: driver.quit()
        except: pass
    gc.collect()


def start_post_session(session, cookies, text_lines, prefix, mention_ids_raw, image_paths, delay):
    session.running = True; session.logs = deque(maxlen=MAX_LOGS)
    session.count = 0; session.idx = 0; session.img_idx = 0
    session.start_time = time.strftime("%H:%M:%S")
    try: open(f"{LOGS_DIR}/{session.id}.log", 'w').close()
    except: pass
    session.log(f'Post session {session.id} starting...')
    manager._save_registry()
    clean_uids = [m.strip().lstrip('@') for m in mention_ids_raw if m.strip()]
    threading.Thread(target=run_post_session,
                     args=(session, cookies, text_lines, prefix, clean_uids, image_paths, delay),
                     daemon=True).start()


# ═════════════════════════════════════════════════════════════════════════════
# ── TAB 3: SMART LOCK ────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════
def get_current_group_name(driver):
    name = driver.execute_script("""
        var sels=['h1','h2','h4','[data-testid="thread-title-text"]',
                  '[data-testid="thread-title"]',
                  'div[role="main"] header span','header span[dir="auto"]'];
        for(var i=0;i<sels.length;i++){
            var el=document.querySelector(sels[i]);
            if(el){var t=el.textContent.trim();if(t.length>1&&t!=='Messenger')return t;}
        }
        var t=document.title.split('|')[0].trim().split('-')[0].trim();
        return(t&&t!=='Messenger'&&t.length>1)?t:null;
    """)
    return (name or '').strip() or None


def restore_group_name(driver, session, target_name):
    session.log(f'Restoring name → "{target_name}"')
    driver.execute_script("""
        var labels=['Customize chat','Chat info','More','Settings','Group info','Edit'];
        var btns=document.querySelectorAll('[role="button"],[aria-label]');
        for(var b of btns){
            var lbl=(b.getAttribute('aria-label')||b.textContent||'').toLowerCase();
            for(var l of labels){if(lbl.includes(l.toLowerCase())){b.click();return true;}}
        }
        return false;
    """)
    time.sleep(3)
    driver.execute_script("""
        var kw=['edit group name','change name','group name','rename'];
        var all=document.querySelectorAll('[role="button"],[role="menuitem"],div,span,button');
        for(var el of all){
            var t=(el.textContent||'').toLowerCase().trim();
            for(var k of kw){if(t===k||t.includes(k)){el.click();return true;}}
        }
        return false;
    """)
    time.sleep(2)
    for inp in driver.find_elements(By.CSS_SELECTOR, 'input[type="text"],input:not([type])'):
        try:
            if not inp.is_displayed(): continue
            inp.send_keys(Keys.CONTROL + 'a'); inp.send_keys(Keys.BACKSPACE)
            inp.clear(); inp.send_keys(target_name); time.sleep(0.5)
            inp.send_keys(Keys.RETURN); time.sleep(2)
            session.log('✅ Group name restored!'); return True
        except: continue
    driver.execute_script(
        "var h=document.querySelector('h1,h2,h4,[data-testid=\"thread-title-text\"]');if(h)h.click();")
    time.sleep(2)
    for inp in driver.find_elements(By.CSS_SELECTOR, 'input[type="text"],input:not([type])'):
        try:
            if not inp.is_displayed(): continue
            inp.send_keys(Keys.CONTROL + 'a'); inp.send_keys(target_name)
            inp.send_keys(Keys.RETURN); time.sleep(2)
            session.log('✅ Group name restored (fallback)!'); return True
        except: continue
    session.log('⚠️ Could not restore name'); return False


def set_member_nickname(driver, session, member_uid, nickname):
    session.log(f'Setting nickname {member_uid}: {nickname}')
    driver.execute_script("""
        var labels=['Members','People','View members','Participants'];
        var all=document.querySelectorAll('[role="button"],[aria-label]');
        for(var el of all){
            var t=(el.getAttribute('aria-label')||el.textContent||'').trim();
            for(var l of labels){if(t.toLowerCase().includes(l.toLowerCase())){el.click();return true;}}
        }
        return false;
    """)
    time.sleep(3)
    clicked = driver.execute_script(f"""
        var links=document.querySelectorAll('a[href*="{member_uid}"]');
        if(links.length>0){{links[0].click();return true;}}
        return false;
    """)
    time.sleep(3)
    if not clicked:
        session.log(f'Member {member_uid} not found in panel'); return False
    driver.execute_script("""
        var kw=['nickname','edit nickname','set nickname'];
        var all=document.querySelectorAll('[role="button"],[role="menuitem"],div,span');
        for(var el of all){
            var t=(el.textContent||'').toLowerCase().trim();
            for(var k of kw){if(t.includes(k)){el.click();return true;}}
        }
        return false;
    """)
    time.sleep(2)
    for inp in driver.find_elements(By.CSS_SELECTOR, 'input[type="text"],input:not([type])'):
        try:
            if not inp.is_displayed(): continue
            inp.send_keys(Keys.CONTROL + 'a'); inp.send_keys(Keys.BACKSPACE)
            inp.clear(); inp.send_keys(nickname); inp.send_keys(Keys.RETURN)
            time.sleep(2); session.log(f'✅ Nickname set: {nickname}'); return True
        except: continue
    session.log(f'⚠️ Could not set nickname for {member_uid}'); return False


def run_smart_lock(session, cookies, group_uid, target_name, nicknames_map, interval, e2e):
    retries = 0; driver = None
    while session.running and retries < 8:
        try:
            if driver is None:
                driver = setup_browser(session)
                session.driver = driver
                login_messenger(driver, session, cookies)
            open_thread(driver, session, group_uid, e2e=e2e)
            if nicknames_map:
                session.log(f'Setting {len(nicknames_map)} nickname(s)...')
                for muid, nick in nicknames_map.items():
                    if not session.running: break
                    open_thread(driver, session, group_uid, e2e=e2e)
                    set_member_nickname(driver, session, muid, nick)
                open_thread(driver, session, group_uid, e2e=e2e)
            session.log('🔒 Smart Lock active — monitoring...')
            retries = 0
            while session.running:
                try:
                    open_thread(driver, session, group_uid, e2e=e2e)
                    current = get_current_group_name(driver)
                    session.log(f'Check → "{current}"')
                    if current and current != target_name:
                        session.log(f'⚠️ Changed! Restoring "{target_name}"')
                        restore_group_name(driver, session, target_name)
                    if nicknames_map and session.running:
                        for muid, nick in nicknames_map.items():
                            if not session.running: break
                            open_thread(driver, session, group_uid, e2e=e2e)
                            set_member_nickname(driver, session, muid, nick)
                    session.count += 1
                    manager.update_count(session.id, session.count)
                    session.log(f'Sleeping {interval}s...')
                    for _ in range(interval):
                        if not session.running: break
                        time.sleep(1)
                except Exception as e:
                    err = str(e)[:60]; session.log(f'Inner error: {err}')
                    if 'session' in err.lower() or 'disconn' in err.lower():
                        session.log('Browser lost, restarting...')
                        try: driver.quit()
                        except: pass
                        driver = None; retries += 1; time.sleep(5); break
                    time.sleep(10)
        except Exception as e:
            session.log(f'Fatal: {str(e)[:60]}'); retries += 1
            try: driver.quit()
            except: pass
            driver = None; time.sleep(10)
    session.running = False; session.log('Smart Lock stopped.')
    manager._save_registry()
    if driver:
        try: driver.quit()
        except: pass
    gc.collect()


def start_smart_lock(session, cookies, group_uid, target_name, nicknames_raw, interval, e2e):
    session.running = True; session.logs = deque(maxlen=MAX_LOGS)
    session.count = 0; session.idx = 0; session.start_time = time.strftime("%H:%M:%S")
    try: open(f"{LOGS_DIR}/{session.id}.log", 'w').close()
    except: pass
    nicknames_map = {}
    for line in nicknames_raw.splitlines():
        line = line.strip()
        if '=' in line:
            parts = line.split('=', 1)
            u, n = parts[0].strip(), parts[1].strip()
            if u and n: nicknames_map[u] = n
    session.log(f'Smart Lock starting | Group:{group_uid} | Name:"{target_name}" | '
                f'Nicks:{len(nicknames_map)} | Interval:{interval}s')
    manager._save_registry()
    threading.Thread(target=run_smart_lock,
                     args=(session, cookies, group_uid, target_name, nicknames_map, interval, e2e),
                     daemon=True).start()


# ═════════════════════════════════════════════════════════════════════════════
# ── TAB 4: AUTO MESSAGE ──────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════
def find_message_input(driver, session):
    session.log('Finding message input...')
    time.sleep(5)
    for sel in ['div[role="textbox"][aria-label*="message" i]',
                'div[contenteditable="true"][aria-label*="message" i]',
                'div[role="textbox"][aria-label*="Message" i]',
                'div[contenteditable="true"][data-lexical-editor="true"]',
                'div[contenteditable="true"]', '[role="textbox"]']:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    ok = driver.execute_script(
                        "return arguments[0].contentEditable==='true'||"
                        "arguments[0].tagName==='TEXTAREA';", el)
                    if ok and el.is_displayed():
                        el.click(); time.sleep(0.3)
                        session.log('Message input found!'); return el
                except: continue
        except: continue
    return None


def send_message(driver, session, inp, text):
    driver.execute_script("""
        var el=arguments[0],txt=arguments[1];
        el.scrollIntoView({block:'center'});el.focus();el.click();
        if(el.tagName==='DIV')el.textContent=txt; else el.value=txt;
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new InputEvent('input',{bubbles:true,data:txt}));
    """, inp, text)
    time.sleep(0.8)
    driver.execute_script("""
        var el=arguments[0];el.focus();
        ['keydown','keypress','keyup'].forEach(function(t){
            el.dispatchEvent(new KeyboardEvent(t,{
                key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
        });
    """, inp)
    time.sleep(1)
    session.log(f'Msg sent: {text[:30]}...')


def run_auto_message(session, cookies, recipient_uids, messages, prefix, delay, e2e):
    retries = 0; driver = None
    while session.running and retries < 8:
        try:
            if driver is None:
                driver = setup_browser(session)
                session.driver = driver
                login_messenger(driver, session, cookies)
            session.log(f'Auto-message | {len(recipient_uids)} recipient(s)')
            retries = 0
            while session.running:
                for uid in recipient_uids:
                    if not session.running: break
                    session.log(f'Opening: {uid}')
                    open_thread(driver, session, uid, e2e=e2e)
                    inp = find_message_input(driver, session)
                    if not inp:
                        session.log(f'❌ Input not found for {uid}, skipping'); continue
                    base = messages[session.idx % len(messages)]
                    session.idx += 1
                    full = f"{prefix} {base}".strip() if prefix else base
                    send_message(driver, session, inp, full)
                    session.count += 1
                    manager.update_count(session.id, session.count)
                    session.log(f'✅ Msg #{session.count} sent to {uid}')
                    jd = max(5, int(delay + random.uniform(-5, 5)))
                    session.log(f'Waiting {jd}s...')
                    for _ in range(jd):
                        if not session.running: break
                        time.sleep(1)
        except Exception as e:
            session.log(f'Fatal: {str(e)[:60]}'); retries += 1
            try: driver.quit()
            except: pass
            driver = None; time.sleep(8)
    session.running = False; session.log('Auto Message stopped.')
    manager._save_registry()
    if driver:
        try: driver.quit()
        except: pass
    gc.collect()


def start_auto_message(session, cookies, recipient_uids, messages, prefix, delay, e2e):
    session.running = True; session.logs = deque(maxlen=MAX_LOGS)
    session.count = 0; session.idx = 0; session.start_time = time.strftime("%H:%M:%S")
    try: open(f"{LOGS_DIR}/{session.id}.log", 'w').close()
    except: pass
    session.log('Auto Message session starting...')
    manager._save_registry()
    threading.Thread(target=run_auto_message,
                     args=(session, cookies, recipient_uids, messages, prefix, delay, e2e),
                     daemon=True).start()


# ═════════════════════════════════════════════════════════════════════════════
# ── TAB 5: GROUP UID EXTRACTOR ───────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════
def extract_groups_from_messenger(session, cookies, result_holder):
    driver = None
    try:
        driver = setup_browser(session)
        session.driver = driver
        login_messenger(driver, session, cookies)
        session.log('Scanning conversations...')
        driver.get('https://www.messenger.com/'); time.sleep(12)
        driver.execute_script("""
            var sb=document.querySelector('[role="navigation"]')||
                   document.querySelector('div[role="list"]');
            if(sb){for(var i=0;i<10;i++)sb.scrollTop+=600;}
        """)
        time.sleep(4)
        convs = driver.execute_script("""
            var results=[],seen=new Set();
            var links=document.querySelectorAll('a[href*="/t/"]');
            links.forEach(function(link){
                var href=link.getAttribute('href')||'';
                var uid=href.replace(/.*\\/t\\//,'').replace(/[?#].*/,'').trim();
                if(!uid||seen.has(uid))return;
                seen.add(uid);
                var nameEl=link.querySelector('span[dir="auto"],span,div[dir="auto"]');
                var name=nameEl?nameEl.textContent.trim():uid;
                var subEl=link.querySelector('div:nth-child(2) span,div:last-child span');
                var subtitle=subEl?subEl.textContent.trim():'';
                results.push({uid:uid,name:name,subtitle:subtitle});
            });
            return results;
        """)
        all_found = [{'uid': (c.get('uid') or '').strip(),
                      'name': (c.get('name') or '').strip(),
                      'subtitle': (c.get('subtitle') or '').strip()}
                     for c in (convs or []) if (c.get('uid') or '').strip()]
        session.log(f'Found {len(all_found)} conversation(s)')
        for idx, conv in enumerate(all_found[:30]):
            if not session.running: break
            uid = conv['uid']
            session.log(f'Checking {idx+1}/{min(len(all_found),30)}: {conv["name"][:20]}')
            try:
                driver.get(f'https://www.messenger.com/t/{uid}'); time.sleep(8)
                info = driver.execute_script("""
                    var nameEl=document.querySelector(
                        'h1,h2,h4,[data-testid="thread-title-text"],[data-testid="thread-title"]');
                    var name=nameEl?nameEl.textContent.trim():null;
                    var memberCount=null;
                    var m=(document.body.innerText||'').match(/(\\d+) (members|people|participants)/i);
                    if(m)memberCount=m[1]+' '+m[2];
                    var isGroup=false;
                    document.querySelectorAll('span,div').forEach(function(el){
                        var t=(el.textContent||'').toLowerCase().trim();
                        if(t==='members'||t.includes('member')||t.includes('participant'))isGroup=true;
                    });
                    return{name:name,memberCount:memberCount,isGroup:isGroup};
                """)
                g_name  = (info.get('name') or conv['name']).strip()
                m_count = info.get('memberCount') or 'N/A'
                is_grp  = info.get('isGroup') or (',' in conv['subtitle'])
                result_holder.append({'uid': uid, 'name': g_name,
                                      'members': m_count, 'is_group': is_grp})
                session.log(f'✅ {g_name[:20]} | {m_count} | Group:{is_grp}')
                session.count += 1
                manager.update_count(session.id, session.count)
            except Exception as e:
                session.log(f'Error on {uid}: {str(e)[:40]}')
        session.log(f'Done! {len(result_holder)} conversations extracted.')
    except Exception as e:
        session.log(f'Fatal: {str(e)[:60]}')
    finally:
        session.running = False; manager._save_registry()
        if driver:
            try: driver.quit()
            except: pass
        gc.collect()


def start_extractor(session, cookies, result_holder):
    session.running = True; session.logs = deque(maxlen=MAX_LOGS)
    session.count = 0; session.start_time = time.strftime("%H:%M:%S")
    try: open(f"{LOGS_DIR}/{session.id}.log", 'w').close()
    except: pass
    session.log('Group UID Extractor starting...')
    manager._save_registry()
    result_holder.clear()
    threading.Thread(target=extract_groups_from_messenger,
                     args=(session, cookies, result_holder),
                     daemon=True).start()


# ═════════════════════════════════════════════════════════════════════════════
# UI
# ═════════════════════════════════════════════════════════════════════════════
if 'view_session'      not in st.session_state: st.session_state.view_session = None
if 'extractor_results' not in st.session_state: st.session_state.extractor_results = []

st.markdown('<div class="main-header"><h1>🔧 FB & Messenger Tools</h1></div>',
            unsafe_allow_html=True)

all_sessions    = manager.get_all_sessions()
active_sessions = manager.get_active_sessions()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Active Sessions", len(active_sessions))
m2.metric("Total Actions",   sum(s.count for s in all_sessions))
m3.metric("All Sessions",    len(all_sessions))
with m4:
    if st.button("↻ Refresh"):
        st.rerun()

st.markdown("---")

# ── SESSION VIEWER ────────────────────────────────────────────────────────────
if st.session_state.view_session:
    sid     = st.session_state.view_session
    session = manager.get_session(sid)
    st.markdown(f"### Session: `{sid}`")
    if session:
        badge = {"comment":"💬","post":"📸","lock":"🔒","message":"📨","extractor":"🔍"
                 }.get(session.session_type, "⚙️")
        if session.running:
            st.markdown(
                f'<div class="status-running"><span class="online-indicator"></span>'
                f'RUNNING {badge} — {session.count} actions'
                f'{" | " + session.profile_id if session.profile_id else ""}</div>',
                unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-stopped">STOPPED</div>', unsafe_allow_html=True)
        logs = manager.get_logs(sid, 35)
        logs_html = '<div class="console-box">'
        for line in logs:
            logs_html += f'<div class="log-line">{line.strip()}</div>'
        logs_html += '</div>'
        st.markdown(logs_html, unsafe_allow_html=True)
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("STOP", disabled=not session.running):
                manager.stop_session(sid); st.rerun()
        with b2:
            if st.button("Delete"):
                manager.delete_session(sid); st.session_state.view_session = None; st.rerun()
        with b3:
            if st.button("↻ Refresh Logs"): st.rerun()
        with b4:
            if st.button("← Back"):
                st.session_state.view_session = None; st.rerun()
    else:
        st.error("Session not found")
        if st.button("← Back"):
            st.session_state.view_session = None; st.rerun()

else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💬 Auto Comment",
        "📸 Auto Post",
        "🔒 Smart Lock",
        "📨 Auto Message",
        "🔍 Group UID Extractor",
    ])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — Auto Comment
    # ══════════════════════════════════════════════════════════════════════
    with tab1:
        st.markdown("### 💬 Auto Comment on Facebook Posts")
        c1, c2 = st.columns(2)
        with c1:
            t1_post_id = st.text_input("Post ID / URL", placeholder="https://facebook.com/...", key="t1_pid")
            t1_prefix  = st.text_input("Prefix (optional)", placeholder="@username", key="t1_prefix")
            t1_delay   = st.number_input("Delay (seconds)", 10, 3600, 30, key="t1_delay")
        with c2:
            t1_cookies = st.text_area("Cookies", height=110, placeholder="Paste cookies...", key="t1_cookies")
        t1_file = st.file_uploader("Upload Comments TXT", type=['txt'], key="t1_file")
        if t1_file:
            t1_comments = t1_file.read().decode('utf-8')
            st.success(f"✅ {len([l for l in t1_comments.splitlines() if l.strip()])} comments loaded")
        else:
            t1_comments = st.text_area("Comments (one per line)", height=70,
                                       placeholder="Nice!\nGreat post!", key="t1_comments")
        if st.button("▶ START AUTO COMMENT", use_container_width=True, key="btn_comment"):
            if not t1_cookies.strip(): st.error("Cookies required!")
            elif not t1_post_id.strip(): st.error("Post ID/URL required!")
            elif not t1_comments.strip(): st.error("Add at least one comment!")
            else:
                s = manager.create_session('comment')
                start_comment_session(s, t1_post_id.strip(), t1_cookies.strip(),
                                      t1_comments, t1_prefix.strip(), int(t1_delay))
                st.success(f"✅ Comment session started! ID: `{s.id}`")
                time.sleep(1); st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — Auto Post
    # ══════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("### 📸 Auto Post on Your Facebook Profile")
        p1, p2 = st.columns(2)
        with p1:
            t2_prefix = st.text_input("Prefix (optional)", placeholder="🔥 Check this!", key="t2_prefix")
            t2_delay  = st.number_input("Delay Between Posts (seconds)", 30, 7200, 120, key="t2_delay")
        with p2:
            t2_cookies = st.text_area("Cookies", height=110, placeholder="Paste cookies...", key="t2_cookies")
        t2_mention = st.text_area("Mention UIDs (one per line — blue link)",
                                  height=60, placeholder="61585863406851\n100072345678",
                                  key="t2_mention")
        t2_txt_file = st.file_uploader("Upload Post Text TXT (one line = one post)",
                                       type=['txt'], key="t2_txt")
        t2_text_lines = []
        if t2_txt_file:
            raw = t2_txt_file.read().decode('utf-8')
            t2_text_lines = [l.strip() for l in raw.splitlines() if l.strip()]
            st.success(f"✅ {len(t2_text_lines)} post lines loaded")
        else:
            t2_manual = st.text_area("Post Lines (one line = one post)", height=70,
                                     placeholder="First post text\nSecond post text", key="t2_manual")
            if t2_manual.strip():
                t2_text_lines = [l.strip() for l in t2_manual.splitlines() if l.strip()]
        t2_imgs = st.file_uploader("Upload Images (img1→post1, img2→post2 ...)",
                                   type=['jpg','jpeg','png','gif','webp'],
                                   accept_multiple_files=True, key="t2_imgs")
        if t2_imgs:
            st.info(f"✅ {len(t2_imgs)} image(s) loaded")
            pcols = st.columns(min(len(t2_imgs), 5))
            for i, img in enumerate(t2_imgs[:5]):
                with pcols[i]: st.image(img, width=70, caption=f"#{i+1}")
        t2_mention_ids = [m.strip() for m in t2_mention.splitlines() if m.strip()]
        preview = []
        if t2_prefix.strip(): preview.append(t2_prefix.strip())
        for m in t2_mention_ids: preview.append(f'@{m.lstrip("@")}')
        preview.append(t2_text_lines[0] if t2_text_lines else "(no text)")
        st.markdown("**First post preview:**")
        st.code(' '.join(preview)[:200], language=None)
        if st.button("▶ START AUTO POST", use_container_width=True, key="btn_post"):
            if not t2_cookies.strip(): st.error("Cookies required!")
            elif not t2_text_lines: st.error("Add post text (file or manual)!")
            else:
                s = manager.create_session('post')
                img_paths = save_uploaded_images(t2_imgs, s.id) if t2_imgs else []
                start_post_session(s, t2_cookies.strip(), t2_text_lines,
                                   t2_prefix.strip(), t2_mention_ids, img_paths, int(t2_delay))
                st.success(f"✅ Post session started! ID: `{s.id}`")
                time.sleep(1); st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — Smart Lock
    # ══════════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown("### 🔒 Smart Lock — Messenger Group Name & Nickname Guard")
        st.info("Enter group E2E UID + name to lock. Tool monitors the group and "
                "auto-restores any changes to name or member nicknames.")
        sl1, sl2 = st.columns(2)
        with sl1:
            t3_gid      = st.text_input("Group E2E UID", placeholder="e.g. 6158586340685", key="t3_gid")
            t3_name     = st.text_input("Group Name to Lock", placeholder="My Group", key="t3_name")
            t3_interval = st.number_input("Check Interval (seconds)", 30, 3600, 60, key="t3_interval")
            t3_e2e      = st.checkbox("E2E Encrypted Thread?", value=True, key="t3_e2e")
        with sl2:
            t3_cookies   = st.text_area("Cookies", height=110,
                                        placeholder="Paste Facebook/Messenger cookies...", key="t3_cookies")
            t3_nicknames = st.text_area("Member Nicknames (optional)\nFormat: UID=Nickname (one per line)",
                                        height=110, placeholder="61585863406851=Bhai\n100072345678=Dost",
                                        key="t3_nicks")
        if st.button("🔒 START SMART LOCK", use_container_width=True, key="btn_lock"):
            if not t3_cookies.strip(): st.error("Cookies required!")
            elif not t3_gid.strip():   st.error("Group UID required!")
            elif not t3_name.strip():  st.error("Group name required!")
            else:
                s = manager.create_session('lock')
                start_smart_lock(s, t3_cookies.strip(), t3_gid.strip(), t3_name.strip(),
                                 t3_nicknames, int(t3_interval), t3_e2e)
                st.success(f"✅ Smart Lock started! ID: `{s.id}`")
                time.sleep(1); st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 4 — Auto Message
    # ══════════════════════════════════════════════════════════════════════
    with tab4:
        st.markdown("### 📨 Auto Message Sender — Messenger Inbox / Group")
        st.info("Enter recipient E2E UIDs. Upload msg.txt or type messages. "
                "Tool opens each inbox, types and sends the message.")
        am1, am2 = st.columns(2)
        with am1:
            t4_uids   = st.text_area("Recipient E2E UIDs (one per line)", height=120,
                                     placeholder="61585863406851\n100072345678\nhttps://messenger.com/t/xxx",
                                     key="t4_uids")
            t4_prefix = st.text_input("Prefix (optional)", placeholder="Hello!", key="t4_prefix")
            t4_delay  = st.number_input("Delay between messages (seconds)", 10, 3600, 30, key="t4_delay")
            t4_e2e    = st.checkbox("E2E Encrypted Thread?", value=True, key="t4_e2e")
        with am2:
            t4_cookies  = st.text_area("Cookies", height=110, placeholder="Paste cookies...", key="t4_cookies")
            t4_msg_file = st.file_uploader("Upload msg.txt (one message per line)",
                                           type=['txt'], key="t4_file")
            t4_manual   = st.text_area("Or type messages here (one per line)", height=80,
                                       placeholder="Hello!\nHow are you?", key="t4_manual")
        t4_messages = []
        if t4_msg_file:
            raw = t4_msg_file.read().decode('utf-8', errors='ignore')
            t4_messages = [l.strip() for l in raw.splitlines() if l.strip()]
            st.success(f"✅ {len(t4_messages)} message(s) loaded")
        elif t4_manual.strip():
            t4_messages = [l.strip() for l in t4_manual.splitlines() if l.strip()]
        if t4_messages:
            st.code(f"Preview: {t4_messages[0][:80]}", language=None)
        if st.button("📨 START AUTO MESSAGE", use_container_width=True, key="btn_msg"):
            t4_uids_list = [u.strip() for u in t4_uids.splitlines() if u.strip()]
            if not t4_cookies.strip(): st.error("Cookies required!")
            elif not t4_uids_list:     st.error("Add at least one recipient UID!")
            elif not t4_messages:      st.error("Add messages!")
            else:
                s = manager.create_session('message')
                start_auto_message(s, t4_cookies.strip(), t4_uids_list,
                                   t4_messages, t4_prefix.strip(), int(t4_delay), t4_e2e)
                st.success(f"✅ Auto Message started! ID: `{s.id}`")
                time.sleep(1); st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 5 — Group UID Extractor
    # ══════════════════════════════════════════════════════════════════════
    with tab5:
        st.markdown("### 🔍 Group UID Extractor — Scan Messenger Conversations")
        st.info("Add cookies → tool opens Messenger and extracts Group Name, Member Count, UID.")
        t5_cookies = st.text_area("Cookies", height=110,
                                   placeholder="Paste Facebook/Messenger cookies...", key="t5_cookies")
        if st.button("🔍 EXTRACT GROUP UIDs", use_container_width=True, key="btn_extract"):
            if not t5_cookies.strip(): st.error("Cookies required!")
            else:
                s = manager.create_session('extractor')
                start_extractor(s, t5_cookies.strip(), st.session_state.extractor_results)
                st.success(f"✅ Extraction started! ID: `{s.id}`")
                st.info("Click '↻ Refresh' above to update results as they come in.")
                time.sleep(2); st.rerun()
        results = st.session_state.extractor_results
        if results:
            st.markdown(f"#### Found {len(results)} conversation(s)")
            csv_lines = ["UID,Name,Members,IsGroup"] + \
                        [f'"{r["uid"]}","{r["name"]}","{r["members"]}","{r["is_group"]}"'
                         for r in results]
            st.download_button("⬇ Download CSV", data="\n".join(csv_lines).encode(),
                               file_name="messenger_groups.csv", mime="text/csv")
            st.markdown('<div class="result-box">', unsafe_allow_html=True)
            for r in results:
                flag = "👥" if r.get('is_group') else "👤"
                st.markdown(
                    f'<div class="result-row">{flag} <b>{r["name"]}</b> &nbsp;|&nbsp; '
                    f'UID: <code>{r["uid"]}</code> &nbsp;|&nbsp; Members: {r["members"]}</div>',
                    unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No results yet — start extraction above.")

# ═════════════════════════════════════════════════════════════════════════════
# ACTIVE SESSIONS PANEL
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### Active Sessions")
BADGE = {"comment":"💬","post":"📸","lock":"🔒","message":"📨","extractor":"🔍"}
active = manager.get_active_sessions()
if active:
    for s in active:
        c1, c2, c3, c4, c5 = st.columns([1, 2, 1, 1, 1])
        with c1: st.write(f"{BADGE.get(s.session_type,'⚙️')} `{s.id}`")
        with c2: st.write(f"{s.session_type} | {s.count} actions")
        with c3:
            if st.button("View", key=f"v_{s.id}"):
                st.session_state.view_session = s.id; st.rerun()
        with c4:
            if st.button("Stop", key=f"s_{s.id}"):
                manager.stop_session(s.id); st.rerun()
        with c5:
            if st.button("Del", key=f"d_{s.id}"):
                manager.delete_session(s.id); st.rerun()
else:
    st.info("No active sessions")

stopped = [s for s in all_sessions if not s.running]
if stopped:
    with st.expander(f"Stopped Sessions ({len(stopped)})"):
        for s in stopped[-10:]:
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1: st.write(f"{BADGE.get(s.session_type,'⚙️')} `{s.id}`")
            with c2: st.write(f"{s.session_type} | {s.count} actions")
            with c3:
                if st.button("Logs", key=f"lg_{s.id}"):
                    st.session_state.view_session = s.id; st.rerun()
            with c4:
                if st.button("Del", key=f"dl_{s.id}"):
                    manager.delete_session(s.id); st.rerun()

st.markdown("---")
lookup = st.text_input("Session ID lookup:", placeholder="XXXXXXXX", key="lookup")
if lookup and st.button("Find", key="btn_find"):
    if manager.get_session(lookup.upper().strip()):
        st.session_state.view_session = lookup.upper().strip(); st.rerun()
    else:
        st.error("Session not found")
