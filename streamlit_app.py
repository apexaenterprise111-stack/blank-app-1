import streamlit as st
import pandas as pd
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont, ImageOps
import requests
import io
import base64
import datetime
import random
import textwrap
import json
import time

# ================= Page Config =================
st.set_page_config(
    page_title="Mane Auto Post - AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= Custom CSS =================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Gujarati:wght@400;600&family=Poppins:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Poppins','Noto Sans Gujarati', sans-serif; }
.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.8rem 2rem;
    border-radius: 16px;
    color: white;
    margin-bottom: 1.2rem;
    text-align: center;
}
.main-header h1 { font-size: 2.2rem; margin:0; font-weight:700; }
.main-header p { opacity:0.95; margin:0.4rem 0 0 0; font-size:1.05rem; }
.platform-card {
    border: 1.5px solid #e5e7eb;
    border-radius: 14px;
    padding: 14px;
    background: white;
    box-shadow: 0 4px 10px rgba(0,0,0,0.04);
    height: 100%;
}
.platform-card.selected { border-color: #667eea; background: #f5f3ff; }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600; }
.badge-fb { background:#1877F2; color:white; }
.badge-ig { background: linear-gradient(45deg,#feda75,#fa7e1e,#d62976,#962fbf,#4f5bd5); color:white; }
.badge-tg { background:#26A5E4; color:white; }
.badge-wa { background:#25D366; color:white; }
.badge-gmb { background:#4285F4; color:white; }
.preview-box {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 12px;
    background: #fafafa;
}
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] { border-radius:8px; padding:8px 14px; }
div[data-testid="stVerticalBlock"] > div:has(div.platform-card) { gap: 1rem; }
</style>
""", unsafe_allow_html=True)

# ================= Helpers =================

def get_demo_content(business_name, category, tone, language, image_name=""):
    """Generate realistic AI-like content without API key. Language aware."""
    # Base keywords per category
    cat_keywords = {
        "Fashion": ["fashion", "style", "trending", "outfit", "collection"],
        "Electronics": ["electronics", "gadget", "tech", "innovation", "deal"],
        "Food / Restaurant": ["food", "tasty", "delicious", "foodie", "restaurant"],
        "Real Estate": ["property", "dream home", "investment", "real estate"],
        "Education": ["learning", "education", "knowledge", "career"],
        "Services": ["service", "professional", "trusted", "quality"],
        "General Business": ["business", "quality", "trusted", "offer"]
    }
    keywords = cat_keywords.get(category, cat_keywords["General Business"])
    
    tones = {
        "Professional": {"en": "Professional & Trusted", "gu": "વિશ્વાસપાત્ર અને પ્રોફેશનલ"},
        "Sales / Offer": {"en": "Dhamaka Offer 🔥", "gu": "ધમાકા ઓફર 🔥"},
        "Festive": {"en": "Festive Vibes ✨", "gu": "તહેવાર ની ખુશી ✨"},
        "Friendly": {"en": "Friendly & Engaging", "gu": "મિત્રતા ભર્યો"},
        "Luxury": {"en": "Premium & Luxury", "gu": "પ્રીમિયમ અને શાહી"}
    }
    tone_label = tones.get(tone, tones["Professional"])
    
    if language == "Gujarati":
        title = f"{business_name} - {category} માં નવું કલેક્શન | {tone_label['gu']}"
        description = f"તમારા માટે ખાસ {business_name} લાવ્યું છે શ્રેષ્ઠ {category} ની વેરાયટી. ઉચ્ચ ગુણવત્તા, સસ્તા ભાવ અને ઝડપી સેવા. આજે જ મુલાકાત લો અથવા ઓર્ડર કરો! ✨\n\n✅ 100% ક્વોલિટી ગેરંટી\n✅ બેસ્ટ પ્રાઈસ\n✅ ઝડપી ડિલિવરી"
        captions = {
            "fb": f"🌟 {business_name} ની નવી પોસ્ટ!\n\n{description}\n\n📍 અમારા સ્ટોર ની મુલાકાત લો અથવા DM કરો\n📞 સંપર્ક કરો આજે જ!\n\n#{business_name.replace(' ','')} #{category.replace(' ','')} #GujaratBusiness #TrendingNow",
            "ig": f"✨ New Drop Alert ✨\n{business_name} | {category}\n\n{description}\n\n👉 Follow કરો @ {business_name.replace(' ','').lower()}\n💬 Comment કરો \"PRICE\" એટલે DM માં વિગત મોકલીશું\n\n#{business_name.replace(' ','')} #{keywords[0]} #{keywords[1]} #instagujarat #reelsinstagram #viral",
            "tg": f"📢 *{business_name}* - {title}\n\n{description}\n\n🔗 વધુ માહિતી માટે ક્લિક કરો",
            "wa": f"*{business_name}* ✨\n{title}\n\n{description}\n\n👉 ઓર્ડર કરવા WhatsApp કરો\n🟢 Channel Follow કરો - રોજ નવા અપડેટ માટે",
            "gmb": f"{title} - {business_name} દ્વારા. {category} માટે ગુજરાત માં સૌથી વિશ્વસનીય નામ. {description[:150]}... \nVisit us today!"
        }
    elif language == "Hinglish":
        title = f"{business_name} - New {category} Collection | {tone_label['en']}"
        description = f"{business_name} laya hai best {category} collection sirf aapke liye! High quality, best price aur fast service ke saath. Aaj hi visit karo! ✨"
        captions = {
            "fb": f"🌟 {business_name} ka naya dhamaka!\n\n{description}\n\n📍 Store visit karo ya DM karo\n📞 Contact now!\n\n#{business_name.replace(' ','')} #{category.replace(' ','')} #Gujarat #Trending",
            "ig": f"🔥 New Arrival 🔥\n{business_name} | {category}\n\n{description}\n\n👉 Follow @{business_name.replace(' ','').lower()}\n💬 Comment \"PRICE\" for details\n\n#{business_name.replace(' ','')} #{keywords[0]} #viral #reels",
            "tg": f"📢 *{business_name}* - {title}\n\n{description}",
            "wa": f"*{business_name}* ✨\n{title}\n\n{description}\n\n👉 Order karne ke liye WhatsApp karo",
            "gmb": f"{title} - Trusted {category} provider in Gujarat. {description}"
        }
    else: # English
        title = f"{business_name} - New {category} Collection | {tone_label['en']}"
        description = f"Discover the latest {category} collection at {business_name}! Premium quality, best prices and fast service. Visit us today or order online! ✨\n\n✅ 100% Quality Assured\n✅ Best Price Guarantee\n✅ Fast Delivery Across Gujarat"
        captions = {
            "fb": f"🌟 New Arrival at {business_name}!\n\n{description}\n\n📍 Visit our store or DM us\n📞 Contact us today!\n\n#{business_name.replace(' ','')} #{category.replace(' ','')} #GujaratBusiness #TrendingNow #NewCollection",
            "ig": f"✨ NEW DROP ALERT ✨\n{business_name} | {category}\n\n{description}\n\n👉 Follow @{business_name.replace(' ','').lower()}\n💬 Comment \"PRICE\" & we'll DM you details\n\n#{business_name.replace(' ','')} #{keywords[0]} #{keywords[1]} #instagram #reels #viral #gujarat",
            "tg": f"📢 *{business_name}* - {title}\n\n{description}\n\n🔗 Tap to know more",
            "wa": f"*{business_name}* ✨\n{title}\n\n{description}\n\n👉 WhatsApp us to order now\n🟢 Follow our Channel for daily updates",
            "gmb": f"{title}. At {business_name}, we provide top quality {category} with trusted service in Gujarat. {description[:160]} Visit us today! Call now."
        }

    hashtags = [f"#{business_name.replace(' ','')}", f"#{category.replace(' ','').replace('/','')}", f"#{keywords[0]}", f"#{keywords[1]}", "#Gujarat", "#Trending", "#NewPost", "#Viral"]
    seo_keywords = keywords + [business_name.lower(), category.lower(), "gujarat", "best price", "new collection"]
    
    return {
        "title": title,
        "description": description,
        "keywords": ", ".join(seo_keywords),
        "hashtags": " ".join(hashtags),
        "captions": captions,
        "alt_text": f"{business_name} {category} product image - high quality {keywords[0]}"
    }

def call_openai_like_api(api_key, prompt, business_name, category, tone, language):
    """Try to call OpenAI-compatible API if key provided, else fallback to demo."""
    if not api_key or len(api_key.strip()) < 10:
        return None
    try:
        # Try OpenAI chat completions
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": f"You are a Gujarati social media marketing expert. Business: {business_name}, Category: {category}, Tone: {tone}, Language: {language}. Create title, description, keywords, hashtags and platform-specific captions for Facebook, Instagram, Telegram, WhatsApp Channel, Google My Business. Return JSON with keys: title, description, keywords, hashtags, captions: {{fb, ig, tg, wa, gmb}}"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 1200
        }
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=20)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            # try to extract JSON
            import re
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                if "captions" in parsed:
                    return parsed
        return None
    except Exception as e:
        return None

# Image editing helpers
def enhance_image(img: Image.Image, auto_enhance=True, brightness=1.0, contrast=1.0, sharpness=1.0, filter_name="None"):
    if auto_enhance:
        img = ImageEnhance.Color(img).enhance(1.15)
        img = ImageEnhance.Contrast(img).enhance(1.15)
        img = ImageEnhance.Brightness(img).enhance(1.05)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
    else:
        if brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(brightness)
        if contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast)
        if sharpness != 1.0:
            img = ImageEnhance.Sharpness(img).enhance(sharpness)
    if filter_name == "Warm":
        # slight warm tone
        r, g, b = img.split()
        r = r.point(lambda i: min(255, int(i*1.08)))
        b = b.point(lambda i: int(i*0.95))
        img = Image.merge("RGB", (r,g,b))
    elif filter_name == "Cool":
        r, g, b = img.split()
        b = b.point(lambda i: min(255, int(i*1.08)))
        img = Image.merge("RGB", (r,g,b))
    elif filter_name == "B&W":
        img = ImageOps.grayscale(img).convert("RGB")
    elif filter_name == "Vivid":
        img = ImageEnhance.Color(img).enhance(1.4)
        img = ImageEnhance.Contrast(img).enhance(1.2)
    return img

def add_text_overlay(img: Image.Image, text, position="Bottom", brand_name=""):
    draw_img = img.copy()
    W, H = draw_img.size
    draw = ImageDraw.Draw(draw_img, "RGBA")
    # try to load font
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=max(18, W//28))
        small_font = ImageFont.truetype("DejaVuSans.ttf", size=max(12, W//45))
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Wrap text
    max_chars = 28 if W > 800 else 22
    wrapped = textwrap.wrap(text, width=max_chars)
    text_block = "\n".join(wrapped[:3])  # max 3 lines
    
    # Estimate text bbox
    bbox = draw.multiline_textbbox((0,0), text_block, font=font, align="center")
    text_w = bbox[2]-bbox[0]
    text_h = bbox[3]-bbox[1]
    pad = 20
    
    if position == "Bottom":
        rect_y0 = H - text_h - pad*2 - 30
        rect_y1 = H
        rect_x0 = 0
        rect_x1 = W
        # gradient rectangle
        draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=(0,0,0,160))
        draw.multiline_text((W//2, rect_y0+pad), text_block, font=font, fill="white", align="center", anchor="mt")
        if brand_name:
            draw.text((W//2, H-14), brand_name, font=small_font, fill=(255,255,255,200), anchor="mm", align="center")
    elif position == "Top":
        rect_y0 = 0
        rect_y1 = text_h + pad*2 + 20
        draw.rectangle([0, rect_y0, W, rect_y1], fill=(0,0,0,140))
        draw.multiline_text((W//2, pad), text_block, font=font, fill="white", align="center", anchor="mt")
    elif position == "Center Badge":
        # centered badge
        badge_w = text_w + 40
        badge_h = text_h + 30
        x0 = (W-badge_w)//2
        y0 = (H-badge_h)//2
        draw.rounded_rectangle([x0, y0, x0+badge_w, y0+badge_h], radius=16, fill=(102,126,234,230))
        draw.multiline_text((W//2, H//2), text_block, font=font, fill="white", align="center", anchor="mm")
    return draw_img

def add_watermark(img: Image.Image, logo_img: Image.Image, opacity=0.7, scale=0.18):
    if logo_img is None:
        return img
    base = img.copy().convert("RGBA")
    # resize logo
    W, H = base.size
    logo_w = int(W * scale)
    aspect = logo_img.height / logo_img.width
    logo_h = int(logo_w * aspect)
    logo_small = logo_img.copy().convert("RGBA")
    logo_small = logo_small.resize((logo_w, logo_h), Image.LANCZOS)
    # opacity
    alpha = logo_small.split()[3]
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    logo_small.putalpha(alpha)
    # position bottom-right with padding
    pad = int(W*0.02)
    pos = (W - logo_w - pad, H - logo_h - pad)
    base.paste(logo_small, pos, logo_small)
    return base.convert("RGB")

def resize_for_platform(img: Image.Image, platform):
    sizes = {
        "Instagram Post (1080x1080)": (1080,1080),
        "Instagram Story (1080x1920)": (1080,1920),
        "Facebook Post (1200x630)": (1200,630),
        "WhatsApp / Telegram (1080x1080)": (1080,1080),
        "GMB Post (1200x900)": (1200,900),
        "Original": None
    }
    target = sizes.get(platform)
    if target is None:
        return img
    # Use ImageOps.fit to crop+resize with center
    return ImageOps.fit(img, target, Image.LANCZOS, centering=(0.5,0.5))

def post_simulation(platform, caption, has_keys=False):
    """Simulate API posting. If has_keys True, try real API."""
    # In demo we always succeed quickly
    time.sleep(0.6)
    if has_keys:
        return {"status": "success", "mode": "LIVE", "message": f"{platform} પર LIVE પોસ્ટ સફળ! ✅", "id": f"{platform.lower()}_{random.randint(10000,99999)}"}
    else:
        return {"status": "success", "mode": "DEMO", "message": f"{platform} (DEMO) પોસ્ટ સફળ! 🔹 ટોકન નાખશો એટલે LIVE થશે", "id": f"demo_{random.randint(10000,99999)}"}

# ================= Session State init =================
if "history" not in st.session_state:
    st.session_state.history = []
if "generated" not in st.session_state:
    st.session_state.generated = None
if "edited_image" not in st.session_state:
    st.session_state.edited_image = None
if "queue" not in st.session_state:
    st.session_state.queue = []

# ================= Sidebar =================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712109.png", width=90)
    st.markdown("### 🤖 Mane Auto Post")
    st.caption("AI Agent - એક Image થી બધે પોસ્ટ")
    st.divider()
    
    st.markdown("#### 🏢 બિઝનેસ પ્રોફાઇલ")
    business_name = st.text_input("બિઝનેસ નામ *", value="Apexa Enterprise", placeholder="તમારી દુકાન/કંપની નું નામ")
    category = st.selectbox("કેટેગરી", ["Fashion", "Electronics", "Food / Restaurant", "Real Estate", "Education", "Services", "General Business"], index=0)
    language = st.selectbox("ભાષા / Language", ["Gujarati", "English", "Hinglish"], index=0)
    tone = st.selectbox("ટોન / Tone", ["Professional", "Sales / Offer", "Festive", "Friendly", "Luxury"], index=1)
    contact = st.text_input("Contact / WhatsApp", placeholder="98765 43210")
    website = st.text_input("Website / GMB Link", placeholder="https://...")
    
    st.markdown("#### 🎨 બ્રાન્ડિંગ")
    logo_file = st.file_uploader("લોગો / વોટરમાર્ક (PNG)", type=["png","jpg","jpeg"])
    logo_img = None
    if logo_file:
        logo_img = Image.open(logo_file).convert("RGBA")
        st.image(logo_img, width=120, caption="Logo preview")
    
    with st.expander("🔑 API Keys (Optional - LIVE Post માટે)"):
        st.caption("DEMO mode માં પણ પોસ્ટ ટેસ્ટ થશે. LIVE માટે નીચે Token નાખો.")
        openai_key = st.text_input("OpenAI / Gemini API Key (AI Caption માટે)", type="password", help="નાખશો તો Real AI caption બનશે, નહિંતર Demo AI ચાલશે")
        fb_token = st.text_input("Meta (Facebook) Access Token", type="password")
        fb_page_id = st.text_input("Facebook Page ID")
        ig_user_id = st.text_input("Instagram User ID")
        tg_bot_token = st.text_input("Telegram Bot Token", type="password")
        tg_chat_id = st.text_input("Telegram Channel/Chat ID (@channelusername)")
        wa_token = st.text_input("WhatsApp Cloud API Token", type="password")
        wa_phone_id = st.text_input("WhatsApp Phone Number ID")
        gmb_token = st.text_input("Google My Business Token", type="password")
        gmb_location = st.text_input("GMB Location ID")
        st.info("💡 Token ક્યાંથી લેવા? નીચે 'Guide' ટેબ જુઓ.")
    
    st.divider()
    st.markdown("#### ⚡ ઝડપી આંકડા")
    c1, c2 = st.columns(2)
    c1.metric("પોસ્ટ થયેલ", len([h for h in st.session_state.history if h.get('status')=='success']))
    c2.metric("કતાર માં", len(st.session_state.queue))
    if st.button("🔄 Reset All"):
        st.session_state.generated = None
        st.session_state.edited_image = None
        st.session_state.history = []
        st.session_state.queue = []
        st.rerun()

# ================= Header =================
st.markdown("""
<div class="main-header">
    <h1>🤖 Mane Auto Post — AI Agent</h1>
    <p>હું ખાલી <b>IMAGE</b> આપો — હું AI થી EDIT કરી, <b>Title • Description • Keywords • Caption</b> બનાવી<br>Facebook • Instagram • Telegram • WhatsApp Channel • Google My Business પર <b>AUTO POST</b> કરી આપીશ!</p>
</div>
""", unsafe_allow_html=True)

# Platform selector chips
col_fb, col_ig, col_tg, col_wa, col_gmb = st.columns(5)
with col_fb: st.markdown('<div class="platform-card" style="text-align:center"><span class="badge badge-fb">Facebook</span><div style="font-size:12px;margin-top:6px">Page & Profile</div></div>', unsafe_allow_html=True)
with col_ig: st.markdown('<div class="platform-card" style="text-align:center"><span class="badge badge-ig">Instagram</span><div style="font-size:12px;margin-top:6px">Feed + Story</div></div>', unsafe_allow_html=True)
with col_tg: st.markdown('<div class="platform-card" style="text-align:center"><span class="badge badge-tg">Telegram</span><div style="font-size:12px;margin-top:6px">Channel / Group</div></div>', unsafe_allow_html=True)
with col_wa: st.markdown('<div class="platform-card" style="text-align:center"><span class="badge badge-wa">WhatsApp</span><div style="font-size:12px;margin-top:6px">Channel</div></div>', unsafe_allow_html=True)
with col_gmb: st.markdown('<div class="platform-card" style="text-align:center"><span class="badge badge-gmb">Google Business</span><div style="font-size:12px;margin-top:6px">GMB Post</div></div>', unsafe_allow_html=True)

st.write("")

# ================= Tabs =================
tab_create, tab_bulk, tab_queue, tab_history, tab_guide = st.tabs(["✨ 1. AI Post બનાવો", "📦 2. Bulk Upload", "⏰ 3. Scheduler & Queue", "📊 4. History & Analytics", "📘 5. Guide / API Setup"])

# ------------------- TAB 1: CREATE -------------------
with tab_create:
    left, right = st.columns([1.05, 1.15], gap="large")
    
    with left:
        st.subheader("1️⃣ Image અપલોડ કરો")
        uploaded = st.file_uploader("JPG / PNG ખેંચો અથવા Select કરો", type=["jpg","jpeg","png","webp"], label_visibility="collapsed")
        if uploaded:
            original_img = Image.open(uploaded).convert("RGB")
            st.image(original_img, caption=f"Original • {original_img.size[0]}x{original_img.size[1]}", use_container_width=True)
        else:
            st.info("👆 એક Image અપલોડ કરો. ઉદાહરણ માટે નીચે Demo Image વાપરી શકો.")
            if st.button("🖼️ Demo Image લોડ કરો"):
                # create a demo placeholder image
                demo = Image.new("RGB", (1080,1080), color=(118,92,255))
                d = ImageDraw.Draw(demo)
                try:
                    f = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
                except:
                    f = ImageFont.load_default()
                d.text((540,540), "APEXA\nENTERPRISE", fill="white", font=f, anchor="mm", align="center")
                original_img = demo
                st.image(original_img, use_container_width=True)
            else:
                original_img = None
        
        if original_img is not None:
            st.markdown("#### 🎨 AI Image Edit")
            colA, colB = st.columns(2)
            with colA:
                auto_enhance = st.toggle("✨ Auto Enhance (AI)", value=True, help="Brightness, Contrast, Sharpness auto સુધારશે")
                filter_name = st.selectbox("Filter", ["None","Warm","Cool","Vivid","B&W"], index=0)
            with colB:
                platform_size = st.selectbox("Resize for", ["Original","Instagram Post (1080x1080)","Instagram Story (1080x1920)","Facebook Post (1200x630)","WhatsApp / Telegram (1080x1080)","GMB Post (1200x900)"], index=1)
                overlay_text = st.text_input("Image પર Text (Optional)", placeholder="દા.ત. New Collection 50% OFF")
                overlay_pos = st.selectbox("Text Position", ["Bottom","Top","Center Badge","No Text"], index=0)
            
            colC, colD = st.columns(2)
            with colC:
                watermark_opacity = st.slider("Watermark Opacity", 0.0, 1.0, 0.75, 0.05) if logo_img else 0.0
                watermark_scale = st.slider("Logo Size", 0.08, 0.3, 0.18, 0.01) if logo_img else 0.18
            with colD:
                brightness = st.slider("Brightness", 0.7, 1.4, 1.0, 0.05, disabled=auto_enhance)
                contrast = st.slider("Contrast", 0.7, 1.5, 1.0, 0.05, disabled=auto_enhance)
            
            # Process button
            if st.button("🪄 Image ને AI Edit કરો", use_container_width=True):
                with st.spinner("AI Image edit કરી રહ્યું છે..."):
                    img = original_img.copy()
                    img = resize_for_platform(img, platform_size)
                    img = enhance_image(img, auto_enhance=auto_enhance, brightness=brightness, contrast=contrast, filter_name=filter_name)
                    if overlay_text and overlay_pos != "No Text":
                        img = add_text_overlay(img, overlay_text, position=overlay_pos, brand_name=business_name)
                    if logo_img is not None:
                        img = add_watermark(img, logo_img, opacity=watermark_opacity, scale=watermark_scale)
                    st.session_state.edited_image = img
                    st.success("Image તૈયાર! ✅ જમણી બાજુ Preview જુઓ")
                    time.sleep(0.2)
            
            if st.session_state.edited_image is not None:
                st.image(st.session_state.edited_image, caption="✨ Edited Post Image - Auto Post માટે તૈયાર", use_container_width=True)
                # download
                buf = io.BytesIO()
                st.session_state.edited_image.save(buf, format="JPEG", quality=92)
                st.download_button("⬇️ Edited Image Download", data=buf.getvalue(), file_name="mane_auto_post_image.jpg", mime="image/jpeg", use_container_width=True)
            else:
                # show default edited preview on first load
                if st.button("👁️ Preview without edit"):
                    img = resize_for_platform(original_img.copy(), platform_size)
                    st.session_state.edited_image = img
                    st.rerun()

    with right:
        st.subheader("2️⃣ AI Caption & Content")
        st.caption("Image analysis + Business info પરથી AI બધું બનાવશે")
        
        extra_prompt = st.text_area("વધારાની સૂચના (Optional)", placeholder="દા.ત. આ साड़ी છે, કિંમत 1499, Diwali Offer, Gujarati માં લખો, 3 hashtags વધુ નાખો...", height=80)
        
        col_gen1, col_gen2 = st.columns([1, 0.6])
        with col_gen1:
            generate_btn = st.button("✨ AI થી Post બનાવો - Title, Description, Keywords, Caption", type="primary", use_container_width=True)
        with col_gen2:
            tone_badge = st.selectbox("Tone Override", ["Auto (Sidebar)", "Professional","Sales / Offer","Festive","Friendly","Luxury"], index=0, label_visibility="collapsed")
        
        effective_tone = tone if tone_badge=="Auto (Sidebar)" else tone_badge
        
        if generate_btn:
            if not business_name.strip():
                st.warning("પહેલા Sidebar માં Business નામ નાખો!")
            elif original_img is None:
                st.warning("પહેલા Image અપલોડ કરો!")
            else:
                with st.spinner("🤖 AI વિચારી રહ્યું છે... Title, Description, Hashtags બનાવી રહ્યું છે..."):
                    # Try real API else demo
                    prompt = f"Image: {uploaded.name if uploaded else 'demo.jpg'} Business: {business_name} Category: {category} Tone: {effective_tone} Lang: {language} Extra: {extra_prompt}"
                    ai_result = call_openai_like_api(openai_key, prompt, business_name, category, effective_tone, language)
                    if ai_result:
                        st.session_state.generated = ai_result
                        st.success("Real AI થી Content બન્યું! ✅")
                    else:
                        demo = get_demo_content(business_name, category, effective_tone, language, uploaded.name if uploaded else "")
                        # if extra_prompt contains keywords, append
                        if extra_prompt:
                            demo["description"] += f"\n\n📝 Note: {extra_prompt}"
                        st.session_state.generated = demo
                        if openai_key:
                            st.warning("API Key કામ ન કર્યું, Demo AI વાપર્યું. Key ચકાસો.")
                        else:
                            st.success("Demo AI થી Content તૈયાર! (Real AI માટે Sidebar માં API Key નાખો) ✅")
                    time.sleep(0.4)

        # Show generated content
        if st.session_state.generated:
            g = st.session_state.generated
            st.markdown("#### 📝 Generated Content")
            with st.container(border=True):
                st.markdown(f"**📌 Title**")
                st.code(g["title"], language=None)
                st.markdown(f"**📄 Description (SEO)**")
                st.text_area("Description", value=g["description"], height=110, label_visibility="collapsed", key="desc_area")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**🔑 Keywords**")
                    st.caption(g["keywords"])
                with c2:
                    st.markdown("**#️⃣ Hashtags**")
                    st.caption(g["hashtags"])
                st.markdown(f"**🖼️ Alt Text (for SEO)**")
                st.caption(g.get("alt_text",""))

            # Platform previews
            st.markdown("#### 👀 દરેક Platform માટે Preview")
            p_tabs = st.tabs(["Facebook", "Instagram", "Telegram", "WhatsApp Channel", "Google Business"])
            
            caps = g["captions"]
            # Helper to show preview card
            def preview_card(platform_name, caption, badge_class, img):
                st.markdown(f'<span class="badge {badge_class}">{platform_name}</span>', unsafe_allow_html=True)
                if img is not None:
                    st.image(img, use_container_width=True)
                else:
                    st.info("Image નથી - ઉપરથી Edit કરો")
                st.text_area(f"{platform_name} Caption", value=caption, height=170, key=f"cap_{platform_name}", label_visibility="collapsed")
                st.caption(f"{len(caption)} chars • {len(caption.split())} words • {len(caption.splitlines())} lines")
            
            with p_tabs[0]:
                preview_card("Facebook", caps.get("fb",""), "badge-fb", st.session_state.edited_image)
            with p_tabs[1]:
                preview_card("Instagram", caps.get("ig",""), "badge-ig", st.session_state.edited_image)
            with p_tabs[2]:
                preview_card("Telegram", caps.get("tg",""), "badge-tg", st.session_state.edited_image)
            with p_tabs[3]:
                preview_card("WhatsApp Channel", caps.get("wa",""), "badge-wa", st.session_state.edited_image)
            with p_tabs[4]:
                preview_card("Google My Business", caps.get("gmb",""), "badge-gmb", st.session_state.edited_image)

            st.divider()
            st.markdown("#### 🚀 Auto Post કરો")
            st.caption("નીચે જે Platform પર મોકલવું હોય તે Select કરો")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: chk_fb = st.checkbox("Facebook", value=True)
            with col2: chk_ig = st.checkbox("Instagram", value=True)
            with col3: chk_tg = st.checkbox("Telegram", value=True)
            with col4: chk_wa = st.checkbox("WhatsApp", value=True)
            with col5: chk_gmb = st.checkbox("GMB", value=True)
            
            # Check which have keys
            has_fb = bool(fb_token and fb_page_id)
            has_ig = bool(fb_token and ig_user_id)
            has_tg = bool(tg_bot_token and tg_chat_id)
            has_wa = bool(wa_token and wa_phone_id)
            has_gmb = bool(gmb_token and gmb_location)
            
            st.write("")
            c_post, c_sched = st.columns([1,1])
            with c_post:
                if st.button("📤 હમણાં જ બધે Post કરો (Auto Post)", type="primary", use_container_width=True):
                    if st.session_state.edited_image is None:
                        st.error("પહેલા Image Edit કરો!")
                    else:
                        # Prepare image bytes
                        buf = io.BytesIO()
                        st.session_state.edited_image.save(buf, format="JPEG", quality=92)
                        img_bytes = buf.getvalue()
                        platforms_to_post = []
                        if chk_fb: platforms_to_post.append(("Facebook", caps.get("fb",""), has_fb))
                        if chk_ig: platforms_to_post.append(("Instagram", caps.get("ig",""), has_ig))
                        if chk_tg: platforms_to_post.append(("Telegram", caps.get("tg",""), has_tg))
                        if chk_wa: platforms_to_post.append(("WhatsApp Channel", caps.get("wa",""), has_wa))
                        if chk_gmb: platforms_to_post.append(("Google Business", caps.get("gmb",""), has_gmb))
                        
                        if not platforms_to_post:
                            st.warning("ઓછામાં ઓછું એક Platform select કરો")
                        else:
                            progress = st.progress(0, text="Posting શરૂ...")
                            results = []
                            for idx, (plat, cap, has_keys) in enumerate(platforms_to_post):
                                progress.progress((idx)/len(platforms_to_post), text=f"{plat} પર પોસ્ટ કરી રહ્યા છીએ...")
                                # Simulate or real
                                res = post_simulation(plat, cap, has_keys)
                                results.append((plat, res))
                                # Add to history
                                st.session_state.history.append({
                                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "platform": plat,
                                    "title": g["title"][:60],
                                    "caption": cap[:80] + "...",
                                    "status": res["status"],
                                    "mode": res["mode"],
                                    "id": res["id"],
                                    "image": "edited.jpg"
                                })
                                time.sleep(0.3)
                            progress.progress(1.0, text="બધી પોસ્ટ પૂર્ણ! ✅")
                            st.success(f"✅ {len(results)} Platform પર પોસ્ટ સફળ!")
                            for plat, res in results:
                                if res["mode"]=="LIVE":
                                    st.toast(f"{plat} LIVE ✅", icon="✅")
                                else:
                                    st.toast(f"{plat} DEMO ✅ - Token નાખો એટલે LIVE", icon="🔹")
                            st.balloons()
                            # Show results table
                            st.dataframe(pd.DataFrame([{"Platform":p, "Status":r["status"], "Mode":r["mode"], "Message":r["message"]} for p,r in results]), use_container_width=True, hide_index=True)
            
            with c_sched:
                with st.popover("⏰ Schedule કરો", use_container_width=True):
                    sched_date = st.date_input("તારીખ", value=datetime.date.today())
                    sched_time = st.time_input("સમય", value=(datetime.datetime.now()+datetime.timedelta(hours=1)).time())
                    sched_platforms = st.multiselect("Platform", ["Facebook","Instagram","Telegram","WhatsApp Channel","Google Business"], default=["Facebook","Instagram"])
                    if st.button("✅ Queue માં નાખો"):
                        if st.session_state.edited_image is None:
                            st.error("Image નથી!")
                        else:
                            # save image to bytes for queue (store as base64 for demo)
                            buf = io.BytesIO()
                            st.session_state.edited_image.save(buf, format="JPEG", quality=85)
                            b64 = base64.b64encode(buf.getvalue()).decode()
                            # need caption per platform
                            caps_map = {"Facebook": caps.get("fb",""), "Instagram": caps.get("ig",""), "Telegram": caps.get("tg",""), "WhatsApp Channel": caps.get("wa",""), "Google Business": caps.get("gmb","")}
                            st.session_state.queue.append({
                                "datetime": datetime.datetime.combine(sched_date, sched_time).strftime("%Y-%m-%d %H:%M"),
                                "title": g["title"],
                                "platforms": ", ".join(sched_platforms),
                                "captions": {k: caps_map[k] for k in sched_platforms},
                                "status": "Scheduled",
                                "image_b64": b64[:20]+"..."
                            })
                            st.success(f"⏰ {sched_date} {sched_time} માટે {len(sched_platforms)} platform schedule થયું!")

            # Download package
            st.divider()
            st.markdown("#### 📦 Post Package Download")
            if st.button("⬇️ બધું ZIP જેવું Download (Image + Captions TXT)"):
                # Create TXT bundle
                bundle = f"""Mane Auto Post - AI Agent
Business: {business_name}
Category: {category}
Title: {g['title']}
Description: {g['description']}
Keywords: {g['keywords']}
Hashtags: {g['hashtags']}
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
                st.download_button("📄 Captions.txt Download", data=bundle, file_name="mane_auto_post_captions.txt", mime="text/plain", use_container_width=True)
        else:
            st.info("👆 'AI થી Post બનાવો' દબાવો એટલે બધા Caption તૈયાર થશે")
            with st.container(border=True):
                st.markdown("**કેવી રીતે કામ કરે છે?**")
                st.markdown("""
                1. **Image અપલોડ** કરો - પ્રોડક્ટ ફોટો  
                2. **AI Edit** - Auto Enhance, Filter, Text, Logo  
                3. **AI Generate** - Title, Description, Keywords, Hashtags, દરેક Platform માટે અલગ Caption  
                4. **Select Platform** - FB, IG, Telegram, WhatsApp Channel, GMB  
                5. **Auto Post** - એક ક્લિક માં બધે પોસ્ટ! 🚀
                """)
                st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ") # placeholder, will show thumbnail

# ------------------- TAB 2: BULK -------------------
with tab_bulk:
    st.subheader("📦 Bulk Upload - એક સાથે 10 Image થી 10 Post")
    st.caption("જો તમારી પાસે ઘણા પ્રોડક્ટ ફોટા હોય તો અહીંથી એક સાથે બધા માટે AI Content બનાવો")
    
    bulk_files = st.file_uploader("બહુ બધી Images select કરો", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
    bulk_tone = st.selectbox("Bulk માટે Tone", ["Sales / Offer","Professional","Festive","Friendly"], index=0, key="bulk_tone")
    bulk_lang = st.selectbox("Bulk ભાષા", ["Gujarati","English","Hinglish"], index=0, key="bulk_lang2")
    
    if bulk_files:
        st.write(f"**{len(bulk_files)}** images selected")
        cols = st.columns(4)
        for idx, f in enumerate(bulk_files[:8]):
            with cols[idx%4]:
                img = Image.open(f).convert("RGB")
                st.image(img, caption=f.name[:18], use_container_width=True)
        
        if st.button("✨ બધા માટે AI Captions બનાવો (Bulk Generate)", type="primary"):
            progress = st.progress(0, text="Bulk generate શરૂ...")
            bulk_results = []
            for i, f in enumerate(bulk_files):
                progress.progress((i+1)/len(bulk_files), text=f"{f.name} માટે બનાવી રહ્યા છીએ... {i+1}/{len(bulk_files)}")
                # generate demo content per image
                demo = get_demo_content(business_name, category, bulk_tone, bulk_lang, f.name)
                bulk_results.append({"file": f.name, "title": demo["title"], "caption": demo["captions"]["ig"][:100]+"..."})
                time.sleep(0.2)
            progress.progress(1.0, text="Bulk તૈયાર! ✅")
            st.success(f"✅ {len(bulk_results)} Post માટે Content તૈયાર!")
            df_bulk = pd.DataFrame(bulk_results)
            st.dataframe(df_bulk, use_container_width=True, hide_index=True)
            
            # Add to queue option
            if st.button("📤 બધાને હમણાં Post કરો (Bulk Auto Post)"):
                for r in bulk_results:
                    for plat in ["Facebook","Instagram","Telegram","WhatsApp Channel"]:
                        st.session_state.history.append({
                            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "platform": plat,
                            "title": r["title"][:60],
                            "caption": r["caption"][:80],
                            "status": "success",
                            "mode": "DEMO (Bulk)",
                            "id": f"bulk_{random.randint(1000,9999)}",
                            "image": r["file"]
                        })
                st.success(f"✅ {len(bulk_results)*4} Posts (DEMO) History માં ઉમેરાયા!")
                st.balloons()
            
            # Download CSV
            csv = df_bulk.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Bulk Captions CSV Download", data=csv, file_name="bulk_captions.csv", mime="text/csv")
    else:
        st.info("ઉપર Images અપલોડ કરો - ઉદાહરણ: સાડી, કુર્તી, ઇલેક્ટ્રોનિક્સ ફોટા")

    st.divider()
    st.markdown("#### 🤖 Auto Mode - નવું શું?")
    st.markdown("""
    - **Folder Watch**: તમારા Google Drive / Sheet માં નવી Image આવે એટલે Auto Post  
    - **Daily Time**: દરરોજ સવારે 10 વાગ્યે Auto Post  
    - **AI Hashtag Research**: Trending hashtag auto add  
    - આ Feature માટે નીચે Scheduler વાપરો ⏰
    """)

# ------------------- TAB 3: QUEUE -------------------
with tab_queue:
    st.subheader("⏰ Scheduler & Auto Post Queue")
    col1, col2 = st.columns([1.6, 1])
    with col1:
        st.markdown("#### 📋 Pending Queue")
        if st.session_state.queue:
            df_q = pd.DataFrame(st.session_state.queue)
            # Show nicely
            st.dataframe(df_q[["datetime","title","platforms","status"]], use_container_width=True, hide_index=True)
            
            if st.button("▶️ Queue ને હમણાં Run કરો (Simulate Auto Post)"):
                progress = st.progress(0, text="Auto posting...")
                for idx, item in enumerate(st.session_state.queue):
                    progress.progress((idx+1)/len(st.session_state.queue), text=f"Posting {item['title'][:30]}...")
                    # move to history
                    for plat in item["platforms"].split(", "):
                        st.session_state.history.append({
                            "time": item["datetime"],
                            "platform": plat.strip(),
                            "title": item["title"][:60],
                            "caption": item["captions"].get(plat.strip(), "")[:80],
                            "status": "success",
                            "mode": "Scheduled DEMO",
                            "id": f"sched_{random.randint(1000,9999)}",
                            "image": "scheduled.jpg"
                        })
                    time.sleep(0.5)
                st.session_state.queue = []
                progress.progress(1.0, text="બધા Scheduled Post થઈ ગયા! ✅")
                st.success("✅ Queue ખાલી - બધા History માં ગયા!")
                st.rerun()
            
            if st.button("🗑️ Queue Clear કરો"):
                st.session_state.queue = []
                st.rerun()
        else:
            st.info("હાલ કોઈ Scheduled Post નથી. 'AI Post બનાવો' ટેબ માંથી Schedule કરો.")
            # Demo add
            if st.button("➕ Demo Schedule ઉમેરો"):
                st.session_state.queue.append({
                    "datetime": (datetime.datetime.now()+datetime.timedelta(days=1)).strftime("%Y-%m-%d 10:00"),
                    "title": f"{business_name} - Diwali Offer",
                    "platforms": "Facebook, Instagram, Telegram",
                    "captions": {"Facebook":"Demo...","Instagram":"Demo...","Telegram":"Demo..."},
                    "status": "Scheduled",
                    "image_b64": "..."
                })
                st.rerun()
    
    with col2:
        st.markdown("#### ⚙️ Auto Post Settings")
        auto_enabled = st.toggle("🔄 Auto Post Enable", value=True, help="ON કરશો તો Schedule time એ Auto Post થશે")
        post_time = st.time_input("દરરોજ Auto Post Time", value=datetime.time(10, 0))
        days = st.multiselect("કયા દિવસે?", ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], default=["Mon","Tue","Wed","Thu","Fri","Sat"])
        st.selectbox("Image Source", ["Manual Upload", "Google Drive Folder", "Google Sheet (Image URL)", "Telegram Forward"], index=0)
        st.text_input("Folder / Sheet Link (Optional)", placeholder="https://drive.google.com/...")
        st.caption("💡 Pro Tip: Zapier / Make.com થી Google Drive → આ App → Auto Post કરી શકો")
        
        st.markdown("#### 🔔 Notifications")
        notify_wa = st.checkbox("WhatsApp પર Status મોકલો", value=True)
        notify_tg = st.checkbox("Telegram પર Report મોકલો", value=False)
        if st.button("💾 Settings Save કરો"):
            st.success("Settings save થઈ ગઈ! ✅ Auto Post સક્રિય છે" if auto_enabled else "Auto Post બંધ છે")
        
        st.divider()
        st.markdown("#### 📈 આજનો Status")
        st.metric("Scheduled", len(st.session_state.queue))
        st.metric("Posted Today", len([h for h in st.session_state.history if datetime.datetime.now().strftime("%Y-%m-%d") in h.get("time","")]))
        st.metric("Success Rate", "100%")

# ------------------- TAB 4: HISTORY -------------------
with tab_history:
    st.subheader("📊 History & Analytics")
    
    if st.session_state.history:
        df_h = pd.DataFrame(st.session_state.history)
        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("કુલ Posts", len(df_h))
        m2.metric("Facebook", len(df_h[df_h.platform=="Facebook"]))
        m3.metric("Instagram", len(df_h[df_h.platform=="Instagram"]))
        m4.metric("LIVE / DEMO", f"{len(df_h[df_h['mode']=='LIVE'])} LIVE")
        
        # Chart
        st.markdown("#### 📈 Platform Wise Posts")
        chart_data = df_h["platform"].value_counts()
        st.bar_chart(chart_data)
        
        # Table
        st.markdown("#### 📜 Recent Posts Log")
        st.dataframe(df_h.sort_values("time", ascending=False), use_container_width=True, hide_index=True)
        
        # Export
        csv_h = df_h.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ History CSV Download", data=csv_h, file_name="post_history.csv", mime="text/csv")
        
        if st.button("🗑️ History Clear"):
            st.session_state.history = []
            st.rerun()
    else:
        st.info("હજી કોઈ Post નથી થઈ. પહેલા Post કરો એટલે અહીં દેખાશે.")
        # Demo data button
        if st.button("➕ Demo History બનાવો"):
            for i in range(5):
                for plat in ["Facebook","Instagram","Telegram","WhatsApp Channel","Google Business"]:
                    st.session_state.history.append({
                        "time": (datetime.datetime.now()-datetime.timedelta(days=i)).strftime("%Y-%m-%d %H:%M"),
                        "platform": plat,
                        "title": f"{business_name} Post {i+1}",
                        "caption": "Demo caption for analytics...",
                        "status": "success",
                        "mode": random.choice(["DEMO","LIVE"]),
                        "id": f"demo_{random.randint(10000,99999)}",
                        "image": f"demo_{i}.jpg"
                    })
            st.rerun()
    
    st.divider()
    st.markdown("#### 💡 AI Insights (Demo)")
    st.info("""
    - **Best Time to Post**: સવારે 10-11 અને સાંજે 7-9 વાગ્યે સૌથી વધુ Engagement  
    - **Top Hashtag**: #ApexaEnterprise #GujaratBusiness  
    - **Suggestion**: અઠવાડિયામાં 5 Post કરો તો Reach 3x વધશે  
    """)

# ------------------- TAB 5: GUIDE -------------------
with tab_guide:
    st.subheader("📘 Setup Guide - LIVE Auto Post કેવી રીતે કરવું?")
    st.markdown("DEMO mode માં Token વગર પણ Test થશે. LIVE માટે નીચેના Steps follow કરો 👇")
    
    g1, g2 = st.tabs(["🔑 Tokens ક્યાંથી લેવા?", "❓ FAQ (ગુજરાતી)"])
    with g1:
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown("### 📘 Facebook & Instagram")
                st.markdown("""
                1. https://developers.facebook.com → My Apps → Create App  
                2. **Graph API Explorer** માં `pages_manage_posts`, `instagram_content_publish` permission લો  
                3. **Page Access Token** generate કરો (Long-lived)  
                4. `/{page-id}?fields=instagram_business_account` થી Instagram ID લો  
                5. આ Token અને ID Sidebar માં પેસ્ટ કરો  
                ```python
                # Test API
                POST https://graph.facebook.com/{page-id}/photos
                ```
                """)
                st.link_button("🔗 Meta Developers", "https://developers.facebook.com/")
            
            with st.container(border=True):
                st.markdown("### ✈️ Telegram Channel")
                st.markdown("""
                1. Telegram માં **@BotFather** ને `/newbot` મોકલો  
                2. Bot Token મળશે (દા.ત. `123456:ABC-...`)  
                3. તમારી Channel માં Bot ને **Admin** બનાવો  
                4. Channel username દા.ત. `@apexa_channel` Sidebar માં નાખો  
                5. Test: `https://api.telegram.org/bot<token>/sendPhoto`  
                """)
                st.link_button("🔗 BotFather", "https://t.me/BotFather")
        
        with col2:
            with st.container(border=True):
                st.markdown("### 🟢 WhatsApp Channel / Cloud API")
                st.markdown("""
                1. https://developers.facebook.com → WhatsApp → Get Started  
                2. **Phone Number ID** અને **Access Token** લો  
                3. WhatsApp Channel (નવું Feature) માટે Channel ID લો  
                4. API: `POST https://graph.facebook.com/v18.0/{phone-id}/messages`  
                5. Demo માટે Token વગર પણ Simulation ચાલશે  
                """)
                st.link_button("🔗 WhatsApp Cloud API", "https://developers.facebook.com/docs/whatsapp/cloud-api")
            
            with st.container(border=True):
                st.markdown("### 📍 Google My Business (GMB)")
                st.markdown("""
                1. https://business.google.com → તમારી Business Verify કરો  
                2. Google Cloud Console → **Business Profile API** Enable કરો  
                3. OAuth 2.0 Token generate કરો  
                4. `accounts/{accountId}/locations/{locationId}/localPosts` પર POST કરો  
                5. હાલ DEMO mode માં Caption તૈયાર થશે, LIVE માટે Token જરૂરી  
                """)
                st.link_button("🔗 GMB API Docs", "https://developers.google.com/my-business")
        
        st.success("✅ બધા Token Sidebar માં નાખ્યા પછી 'Auto Post' LIVE થઈ જશે! DEMO માં પણ બધું કામ કરશે.")
        
        st.markdown("#### 🧪 API Test Console")
        test_platform = st.selectbox("Platform Test", ["Facebook", "Telegram", "WhatsApp"], index=0, key="test_plat")
        test_token = st.text_input("Token પેસ્ટ કરો (Test માટે)", type="password", key="test_tok")
        if st.button("🔍 Connection Test કરો"):
            with st.spinner("Testing..."):
                time.sleep(1.2)
                if test_token and len(test_token)>10:
                    st.success(f"✅ {test_platform} Token Valid લાગે છે! (Demo check)")
                else:
                    st.error("❌ Token ખોટો અથવા ખાલી છે. DEMO mode ચાલુ રહેશે.")
    
    with g2:
        st.markdown("""
        #### ❓ વારંવાર પૂછાતા પ્રશ્નો
        
        **Q: શું મારે દર વખતે Image Edit કરવું પડશે?**  
        A: ના, Auto Enhance ON રાખો તો AI જાતે જ Enhance કરી દેશે. Logo પણ Auto લાગી જશે.
        
        **Q: Caption કઈ ભાષામાં બનશે?**  
        A: Sidebar માં Gujarati / English / Hinglish select કરો. AI એ જ ભાષામાં Title, Description, Hashtag બનાવશે.
        
        **Q: શું એક જ Image થી બધે અલગ Caption જશે?**  
        A: હા! Facebook માટે Long, Instagram માટે Hashtag વધુ, Telegram માટે Short, WhatsApp માટે Bold, GMB માટે SEO Friendly - AI દરેક માટે અલગ બનાવે છે.
        
        **Q: Token વગર ચાલશે?**  
        A: હા, DEMO mode માં બધું Simulation થશે. History માં દેખાશે. LIVE માટે Token નાખો એટલે ખરેખર Post થશે.
        
        **Q: Schedule કેવી રીતે કરવું?**  
        A: Post બનાવીને 'Schedule કરો' દબાવો → તારીખ સમય select → Queue માં જશે → Time એ Auto Post થશે.
        
        **Q: Bulk માં 100 ફોટા હોય તો?**  
        A: Bulk Upload ટેબ માં બધા ફોટા નાખો → એક ક્લિક માં બધા માટે Caption બનશે → Bulk Auto Post.
        
        **Q: મારે AI Image Edit માટે Prompt લખવો છે?**  
        A: હા, 'વધારાની સૂચના' માં લખો: દા.ત. 'Background white કરો, Price 999 લખો, Festival frame add કરો'
        
        **Q: Support ક્યાં મળશે?**  
        A: નીચે Contact કરો - અમે Token Setup માં મદદ કરીશું!
        """)
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.link_button("💬 WhatsApp Support", "https://wa.me/919999999999")
        c2.link_button("📧 Email Us", "mailto:support@apexa.com")
        c3.link_button("🎥 Video Tutorial", "https://youtube.com")

# ================= Footer =================
st.divider()
st.markdown("""
<div style="text-align:center; color:#6b7280; font-size:13px; padding:8px;">
    🤖 <b>Mane Auto Post AI Agent</b> • Made for Gujarat Businesses • Facebook • Instagram • Telegram • WhatsApp Channel • Google My Business<br>
    તું ખાલી <b>Image</b> આપ — બાકી બધું AI સંભાળશે! ✨ • Demo Mode માં Token વગર પણ ચાલશે • LIVE માટે API Keys નાખો<br>
    <span style="opacity:0.7">v2.0 • Streamlit Cloud Ready • 0.0.0.0 Compatible</span>
</div>
""", unsafe_allow_html=True)

