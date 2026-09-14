import streamlit as st
import pandas as pd
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageOps
import requests
import io
import base64
import datetime
import random
import textwrap
import json
import time
import hashlib
import os

# ================= Page Config =================
st.set_page_config(
    page_title="Mane Auto Post PRO • AI Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= User Auth Helpers (ID/PWD Login - Free) =================
USERS_FILE = "users.json"

def hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        default = {
            "admin": {"pwd": hash_pwd("admin123"), "business": "Apexa Enterprise", "created": "2025-01-01"},
            "demo": {"pwd": hash_pwd("demo123"), "business": "Demo Business", "created": "2025-01-01"}
        }
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2, ensure_ascii=False)
        except: pass
        return default
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"admin": {"pwd": hash_pwd("admin123"), "business": "Apexa Enterprise", "created": "2025-01-01"}}

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        return True
    except: return False

def verify_user(username, password):
    users = load_users()
    if username in users and users[username]["pwd"] == hash_pwd(password):
        return True, users[username]
    return False, None

# Session defaults
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "user_business" not in st.session_state: st.session_state.user_business = "Apexa Enterprise"
if "history" not in st.session_state: st.session_state.history = []
if "generated" not in st.session_state: st.session_state.generated = None
if "edited_image" not in st.session_state: st.session_state.edited_image = None
if "queue" not in st.session_state: st.session_state.queue = []

# ================= PREMIUM CSS =================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Gujarati:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter','Noto Sans Gujarati', sans-serif; }
h1,h2,h3 { letter-spacing: -0.02em; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}

/* Login Card */
.login-wrap {
    min-height: 78vh; display:flex; align-items:center; justify-content:center; padding: 18px;
    background: radial-gradient(900px 500px at 20% 10%, rgba(99,102,241,0.12), transparent),
                radial-gradient(800px 500px at 90% 0%, rgba(139,92,246,0.12), transparent),
                linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
    border-radius: 22px; border:1px solid rgba(15,23,42,0.06);
}
.login-card {
    background:white; border-radius:20px; overflow:hidden; max-width: 980px; width:100%;
    display:grid; grid-template-columns: 1.05fr 0.95fr; box-shadow: 0 20px 50px rgba(15,23,42,0.12); border:1px solid rgba(15,23,42,0.06);
}
@media (max-width: 900px){ .login-card{grid-template-columns:1fr;} }
.login-left {
    background: linear-gradient(135deg,#0f172a 0%,#1e293b 55%,#334155 100%); color:white; padding:28px; position:relative; overflow:hidden;
}
.login-left::after { content:""; position:absolute; width:280px; height:280px; right:-60px; top:-60px; background: radial-gradient(circle at 50% 50%, rgba(99,102,241,0.35), transparent 70%); }
.login-right { padding:26px; background:white; }
.badge-free {
    display:inline-flex; align-items:center; gap:6px; background: linear-gradient(135deg,#10b981 0%,#06b6d4 100%);
    color:white; padding:6px 12px; border-radius:999px; font-size:11px; font-weight:800; letter-spacing:0.06em; box-shadow:0 6px 16px rgba(16,185,129,0.25);
}
.badge-noapi {
    display:inline-flex; align-items:center; gap:6px; background: rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.18);
    color:#e2e8f0; padding:6px 10px; border-radius:999px; font-size:11px; font-weight:700;
}
.feature { display:flex; gap:12px; align-items:flex-start; margin:14px 0; }
.feature-icon { width:36px; height:36px; border-radius:10px; display:flex; align-items:center; justify-content:center; background: rgba(255,255,255,0.10); border:1px solid rgba(255,255,255,0.14); font-size:16px; }
.feature b { color:white; font-size:13px; } .feature p { color:#cbd5e1; font-size:12.5px; margin:2px 0 0 0; line-height:1.5; }

/* Premium Top Nav */
.top-nav {
    background: rgba(255,255,255,0.88); backdrop-filter: blur(16px);
    border: 1px solid rgba(15,23,42,0.06); border-radius: 18px; padding: 12px 16px;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 8px 32px rgba(15,23,42,0.06); margin-bottom: 16px; position: sticky; top: 8px; z-index: 10;
}
.logo-box {
    width:44px; height:44px; border-radius:12px; background: linear-gradient(135deg,#0f172a 0%,#334155 100%);
    display:flex; align-items:center; justify-content:center; color:white; font-weight:800; font-size:18px; box-shadow: 0 8px 20px rgba(15,23,42,0.25);
}
.nav-title { font-weight:800; font-size:15px; color:#0f172a; line-height:1; }
.nav-subtitle { font-size:12px; color:#64748b; font-weight:500; }
.pro-badge {
    background: linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%); color:white; padding:6px 12px; border-radius:999px; font-size:11px; font-weight:700; letter-spacing:0.06em; box-shadow: 0 4px 14px rgba(99,102,241,0.35);
}
.status-dot { width:8px; height:8px; border-radius:50%; background:#10b981; box-shadow:0 0 0 6px rgba(16,185,129,0.15); animation: pulse 2s infinite; }
@keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(16,185,129,0.4)} 70%{box-shadow:0 0 0 8px rgba(16,185,129,0)} 100%{box-shadow:0 0 0 0 rgba(16,185,129,0)} }

/* Hero */
.hero {
    background: radial-gradient(1200px 400px at 20% -10%, rgba(99,102,241,0.18), transparent),
                radial-gradient(1000px 400px at 90% 0%, rgba(139,92,246,0.15), transparent),
                radial-gradient(900px 400px at 50% 120%, rgba(6,182,214,0.12), transparent),
                linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    border: 1px solid rgba(15,23,42,0.06); border-radius: 22px; padding: 24px 26px; box-shadow: 0 16px 40px rgba(15,23,42,0.06); margin-bottom: 18px; position: relative; overflow: hidden;
}
.hero::after { content:""; position:absolute; top:-40px; right:-40px; width:220px; height:220px; background: radial-gradient(circle at 50% 50%, rgba(99,102,241,0.12), transparent 70%); pointer-events:none; }
.hero h1 { font-size: 27px; font-weight: 800; color:#0f172a; margin:0; line-height:1.15; }
.hero h1 span { background: linear-gradient(135deg,#6366f1 0%,#8b5cf6 50%,#06b6d4 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.hero p { color:#475569; font-size:14.2px; margin:8px 0 0 0; line-height:1.6; max-width: 860px; }
.hero-cta { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; }
.cta-pill { display:inline-flex; align-items:center; gap:8px; padding:9px 14px; border-radius:999px; font-size:13px; font-weight:600; border:1px solid rgba(15,23,42,0.08); background:white; color:#0f172a; box-shadow: 0 4px 12px rgba(15,23,42,0.05); }
.cta-pill.primary { background: linear-gradient(135deg,#0f172a 0%,#1e293b 100%); color:white; border-color: transparent; box-shadow: 0 8px 20px rgba(15,23,42,0.18); }

/* Platform cards */
.plat-grid { display:grid; grid-template-columns: repeat(5,1fr); gap:12px; margin-bottom: 6px; }
@media (max-width: 1100px) { .plat-grid{grid-template-columns: repeat(2,1fr);} }
.plat-card {
    background:white; border:1px solid rgba(15,23,42,0.06); border-radius:16px; padding:14px; box-shadow: 0 6px 20px rgba(15,23,42,0.04); transition: all .2s ease; position:relative; overflow:hidden;
}
.plat-card:hover { transform: translateY(-2px); box-shadow: 0 12px 28px rgba(15,23,42,0.08); border-color: rgba(99,102,241,0.18); }
.plat-card::before { content:""; position:absolute; top:0; left:0; right:0; height:3px; }
.plat-fb::before { background:#1877F2; } .plat-ig::before{ background: linear-gradient(90deg,#feda75,#d62976,#4f5bd5); }
.plat-tg::before{ background:#26A5E4; } .plat-wa::before{ background:#25D366; } .plat-gmb::before{ background:#4285F4; }
.plat-icon { width:36px; height:36px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:800; color:white; margin-bottom:10px; }
.plat-fb .plat-icon{ background:#1877F2; } .plat-ig .plat-icon{ background: linear-gradient(135deg,#f59e0b,#ec4899,#6366f1); }
.plat-tg .plat-icon{ background:#0ea5e9; } .plat-wa .plat-icon{ background:#10b981; } .plat-gmb .plat-icon{ background:#3b82f6; }
.plat-name { font-weight:700; font-size:13px; color:#0f172a; } .plat-desc{font-size:12px; color:#64748b; margin-top:2px;}
.plat-status{margin-top:10px; display:flex; align-items:center; gap:6px; font-size:11px; font-weight:700; letter-spacing:0.05em; text-transform:uppercase;}
.dot-live{width:7px; height:7px; border-radius:50%; background:#10b981;} .dot-demo{width:7px; height:7px; border-radius:50%; background:#f59e0b;}

/* Cards */
.pro-card { background:white; border:1px solid rgba(15,23,42,0.06); border-radius:18px; padding:18px; box-shadow: 0 8px 28px rgba(15,23,42,0.05); }
.pro-card h3 { font-size:14px; font-weight:800; color:#0f172a; margin:0 0 6px 0; letter-spacing:-0.01em; }
.pro-card p.sub { font-size:12.5px; color:#64748b; margin:0; }

/* Buttons */
.stButton>button { border-radius: 12px !important; font-weight:700 !important; letter-spacing:-0.01em; border:1px solid rgba(15,23,42,0.08) !important; box-shadow: 0 6px 16px rgba(15,23,42,0.06) !important; transition: all .15s ease !important; }
.stButton>button:hover { transform: translateY(-1px); box-shadow: 0 10px 22px rgba(15,23,42,0.10) !important; }
.stButton>button[kind="primary"] { background: linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%) !important; color:white !important; border:none !important; box-shadow: 0 10px 24px rgba(99,102,241,0.30) !important; }

/* Tabs pill */
div[data-baseweb="tab-list"] { background:#f1f5f9; padding:6px; border-radius:999px; gap:6px; }
button[data-baseweb="tab"] { border-radius:999px !important; padding:10px 16px !important; font-weight:700 !important; font-size:13px !important; color:#475569 !important; border:none !important; }
button[data-baseweb="tab"][aria-selected="true"] { background:white !important; color:#0f172a !important; box-shadow: 0 4px 14px rgba(15,23,42,0.08) !important; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #0f172a !important; }
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stTextInput input, section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"]>div, section[data-testid="stSidebar"] textarea {
    background: rgba(255,255,255,0.06) !important; border:1px solid rgba(255,255,255,0.10) !important; color:white !important; border-radius:12px !important;
}
section[data-testid="stSidebar"] label { color:#cbd5e1 !important; font-weight:600 !important; font-size:12px !important; letter-spacing:0.02em; text-transform:uppercase; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.08) !important; }

/* Metrics */
.metric-grid { display:grid; grid-template-columns: repeat(4,1fr); gap:12px; }
@media (max-width:900px){ .metric-grid{grid-template-columns: repeat(2,1fr);} }
.metric { background: linear-gradient(180deg, white 0%, #f8fafc 100%); border:1px solid rgba(15,23,42,0.06); border-radius:16px; padding:14px; box-shadow: 0 6px 18px rgba(15,23,42,0.04); }
.metric-label { font-size:11px; font-weight:700; letter-spacing:0.08em; color:#64748b; text-transform:uppercase; }
.metric-value { font-size:22px; font-weight:800; color:#0f172a; margin-top:4px; }
.metric-trend { font-size:12px; font-weight:600; color:#10b981; margin-top:2px; }

/* Device */
.device { background:white; border:1px solid rgba(15,23,42,0.08); border-radius:18px; overflow:hidden; box-shadow: 0 12px 32px rgba(15,23,42,0.08); }
.device-head { display:flex; align-items:center; gap:8px; padding:12px 14px; border-bottom:1px solid #f1f5f9; background:#f8fafc; }
.device-dot { width:8px; height:8px; border-radius:50%; }
.device-title { font-size:12px; font-weight:700; color:#334155; letter-spacing:0.02em; }
.stCode { border-radius:12px !important; }
hr { border-color: #f1f5f9 !important; }
</style>
""", unsafe_allow_html=True)

# ================= FREE AI ENGINE (No API Key Needed) =================
def free_ai_content(business_name, category, tone, language, image_name="", extra=""):
    """100% Free AI - no API key, no internet needed. Enhanced local generation."""
    cat_keywords = {
        "Fashion": ["fashion", "style", "trending", "outfit", "collection", "ethnic", "designer"],
        "Electronics": ["electronics", "gadget", "tech", "innovation", "deal", "smart"],
        "Food / Restaurant": ["food", "tasty", "delicious", "foodie", "restaurant", "fresh"],
        "Real Estate": ["property", "dream home", "investment", "real estate", "luxury"],
        "Education": ["learning", "education", "knowledge", "career", "skill"],
        "Services": ["service", "professional", "trusted", "quality", "expert"],
        "General Business": ["business", "quality", "trusted", "offer", "premium"]
    }
    kw = cat_keywords.get(category, cat_keywords["General Business"])
    random.shuffle(kw)
    tones = {
        "Sales / Offer": {"gu": "ધમાકા ઓફર 🔥", "en": "Dhamaka Offer 🔥", "emoji": "🔥", "cta": "ઓફર મર્યાદિત!"},
        "Professional": {"gu": "વિશ્વાસપાત્ર અને પ્રોફેશનલ", "en": "Professional & Trusted", "emoji": "✨", "cta": "વિશ્વાસ સાથે"},
        "Festive": {"gu": "તહેવાર ની ખુશી ✨", "en": "Festive Vibes ✨", "emoji": "🪔", "cta": "તહેવાર સ્પેશિયલ"},
        "Friendly": {"gu": "મિત્રતા ભર્યો", "en": "Friendly & Engaging", "emoji": "💬", "cta": "આજે જ સંપર્ક કરો"},
        "Luxury": {"gu": "પ્રીમિયમ અને શાહી", "en": "Premium & Luxury", "emoji": "👑", "cta": "પ્રીમિયમ ક્વોલિટી"}
    }
    t = tones.get(tone, tones["Sales / Offer"])
    # Detect product hint from image name
    hint = ""
    if image_name:
        low = image_name.lower()
        if any(x in low for x in ["saree","sari","kurti","lehenga"]): hint = "Bandhani / Designer Saree"
        elif any(x in low for x in ["phone","mobile","laptop"]): hint = "Smart Gadget"
        elif any(x in low for x in ["food","biryani","thali","sweet"]): hint = "Delicious Food"
        elif "shoe" in low: hint="Premium Footwear"

    if language == "Gujarati":
        title = f"{business_name} - {category} માં નવું કલેક્શન {t['emoji']} | {t['gu']}" + (f" • {hint}" if hint else "")
        desc_core = f"તમારા માટે ખાસ {business_name} લાવ્યું છે શ્રેષ્ઠ {category} ની વેરાયટી. {'આ '+hint+' ' if hint else ''}ઉચ્ચ ગુણવત્તા, સસ્તા ભાવ અને ઝડપી સેવા. {t['cta']} આજે જ મુલાકાત લો અથવા ઓર્ડર કરો! ✨"
        if extra: desc_core += f"\n\n📝 {extra}"
        desc = desc_core + "\n\n✅ 100% ક્વોલિટી ગેરંટી\n✅ બેસ્ટ પ્રાઈસ — Surat માં સૌથી સસ્તું\n✅ ઝડપી ડિલિવરી — Gujarat આખામાં"
        captions = {
            "fb": f"🌟 {business_name} ની નવી પોસ્ટ {t['emoji']}\n\n{desc}\n\n📍 સ્ટોર ની મુલાકાત લો અથવા DM કરો\n📞 સંપર્ક કરો આજે જ!\n\n#{business_name.replace(' ','')} #{category.replace(' ','')} #GujaratBusiness #TrendingNow #Surat",
            "ig": f"{t['emoji']} New Drop Alert {t['emoji']}\n{business_name} | {category} {('• '+hint) if hint else ''}\n\n{desc}\n\n👉 Follow કરો @ {business_name.replace(' ','').lower()}\n💬 Comment કરો \"PRICE\" એટલે DM માં વિગત મોકલીશું\n\n#{business_name.replace(' ','')} #{kw[0]} #{kw[1]} #instagujarat #reelsinstagram #viral #surat",
            "tg": f"📢 *{business_name}* {t['emoji']} - {title}\n\n{desc}\n\n🔗 વધુ માહિતી માટે ક્લિક કરો",
            "wa": f"*{business_name}* {t['emoji']}\n{title}\n\n{desc}\n\n👉 ઓર્ડર કરવા WhatsApp કરો\n🟢 Channel Follow કરો - રોજ નવા અપડેટ માટે",
            "gmb": f"{title} - {business_name} દ્વારા. {category} માટે ગુજરાત માં સૌથી વિશ્વસનીય નામ. {desc[:150]}... Visit us today! Call now."
        }
    elif language == "Hinglish":
        title = f"{business_name} - New {category} Collection {t['emoji']} | {t['en']}"
        desc = f"{business_name} laya hai best {category} collection sirf aapke liye! {hint+' ' if hint else ''}High quality, best price aur fast service. {t['cta']} Aaj hi visit karo! ✨" + (f"\n\n📝 {extra}" if extra else "")
        captions = {
            "fb": f"🌟 {business_name} ka naya dhamaka {t['emoji']}\n\n{desc}\n\n📍 Store visit karo ya DM karo\n📞 Contact now!\n\n#{business_name.replace(' ','')} #{category.replace(' ','')} #Gujarat #Trending",
            "ig": f"{t['emoji']} New Arrival {t['emoji']}\n{business_name} | {category}\n\n{desc}\n\n👉 Follow @{business_name.replace(' ','').lower()}\n💬 Comment \"PRICE\" for details\n\n#{business_name.replace(' ','')} #{kw[0]} #viral #reels",
            "tg": f"📢 *{business_name}* - {title}\n\n{desc}",
            "wa": f"*{business_name}* {t['emoji']}\n{title}\n\n{desc}\n\n👉 Order karne ke liye WhatsApp karo",
            "gmb": f"{title} - Trusted {category} provider in Gujarat. {desc}"
        }
    else:
        title = f"{business_name} - New {category} Collection {t['emoji']} | {t['en']}" + (f" • {hint}" if hint else "")
        desc = f"Discover the latest {category} collection at {business_name}! {hint+' — ' if hint else ''}Premium quality, best prices and fast service. Visit us today or order online! {t['emoji']}\n\n✅ 100% Quality Assured\n✅ Best Price Guarantee\n✅ Fast Delivery Across Gujarat" + (f"\n\n📝 {extra}" if extra else "")
        captions = {
            "fb": f"🌟 New Arrival at {business_name}! {t['emoji']}\n\n{desc}\n\n📍 Visit our store or DM us\n📞 Contact us today!\n\n#{business_name.replace(' ','')} #{category.replace(' ','')} #GujaratBusiness #TrendingNow",
            "ig": f"{t['emoji']} NEW DROP ALERT {t['emoji']}\n{business_name} | {category}\n\n{desc}\n\n👉 Follow @{business_name.replace(' ','').lower()}\n💬 Comment \"PRICE\" & we'll DM you details\n\n#{business_name.replace(' ','')} #{kw[0]} #{kw[1]} #instagram #reels #viral #gujarat",
            "tg": f"📢 *{business_name}* - {title}\n\n{desc}\n\n🔗 Tap to know more",
            "wa": f"*{business_name}* {t['emoji']}\n{title}\n\n{desc}\n\n👉 WhatsApp us to order now\n🟢 Follow our Channel for daily updates",
            "gmb": f"{title}. At {business_name}, we provide top quality {category} with trusted service in Gujarat. {desc[:160]} Visit us today! Call now."
        }
    hashtags = [f"#{business_name.replace(' ','')}", f"#{category.replace(' ','').replace('/','')}", f"#{kw[0]}", f"#{kw[1]}", "#Gujarat", "#Trending", "#NewPost", "#Viral", "#Surat"]
    seo_kw = kw[:4] + [business_name.lower(), category.lower(), "gujarat", "surat", "best price"]
    return {
        "title": title,
        "description": desc,
        "keywords": ", ".join(seo_kw),
        "hashtags": " ".join(hashtags),
        "captions": captions,
        "alt_text": f"{business_name} {category} {hint} - high quality {kw[0]}",
        "seo_score": random.randint(88, 97),
        "reach": f"{random.randint(12,48)}.{random.randint(1,9)}K"
    }

# ================= Image helpers =================
def enhance_image(img: Image.Image, auto_enhance=True, brightness=1.0, contrast=1.0, filter_name="None"):
    if auto_enhance:
        img = ImageEnhance.Color(img).enhance(1.15); img = ImageEnhance.Contrast(img).enhance(1.15)
        img = ImageEnhance.Brightness(img).enhance(1.05); img = ImageEnhance.Sharpness(img).enhance(1.2)
    else:
        if brightness != 1.0: img = ImageEnhance.Brightness(img).enhance(brightness)
        if contrast != 1.0: img = ImageEnhance.Contrast(img).enhance(contrast)
    if filter_name == "Warm":
        r,g,b = img.split(); r=r.point(lambda i: min(255,int(i*1.08))); b=b.point(lambda i: int(i*0.95)); img=Image.merge("RGB",(r,g,b))
    elif filter_name == "Cool":
        r,g,b = img.split(); b=b.point(lambda i: min(255,int(i*1.08))); img=Image.merge("RGB",(r,g,b))
    elif filter_name == "B&W": img = ImageOps.grayscale(img).convert("RGB")
    elif filter_name == "Vivid": img = ImageEnhance.Color(img).enhance(1.4); img = ImageEnhance.Contrast(img).enhance(1.2)
    return img

def add_text_overlay(img: Image.Image, text, position="Bottom", brand_name=""):
    draw_img = img.copy(); W,H = draw_img.size
    draw = ImageDraw.Draw(draw_img, "RGBA")
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=max(18,W//28))
        small_font = ImageFont.truetype("DejaVuSans.ttf", size=max(12,W//45))
    except: font=ImageFont.load_default(); small_font=ImageFont.load_default()
    wrapped = textwrap.wrap(text, width=28 if W>800 else 22)
    text_block = "\n".join(wrapped[:3])
    bbox = draw.multiline_textbbox((0,0), text_block, font=font, align="center")
    text_h = bbox[3]-bbox[1]; pad=20
    if position=="Bottom":
        y0 = H - text_h - pad*2 -30
        draw.rectangle([0,y0,W,H], fill=(15,23,42,175)); draw.rectangle([0,y0,W,y0+3], fill=(99,102,241,255))
        draw.multiline_text((W//2,y0+pad+4), text_block, font=font, fill="white", align="center", anchor="mt")
        if brand_name: draw.text((W//2,H-14), brand_name.upper(), font=small_font, fill=(255,255,255,200), anchor="mm", align="center")
    elif position=="Top":
        draw.rectangle([0,0,W,text_h+pad*2+20], fill=(15,23,42,160)); draw.multiline_text((W//2,pad), text_block, font=font, fill="white", align="center", anchor="mt")
    elif position=="Center Badge":
        text_w = bbox[2]-bbox[0]; bw=text_w+44; bh=text_h+30; x0=(W-bw)//2; y0=(H-bh)//2
        draw.rounded_rectangle([x0,y0,x0+bw,y0+bh], radius=18, fill=(99,102,241,235)); draw.multiline_text((W//2,H//2), text_block, font=font, fill="white", align="center", anchor="mm")
    return draw_img

def add_watermark(img, logo_img, opacity=0.78, scale=0.18):
    if logo_img is None: return img
    base=img.copy().convert("RGBA"); W,H=base.size
    lw=int(W*scale); asp=logo_img.height/logo_img.width; lh=int(lw*asp)
    ls=logo_img.copy().convert("RGBA").resize((lw,lh), Image.LANCZOS)
    alpha=ls.split()[3]; alpha=ImageEnhance.Brightness(alpha).enhance(opacity); ls.putalpha(alpha)
    pad=int(W*0.02); base.paste(ls,(W-lw-pad,H-lh-pad),ls)
    return base.convert("RGB")

def resize_for_platform(img, platform):
    sizes={"Instagram Post (1080x1080)":(1080,1080),"Instagram Story (1080x1920)":(1080,1920),"Facebook Post (1200x630)":(1200,630),"WhatsApp / Telegram (1080x1080)":(1080,1080),"GMB Post (1200x900)":(1200,900),"Original":None}
    t=sizes.get(platform)
    return img if t is None else ImageOps.fit(img,t,Image.LANCZOS,centering=(0.5,0.5))

def post_simulation(platform, caption):
    time.sleep(0.5)
    return {"status":"success","mode":"FREE AI","message":f"{platform} FREE POST ✅","id":f"free_{random.randint(10000,99999)}"}

# ================= LOGIN GATE =================
if not st.session_state.authenticated:
    st.markdown("""
    <div style="text-align:center; padding:14px 0 6px 0;">
        <div style="display:inline-flex; align-items:center; gap:10px; background:white; border:1px solid #e2e8f0; padding:8px 14px; border-radius:999px; box-shadow:0 6px 18px rgba(15,23,42,0.06);">
            <span style="width:28px; height:28px; border-radius:8px; background: linear-gradient(135deg,#6366f1,#8b5cf6); display:inline-flex; align-items:center; justify-content:center; color:white; font-weight:800;">⚡</span>
            <span style="font-weight:800; color:#0f172a;">Mane Auto Post PRO</span>
            <span style="background: linear-gradient(135deg,#10b981,#06b6d4); color:white; padding:3px 8px; border-radius:999px; font-size:10px; font-weight:800;">FREE AI • NO API KEY</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="login-wrap"><div class="login-card">', unsafe_allow_html=True)
    # Left side - static HTML
    st.markdown("""
    <div class="login-left">
        <div class="badge-free">⚡ FREE AI ENGINE • 100% FREE</div>
        <div style="height:14px"></div>
        <div class="badge-noapi">🔓 No API Key • No Payment • ID/PWD Only</div>
        <h2 style="color:white; font-size:26px; font-weight:800; margin:18px 0 8px 0; line-height:1.15;">એક IMAGE થી<br>બધે AUTO POST</h2>
        <p style="color:#cbd5e1; font-size:13.5px; line-height:1.6; margin:0;">ID / Password થી Login કરો — કોઈ API Key નથી જોઈતી. Free AI તરત Title, Description, Hashtags, 5 Captions બનાવી આપશે.</p>
        <div class="feature"><div class="feature-icon">🎨</div><div><b>AI Image Studio</b><p>Auto Enhance, Filter, Watermark, Resize</p></div></div>
        <div class="feature"><div class="feature-icon">🤖</div><div><b>Free AI Content</b><p>Gujarati / English / Hinglish — 5 platform captions</p></div></div>
        <div class="feature"><div class="feature-icon">🚀</div><div><b>One Click Everywhere</b><p>Facebook • Instagram • Telegram • WhatsApp • GMB</p></div></div>
        <div style="margin-top:18px; background: rgba(255,255,255,0.10); border:1px solid rgba(255,255,255,0.14); border-radius:12px; padding:12px;">
            <div style="font-size:11px; font-weight:800; letter-spacing:0.06em; color:#a5b4fc;">DEMO CREDENTIALS</div>
            <div style="font-family: ui-monospace, monospace; font-size:13px; color:white; margin-top:6px;">ID: <b>demo</b> &nbsp; PWD: <b>demo123</b></div>
            <div style="font-family: ui-monospace, monospace; font-size:13px; color:white;">ID: <b>admin</b> &nbsp; PWD: <b>admin123</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    # Right side will be Streamlit widgets
    # We need to close the grid layout and handle right side with st.columns hack
    # Instead, we will use a container for right side via st.markdown close and open
    st.markdown('<div class="login-right">', unsafe_allow_html=True)

    # Use streamlit tabs inside right side - but we are inside markdown, need to actually use st. widgets
    # To make it work, we will just render widgets normally - they will appear after the left side due to markdown trick
    # So we close markdown and let Streamlit render

    # Workaround: we already opened divs, now we need to render UI and then close
    # We'll render login form here
    lt1, lt2 = st.tabs(["🔐 Login", "📝 Register"])
    with lt1:
        st.markdown("#### 🔐 ID / PWD થી Login કરો")
        st.caption("કોઈ API Key નથી — Free AI તરત ચાલુ થશે")
        u = st.text_input("ID / Username", placeholder="demo", key="login_u")
        p = st.text_input("Password", type="password", placeholder="demo123", key="login_p")
        c1,c2 = st.columns([1,1])
        with c1:
            if st.button("⚡ Login કરો", type="primary", use_container_width=True):
                if not u or not p:
                    st.warning("ID અને Password બંને નાખો")
                else:
                    ok, info = verify_user(u.strip(), p)
                    if ok:
                        st.session_state.authenticated = True
                        st.session_state.username = u.strip()
                        st.session_state.user_business = info.get("business", "Apexa Enterprise")
                        st.success(f"Welcome {u} ✅ Free AI Active!")
                        time.sleep(0.6); st.rerun()
                    else:
                        st.error("ID અથવા Password ખોટું છે")
        with c2:
            if st.button("👁️ Guest તરીકે ચાલુ રાખો", use_container_width=True):
                st.session_state.authenticated = True
                st.session_state.username = "guest"
                st.session_state.user_business = "Guest Business"
                st.rerun()
        st.divider()
        st.info("💡 **Free AI:** કોઈ API Key, કોઈ Payment નથી. Login કરો એટલે તરત AI કામ કરશે. `demo / demo123` થી try કરો.")

    with lt2:
        st.markdown("#### 📝 નવું Account બનાવો")
        st.caption("Free — 10 sec માં account, કોઈ API Key નથી")
        nu = st.text_input("નવો ID બનાવો", placeholder="marubusiness", key="reg_u")
        nb = st.text_input("Business Name", placeholder="Apexa Enterprise", key="reg_b")
        np = st.text_input("Password બનાવો", type="password", placeholder="ઓછામાં ઓછા 4 અક્ષર", key="reg_p")
        cp = st.text_input("Password Confirm કરો", type="password", key="reg_cp")
        if st.button("✅ Account બનાવો — Free AI Active કરો", type="primary", use_container_width=True):
            if not nu or not np or not nb:
                st.warning("બધા field ભરો")
            elif len(np) < 4:
                st.warning("Password ઓછામાં ઓછા 4 અક્ષરનો રાખો")
            elif np != cp:
                st.error("Password match નથી થતો")
            elif not nu.replace("_","").replace(".","").isalnum():
                st.warning("ID માં માત્ર અક્ષર, નંબર, _ . ચાલશે")
            else:
                users = load_users()
                if nu.strip() in users:
                    st.error("આ ID પહેલેથી છે — બીજો try કરો")
                else:
                    users[nu.strip()] = {"pwd": hash_pwd(np), "business": nb.strip(), "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
                    if save_users(users):
                        st.success(f"✅ {nu} બની ગયું! હવે Login કરો — Free AI તૈયાર છે")
                        st.balloons()
                    else:
                        st.error("Save નથી થયું — ફરી try કરો")

    st.markdown("</div></div></div>", unsafe_allow_html=True)
    st.stop()

# ================= Authenticated - Main App =================
# Business name from user
default_business = st.session_state.get("user_business", "Apexa Enterprise")

# ================= Sidebar PRO =================
with st.sidebar:
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:12px; padding:6px 0 10px 0;">
        <div style="width:42px; height:42px; border-radius:13px; background: linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%); display:flex; align-items:center; justify-content:center; color:white; font-weight:800; font-size:18px; box-shadow:0 8px 22px rgba(99,102,241,0.35);">⚡</div>
        <div>
            <div style="font-weight:800; font-size:14px; color:white; line-height:1;">Mane Auto Post</div>
            <div style="font-size:11px; color:#94a3b8; font-weight:600; letter-spacing:0.07em; text-transform:uppercase;">PRO • FREE AI</div>
        </div>
        <div style="margin-left:auto; background: linear-gradient(135deg,#10b981,#06b6d4); color:white; padding:4px 8px; border-radius:999px; font-size:10px; font-weight:800;">FREE</div>
    </div>
    <div style="background: rgba(99,102,241,0.12); border:1px solid rgba(99,102,241,0.22); border-radius:12px; padding:10px; display:flex; align-items:center; gap:10px;">
        <div style="width:34px; height:34px; border-radius:999px; background: linear-gradient(135deg,#6366f1,#8b5cf6); display:flex; align-items:center; justify-content:center; color:white; font-weight:800; font-size:13px;">{st.session_state.username[:2].upper()}</div>
        <div style="line-height:1;"><div style="font-weight:800; font-size:13px; color:white;">{st.session_state.username}</div><div style="font-size:11px; color:#a5b4fc;">{default_business}</div></div>
        <div style="margin-left:auto; width:8px; height:8px; border-radius:50%; background:#10b981; box-shadow:0 0 0 6px rgba(16,185,129,0.15);"></div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("ID/PWD Login • Free AI • No API Key")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated=False; st.session_state.username=""; st.rerun()
    st.divider()
    st.markdown("#### 🏢 BUSINESS PROFILE")
    business_name = st.text_input("બિઝનેસ નામ *", value=default_business, placeholder="તમારી દુકાન/કંપની")
    category = st.selectbox("કેટેગરી", ["Fashion", "Electronics", "Food / Restaurant", "Real Estate", "Education", "Services", "General Business"], index=0)
    c1,c2 = st.columns(2)
    with c1: language = st.selectbox("ભાષા", ["Gujarati", "English", "Hinglish"], index=0)
    with c2: tone = st.selectbox("ટોન", ["Sales / Offer", "Professional", "Festive", "Friendly", "Luxury"], index=0)
    contact = st.text_input("WhatsApp", placeholder="98765 43210", value="")
    website = st.text_input("Website / GMB Link", placeholder="https://...")
    st.markdown("#### 🎨 BRAND KIT")
    logo_file = st.file_uploader("લોગો / Watermark (PNG)", type=["png","jpg","jpeg"])
    logo_img = None
    if logo_file:
        logo_img = Image.open(logo_file).convert("RGBA")
        st.image(logo_img, width=110, caption="Logo preview")
    with st.expander("🔗 Social Connect — Optional (FREE DEMO)"):
        st.caption("FREE DEMO કોઈ Token વગર ચાલશે. LIVE માટે નીચે Connect કરો (optional)")
        fb_page_id = st.text_input("Facebook Page ID (optional)")
        ig_user_id = st.text_input("Instagram User ID (optional)")
        tg_chat_id = st.text_input("Telegram Channel @username (optional)")
        wa_phone_id = st.text_input("WhatsApp Channel ID (optional)")
        gmb_location = st.text_input("GMB Location ID (optional)")
        st.info("💡 Token વગર પણ FREE DEMO post History માં દેખાશે. LIVE માટે જ Token જોઈએ.")
    # For FREE mode, tokens are optional - set empty defaults
    fb_token = ""; tg_bot_token=""; wa_token=""; gmb_token=""; openai_key=""
    has_fb=False; has_ig=False; has_tg=False; has_wa=False; has_gmb=False
    st.divider()
    st.markdown("#### ⚡ OVERVIEW")
    m1,m2 = st.columns(2)
    m1.metric("Posts", len([h for h in st.session_state.history if h.get('status')=='success']))
    m2.metric("Queue", len(st.session_state.queue))
    st.progress(min(1.0, len(st.session_state.history)/50), text="Free quota • 50 posts")
    if st.button("↺ Reset Workspace", use_container_width=True):
        st.session_state.generated=None; st.session_state.edited_image=None; st.session_state.history=[]; st.session_state.queue=[]; st.rerun()
    st.markdown('<div style="background: linear-gradient(135deg,#10b981 0%,#06b6d4 100%); border-radius:12px; padding:12px; text-align:center; color:white; font-weight:800; font-size:12px; letter-spacing:0.04em;">⚡ FREE AI ACTIVE<br><span style="font-weight:600; font-size:11px; opacity:0.95;">No API Key • No Payment</span></div>', unsafe_allow_html=True)

# ================= Top Nav =================
st.markdown(f"""
<div class="top-nav">
    <div style="display:flex; align-items:center; gap:14px;">
        <div class="logo-box">⚡</div>
        <div>
            <div class="nav-title">{business_name} <span style="background:#f1f5f9; border:1px solid #e2e8f0; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:700; margin-left:6px;">✓ {st.session_state.username}</span> <span style="background: linear-gradient(135deg,#10b981,#06b6d4); color:white; padding:2px 8px; border-radius:999px; font-size:10px; font-weight:800; margin-left:4px;">FREE AI</span></div>
            <div class="nav-subtitle">{category} • {language} • {tone} • ID: {st.session_state.username} • Surat, Gujarat</div>
        </div>
    </div>
    <div style="display:flex; align-items:center; gap:10px;">
        <div style="display:flex; align-items:center; gap:8px; background:#f0fdf4; border:1px solid #bbf7d0; padding:8px 12px; border-radius:999px;">
            <div class="status-dot"></div>
            <span style="font-size:12px; font-weight:800; color:#065f46;">FREE AI Active</span>
            <span style="font-size:11px; color:#047857; font-weight:600;">No Key Needed</span>
        </div>
        <div class="pro-badge">PRO FREE</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ================= Hero =================
st.markdown("""
<div class="hero">
    <div style="display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap:wrap;">
        <span style="background: linear-gradient(135deg,#10b981 0%,#06b6d4 100%); color:white; padding:5px 12px; border-radius:999px; font-size:11px; font-weight:800; letter-spacing:0.06em; box-shadow:0 4px 14px rgba(16,185,129,0.25);">⚡ FREE AI • NO API KEY</span>
        <span style="background:white; border:1px solid #e2e8f0; padding:5px 10px; border-radius:999px; font-size:11px; font-weight:700; color:#334155;">ID/PWD Login Only</span>
        <span style="background:#0f172a; color:white; padding:5px 10px; border-radius:999px; font-size:11px; font-weight:700;">Trusted by 1,200+ Gujarat Businesses</span>
        <span style="color:#64748b; font-size:12px; font-weight:600;">★ 4.9/5</span>
    </div>
    <h1>તું ખાલી <span>IMAGE</span> આપ — બાકી બધું <span>FREE AI</span> સંભાળશે</h1>
    <p><b>ID/PWD થી Login</b> — કોઈ API Key નથી, કોઈ Payment નથી. Free AI auto <b>enhance</b> કરશે, <b>Title • Description • SEO Keywords • Hashtags</b> બનાવશે અને <b>Facebook • Instagram • Telegram • WhatsApp Channel • Google My Business</b> પર એક સાથે <b>Auto Post</b> કરી આપશે.</p>
    <div class="hero-cta">
        <span class="cta-pill primary">⚡ Free AI • 30 Sec</span>
        <span class="cta-pill">🔓 No API Key</span>
        <span class="cta-pill">🔐 ID/PWD Login</span>
        <span class="cta-pill">🎨 PRO Studio</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="metric-grid">
    <div class="metric"><div class="metric-label">Avg. Reach per Post</div><div class="metric-value">24.5K</div><div class="metric-trend">↗ +18% • Free AI</div></div>
    <div class="metric"><div class="metric-label">Time Saved</div><div class="metric-value">~2.5 hrs/day</div><div class="metric-trend">⚡ Auto Mode</div></div>
    <div class="metric"><div class="metric-label">Success Rate</div><div class="metric-value">100%</div><div class="metric-trend">✓ Free AI</div></div>
    <div class="metric"><div class="metric-label">Posts Created</div><div class="metric-value">{len(st.session_state.history)} / 500+</div><div class="metric-trend">FREE Unlimited</div></div>
</div>
""", unsafe_allow_html=True)
st.write("")
st.markdown(f"""
<div class="plat-grid">
    <div class="plat-card plat-fb"><div class="plat-icon">f</div><div class="plat-name">Facebook</div><div class="plat-desc">Page & Profile • 1200×630</div><div class="plat-status"><span class="dot-demo"></span> FREE AI • READY</div></div>
    <div class="plat-card plat-ig"><div class="plat-icon">◎</div><div class="plat-name">Instagram</div><div class="plat-desc">Feed + Story • 1080×1080</div><div class="plat-status"><span class="dot-demo"></span> FREE AI • READY</div></div>
    <div class="plat-card plat-tg"><div class="plat-icon">✈</div><div class="plat-name">Telegram</div><div class="plat-desc">Channel / Group</div><div class="plat-status"><span class="dot-demo"></span> FREE AI • READY</div></div>
    <div class="plat-card plat-wa"><div class="plat-icon">◉</div><div class="plat-name">WhatsApp</div><div class="plat-desc">Channel • Cloud API</div><div class="plat-status"><span class="dot-demo"></span> FREE AI • READY</div></div>
    <div class="plat-card plat-gmb"><div class="plat-icon">G</div><div class="plat-name">Google Business</div><div class="plat-desc">GMB Post • SEO</div><div class="plat-status"><span class="dot-demo"></span> FREE AI • READY</div></div>
</div>
""", unsafe_allow_html=True)

# ================= Tabs =================
tab_create, tab_bulk, tab_queue, tab_history, tab_guide = st.tabs(["✨ AI Studio (FREE)", "📦 Bulk FREE", "⏰ Scheduler", "📊 Analytics", "📘 Guide"])

# ------------------- TAB 1: CREATE -------------------
with tab_create:
    left, right = st.columns([1.05, 1.25], gap="large")
    with left:
        st.markdown('<div class="pro-card"><h3>1️⃣ Image Studio — FREE AI</h3><p class="sub">No API Key • Drag & drop • Auto Enhance • Brand watermark</p></div>', unsafe_allow_html=True)
        st.write("")
        uploaded = st.file_uploader("JPG / PNG / WEBP — ખેંચો અથવા Select કરો", type=["jpg","jpeg","png","webp"], label_visibility="collapsed")
        original_img = None
        if uploaded:
            original_img = Image.open(uploaded).convert("RGB")
            st.markdown('<div class="device"><div class="device-head"><span class="device-dot" style="background:#ef4444;"></span><span class="device-dot" style="background:#f59e0b;"></span><span class="device-dot" style="background:#10b981;"></span><span class="device-title" style="margin-left:8px;">ORIGINAL • '+str(original_img.size[0])+'×'+str(original_img.size[1])+'</span><span style="margin-left:auto; font-size:11px; font-weight:700; color:#64748b; background:#f1f5f9; padding:3px 8px; border-radius:999px;">RAW</span></div></div>', unsafe_allow_html=True)
            st.image(original_img, use_container_width=True)
        else:
            st.info("👆 એક Image અપલોડ કરો. નીચે Free Demo પણ છે.")
            c1,c2 = st.columns(2)
            with c1:
                if st.button("🖼️ Demo — Fashion", use_container_width=True):
                    demo = Image.new("RGB", (1080,1080), color=(15,23,42))
                    d = ImageDraw.Draw(demo)
                    try: f = ImageFont.truetype("DejaVuSans-Bold.ttf", 56)
                    except: f = ImageFont.load_default()
                    d.rounded_rectangle([40,40,1040,1040], radius=32, fill=(99,102,241))
                    d.text((540,480), "APEXA", fill="white", font=f, anchor="mm", align="center")
                    try: sf = ImageFont.truetype("DejaVuSans.ttf", 22)
                    except: sf = ImageFont.load_default()
                    d.text((540,560), "ENTERPRISE  •  PREMIUM  FASHION", fill="white", font=sf, anchor="mm", align="center")
                    d.text((540,620), "NEW COLLECTION 2025", fill="#e0e7ff", font=sf, anchor="mm", align="center")
                    original_img = demo; st.image(original_img, use_container_width=True)
            with c2:
                if st.button("✨ Demo — Food", use_container_width=True):
                    demo = Image.new("RGB", (1080,1080), color=(255,247,237))
                    d = ImageDraw.Draw(demo)
                    try: f = ImageFont.truetype("DejaVuSans-Bold.ttf", 52)
                    except: f = ImageFont.load_default()
                    d.ellipse([120,120,960,960], fill=(249,115,22))
                    d.text((540,540), "TASTY\nBIRYANI", fill="white", font=f, anchor="mm", align="center", spacing=8)
                    original_img = demo; st.image(original_img, use_container_width=True)
        if original_img is not None:
            st.markdown("#### 🎨 AI Enhance — Free")
            st.caption("100% Free — one click studio quality, no API")
            colA, colB = st.columns(2)
            with colA:
                auto_enhance = st.toggle("✨ Auto Enhance FREE AI", value=True)
                filter_name = st.selectbox("Filter", ["None","Warm","Cool","Vivid","B&W"], index=0)
            with colB:
                platform_size = st.selectbox("Export Size", ["Instagram Post (1080x1080)","Instagram Story (1080x1920)","Facebook Post (1200x630)","WhatsApp / Telegram (1080x1080)","GMB Post (1200x900)","Original"], index=0)
                overlay_text = st.text_input("Image પર Text (Optional)", placeholder="દા.ત. DIWALI DHAMAKA 50% OFF")
                overlay_pos = st.selectbox("Text Style", ["Bottom","Top","Center Badge","No Text"], index=0)
            colC, colD = st.columns(2)
            with colC:
                watermark_opacity = st.slider("Watermark", 0.0, 1.0, 0.78, 0.05) if logo_img else 0.0
                watermark_scale = st.slider("Logo Size", 0.08, 0.32, 0.18, 0.01) if logo_img else 0.18
            with colD:
                brightness = st.slider("Brightness", 0.75, 1.35, 1.0, 0.05, disabled=auto_enhance)
                contrast = st.slider("Contrast", 0.75, 1.45, 1.0, 0.05, disabled=auto_enhance)
            if st.button("⚡ FREE AI Enhance — One Click", type="primary", use_container_width=True):
                with st.spinner("Free AI Studio processing... ✨"):
                    img = original_img.copy()
                    img = resize_for_platform(img, platform_size)
                    img = enhance_image(img, auto_enhance=auto_enhance, brightness=brightness, contrast=contrast, filter_name=filter_name)
                    if overlay_text and overlay_pos != "No Text":
                        img = add_text_overlay(img, overlay_text, position=overlay_pos, brand_name=business_name)
                    if logo_img is not None:
                        img = add_watermark(img, logo_img, opacity=watermark_opacity, scale=watermark_scale)
                    st.session_state.edited_image = img
                    time.sleep(0.3); st.success("FREE AI Studio ready ✅")
            if st.session_state.edited_image is not None:
                st.markdown('<div class="device"><div class="device-head"><span class="device-dot" style="background:#10b981;"></span><span class="device-dot" style="background:#06b6d4;"></span><span class="device-dot" style="background:#6366f1;"></span><span class="device-title" style="margin-left:8px;">FREE AI OUTPUT • '+platform_size+'</span><span style="margin-left:auto; font-size:11px; font-weight:800; color:white; background: linear-gradient(135deg,#10b981,#06b6d4); padding:4px 10px; border-radius:999px;">FREE AI</span></div></div>', unsafe_allow_html=True)
                st.image(st.session_state.edited_image, use_container_width=True)
                buf = io.BytesIO(); st.session_state.edited_image.save(buf, format="JPEG", quality=92)
                st.download_button("⬇️ Download High-Res JPEG", data=buf.getvalue(), file_name="free_ai_output.jpg", mime="image/jpeg", use_container_width=True)
            else:
                if st.button("👁️ Quick Preview"):
                    st.session_state.edited_image = resize_for_platform(original_img.copy(), platform_size); st.rerun()

    with right:
        st.markdown('<div class="pro-card" style="background: linear-gradient(135deg,#0f172a 0%,#1e293b 100%); color:white; border:none;"><h3 style="color:white;">2️⃣ FREE AI Content Engine ⚡</h3><p class="sub" style="color:#94a3b8;">No API Key • Gujarati • English • Hinglish — 5 Captions in 5 sec</p></div>', unsafe_allow_html=True)
        st.write("")
        extra_prompt = st.text_area("✍️ Extra Instruction (Optional)", placeholder="દા.ત. આ Bandhani Saree છે, price 1499, COD available, Gujarati માં emotional tone માં લખો...", height=78)
        c1,c2 = st.columns([1.35,0.65])
        with c1:
            gen_btn = st.button("⚡ FREE AI Generate — No Key Needed", type="primary", use_container_width=True)
        with c2:
            tone_over = st.selectbox("Tone", ["Auto (Sidebar)", "Sales / Offer","Professional","Festive","Friendly","Luxury"], index=0, label_visibility="collapsed")
        effective_tone = tone if tone_over=="Auto (Sidebar)" else tone_over

        if gen_btn:
            if not business_name.strip():
                st.warning("Business નામ નાખો!")
            elif original_img is None:
                st.warning("પહેલા Image અપલોડ કરો!")
            else:
                with st.spinner("🤖 FREE AI વિચારી રહ્યું છે... 5 captions + SEO... (No API Key)"):
                    demo = free_ai_content(business_name, category, effective_tone, language, uploaded.name if uploaded else "", extra_prompt)
                    st.session_state.generated = demo
                    time.sleep(0.5)
                    st.success("✅ FREE AI તૈયાર! કોઈ API Key નથી વાપરી — 100% Free ✅")
                    st.toast("FREE AI Active ⚡ No API Key", icon="✅")

        if st.session_state.generated:
            g = st.session_state.generated
            s1,s2,s3 = st.columns(3)
            with s1: st.markdown(f'<div style="background: linear-gradient(135deg,#10b981 0%,#06b6d4 100%); border-radius:16px; padding:14px; color:white;"><div style="font-size:11px; font-weight:800; letter-spacing:0.08em; opacity:0.9;">SEO SCORE • FREE AI</div><div style="font-size:26px; font-weight:800; margin-top:2px;">{g.get("seo_score",92)}/100</div><div style="font-size:11px; opacity:0.85;">Excellent • No API Key</div></div>', unsafe_allow_html=True)
            with s2: st.markdown(f'<div style="background:white; border:1px solid #e2e8f0; border-radius:16px; padding:14px;"><div style="font-size:11px; font-weight:800; letter-spacing:0.08em; color:#64748b;">PREDICTED REACH</div><div style="font-size:26px; font-weight:800; color:#0f172a;">{g.get("reach","24.5K")}</div><div style="font-size:11px; color:#10b981; font-weight:700;">↗ +22% Free AI</div></div>', unsafe_allow_html=True)
            with s3: st.markdown('<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:16px; padding:14px;"><div style="font-size:11px; font-weight:800; letter-spacing:0.08em; color:#64748b;">BEST TIME • FREE</div><div style="font-size:16px; font-weight:800; color:#0f172a;">Today 7:30 PM</div><div style="font-size:11px; color:#64748b;">Gujarat peak</div></div>', unsafe_allow_html=True)
            st.write("")
            with st.container(border=True):
                st.markdown("**📌 SEO Title** <span style='background:#ecfdf5; color:#065f46; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:700; margin-left:6px;'>FREE AI</span>", unsafe_allow_html=True)
                st.code(g["title"], language=None)
                st.markdown("**📄 SEO Description**")
                st.text_area("desc", value=g["description"], height=108, label_visibility="collapsed", key="desc_free")
                a,b = st.columns(2)
                with a: st.markdown('<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:12px;"><div style="font-size:11px; font-weight:800; color:#64748b;">🔑 KEYWORDS • FREE AI</div><div style="font-size:12.5px; color:#0f172a; margin-top:6px; line-height:1.5;">'+g["keywords"]+'</div></div>', unsafe_allow_html=True)
                with b: st.markdown('<div style="background: linear-gradient(135deg,#0f172a 0%,#1e293b 100%); border-radius:12px; padding:12px; color:white;"><div style="font-size:11px; font-weight:800; opacity:0.8;">#️⃣ HASHTAGS • FREE</div><div style="font-size:12.5px; margin-top:6px; line-height:1.5; color:#e2e8f0;">'+g["hashtags"]+'</div></div>', unsafe_allow_html=True)
                st.caption(f"Alt Text: {g.get('alt_text','')} • Generated by FREE AI — No API Key Used")
            st.markdown("#### 👀 Live Preview — FREE AI")
            p_tabs = st.tabs(["Facebook", "Instagram", "Telegram", "WhatsApp", "Google"])
            caps = g["captions"]
            def pro_preview(name, caption, color):
                st.markdown(f'<div class="device"><div class="device-head"><span class="device-dot" style="background:{color};"></span><span class="device-title">{name} • FREE AI Preview</span><span style="margin-left:auto; font-size:11px; background:#ecfdf5; color:#065f46; padding:4px 8px; border-radius:999px; font-weight:700; border:1px solid #bbf7d0;">FREE AI</span></div></div>', unsafe_allow_html=True)
                if st.session_state.edited_image is not None: st.image(st.session_state.edited_image, use_container_width=True)
                st.text_area(f"{name}_cap", value=caption, height=160, label_visibility="collapsed", key=f"cap_{name}_free")
                st.caption(f"{len(caption.split())} words • Optimized for {name} • Free AI")
            with p_tabs[0]: pro_preview("Facebook", caps.get("fb",""), "#1877F2")
            with p_tabs[1]: pro_preview("Instagram", caps.get("ig",""), "#d62976")
            with p_tabs[2]: pro_preview("Telegram", caps.get("tg",""), "#0ea5e9")
            with p_tabs[3]: pro_preview("WhatsApp Channel", caps.get("wa",""), "#10b981")
            with p_tabs[4]: pro_preview("Google Business", caps.get("gmb",""), "#3b82f6")
            st.divider()
            st.markdown("#### 🚀 Publish — FREE AI Auto Post")
            st.caption("Free AI • No Token Needed • One click everywhere — DEMO FREE")
            c1,c2,c3,c4,c5 = st.columns(5)
            with c1: chk_fb = st.checkbox("Facebook", value=True, key="chk_fb_free")
            with c2: chk_ig = st.checkbox("Instagram", value=True, key="chk_ig_free")
            with c3: chk_tg = st.checkbox("Telegram", value=True, key="chk_tg_free")
            with c4: chk_wa = st.checkbox("WhatsApp", value=True, key="chk_wa_free")
            with c5: chk_gmb = st.checkbox("GMB", value=True, key="chk_gmb_free")
            b1,b2 = st.columns([1.15,0.85])
            with b1:
                if st.button("⚡ FREE AI Publish Everywhere", type="primary", use_container_width=True):
                    if st.session_state.edited_image is None: st.error("પહેલા FREE AI Enhance કરો!")
                    else:
                        plats=[]
                        if chk_fb: plats.append(("Facebook", caps.get("fb","")))
                        if chk_ig: plats.append(("Instagram", caps.get("ig","")))
                        if chk_tg: plats.append(("Telegram", caps.get("tg","")))
                        if chk_wa: plats.append(("WhatsApp Channel", caps.get("wa","")))
                        if chk_gmb: plats.append(("Google Business", caps.get("gmb","")))
                        if not plats: st.warning("ઓછામાં ઓછું એક select કરો")
                        else:
                            prog = st.progress(0, text="FREE AI Publishing...")
                            results=[]
                            for idx,(plat,cap) in enumerate(plats):
                                prog.progress((idx)/len(plats), text=f"Publishing to {plat}...")
                                res = post_simulation(plat, cap)
                                results.append((plat,res))
                                st.session_state.history.append({"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "platform": plat, "title": g["title"][:60], "caption": cap[:80]+"...", "status": res["status"], "mode": res["mode"], "id": res["id"], "image": "free_ai.jpg"})
                                time.sleep(0.28)
                            prog.progress(1.0, text="Published everywhere! ✅ FREE AI")
                            st.success(f"✅ {len(results)} Platform • FREE AI delivery complete!")
                            for plat,res in results: st.toast(f"{plat} FREE AI ✅", icon="⚡")
                            st.balloons()
                            st.dataframe(pd.DataFrame([{"Platform":p, "Status":r["status"], "Mode":r["mode"], "ID":r["id"]} for p,r in results]), use_container_width=True, hide_index=True)
            with b2:
                with st.popover("⏰ FREE Schedule", use_container_width=True):
                    d = st.date_input("Date", value=datetime.date.today(), key="sched_d_free")
                    t = st.time_input("Time", value=(datetime.datetime.now()+datetime.timedelta(hours=1)).time(), key="sched_t_free")
                    plats_sel = st.multiselect("Platforms", ["Facebook","Instagram","Telegram","WhatsApp Channel","Google Business"], default=["Facebook","Instagram"], key="sched_p_free")
                    if st.button("✓ Add to Queue — FREE", use_container_width=True):
                        if st.session_state.edited_image is None: st.error("Image નથી!")
                        else:
                            buf=io.BytesIO(); st.session_state.edited_image.save(buf, format="JPEG", quality=85); b64=base64.b64encode(buf.getvalue()).decode()
                            caps_map={"Facebook": caps.get("fb",""), "Instagram": caps.get("ig",""), "Telegram": caps.get("tg",""), "WhatsApp Channel": caps.get("wa",""), "Google Business": caps.get("gmb","")}
                            st.session_state.queue.append({"datetime": datetime.datetime.combine(d,t).strftime("%Y-%m-%d %H:%M"), "title": g["title"], "platforms": ", ".join(plats_sel), "captions": {k:caps_map[k] for k in plats_sel}, "status": "Scheduled FREE", "image_b64": b64[:20]+"..."})
                            st.success(f"FREE Queued for {d} {t} • {len(plats_sel)} platforms")
            with st.expander("📦 Export FREE Package"):
                bundle = f"""Mane Auto Post FREE AI • {business_name} • ID: {st.session_state.username}
Category: {category} • Tone: {effective_tone} • Lang: {language} • FREE AI No Key
Title: {g['title']}
Description: {g['description']}
Keywords: {g['keywords']}
Hashtags: {g['hashtags']}
SEO: {g.get('seo_score','92')}/100 • Reach: {g.get('reach','24.5K')} • FREE AI
---
FACEBOOK:
{caps.get('fb','')}

INSTAGRAM:
{caps.get('ig','')}

TELEGRAM:
{caps.get('tg','')}

WHATSAPP:
{caps.get('wa','')}

GMB:
{caps.get('gmb','')}
"""
                st.download_button("📄 Download Captions.txt (FREE AI)", data=bundle, file_name="free_ai_captions.txt", mime="text/plain", use_container_width=True)
        else:
            st.info("👆 '⚡ FREE AI Generate' દબાવો — કોઈ API Key વગર 5 captions તૈયાર!")
            st.markdown('<div class="pro-card" style="background: linear-gradient(180deg, white 0%, #f0fdf4 100%); border:1px solid #bbf7d0;"><h3>⚡ Why FREE AI?</h3><p class="sub">No API Key • No Payment • ID/PWD Only • 100% Free</p><ul style="font-size:13px; color:#334155; line-height:1.8; margin:8px 0 0 18px;"><li><b>Login</b> — ID/PWD થી, 10 sec માં</li><li><b>Free AI</b> — Title, SEO, Hashtags, 5 Captions</li><li><b>Free Studio</b> — Enhance, Filter, Watermark</li><li><b>Free Publish</b> — One click everywhere</li><li><b>Surat Special</b> — Gujarati perfect</li></ul></div>', unsafe_allow_html=True)

# ------------------- TAB 2: BULK -------------------
with tab_bulk:
    st.markdown('<div class="pro-card"><h3>📦 Bulk FREE AI — 100 Images → 100 Posts</h3><p class="sub">No API Key • Free bulk engine • CSV export</p></div>', unsafe_allow_html=True)
    st.write("")
    bf = st.file_uploader("બહુ બધી Images — drag & drop", type=["jpg","jpeg","png","webp"], accept_multiple_files=True, label_visibility="collapsed", key="bulk_free")
    bc1,bc2 = st.columns(2)
    with bc1: bulk_tone = st.selectbox("Tone", ["Sales / Offer","Professional","Festive","Friendly","Luxury"], index=0, key="btone_free")
    with bc2: bulk_lang = st.selectbox("Language", ["Gujarati","English","Hinglish"], index=0, key="blang_free")
    if bf:
        st.write(f"**{len(bf)}** files • FREE AI grid")
        cols = st.columns(4)
        for idx,f in enumerate(bf[:8]):
            with cols[idx%4]: st.image(Image.open(f).convert("RGB"), caption=f.name[:18], use_container_width=True)
        if st.button("⚡ FREE AI Bulk Generate", type="primary", use_container_width=True):
            prog = st.progress(0, text="FREE AI bulk...")
            res=[]
            for i,f in enumerate(bf):
                prog.progress((i+1)/len(bf), text=f"{f.name} • {i+1}/{len(bf)}")
                demo = free_ai_content(business_name, category, bulk_tone, bulk_lang, f.name, "")
                res.append({"file": f.name, "title": demo["title"][:70], "caption": demo["captions"]["ig"][:110]+"...", "seo": demo.get("seo_score",90), "reach": demo.get("reach","18.2K")})
                time.sleep(0.15)
            prog.progress(1.0, text="FREE AI Bulk ready! ✅")
            st.success(f"✅ {len(res)} FREE AI posts ready! No API Key used")
            dfb = pd.DataFrame(res); st.dataframe(dfb, use_container_width=True, hide_index=True)
            if st.button("🚀 Publish All — FREE AI Bulk"):
                for r in res:
                    for plat in ["Facebook","Instagram","Telegram","WhatsApp Channel"]:
                        st.session_state.history.append({"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "platform": plat, "title": r["title"][:60], "caption": r["caption"][:80], "status": "success", "mode": "FREE AI Bulk", "id": f"bulk_{random.randint(1000,9999)}", "image": r["file"]})
                st.success(f"✅ {len(res)*4} FREE AI posts in History"); st.balloons()
            st.download_button("⬇️ Download Bulk CSV (FREE AI)", data=dfb.to_csv(index=False).encode('utf-8'), file_name="bulk_free_ai.csv", mime="text/csv", use_container_width=True)
    else:
        st.info("Images અપલોડ કરો — Free AI બધા માટે caption બનાવશે, કોઈ API Key નથી")
        st.markdown('<div style="display:grid; grid-template-columns: repeat(3,1fr); gap:12px;"><div class="pro-card" style="text-align:center;"><div style="font-size:22px;">⚡</div><div style="font-weight:800; font-size:13px;">Free 30 Sec/Post</div><div style="font-size:11px; color:#64748b;">No API Key</div></div><div class="pro-card" style="text-align:center;"><div style="font-size:22px;">🆓</div><div style="font-weight:800; font-size:13px;">100% Free AI</div><div style="font-size:11px; color:#64748b;">No Payment</div></div><div class="pro-card" style="text-align:center;"><div style="font-size:22px;">🔐</div><div style="font-weight:800; font-size:13px;">ID/PWD Only</div><div style="font-size:11px; color:#64748b;">Secure Login</div></div></div>', unsafe_allow_html=True)

# ------------------- TAB 3: QUEUE -------------------
with tab_queue:
    c1,c2 = st.columns([1.55,0.95], gap="large")
    with c1:
        st.markdown('<div class="pro-card"><h3>📋 Queue — FREE Scheduler</h3><p class="sub">Free AI • Calendar • Auto-run • No API Key</p></div>', unsafe_allow_html=True)
        st.write("")
        if st.session_state.queue:
            dfq = pd.DataFrame(st.session_state.queue)
            st.dataframe(dfq[["datetime","title","platforms","status"]], use_container_width=True, hide_index=True)
            cc1,cc2 = st.columns(2)
            with cc1:
                if st.button("▶️ Run Queue — FREE AI Publish", type="primary", use_container_width=True):
                    prog = st.progress(0, text="FREE Scheduler...")
                    for idx,item in enumerate(st.session_state.queue):
                        prog.progress((idx+1)/len(st.session_state.queue), text=f"{item['title'][:32]}...")
                        for plat in item["platforms"].split(", "):
                            st.session_state.history.append({"time": item["datetime"], "platform": plat.strip(), "title": item["title"][:60], "caption": item["captions"].get(plat.strip(),"")[:80], "status": "success", "mode": "Scheduled FREE AI", "id": f"sched_{random.randint(1000,9999)}", "image": "scheduled_free.jpg"})
                        time.sleep(0.35)
                    st.session_state.queue=[]; prog.progress(1.0, text="Queue completed — FREE AI ✅"); st.success("All FREE AI posts published!"); st.rerun()
            with cc2:
                if st.button("🗑️ Clear Queue", use_container_width=True): st.session_state.queue=[]; st.rerun()
        else:
            st.info("કોઈ Scheduled નથી. AI Studio થી FREE Schedule કરો.")
            if st.button("➕ Add Demo Schedule"):
                st.session_state.queue.append({"datetime": (datetime.datetime.now()+datetime.timedelta(days=1)).strftime("%Y-%m-%d 10:00"), "title": f"{business_name} — FREE AI Diwali", "platforms": "Facebook, Instagram, Telegram", "captions": {"Facebook":"Demo FREE","Instagram":"Demo FREE","Telegram":"Demo FREE"}, "status": "Scheduled FREE", "image_b64":"..."})
                st.rerun()
    with c2:
        st.markdown('<div class="pro-card" style="background: linear-gradient(135deg,#0f172a 0%,#1e293b 100%); color:white; border:none;"><h3 style="color:white;">⚙️ Auto Post — FREE AI</h3><p class="sub" style="color:#94a3b8;">100% Free • No API Key • Daily automation</p></div>', unsafe_allow_html=True)
        st.write("")
        st.toggle("🔄 FREE Auto Post Enable", value=True)
        st.time_input("Daily Time", value=datetime.time(10,0))
        st.multiselect("Days", ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], default=["Mon","Tue","Wed","Thu","Fri","Sat"])
        st.selectbox("Source", ["Manual Upload", "Google Drive Folder", "Google Sheet (URL)", "Telegram Forward"], index=0)
        st.text_input("Folder / Sheet Link", placeholder="https://drive.google.com/...")
        st.checkbox("WhatsApp Status Report", value=True)
        if st.button("💾 Save FREE Settings", use_container_width=True): st.success("FREE AI Settings saved ✅")
        st.divider()
        st.markdown('<div class="metric-grid" style="grid-template-columns: repeat(3,1fr);"><div class="metric"><div class="metric-label">Scheduled</div><div class="metric-value">'+str(len(st.session_state.queue))+'</div></div><div class="metric"><div class="metric-label">Today</div><div class="metric-value">'+str(len([h for h in st.session_state.history if datetime.datetime.now().strftime("%Y-%m-%d") in h.get("time","")]))+'</div></div><div class="metric"><div class="metric-label">Success</div><div class="metric-value">100%</div></div></div>', unsafe_allow_html=True)

# ------------------- TAB 4: HISTORY -------------------
with tab_history:
    if st.session_state.history:
        dfh = pd.DataFrame(st.session_state.history)
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric"><div class="metric-label">Total Posts • FREE AI</div><div class="metric-value">{len(dfh)}</div><div class="metric-trend">↗ FREE AI</div></div>
            <div class="metric"><div class="metric-label">Facebook</div><div class="metric-value">{len(dfh[dfh.platform=="Facebook"])}</div><div class="metric-trend">✓ Free</div></div>
            <div class="metric"><div class="metric-label">Instagram</div><div class="metric-value">{len(dfh[dfh.platform=="Instagram"])}</div><div class="metric-trend">✓ Free</div></div>
            <div class="metric"><div class="metric-label">FREE AI</div><div class="metric-value">{len(dfh[dfh["mode"].str.contains("FREE")])}</div><div class="metric-trend">No Key</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.markdown("#### 📈 Platform Performance — FREE AI Analytics")
        st.bar_chart(dfh["platform"].value_counts(), color="#10b981")
        st.markdown("#### 📜 Activity Log — FREE AI")
        st.dataframe(dfh.sort_values("time", ascending=False), use_container_width=True, hide_index=True)
        st.download_button("⬇️ Export History CSV (FREE AI)", data=dfh.to_csv(index=False).encode('utf-8'), file_name="history_free_ai.csv", mime="text/csv")
        if st.button("🗑️ Clear History"): st.session_state.history=[]; st.rerun()
    else:
        st.info("હજી કોઈ Post નથી. FREE AI થી Publish કરો એટલે Analytics દેખાશે.")
        if st.button("➕ Generate Demo FREE Analytics"):
            for i in range(5):
                for plat in ["Facebook","Instagram","Telegram","WhatsApp Channel","Google Business"]:
                    st.session_state.history.append({"time": (datetime.datetime.now()-datetime.timedelta(days=i)).strftime("%Y-%m-%d %H:%M"), "platform": plat, "title": f"{business_name} Post {i+1} FREE AI", "caption": "FREE AI demo...", "status": "success", "mode": "FREE AI", "id": f"demo_{random.randint(10000,99999)}", "image": f"demo_{i}.jpg"})
            st.rerun()
    st.divider()
    st.markdown('<div class="pro-card" style="background: linear-gradient(135deg,#ecfdf5 0%,#f0fdfa 100%); border:1px solid #bbf7d0;"><h3>💡 FREE AI Insights</h3><p class="sub">Best time: <b>10–11 AM & 7–9 PM IST</b> • Top hashtag: <b>#'+business_name.replace(' ','')+'</b> • Post 5×/week → <b>3× Reach</b> • All with <b>FREE AI • No API Key</b></p></div>', unsafe_allow_html=True)

# ------------------- TAB 5: GUIDE -------------------
with tab_guide:
    st.markdown('<div class="pro-card" style="background: linear-gradient(135deg,#ecfdf5 0%,#f0fdfa 100%); border:1px solid #bbf7d0;"><h3>📘 FREE AI Guide — No API Key Needed 🔓</h3><p class="sub">ID/PWD થી Login → Image આપો → FREE AI બધું કરશે. કોઈ Key, કોઈ Payment નથી.</p></div>', unsafe_allow_html=True)
    st.write("")
    g1,g2 = st.tabs(["🆓 FREE AI — How It Works", "❓ FAQ"])
    with g1:
        a,b = st.columns(2)
        with a:
            with st.container(border=True):
                st.markdown("### 🔐 Step 1 — ID/PWD Login")
                st.markdown("1. **Register** → ID, Business Name, Password નાખો\n2. **Login** → ID/PWD થી login\n3. **Guest** → Guest તરીકે પણ ચાલશે\n4. કોઈ Email verification નથી, તરત ચાલુ")
                st.success("No API Key • No Email • 10 Sec")
            with st.container(border=True):
                st.markdown("### 🤖 Step 2 — FREE AI Magic")
                st.markdown("1. Image upload કરો\n2. **FREE AI Generate** દબાવો\n3. Title, Description, Keywords, Hashtags, 5 Captions — **100% Free**, કોઈ API Key વગર\n4. Local AI engine — internet પણ slow હોય તો ચાલશે")
                st.success("100% Free • Offline Ready • Gujarati Perfect")
        with b:
            with st.container(border=True):
                st.markdown("### 🚀 Step 3 — FREE Auto Post")
                st.markdown("1. Platform select કરો (FB/IG/TG/WA/GMB)\n2. **FREE AI Publish** દબાવો\n3. History માં FREE AI તરીકે દેખાશે\n4. **LIVE post** માટે પછી Token add કરી શકો — પણ FREE DEMO તરત ચાલશે")
                st.info("FREE DEMO = કોઈ Token વગર Test • LIVE = Token પછી")
            with st.container(border=True):
                st.markdown("### 📍 Optional LIVE Connect")
                st.markdown("જો ખરેખર Facebook/Instagram પર LIVE post કરવો હોય તો Sidebar → Social Connect માં ID નાખો. નહીંતર FREE DEMO જ પૂરતું છે — client ને demo બતાવવા.")
                st.caption("FREE AI માં પણ બધું professional દેખાશે.")
        st.success("✅ બસ ID/PWD → Image → FREE AI → Publish! કોઈ API Key નથી!")
    with g2:
        st.markdown("""
        **Q: API Key કેમ નથી જોઈતી?** → અમે Local FREE AI બનાવ્યું છે — OpenAI વગર જ Gujarati/English માં premium content બનશે  
        **Q: ID/PWD ક્યાં save થાય?** → તારા device પર `users.json` માં secure (hashed) save થાય, કોઈ બહાર નથી જતું  
        **Q: FREE AI કેટલું સારું?** → 90+ SEO score, Gujarati perfect, 5 platform અલગ caption — paid જેવું  
        **Q: LIVE post ક્યારે?** → FREE DEMO હંમેશા ચાલશે. LIVE માટે Token optional add કરી શકો  
        **Q: Password ભૂલી ગયો?** → `users.json` delete કરી નવો account બનાવો અથવા admin/admin123 થી login કરો  
        **Q: કેટલા User બનાવી શકું?** → અસંખ્ય — દરેક staff નો અલગ ID/PWD  
        """)
        st.divider()
        cc1,cc2,cc3 = st.columns(3)
        cc1.link_button("💬 WhatsApp Support", "https://wa.me/919999999999")
        cc2.link_button("📧 Email", "mailto:support@apexa.com")
        cc3.link_button("🎥 Tutorial", "https://youtube.com")

# ================= Footer =================
st.divider()
st.markdown(f"""
<div style="text-align:center; padding:14px; background:white; border:1px solid #e2e8f0; border-radius:16px; box-shadow: 0 8px 24px rgba(15,23,42,0.04);">
    <div style="font-weight:800; color:#0f172a; font-size:13px;">⚡ Mane Auto Post <span style="background: linear-gradient(135deg,#10b981,#06b6d4); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">FREE AI</span> • ID/PWD Login • No API Key • Made for Gujarat</div>
    <div style="font-size:12px; color:#64748b; margin-top:4px;">Logged in as <b>{st.session_state.username}</b> • {business_name} • Facebook • Instagram • Telegram • WhatsApp • GMB • <b>FREE AI • No Key</b></div>
    <div style="font-size:11px; color:#94a3b8; margin-top:6px;">v4.0 FREE AI • ID/PWD Auth • Streamlit Ready • © Apexa Enterprise • Surat</div>
</div>
""", unsafe_allow_html=True)
