from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
import re
import secrets

# ===================== تنظیمات =====================
UPLOAD_DIR = 'uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ===================== دیتابیس =====================
def get_db():
    conn = sqlite3.connect('arka.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT, phone TEXT UNIQUE,
        national_code TEXT UNIQUE, password TEXT,
        city TEXT, is_admin INTEGER DEFAULT 0,
        remember_token TEXT, created_at TEXT)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT, price TEXT,
        city TEXT, category TEXT, user_id INTEGER,
        views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active', is_special INTEGER DEFAULT 0,
        image1 TEXT, image2 TEXT, image3 TEXT, image4 TEXT,
        created_at TEXT)''')
    db.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER, receiver_id INTEGER,
        ad_id INTEGER, content TEXT,
        is_read INTEGER DEFAULT 0, created_at TEXT)''')
    db.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, ad_id INTEGER, created_at TEXT)''')
    db.commit()
    db.close()
    
    db = get_db()
    admin = db.execute("SELECT * FROM users WHERE phone='09123456789'").fetchone()
    if not admin:
        hashed = hashlib.sha256('admin123'.encode()).hexdigest()
        db.execute("INSERT INTO users (full_name,phone,national_code,password,is_admin,created_at) VALUES (?,?,?,?,?,?)",
                   ('مدیر آرکا','09123456789','1234567890',hashed,1,datetime.now().isoformat()))
        db.commit()
        print('✅ ادمین: 09123456789 / admin123')
    db.close()

# ===================== نشست =====================
sessions = {}

def get_user_from_cookie(cookies):
    if not cookies: return None
    for c in cookies.split(';'):
        c = c.strip()
        if c.startswith('session_id='):
            u = sessions.get(c.split('=')[1])
            if u: return u
    for c in cookies.split(';'):
        c = c.strip()
        if c.startswith('remember_token='):
            token = c.split('=')[1]
            db = get_db()
            u = db.execute("SELECT * FROM users WHERE remember_token=?", (token,)).fetchone()
            db.close()
            if u:
                sid = secrets.token_hex(32)
                sessions[sid] = {'user_id': u['id'], 'user_name': u['full_name']}
                return sessions[sid]
    return None

def create_session(user_id, user_name):
    sid = secrets.token_hex(32)
    sessions[sid] = {'user_id': user_id, 'user_name': user_name}
    return sid

def delete_session(cookies):
    if cookies:
        for c in cookies.split(';'):
            c = c.strip()
            if c.startswith('session_id='):
                sessions.pop(c.split('=')[1], None)
            if c.startswith('remember_token='):
                token = c.split('=')[1]
                db = get_db()
                db.execute("UPDATE users SET remember_token=NULL WHERE remember_token=?", (token,))
                db.commit()
                db.close()

# ===================== آپلود =====================
def parse_multipart_form(content_type, body):
    boundary = None
    for part in content_type.split(';'):
        part = part.strip()
        if part.startswith('boundary='):
            boundary = part.split('=', 1)[1].strip().strip('"').encode()
            break
    if not boundary: return {}
    result = {}
    parts = body.split(b'--' + boundary)
    for part in parts:
        if b'Content-Disposition' not in part: continue
        if b'\r\n\r\n' in part:
            header_part, data = part.split(b'\r\n\r\n', 1)
        elif b'\n\n' in part:
            header_part, data = part.split(b'\n\n', 1)
        else: continue
        data = data.rstrip(b'\r\n')
        if data.endswith(b'--'):
            data = data[:-2].rstrip(b'\r\n')
        header_str = header_part.decode('utf-8', errors='ignore')
        name_match = re.search(r'name="([^"]+)"', header_str)
        if not name_match: continue
        field_name = name_match.group(1)
        if 'filename=' in header_str:
            filename_match = re.search(r'filename="([^"]*)"', header_str)
            filename = filename_match.group(1) if filename_match else ''
            result[field_name] = [data]
            result[field_name + '_filename'] = [filename]
        else:
            result[field_name] = [data]
    return result

def save_uploaded_file(file_data):
    try:
        if file_data and file_data[0]:
            data = file_data[0]
            if not data or len(data) < 100: return None
            filename = f"img_{secrets.token_hex(8)}.jpg"
            filepath = os.path.join(UPLOAD_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(data)
            return filename
    except: pass
    return None

# ===================== قالب HTML فوق لوکس =====================
def html_template(content, title='ARKA', user=None, admin=False):
    return f'''<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | ARKA</title>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@100;200;300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
/* ============================================
   ARKA - Ultra Premium Theme
   ============================================ */
*{{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
html{{scroll-behavior:smooth}}
body{{
    font-family:'Vazirmatn',system-ui,sans-serif;
    background:#03040a;
    color:#e8eaf0;
    min-height:100vh;
    overflow-x:hidden;
    line-height:1.6;
    -webkit-font-smoothing:antialiased;
    position:relative;
}}

/* ==================== لایه ستاره‌های متحرک ==================== */
#starfield{{
    position:fixed;top:0;left:0;
    width:100%;height:100%;
    z-index:-5;overflow:hidden;pointer-events:none;
}}
.star{{
    position:absolute;background:#fff;border-radius:50%;
    animation:twinkle 3s infinite ease-in-out;
}}
.star.xs{{width:1px;height:1px}}
.star.sm{{width:2px;height:2px}}
.star.md{{width:3px;height:3px}}
.star.lg{{width:4px;height:4px}}
.star.glow{{box-shadow:0 0 8px 2px rgba(255,255,255,0.7)}}
.star.blue{{background:#8890ff;box-shadow:0 0 10px 2px rgba(88,101,242,0.8)}}
.star.pink{{background:#eb459e;box-shadow:0 0 10px 2px rgba(235,69,158,0.8)}}
.star.gold{{background:#faa61a;box-shadow:0 0 10px 2px rgba(250,166,26,0.8)}}
.star.cyan{{background:#00d4ff;box-shadow:0 0 10px 2px rgba(0,212,255,0.8)}}
@keyframes twinkle{{
    0%,100%{{opacity:0.15;transform:scale(0.8)}}
    50%{{opacity:1;transform:scale(1.6)}}
}}

/* ستاره‌های دنباله‌دار */
.shooting-star{{
    position:absolute;width:2px;height:2px;background:#fff;
    border-radius:50%;box-shadow:0 0 12px 4px rgba(255,255,255,0.9);
    animation:shoot 4s linear infinite;opacity:0;
}}
.shooting-star::after{{
    content:'';position:absolute;top:0;left:0;
    width:150px;height:1px;
    background:linear-gradient(90deg,#fff,transparent);
    transform:translateX(-150px);
}}
@keyframes shoot{{
    0%{{transform:translate(0,0) rotate(-45deg);opacity:0}}
    10%{{opacity:1}}
    100%{{transform:translate(-800px,800px) rotate(-45deg);opacity:0}}
}}

/* سیارک‌های شناور */
.asteroid{{
    position:absolute;border-radius:50%;
    background:radial-gradient(circle at 30% 30%,rgba(255,255,255,0.2),rgba(88,101,242,0.05));
    box-shadow:inset -8px -8px 20px rgba(0,0,0,0.6),0 0 30px rgba(88,101,242,0.2);
    animation:floatAsteroid 25s infinite ease-in-out;
}}
@keyframes floatAsteroid{{
    0%,100%{{transform:translate(0,0) rotate(0deg)}}
    25%{{transform:translate(40px,-50px) rotate(90deg)}}
    50%{{transform:translate(-30px,40px) rotate(180deg)}}
    75%{{transform:translate(50px,30px) rotate(270deg)}}
}}

/* شهاب‌سنگ */
.meteor{{
    position:absolute;width:3px;height:3px;
    background:#faa61a;border-radius:50%;
    box-shadow:0 0 20px 6px rgba(250,166,26,0.9);
    animation:meteorFall 8s linear infinite;opacity:0;
}}
@keyframes meteorFall{{
    0%{{transform:translate(0,-100px);opacity:0}}
    15%{{opacity:1}}
    100%{{transform:translate(-400px,800px);opacity:0}}
}}

/* ==================== پس‌زمینه‌های کهکشانی ==================== */
.bg-grid{{
    position:fixed;top:0;left:0;width:100%;height:100%;
    background-image:
        linear-gradient(rgba(255,255,255,0.02) 1px,transparent 1px),
        linear-gradient(90deg,rgba(255,255,255,0.02) 1px,transparent 1px);
    background-size:80px 80px;
    z-index:-4;
    mask-image:radial-gradient(ellipse at center,black 30%,transparent 75%);
    -webkit-mask-image:radial-gradient(ellipse at center,black 30%,transparent 75%);
}}
.bg-glow{{
    position:fixed;top:0;left:0;width:100%;height:100%;
    background:
        radial-gradient(circle at 15% 20%,rgba(88,101,242,0.15) 0%,transparent 40%),
        radial-gradient(circle at 85% 80%,rgba(235,69,158,0.12) 0%,transparent 40%),
        radial-gradient(circle at 50% 50%,rgba(0,212,255,0.08) 0%,transparent 60%);
    z-index:-3;
    animation:galaxyPulse 12s ease-in-out infinite;
}}
@keyframes galaxyPulse{{
    0%,100%{{opacity:0.5;transform:scale(1)}}
    50%{{opacity:1;transform:scale(1.15)}}
}}

/* کهکشان چرخان */
.galaxy-spin{{
    position:fixed;top:50%;left:50%;
    width:200vw;height:200vw;
    transform:translate(-50%,-50%);
    background:conic-gradient(from 0deg,transparent,rgba(88,101,242,0.05),transparent,rgba(235,69,158,0.05),transparent);
    animation:spin 120s linear infinite;
    z-index:-2;pointer-events:none;
    filter:blur(40px);
}}
@keyframes spin{{
    from{{transform:translate(-50%,-50%) rotate(0deg)}}
    to{{transform:translate(-50%,-50%) rotate(360deg)}}
}}

/* ==================== کانتینر ==================== */
.container{{max-width:1200px;margin:0 auto;padding:24px;position:relative;z-index:1}}

/* ==================== هدر فوق لوکس ==================== */
.header{{
    display:flex;justify-content:space-between;align-items:center;
    flex-wrap:wrap;gap:16px;padding:16px 28px;
    background:linear-gradient(135deg,rgba(10,12,20,0.9),rgba(20,15,40,0.9));
    backdrop-filter:blur(30px) saturate(180%);
    -webkit-backdrop-filter:blur(30px) saturate(180%);
    border:1px solid rgba(255,255,255,0.08);
    border-radius:20px;position:sticky;top:16px;z-index:1000;
    margin-bottom:32px;
    box-shadow:
        0 10px 40px rgba(0,0,0,0.5),
        0 0 80px rgba(88,101,242,0.1),
        inset 0 0 0 1px rgba(255,255,255,0.03);
}}
.header::before{{
    content:'';position:absolute;top:0;left:0;right:0;height:1px;
    background:linear-gradient(90deg,transparent,rgba(88,101,242,0.5),rgba(235,69,158,0.5),transparent);
    border-radius:20px 20px 0 0;
}}
.logo{{
    display:flex;align-items:center;gap:12px;
    text-decoration:none;font-size:24px;font-weight:900;
    letter-spacing:-0.8px;color:#fff;
}}
.logo-mark{{
    width:42px;height:42px;border-radius:12px;
    background:linear-gradient(135deg,#5865f2 0%,#eb459e 50%,#faa61a 100%);
    display:flex;align-items:center;justify-content:center;
    font-size:20px;color:#fff;font-weight:900;
    box-shadow:
        0 8px 24px rgba(88,101,242,0.5),
        0 0 40px rgba(235,69,158,0.3),
        inset 0 0 20px rgba(255,255,255,0.2);
    position:relative;overflow:hidden;
    animation:logoPulse 3s ease-in-out infinite;
}}
@keyframes logoPulse{{
    0%,100%{{box-shadow:0 8px 24px rgba(88,101,242,0.5),0 0 40px rgba(235,69,158,0.3)}}
    50%{{box-shadow:0 8px 30px rgba(88,101,242,0.7),0 0 60px rgba(235,69,158,0.5),0 0 80px rgba(250,166,26,0.3)}}
}}
.logo-mark::before{{
    content:'';position:absolute;
    top:-50%;left:-50%;width:200%;height:200%;
    background:linear-gradient(45deg,transparent,rgba(255,255,255,0.4),transparent);
    animation:shine 3s infinite;
}}
@keyframes shine{{
    from{{transform:translateX(-100%) rotate(45deg)}}
    to{{transform:translateX(100%) rotate(45deg)}}
}}
.logo-text{{background:linear-gradient(135deg,#fff 0%,#8890ff 50%,#eb459e 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.logo-text span{{background:linear-gradient(135deg,#eb459e 0%,#faa61a 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}

/* ==================== دکمه‌های لوکس ==================== */
.btn{{
    display:inline-flex;align-items:center;justify-content:center;gap:8px;
    padding:11px 20px;border-radius:12px;text-decoration:none;color:#fff;
    background:linear-gradient(135deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03));
    border:1px solid rgba(255,255,255,0.1);
    cursor:pointer;font-family:inherit;font-weight:600;font-size:13px;
    transition:all 0.3s cubic-bezier(0.175,0.885,0.32,1.275);
    white-space:nowrap;position:relative;overflow:hidden;
}}
.btn::before{{
    content:'';position:absolute;
    top:0;left:-100%;width:100%;height:100%;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,0.15),transparent);
    transition:left 0.5s;
}}
.btn:hover::before{{left:100%}}
.btn:hover{{
    background:linear-gradient(135deg,rgba(255,255,255,0.15),rgba(255,255,255,0.05));
    border-color:rgba(255,255,255,0.2);
    transform:translateY(-2px);
    box-shadow:0 8px 24px rgba(0,0,0,0.3);
}}
.btn-primary{{
    background:linear-gradient(135deg,#5865f2 0%,#4752c4 100%);
    border:none;
    box-shadow:0 8px 24px rgba(88,101,242,0.4),inset 0 0 0 1px rgba(255,255,255,0.1);
}}
.btn-primary:hover{{
    box-shadow:0 12px 40px rgba(88,101,242,0.6),0 0 60px rgba(88,101,242,0.3);
}}
.btn-accent{{
    background:linear-gradient(135deg,#eb459e 0%,#c73585 100%);
    border:none;
    box-shadow:0 8px 24px rgba(235,69,158,0.4);
}}
.btn-accent:hover{{
    box-shadow:0 12px 40px rgba(235,69,158,0.6),0 0 60px rgba(235,69,158,0.3);
}}
.btn-gold{{
    background:linear-gradient(135deg,#faa61a 0%,#f0883e 100%);
    border:none;color:#03040a;font-weight:800;
    box-shadow:0 8px 24px rgba(250,166,26,0.4);
}}
.btn-gold:hover{{
    box-shadow:0 12px 40px rgba(250,166,26,0.6),0 0 60px rgba(250,166,26,0.3);
}}
.btn-danger{{
    background:rgba(237,66,69,0.15);
    border:1px solid rgba(237,66,69,0.3);
    color:#ff6b6b;
}}
.btn-danger:hover{{background:rgba(237,66,69,0.25);box-shadow:0 8px 24px rgba(237,66,69,0.3)}}
.btn-ghost{{background:transparent;border:1px solid rgba(255,255,255,0.12)}}
.btn-sm{{padding:8px 14px;font-size:12px}}

/* ==================== کارت‌های لوکس ==================== */
.card{{
    background:linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01));
    border:1px solid rgba(255,255,255,0.06);
    border-radius:20px;padding:28px;margin:18px 0;
    transition:all 0.4s cubic-bezier(0.175,0.885,0.32,1.275);
    backdrop-filter:blur(20px);
    -webkit-backdrop-filter:blur(20px);
    position:relative;overflow:hidden;
    box-shadow:0 8px 32px rgba(0,0,0,0.3),inset 0 0 0 1px rgba(255,255,255,0.02);
}}
.card::before{{
    content:'';position:absolute;top:0;left:0;right:0;height:1px;
    background:linear-gradient(90deg,transparent,rgba(88,101,242,0.4),transparent);
}}
.card:hover{{
    border-color:rgba(88,101,242,0.3);
    background:linear-gradient(135deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02));
    box-shadow:0 20px 60px rgba(0,0,0,0.4),0 0 80px rgba(88,101,242,0.15),inset 0 0 0 1px rgba(255,255,255,0.05);
    transform:translateY(-4px);
}}

/* ==================== ورودی‌های لوکس ==================== */
input,textarea,select{{
    width:100%;padding:14px 18px;margin:8px 0;
    border-radius:12px;
    border:1px solid rgba(255,255,255,0.08);
    background:linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01));
    color:#e8eaf0;font-family:inherit;font-size:14px;
    transition:all 0.3s;outline:none;
    backdrop-filter:blur(10px);
}}
input:focus,textarea:focus,select:focus{{
    border-color:rgba(88,101,242,0.6);
    background:linear-gradient(135deg,rgba(88,101,242,0.08),rgba(88,101,242,0.03));
    box-shadow:0 0 0 4px rgba(88,101,242,0.1),0 0 40px rgba(88,101,242,0.2);
    transform:translateY(-2px);
}}
input::placeholder,textarea::placeholder{{color:rgba(255,255,255,0.3)}}

/* ==================== گرید آگهی لوکس ==================== */
.grid{{
    display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
    gap:22px;margin:28px 0;
}}
.ad-card{{
    background:linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01));
    border:1px solid rgba(255,255,255,0.06);
    border-radius:18px;overflow:hidden;
    transition:all 0.4s cubic-bezier(0.175,0.885,0.32,1.275);
    position:relative;backdrop-filter:blur(20px);
    box-shadow:0 8px 32px rgba(0,0,0,0.3);
}}
.ad-card::before{{
    content:'';position:absolute;top:0;left:0;right:0;height:2px;
    background:linear-gradient(90deg,#5865f2,#eb459e,#faa61a);
    opacity:0;transition:opacity 0.4s;z-index:10;
}}
.ad-card:hover::before{{opacity:1}}
.ad-card:hover{{
    transform:translateY(-8px);
    border-color:rgba(88,101,242,0.4);
    box-shadow:0 30px 80px rgba(0,0,0,0.5),0 0 100px rgba(88,101,242,0.2);
}}
.ad-card .image{{
    height:210px;display:flex;align-items:center;justify-content:center;
    font-size:70px;
    background:linear-gradient(135deg,rgba(88,101,242,0.1),rgba(235,69,158,0.05));
    overflow:hidden;position:relative;color:rgba(255,255,255,0.15);
}}
.ad-card .image img{{
    width:100%;height:100%;object-fit:cover;
    transition:transform 0.7s cubic-bezier(0.175,0.885,0.32,1.275);
}}
.ad-card:hover .image img{{transform:scale(1.1)}}
.ad-card .special-badge{{
    position:absolute;top:14px;right:14px;
    background:linear-gradient(135deg,#faa61a,#f0883e);
    color:#03040a;padding:6px 14px;border-radius:8px;
    font-size:11px;font-weight:900;z-index:10;
    box-shadow:0 4px 16px rgba(250,166,26,0.5);
    letter-spacing:0.5px;
    animation:badgeGlow 2s ease-in-out infinite;
}}
@keyframes badgeGlow{{
    0%,100%{{box-shadow:0 4px 16px rgba(250,166,26,0.5)}}
    50%{{box-shadow:0 4px 30px rgba(250,166,26,0.9),0 0 40px rgba(250,166,26,0.4)}}
}}
.ad-card .info{{padding:20px}}
.ad-card .title{{
    font-weight:700;font-size:16px;margin-bottom:10px;
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
    overflow:hidden;line-height:1.6;
}}
.ad-card .price{{
    font-size:22px;font-weight:900;margin:10px 0;
    background:linear-gradient(135deg,#8890ff,#eb459e);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    letter-spacing:-0.5px;
}}
.ad-card .meta{{
    display:flex;justify-content:space-between;
    font-size:11px;color:rgba(255,255,255,0.35);
    margin-top:14px;padding-top:14px;
    border-top:1px solid rgba(255,255,255,0.05);
}}

/* ==================== آمار لوکس ==================== */
.stats-grid{{
    display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
    gap:16px;margin:24px 0;
}}
.stat-card{{
    background:linear-gradient(135deg,rgba(255,255,255,0.05),rgba(255,255,255,0.01));
    border:1px solid rgba(255,255,255,0.06);
    padding:24px;border-radius:18px;text-align:center;
    transition:all 0.4s;backdrop-filter:blur(20px);
    position:relative;overflow:hidden;
}}
.stat-card::before{{
    content:'';position:absolute;top:-50%;left:-50%;
    width:200%;height:200%;
    background:conic-gradient(from 0deg,transparent,rgba(88,101,242,0.15),transparent);
    animation:rotateStat 6s linear infinite;
    opacity:0;transition:opacity 0.4s;
}}
.stat-card:hover::before{{opacity:1}}
@keyframes rotateStat{{
    from{{transform:rotate(0deg)}}
    to{{transform:rotate(360deg)}}
}}
.stat-card:hover{{
    border-color:rgba(88,101,242,0.4);
    transform:translateY(-6px);
    box-shadow:0 20px 60px rgba(0,0,0,0.4),0 0 80px rgba(88,101,242,0.2);
}}
.stat-card .num{{
    font-size:34px;font-weight:900;margin-bottom:6px;
    background:linear-gradient(135deg,#fff,#8890ff,#eb459e);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    position:relative;z-index:1;
    letter-spacing:-1px;
}}
.stat-card .label{{
    color:rgba(255,255,255,0.45);font-size:13px;font-weight:500;
    position:relative;z-index:1;
}}

/* ==================== بج‌ها ==================== */
.badge{{
    display:inline-flex;align-items:center;gap:5px;
    padding:5px 12px;border-radius:8px;
    font-size:11px;font-weight:700;letter-spacing:0.3px;
}}
.badge-primary{{
    background:linear-gradient(135deg,rgba(88,101,242,0.25),rgba(88,101,242,0.1));
    color:#a0a8ff;border:1px solid rgba(88,101,242,0.3);
}}
.badge-admin{{
    background:linear-gradient(135deg,#faa61a,#f0883e);
    color:#03040a;font-weight:900;
    box-shadow:0 4px 16px rgba(250,166,26,0.4);
}}

/* ==================== چت ==================== */
.chat-box{{
    max-height:520px;overflow-y:auto;padding:20px;
    background:linear-gradient(135deg,rgba(0,0,0,0.4),rgba(0,0,0,0.2));
    border-radius:18px;margin:20px 0;
    border:1px solid rgba(255,255,255,0.05);
    backdrop-filter:blur(20px);
}}
.chat-box::-webkit-scrollbar{{width:8px}}
.chat-box::-webkit-scrollbar-track{{background:transparent}}
.chat-box::-webkit-scrollbar-thumb{{background:linear-gradient(180deg,#5865f2,#eb459e);border-radius:4px}}
.chat-msg{{
    margin:10px 0;padding:14px 18px;border-radius:16px;
    max-width:75%;font-size:14px;line-height:1.7;
    animation:fadeInUp 0.4s ease;
}}
@keyframes fadeInUp{{
    from{{opacity:0;transform:translateY(15px)}}
    to{{opacity:1;transform:translateY(0)}}
}}
.chat-msg.me{{
    background:linear-gradient(135deg,#5865f2,#4752c4);
    margin-left:auto;margin-right:0;color:#fff;
    box-shadow:0 8px 24px rgba(88,101,242,0.4);
}}
.chat-msg.other{{
    background:linear-gradient(135deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03));
    margin-right:auto;margin-left:0;
    border:1px solid rgba(255,255,255,0.08);
}}
.chat-msg small{{display:block;font-size:10px;opacity:0.5;margin-top:8px}}

/* ==================== گالری ==================== */
.image-gallery{{
    display:grid;grid-template-columns:2fr 1fr 1fr;
    gap:10px;margin:24px 0;border-radius:18px;overflow:hidden;
}}
.image-gallery img{{
    width:100%;height:230px;object-fit:cover;
    cursor:pointer;transition:all 0.4s;
    border-radius:12px;
}}
.image-gallery img:hover{{
    transform:scale(1.03);
    box-shadow:0 20px 60px rgba(88,101,242,0.4);
}}
.image-gallery .main{{grid-row:span 2;height:470px}}

/* ==================== فوتر لوکس ==================== */
.footer{{
    text-align:center;padding:40px 0 24px;margin-top:60px;
    border-top:1px solid rgba(255,255,255,0.05);
    color:rgba(255,255,255,0.35);font-size:13px;
    position:relative;
}}
.footer::before{{
    content:'';position:absolute;top:-1px;left:50%;
    transform:translateX(-50%);width:200px;height:1px;
    background:linear-gradient(90deg,transparent,#5865f2,#eb459e,transparent);
}}
.footer strong{{
    background:linear-gradient(135deg,#8890ff,#eb459e);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    font-size:16px;font-weight:900;
}}

/* ==================== هدر صفحه ==================== */
.page-header{{
    text-align:center;padding:60px 20px 40px;
    border-bottom:1px solid rgba(255,255,255,0.04);
    margin-bottom:40px;position:relative;
}}
.page-header::after{{
    content:'';position:absolute;bottom:-1px;left:50%;
    transform:translateX(-50%);width:300px;height:1px;
    background:linear-gradient(90deg,transparent,#5865f2,#eb459e,transparent);
}}
.page-header h1{{
    font-size:48px;font-weight:900;letter-spacing:-1.5px;
    line-height:1.2;margin-bottom:14px;
    background:linear-gradient(135deg,#fff 0%,#8890ff 50%,#eb459e 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    animation:titleGlow 4s ease-in-out infinite;
}}
@keyframes titleGlow{{
    0%,100%{{filter:drop-shadow(0 0 20px rgba(88,101,242,0.3))}}
    50%{{filter:drop-shadow(0 0 40px rgba(235,69,158,0.5))}}
}}
.page-header p{{color:rgba(255,255,255,0.45);font-size:17px}}

/* ==================== جستجو ==================== */
.search-bar{{
    background:linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01));
    border:1px solid rgba(255,255,255,0.06);
    border-radius:18px;padding:20px;margin-bottom:28px;
    backdrop-filter:blur(20px);
    box-shadow:0 8px 32px rgba(0,0,0,0.3);
}}

/* ==================== واکنش‌گرا ==================== */
@media(max-width:768px){{
    .container{{padding:16px}}
    .header{{padding:14px 18px;top:8px;margin-bottom:24px;border-radius:16px}}
    .logo{{font-size:18px}}
    .logo-mark{{width:36px;height:36px;font-size:16px}}
    .grid{{grid-template-columns:1fr 1fr;gap:14px}}
    .image-gallery{{grid-template-columns:1fr 1fr}}
    .image-gallery .main{{grid-column:span 2;height:220px}}
    .image-gallery img{{height:150px}}
    .page-header h1{{font-size:30px}}
    .page-header{{padding:40px 16px 28px}}
    .btn{{padding:9px 14px;font-size:12px}}
    .card{{padding:20px;border-radius:16px}}
    .stat-card .num{{font-size:26px}}
}}
@media(max-width:480px){{
    .grid{{grid-template-columns:1fr}}
    .stats-grid{{grid-template-columns:1fr 1fr}}
    .logo-text{{font-size:16px}}
}}
</style>
</head>
<body>
<div id="starfield"></div>
<div class="bg-grid"></div>
<div class="bg-glow"></div>
<div class="galaxy-spin"></div>
<div class="container">
    <div class="header">
        <a href="/" class="logo"><div class="logo-mark">A</div><div class="logo-text">ARK<span>A</span></div></a>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            {f"""<span class='badge {'badge-admin' if admin else 'badge-primary'}'>{'👑 ' if admin else '👤 '}{user['user_name']}</span>
            <a href='/dashboard' class='btn btn-sm'>داشبورد</a>
            <a href='/favorites' class='btn btn-sm'>ذخیره‌ها</a>
            <a href='/messages' class='btn btn-sm'>پیام‌ها</a>
            <a href='/logout' class='btn btn-sm btn-danger'>خروج</a>""" if user else """<a href='/login' class='btn btn-sm btn-ghost'>ورود</a><a href='/register' class='btn btn-sm btn-primary'>ثبت‌نام</a>"""}
        </div>
    </div>
    {content}
    <div class="footer"><strong>ARKA</strong> &copy; ۲۰۲۴<br><small style="opacity:0.5">پلتفرم معاملات هوشمند</small></div>
</div>

<script>
(function() {{
    const sf = document.getElementById('starfield');
    if (!sf) return;
    
    // ستاره‌های ثابت
    const colors = ['', '', 'blue', 'pink', 'gold', 'cyan', 'glow'];
    const sizes = ['xs', 'sm', 'md', 'lg'];
    for (let i = 0; i < 200; i++) {{
        const s = document.createElement('div');
        s.className = 'star ' + sizes[Math.floor(Math.random() * sizes.length)];
        const c = colors[Math.floor(Math.random() * colors.length)];
        if (c) s.classList.add(c);
        s.style.left = Math.random() * 100 + '%';
        s.style.top = Math.random() * 100 + '%';
        s.style.animationDelay = Math.random() * 4 + 's';
        s.style.animationDuration = (2 + Math.random() * 4) + 's';
        sf.appendChild(s);
    }}
    
    // ستاره‌های دنباله‌دار
    for (let i = 0; i < 6; i++) {{
        const ss = document.createElement('div');
        ss.className = 'shooting-star';
        ss.style.left = (Math.random() * 100) + '%';
        ss.style.top = (Math.random() * 60) + '%';
        ss.style.animationDelay = (Math.random() * 15) + 's';
        ss.style.animationDuration = (3 + Math.random() * 4) + 's';
        sf.appendChild(ss);
    }}
    
    // سیارک‌ها
    for (let i = 0; i < 4; i++) {{
        const a = document.createElement('div');
        a.className = 'asteroid';
        const size = 30 + Math.random() * 60;
        a.style.width = size + 'px';
        a.style.height = size + 'px';
        a.style.left = Math.random() * 100 + '%';
        a.style.top = Math.random() * 100 + '%';
        a.style.animationDelay = (Math.random() * 12) + 's';
        a.style.animationDuration = (20 + Math.random() * 20) + 's';
        sf.appendChild(a);
    }}
    
    // شهاب‌سنگ‌ها
    for (let i = 0; i < 4; i++) {{
        const m = document.createElement('div');
        m.className = 'meteor';
        m.style.left = (Math.random() * 100) + '%';
        m.style.top = (Math.random() * 40) + '%';
        m.style.animationDelay = (Math.random() * 20) + 's';
        m.style.animationDuration = (6 + Math.random() * 6) + 's';
        sf.appendChild(m);
    }}
    
    // پارالاکس با ماوس
    document.addEventListener('mousemove', function(e) {{
        const x = (e.clientX / window.innerWidth - 0.5) * 30;
        const y = (e.clientY / window.innerHeight - 0.5) * 30;
        sf.style.transform = 'translate(' + x + 'px,' + y + 'px)';
    }});
}})();
</script>
</body>
</html>'''

# ===================== بقیه کدها بدون تغییر =====================
# (از خط‌های بعدی استفاده کن - دقیقاً همون کد قبلی)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        user = get_user_from_cookie(self.headers.get('Cookie'))
        admin = user and self.is_admin(user['user_id'])
        
        if path.startswith('/uploads/'):
            self.serve_image(path); return
        
        routes = {
            '/': lambda: self.handle_index(query, user, admin),
            '/login': lambda: self.handle_login_page(user),
            '/register': lambda: self.handle_register_page(user),
            '/dashboard': lambda: self.handle_dashboard(user, admin),
            '/add-ad': lambda: self.handle_add_ad_page(user),
            '/favorites': lambda: self.handle_favorites(user),
            '/messages': lambda: self.handle_messages(user),
            '/logout': lambda: self.handle_logout(),
        }
        
        if path in routes: routes[path]()
        elif path.startswith('/ad/'): self.handle_ad_detail(path, user, admin)
        elif path.startswith('/chat/'): self.handle_chat_page(path, user)
        elif path.startswith('/delete-ad/'): self.handle_delete_ad(path, user)
        elif path.startswith('/favorite/'): self.handle_toggle_favorite(path, user)
        elif path.startswith('/edit-ad/'): self.handle_edit_ad_page(path, user)
        elif path.startswith('/like/'): self.handle_like(path, user)
        else: self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        user = get_user_from_cookie(self.headers.get('Cookie'))
        
        if path == '/login':
            body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
            self.handle_login(urllib.parse.parse_qs(body))
        elif path == '/register':
            body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
            self.handle_register(urllib.parse.parse_qs(body))
        elif path == '/add-ad':
            self.handle_add_ad(user)
        elif path.startswith('/edit-ad/'):
            self.handle_edit_ad(path, user)
        elif path.startswith('/chat/'):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
            self.handle_chat(path, urllib.parse.parse_qs(body), user)
        else: self.send_error(404)

    def serve_image(self, path):
        filename = path.split('/')[-1]
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(filepath):
            self.send_response(200)
            ext = filename.split('.')[-1].lower()
            self.send_header('Content-type', {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','gif':'image/gif'}.get(ext, 'image/jpeg'))
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            with open(filepath, 'rb') as f: self.wfile.write(f.read())
        else: self.send_error(404)

    def is_admin(self, uid):
        db = get_db()
        u = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
        db.close()
        return u and u['is_admin'] == 1

    def get_categories(self):
        return ['املاک','خودرو','دیجیتال','لوازم خانه','پوشاک','کتاب','خدمات','استخدام']

    def get_cities(self):
        return ['تهران','اصفهان','مشهد','شیراز','تبریز','اهواز','کرج','قم','کرمانشاه','رشت']

    def redirect(self, loc):
        self.send_response(302); self.send_header('Location', loc); self.end_headers()

    def redirect_cookie(self, loc, sid, remember=None):
        cookies = [f'session_id={sid}; Path=/']
        if remember:
            exp = (datetime.now()+timedelta(days=30)).strftime('%a, %d-%b-%Y %H:%M:%S GMT')
            cookies.append(f'remember_token={remember}; Path=/; Expires={exp}')
        self.send_response(302)
        for c in cookies: self.send_header('Set-Cookie', c)
        self.send_header('Location', loc); self.end_headers()

    def send_page(self, html):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def send_msg(self, msg, url, ok=True):
        color = '#5ddb8a' if ok else '#ff6b6b'
        bg = 'rgba(59,165,93,0.1)' if ok else 'rgba(237,66,69,0.1)'
        border = 'rgba(59,165,93,0.2)' if ok else 'rgba(237,66,69,0.2)'
        icon = '✓' if ok else '✕'
        self.send_page(f'''<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>ARKA</title>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;900&display=swap" rel="stylesheet">
<style>body{{font-family:Vazirmatn;background:#03040a;color:#e8eaf0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px}}
.box{{background:linear-gradient(135deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02));padding:50px;border-radius:24px;border:1px solid rgba(255,255,255,0.08);max-width:440px;text-align:center;backdrop-filter:blur(20px);box-shadow:0 20px 60px rgba(0,0,0,0.5)}}
.icon{{width:80px;height:80px;margin:0 auto 24px;border-radius:50%;background:{bg};border:2px solid {border};display:flex;align-items:center;justify-content:center;font-size:36px;color:{color}}}
h2{{margin:0 0 16px;font-size:24px;font-weight:800}}p{{color:rgba(255,255,255,0.5);margin:0 0 28px;font-size:14px}}
a{{display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#5865f2,#4752c4);color:#fff;text-decoration:none;border-radius:12px;font-weight:700;font-size:14px;box-shadow:0 8px 24px rgba(88,101,242,0.4)}}</style>
</head><body><div class="box"><div class="icon">{icon}</div><h2>{msg}</h2><a href="{url}">ادامه</a></div></body></html>''')

    def handle_index(self, query, user, admin):
        db = get_db()
        search = query.get('search',[''])[0]
        category = query.get('category',[''])[0]
        city = query.get('city',[''])[0]
        sort = query.get('sort',['new'])[0]
        
        sql = "SELECT * FROM ads WHERE status='active'"
        params = []
        if category: sql += " AND category=?"; params.append(category)
        if city: sql += " AND city=?"; params.append(city)
        if search:
            sql += " AND (title LIKE ? OR description LIKE ? OR city LIKE ?)"
            params.extend([f'%{search}%']*3)
        if sort == 'price': sql += " ORDER BY CAST(price AS INTEGER) ASC"
        elif sort == 'price-desc': sql += " ORDER BY CAST(price AS INTEGER) DESC"
        elif sort == 'views': sql += " ORDER BY views DESC"
        else: sql += " ORDER BY is_special DESC, created_at DESC"
        
        ads = db.execute(sql, params).fetchall()
        total = db.execute("SELECT COUNT(*) FROM ads WHERE status='active'").fetchone()[0]
        users_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        db.close()
        
        cat_opts = ''.join([f"<option value='{c}' {'selected' if c==category else ''}>{c}</option>" for c in self.get_categories()])
        city_opts = ''.join([f"<option value='{c}' {'selected' if c==city else ''}>{c}</option>" for c in self.get_cities()])
        
        ads_html = ''.join([self.render_ad_card(a) for a in ads])
        
        content = f'''
        <div class="page-header"><h1>بازار هوشمند آرکا</h1><p>خرید و فروش مطمئن، سریع و بدون واسطه</p></div>
        <div class="stats-grid" style="margin-bottom:28px">
            <div class="stat-card"><div class="num">{total}</div><div class="label">آگهی فعال</div></div>
            <div class="stat-card"><div class="num">{users_count}</div><div class="label">کاربر عضو</div></div>
            <div class="stat-card"><div class="num">۱۰۰٪</div><div class="label">رایگان</div></div>
            <div class="stat-card"><div class="num">۲۴/۷</div><div class="label">پشتیبانی</div></div>
        </div>
        <div class="search-bar"><form method="GET" style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr auto;gap:10px">
            <input type="text" name="search" placeholder="جستجو در آرکا..." value="{search}">
            <select name="category"><option value="">همه دسته‌ها</option>{cat_opts}</select>
            <select name="city"><option value="">همه شهرها</option>{city_opts}</select>
            <select name="sort">
                <option value="new" {'selected' if sort=='new' else ''}>جدیدترین</option>
                <option value="price" {'selected' if sort=='price' else ''}>ارزان‌ترین</option>
                <option value="price-desc" {'selected' if sort=='price-desc' else ''}>گران‌ترین</option>
                <option value="views" {'selected' if sort=='views' else ''}>پربازدید</option>
            </select>
            <button type="submit" class="btn btn-primary">جستجو</button>
        </form></div>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:20px">
            <h2 style="font-size:20px;font-weight:800">آگهی‌های اخیر</h2>
            <a href="/add-ad" class="btn btn-accent">+ ثبت آگهی جدید</a>
        </div>
        <div class="grid">{ads_html if ads else '<div class="card" style="text-align:center;padding:80px;grid-column:1/-1"><p style="color:rgba(255,255,255,0.4)">هنوز آگهی‌ای ثبت نشده است</p></div>'}</div>
        '''
        self.send_page(html_template(content, 'بازار آرکا', user, admin))

    def render_ad_card(self, ad):
        img = f"<img src='/uploads/{ad['image1']}'>" if ad['image1'] else "◈"
        return f'''
        <a href='/ad/{ad["id"]}' style='text-decoration:none;color:inherit'>
            <div class='ad-card'>
                {f"<div class='special-badge'>✦ ویژه</div>" if ad['is_special'] else ""}
                <div class='image'>{img}</div>
                <div class='info'>
                    <div class='title'>{ad['title']}</div>
                    <div class='price'>{ad['price']} <span style='font-size:13px;opacity:0.6'>تومان</span></div>
                    <div style='color:rgba(255,255,255,0.4);font-size:12px;margin-top:4px'>{ad['city']} • {ad['category']}</div>
                    <div class='meta'><span>بازدید {ad['views']}</span><span>{ad['created_at'][:10]}</span></div>
                </div>
            </div>
        </a>'''

    def handle_login_page(self, user):
        if user: self.redirect('/dashboard'); return
        content = '''
        <div class="card" style="max-width:440px;margin:40px auto">
            <div style="text-align:center;margin-bottom:32px">
                <div style="width:72px;height:72px;margin:0 auto 20px;border-radius:18px;background:linear-gradient(135deg,#5865f2,#eb459e);display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:900;color:#fff;box-shadow:0 12px 40px rgba(88,101,242,0.5)">A</div>
                <h2 style="font-size:24px;font-weight:800;margin-bottom:10px">ورود به آرکا</h2>
                <p style="color:rgba(255,255,255,0.4);font-size:14px">به حساب کاربری خود وارد شوید</p>
            </div>
            <form method="POST">
                <input type="tel" name="phone" placeholder="شماره موبایل" required>
                <input type="password" name="password" placeholder="رمز عبور" required>
                <label style="display:flex;align-items:center;gap:10px;margin:16px 0;cursor:pointer;font-size:13px;color:rgba(255,255,255,0.6)">
                    <input type="checkbox" name="remember" value="1" style="width:auto;margin:0">مرا به خاطر بسپار
                </label>
                <button class="btn btn-primary" style="width:100%;padding:15px;font-size:15px">ورود</button>
            </form>
            <p style="text-align:center;margin-top:28px;color:rgba(255,255,255,0.4);font-size:13px">
                حساب ندارید؟ <a href="/register" style="color:#8890ff;text-decoration:none;font-weight:700">ثبت‌نام کنید</a>
            </p>
        </div>
        '''
        self.send_page(html_template(content, 'ورود', user))

    def handle_register_page(self, user):
        if user: self.redirect('/dashboard'); return
        city_opts = ''.join([f"<option value='{c}'>{c}</option>" for c in self.get_cities()])
        content = f'''
        <div class="card" style="max-width:500px;margin:40px auto">
            <div style="text-align:center;margin-bottom:32px">
                <div style="width:72px;height:72px;margin:0 auto 20px;border-radius:18px;background:linear-gradient(135deg,#eb459e,#faa61a);display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:900;color:#fff;box-shadow:0 12px 40px rgba(235,69,158,0.5)">A</div>
                <h2 style="font-size:24px;font-weight:800;margin-bottom:10px">عضویت در آرکا</h2>
                <p style="color:rgba(255,255,255,0.4);font-size:14px">حساب کاربری جدید بسازید</p>
            </div>
            <form method="POST">
                <input type="text" name="full_name" placeholder="نام و نام خانوادگی" required>
                <input type="tel" name="phone" placeholder="شماره موبایل" required>
                <input type="text" name="national_code" placeholder="کد ملی" required>
                <select name="city">{city_opts}</select>
                <input type="password" name="password" placeholder="رمز عبور (حداقل ۶ کاراکتر)" required>
                <button class="btn btn-primary" style="width:100%;padding:15px;font-size:15px;margin-top:8px">ایجاد حساب</button>
            </form>
            <p style="text-align:center;margin-top:28px;color:rgba(255,255,255,0.4);font-size:13px">
                حساب دارید؟ <a href="/login" style="color:#8890ff;text-decoration:none;font-weight:700">وارد شوید</a>
            </p>
        </div>
        '''
        self.send_page(html_template(content, 'ثبت‌نام', user))

    def handle_login(self, form):
        phone = form.get('phone',[''])[0]
        password = form.get('password',[''])[0]
        remember = form.get('remember',['0'])[0]
        hashed = hashlib.sha256(password.encode()).hexdigest()
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE phone=? AND password=?", (phone, hashed)).fetchone()
        if u:
            sid = create_session(u['id'], u['full_name'])
            if remember == '1':
                token = secrets.token_hex(32)
                db.execute("UPDATE users SET remember_token=? WHERE id=?", (token, u['id']))
                db.commit(); db.close()
                self.redirect_cookie('/dashboard', sid, remember=token)
            else:
                db.close()
                self.redirect_cookie('/dashboard', sid)
        else:
            db.close()
            self.send_msg('شماره موبایل یا رمز عبور اشتباه است', '/login', ok=False)

    def handle_register(self, form):
        name = form.get('full_name',[''])[0]
        phone = form.get('phone',[''])[0]
        national = form.get('national_code',[''])[0]
        city = form.get('city',[''])[0]
        password = form.get('password',[''])[0]
        
        if not re.match(r'^09[0-9]{9}$', phone):
            self.send_msg('شماره موبایل معتبر نیست', '/register', ok=False); return
        if len(password) < 6:
            self.send_msg('رمز عبور باید حداقل ۶ کاراکتر باشد', '/register', ok=False); return
        
        hashed = hashlib.sha256(password.encode()).hexdigest()
        db = get_db()
        if db.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone():
            db.close(); self.send_msg('این شماره قبلاً ثبت شده است', '/register', ok=False); return
        db.execute("INSERT INTO users (full_name,phone,national_code,password,city,created_at) VALUES (?,?,?,?,?,?)",
                   (name,phone,national,hashed,city,datetime.now().isoformat()))
        db.commit(); db.close()
        self.send_msg('حساب شما با موفقیت ساخته شد', '/login')

    def handle_logout(self):
        delete_session(self.headers.get('Cookie'))
        self.send_response(302)
        self.send_header('Set-Cookie', 'session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.send_header('Set-Cookie', 'remember_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.send_header('Location', '/')
        self.end_headers()

    def handle_dashboard(self, user, admin):
        if not user: self.redirect('/login'); return
        db = get_db()
        ads = db.execute("SELECT * FROM ads WHERE user_id=? ORDER BY created_at DESC", (user['user_id'],)).fetchall()
        views = sum(a['views'] for a in ads)
        likes = sum(a['likes'] for a in ads)
        unread = db.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=? AND is_read=0", (user['user_id'],)).fetchone()[0]
        db.close()
        
        content = f'''
        <div class="page-header"><h1>داشبورد</h1><p>خوش آمدید، {user['user_name']}</p></div>
        <div class="stats-grid">
            <div class="stat-card"><div class="num">{len(ads)}</div><div class="label">آگهی</div></div>
            <div class="stat-card"><div class="num">{views}</div><div class="label">بازدید</div></div>
            <div class="stat-card"><div class="num">{likes}</div><div class="label">پسند</div></div>
            <div class="stat-card"><div class="num">{unread}</div><div class="label">پیام جدید</div></div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin:28px 0 20px">
            <h2 style="font-size:20px;font-weight:800">آگهی‌های من</h2>
            <a href="/add-ad" class="btn btn-primary">+ آگهی جدید</a>
        </div>
        <div class="grid">{''.join([self.render_ad_card(a) for a in ads]) if ads else '<div class="card" style="text-align:center;padding:80px;grid-column:1/-1"><p style="color:rgba(255,255,255,0.4)">هنوز آگهی ثبت نکرده‌اید</p></div>'}</div>
        '''
        self.send_page(html_template(content, 'داشبورد', user, admin))

    def handle_add_ad_page(self, user):
        if not user: self.redirect('/login'); return
        cat_opts = ''.join([f"<option value='{c}'>{c}</option>" for c in self.get_categories()])
        city_opts = ''.join([f"<option value='{c}'>{c}</option>" for c in self.get_cities()])
        content = f'''
        <div class="card" style="max-width:700px;margin:auto">
            <h2 style="font-size:22px;font-weight:800;margin-bottom:28px">ثبت آگهی جدید</h2>
            <form method="POST" enctype="multipart/form-data">
                <input type="text" name="title" placeholder="عنوان آگهی" required>
                <textarea name="description" placeholder="توضیحات کامل" rows="5" required></textarea>
                <input type="text" name="price" placeholder="قیمت (تومان)" required>
                <select name="category" required>{cat_opts}</select>
                <select name="city" required>{city_opts}</select>
                <div style="margin-top:24px;padding:24px;background:linear-gradient(135deg,rgba(88,101,242,0.08),rgba(235,69,158,0.04));border-radius:16px;border:1px dashed rgba(88,101,242,0.3)">
                    <p style="font-size:13px;color:rgba(255,255,255,0.6);margin-bottom:14px;font-weight:600">تصاویر آگهی (حداکثر ۴ عکس)</p>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                        <input type="file" name="image1" accept="image/*">
                        <input type="file" name="image2" accept="image/*">
                        <input type="file" name="image3" accept="image/*">
                        <input type="file" name="image4" accept="image/*">
                    </div>
                </div>
                <label style="display:flex;align-items:center;gap:10px;margin:18px 0;cursor:pointer;font-size:13px;color:rgba(255,255,255,0.6)">
                    <input type="checkbox" name="is_special" value="1" style="width:auto;margin:0">نمایش به عنوان آگهی ویژه ✦
                </label>
                <button class="btn btn-primary" style="width:100%;padding:16px;font-size:15px">ثبت آگهی</button>
            </form>
        </div>
        '''
        self.send_page(html_template(content, 'ثبت آگهی', user))

    def handle_add_ad(self, user):
        if not user: self.redirect('/login'); return
        ct = self.headers.get('Content-Type', '')
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        try:
            form = parse_multipart_form(ct, body)
        except:
            self.send_msg('خطا در آپلود', '/add-ad', ok=False); return
        
        title = form.get('title', [b''])[0].decode('utf-8', errors='ignore')
        description = form.get('description', [b''])[0].decode('utf-8', errors='ignore')
        price = form.get('price', [b''])[0].decode('utf-8', errors='ignore')
        category = form.get('category', [b''])[0].decode('utf-8', errors='ignore')
        city = form.get('city', [b''])[0].decode('utf-8', errors='ignore')
        is_special = form.get('is_special', [b'0'])[0].decode('utf-8', errors='ignore')
        
        imgs = [None, None, None, None]
        for i in range(1, 5):
            try:
                key = f'image{i}'
                if key in form:
                    imgs[i-1] = save_uploaded_file(form.get(key))
            except: pass
        
        db = get_db()
        db.execute("INSERT INTO ads (title,description,price,city,category,user_id,is_special,image1,image2,image3,image4,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (title,description,price,city,category,user['user_id'],1 if is_special else 0,imgs[0],imgs[1],imgs[2],imgs[3],datetime.now().isoformat()))
        db.commit(); db.close()
        self.send_msg('آگهی با موفقیت ثبت شد', '/dashboard')

    def handle_ad_detail(self, path, user, admin):
        ad_id = int(path.split('/')[-1])
        db = get_db()
        db.execute("UPDATE ads SET views=views+1 WHERE id=?", (ad_id,))
        db.commit()
        ad = db.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
        if not ad:
            db.close(); self.send_msg('آگهی یافت نشد', '/', ok=False); return
        owner = db.execute("SELECT full_name FROM users WHERE id=?", (ad['user_id'],)).fetchone()
        db.close()
        
        images = [i for i in [ad['image1'],ad['image2'],ad['image3'],ad['image4']] if i]
        if images:
            gallery = f'<div class="image-gallery"><img src="/uploads/{images[0]}" class="main">' + ''.join([f'<img src="/uploads/{i}">' for i in images[1:4]]) + '</div>'
        else:
            gallery = f'<div style="text-align:center;padding:100px;font-size:100px;color:rgba(88,101,242,0.15)">◈</div>'
        
        is_owner = user and user['user_id'] == ad['user_id']
        
        content = f'''
        <div class="card">
            {gallery}
            <div style="margin-top:28px">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:24px">
                    <div>
                        <h1 style="font-size:30px;font-weight:900;margin-bottom:10px;letter-spacing:-0.5px">{ad['title']}</h1>
                        <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:13px;color:rgba(255,255,255,0.5)">
                            <span>📍 {ad['city']}</span><span>•</span><span>📂 {ad['category']}</span><span>•</span>
                            <span>👤 {owner['full_name'] if owner else 'ناشناس'}</span>
                        </div>
                    </div>
                    {f'<div class="badge badge-admin">✦ آگهی ویژه</div>' if ad['is_special'] else ''}
                </div>
                <div style="font-size:38px;font-weight:900;margin:20px 0;background:linear-gradient(135deg,#8890ff,#eb459e);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-1px">
                    {ad['price']} <span style="font-size:16px;opacity:0.6">تومان</span>
                </div>
                <div style="background:linear-gradient(135deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01));padding:24px;border-radius:16px;margin:24px 0;border:1px solid rgba(255,255,255,0.05)">
                    <p style="white-space:pre-wrap;line-height:2.2;color:rgba(255,255,255,0.8);font-size:14px">{ad['description']}</p>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;padding-top:24px;border-top:1px solid rgba(255,255,255,0.05)">
                    <div style="display:flex;gap:18px;font-size:12px;color:rgba(255,255,255,0.4)">
                        <span>👁️ {ad['views']} بازدید</span><span>❤️ {ad['likes']} پسند</span><span>📅 {ad['created_at'][:10]}</span>
                    </div>
                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                        {f'<a href="/like/{ad["id"]}" class="btn btn-sm">❤️ پسندیدن</a>' if user else ''}
                        {f'<a href="/favorite/{ad["id"]}" class="btn btn-sm">⭐ ذخیره</a>' if user else ''}
                        {f'<a href="/chat/{ad["id"]}" class="btn btn-sm btn-primary">💬 ارسال پیام</a>' if user and not is_owner else ''}
                        {f'<a href="/edit-ad/{ad["id"]}" class="btn btn-sm">✏️ ویرایش</a>' if is_owner or admin else ''}
                        <a href="/" class="btn btn-sm btn-ghost">بازگشت</a>
                    </div>
                </div>
            </div>
        </div>
        '''
        self.send_page(html_template(content, ad['title'], user, admin))

    def handle_edit_ad_page(self, path, user):
        if not user: self.redirect('/login'); return
        ad_id = int(path.split('/')[-1])
        db = get_db()
        ad = db.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
        db.close()
        if not ad or ad['user_id'] != user['user_id']:
            self.redirect('/dashboard'); return
        cat_opts = ''.join([f"<option value='{c}' {'selected' if c==ad['category'] else ''}>{c}</option>" for c in self.get_categories()])
        city_opts = ''.join([f"<option value='{c}' {'selected' if c==ad['city'] else ''}>{c}</option>" for c in self.get_cities()])
        content = f'''
        <div class="card" style="max-width:700px;margin:auto">
            <h2 style="font-size:22px;font-weight:800;margin-bottom:28px">ویرایش آگهی</h2>
            <form method="POST" enctype="multipart/form-data">
                <input type="text" name="title" value="{ad['title']}" required>
                <textarea name="description" rows="5" required>{ad['description']}</textarea>
                <input type="text" name="price" value="{ad['price']}" required>
                <select name="category">{cat_opts}</select>
                <select name="city">{city_opts}</select>
                <select name="status">
                    <option value="active" {'selected' if ad['status']=='active' else ''}>فعال</option>
                    <option value="inactive" {'selected' if ad['status']=='inactive' else ''}>غیرفعال</option>
                </select>
                <div style="margin-top:18px"><input type="file" name="image1" accept="image/*"></div>
                <button class="btn btn-primary" style="width:100%;padding:16px;margin-top:10px">ذخیره تغییرات</button>
            </form>
        </div>
        '''
        self.send_page(html_template(content, 'ویرایش', user))

    def handle_edit_ad(self, path, user):
        if not user: self.redirect('/login'); return
        ad_id = int(path.split('/')[-1])
        ct = self.headers.get('Content-Type', '')
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        try:
            form = parse_multipart_form(ct, body)
        except:
            self.send_msg('خطا', f'/edit-ad/{ad_id}', ok=False); return
        
        title = form.get('title', [b''])[0].decode('utf-8', errors='ignore')
        description = form.get('description', [b''])[0].decode('utf-8', errors='ignore')
        price = form.get('price', [b''])[0].decode('utf-8', errors='ignore')
        category = form.get('category', [b''])[0].decode('utf-8', errors='ignore')
        city = form.get('city', [b''])[0].decode('utf-8', errors='ignore')
        status = form.get('status', [b'active'])[0].decode('utf-8', errors='ignore')
        img = save_uploaded_file(form.get('image1'))
        
        db = get_db()
        if img:
            db.execute("UPDATE ads SET title=?,description=?,price=?,city=?,category=?,status=?,image1=? WHERE id=? AND user_id=?",
                       (title,description,price,city,category,status,img,ad_id,user['user_id']))
        else:
            db.execute("UPDATE ads SET title=?,description=?,price=?,city=?,category=?,status=? WHERE id=? AND user_id=?",
                       (title,description,price,city,category,status,ad_id,user['user_id']))
        db.commit(); db.close()
        self.send_msg('تغییرات ذخیره شد', '/dashboard')

    def handle_delete_ad(self, path, user):
        if not user: self.redirect('/login'); return
        ad_id = int(path.split('/')[-1])
        db = get_db()
        ad = db.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
        if ad and ad['user_id'] == user['user_id']:
            for img in [ad['image1'],ad['image2'],ad['image3'],ad['image4']]:
                if img and os.path.exists(os.path.join(UPLOAD_DIR,img)):
                    try: os.remove(os.path.join(UPLOAD_DIR,img))
                    except: pass
            db.execute("DELETE FROM ads WHERE id=?", (ad_id,))
            db.commit()
        db.close()
        self.redirect('/dashboard')

    def handle_favorites(self, user):
        if not user: self.redirect('/login'); return
        db = get_db()
        favs = db.execute("SELECT a.* FROM favorites f JOIN ads a ON f.ad_id=a.id WHERE f.user_id=? ORDER BY f.created_at DESC", (user['user_id'],)).fetchall()
        db.close()
        content = f'''
        <div class="page-header"><h1>ذخیره‌ها</h1><p>آگهی‌های مورد علاقه شما</p></div>
        <div class="grid">{''.join([self.render_ad_card(a) for a in favs]) if favs else '<div class="card" style="text-align:center;padding:80px;grid-column:1/-1"><p style="color:rgba(255,255,255,0.4)">موردی ذخیره نکرده‌اید</p></div>'}</div>
        '''
        self.send_page(html_template(content, 'ذخیره‌ها', user))

    def handle_messages(self, user):
        if not user: self.redirect('/login'); return
        db = get_db()
        msgs = db.execute("SELECT m.*,a.title ad_title,u.full_name sender_name FROM messages m JOIN ads a ON m.ad_id=a.id JOIN users u ON m.sender_id=u.id WHERE m.receiver_id=? OR m.sender_id=? ORDER BY m.created_at DESC", (user['user_id'],user['user_id'])).fetchall()
        db.close()
        content = f'''
        <div class="page-header"><h1>پیام‌ها</h1><p>گفتگوهای شما در آرکا</p></div>
        {f'<div class="card">' + ''.join([f'<div style="display:flex;justify-content:space-between;align-items:center;padding:18px 0;border-bottom:1px solid rgba(255,255,255,0.05)"><div><strong style="font-size:14px">{msg["sender_name"]}</strong><div style="color:rgba(255,255,255,0.5);font-size:13px;margin:6px 0">{msg["content"][:80]}</div><div style="color:rgba(255,255,255,0.3);font-size:11px">📌 {msg["ad_title"]}</div></div><a href="/chat/{msg["ad_id"]}" class="btn btn-sm">باز کردن</a></div>' for msg in msgs]) + '</div>' if msgs else '<div class="card" style="text-align:center;padding:80px"><p style="color:rgba(255,255,255,0.4)">پیامی ندارید</p></div>'}
        '''
        self.send_page(html_template(content, 'پیام‌ها', user))

    def handle_chat_page(self, path, user):
        if not user: self.redirect('/login'); return
        ad_id = int(path.split('/')[-1])
        db = get_db()
        ad = db.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
        if not ad:
            db.close(); self.send_msg('آگهی نیست', '/', ok=False); return
        msgs = db.execute("SELECT * FROM messages WHERE ad_id=? AND (sender_id=? OR receiver_id=?) ORDER BY created_at", (ad_id,user['user_id'],user['user_id'])).fetchall()
        db.execute("UPDATE messages SET is_read=1 WHERE receiver_id=? AND ad_id=?", (user['user_id'],ad_id))
        db.commit(); db.close()
        
        msg_html = ''.join([f'<div class="chat-msg {"me" if m["sender_id"]==user["user_id"] else "other"}">{m["content"]}<small>{m["created_at"][:16]}</small></div>' for m in msgs])
        
        content = f'''
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:12px">
                <h2 style="font-size:18px;font-weight:800">💬 گفتگو: {ad['title']}</h2>
                <a href="/ad/{ad_id}" class="btn btn-sm btn-ghost">بازگشت</a>
            </div>
            <div class="chat-box" id="cb">{msg_html if msg_html else '<p style="text-align:center;color:rgba(255,255,255,0.3);padding:40px">اولین پیام را بفرستید</p>'}</div>
            <form method="POST" style="display:flex;gap:10px;margin-top:20px">
                <input type="text" name="content" placeholder="پیام خود را بنویسید..." required>
                <button type="submit" class="btn btn-primary">ارسال</button>
            </form>
        </div>
        <script>const b=document.getElementById('cb');if(b)b.scrollTop=b.scrollHeight;</script>
        '''
        self.send_page(html_template(content, 'گفتگو', user))

    def handle_chat(self, path, form, user):
        if not user: self.redirect('/login'); return
        ad_id = int(path.split('/')[-1])
        content = form.get('content', [''])[0]
        if content:
            db = get_db()
            ad = db.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
            if ad:
                db.execute("INSERT INTO messages (sender_id,receiver_id,ad_id,content,created_at) VALUES (?,?,?,?,?)",
                           (user['user_id'],ad['user_id'],ad_id,content,datetime.now().isoformat()))
                db.commit()
            db.close()
        self.redirect(f'/chat/{ad_id}')

    def handle_like(self, path, user):
        if not user: self.redirect('/login'); return
        ad_id = int(path.split('/')[-1])
        db = get_db()
        db.execute("UPDATE ads SET likes=likes+1 WHERE id=?", (ad_id,))
        db.commit(); db.close()
        self.redirect(f'/ad/{ad_id}')

    def handle_toggle_favorite(self, path, user):
        if not user: self.redirect('/login'); return
        ad_id = int(path.split('/')[-1])
        db = get_db()
        fav = db.execute("SELECT * FROM favorites WHERE user_id=? AND ad_id=?", (user['user_id'],ad_id)).fetchone()
        if fav:
            db.execute("DELETE FROM favorites WHERE user_id=? AND ad_id=?", (user['user_id'],ad_id))
        else:
            db.execute("INSERT INTO favorites (user_id,ad_id,created_at) VALUES (?,?,?)",
                       (user['user_id'],ad_id,datetime.now().isoformat()))
        db.commit(); db.close()
        self.redirect(self.headers.get('Referer', '/'))

# ===================== اجرا =====================
def run():
    init_db()
    port = 5000
    server = HTTPServer(('0.0.0.0', port), Handler)
    print('='*60)
    print('  🌌 ARKA  |  پلتفرم معاملات هوشمند')
    print('='*60)
    print(f'  ✅ سرور فعال: http://localhost:{port}')
    print(f'  👑 ادمین: 09123456789 / admin123')
    print('='*60)
    server.serve_forever()

if __name__ == '__main__':
    run()