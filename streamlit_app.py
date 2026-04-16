import streamlit as st
import pandas as pd

# Page Configuration for Mobile & Desktop
st.set_page_config(page_title="Business Daily Diary", layout="wide", initial_sidebar_state="collapsed")

# Custom Styling
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stSidebar"] { background-color: #1e293b; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. INITIAL DATA SETTINGS ---
if 'bank_data' not in st.session_state:
    st.session_state.bank_data = pd.DataFrame([
        {"BANK": "BHAVNA-BOB", "OPENING": 8385, "IN": 19302, "OUT": 0},
        {"BANK": "MUMMY-VARA", "OPENING": 58008, "IN": 9863, "OUT": 0},
        {"BANK": "BOSS-UNI", "OPENING": 75239, "IN": 0, "OUT": 0},
        {"BANK": "SBI VISHAL", "OPENING": 25, "IN": 0, "OUT": 0},
        {"BANK": "IDBI APEXA", "OPENING": 14877, "IN": 0, "OUT": 0},
        {"BANK": "BOB VISHAL", "OPENING": 35, "IN": 0, "OUT": 0},
        {"BANK": "BOB PANTH", "OPENING": 16192, "IN": 475, "OUT": 0},
        {"BANK": "OTHER BANK", "OPENING": 1489, "IN": 0, "OUT": 0},
    ])

if 'cash_data' not in st.session_state:
    st.session_state.cash_data = pd.DataFrame([
        {"LOCATION": "KATARGAM", "OPENING": 192500, "IN": 19000, "OUT": 66000},
        {"LOCATION": "YOGI CHOWK", "OPENING": 314500, "IN": 154000, "OUT": 115000},
    ])

if 'khata_data' not in st.session_state:
    st.session_state.khata_data = pd.DataFrame([
        {"BRANCH": "KATARGAM", "OPENING": 95450, "IN": 0, "OUT": 0},
        {"BRANCH": "YOGI CHOWK", "OPENING": 565283, "IN": 70590, "OUT": 54960},
    ])

if 'party_data' not in st.session_state:
    st.session_state.party_data = pd.DataFrame([
        {"PARTY": "PUSHPA", "CURRENT": 552073, "ADD": 0, "LESS": 0},
        {"PARTY": "ANSARI", "CURRENT": 117820, "ADD": 0, "LESS": 0},
        {"PARTY": "JUNED", "CURRENT": 181150, "ADD": 0, "LESS": 0},
        {"PARTY": "MUSHIR", "CURRENT": -11180, "ADD": 0, "LESS": 0},
        {"PARTY": "MAMTA", "CURRENT": 43480, "ADD": 53080, "LESS": 280},
        {"PARTY": "SAJIDA", "CURRENT": 1840, "ADD": 0, "LESS": 0},
        {"PARTY": "SALMAN", "CURRENT": 397215, "ADD": 0, "LESS": 0},
        {"PARTY": "DIPALI", "CURRENT": 320672, "ADD": 59628, "LESS": 0},
        {"PARTY": "MOHIT", "CURRENT": 110760, "ADD": 6000, "LESS": 22500},
        {"PARTY": "TOFIK", "CURRENT": 0, "ADD": 254160, "LESS": 150000},
        {"PARTY": "FABRIC", "CURRENT": 47759, "ADD": 0, "LESS": 0},
        {"PARTY": "GOLD LOAN", "CURRENT": 46000, "ADD": 0, "LESS": 0},
        {"PARTY": "PARTY-4", "CURRENT": 125300, "ADD": 57500, "LESS": 10000},
        {"PARTY": "PARTY-5", "CURRENT": 0, "ADD": 17000, "LESS": 17000},
    ])

# --- 2. SIDEBAR NAVIGATION ---
st.sidebar.title("💎 વ્યાપાર મેનેજર")
menu = st.sidebar.radio("મેનુ", ["📊 ડેશબોર્ડ", "🏦 બેંક હિસાબ", "💵 રોકડ (Cash)", "📖 ખાતાબુક", "👥 પાર્ટી લેજર"])

# --- 3. CALCULATIONS ---
bank_total = (st.session_state.bank_data['OPENING'] + st.session_state.bank_data['IN'] - st.session_state.bank_data['OUT']).sum()
cash_total = (st.session_state.cash_data['OPENING'] + st.session_state.cash_data['IN'] - st.session_state.cash_data['OUT']).sum()
total_sales = st.session_state.bank_data['IN'].sum() + st.session_state.cash_data['IN'].sum()

# --- 4. DASHBOARD ---
if menu == "📊 ડેશબોર્ડ":
    st.header("આજની સ્થિતિની ઝલક")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("કુલ રોકડ (Cash Balance)", f"₹ {cash_total:,.0f}")
        st.metric("બેંક બેલેન્સ (Bank Balance)", f"₹ {bank_total:,.0f}")
    with col2:
        st.metric("આજનું કુલ વેચાણ (Total Sales)", f"₹ {total_sales:,.0f}")
        st.metric("કુલ સંપત્તિ (Total Assets)", f"₹ {cash_total + bank_total:,.0f}")
    
    st.divider()
    st.subheader("💡 ઝડપી માહિતી")
    st.info(f"પાર્ટીઓ પાસેથી કુલ ₹ { (st.session_state.party_data['CURRENT'] + st.session_state.party_data['ADD'] - st.session_state.party_data['LESS']).sum():,.0f} લેવાના બાકી છે.")

# --- 5. BANK SECTION ---
elif menu == "🏦 બેંક હિસાબ":
    st.header("🏦 બેંક ટ્રાન્ઝેક્શન")
    df_b = st.session_state.bank_data
    df_b['CLOSING'] = df_b['OPENING'] + df_b['IN'] - df_b['OUT']
    edited_bank = st.data_editor(df_b, num_rows="dynamic", use_container_width=True)
    st.session_state.bank_data = edited_bank
    st.success(f"બેંક ટોટલ: ₹ {edited_bank['CLOSING'].sum():,.0f}")

# --- 6. CASH SECTION ---
elif menu == "💵 રોકડ (Cash)":
    st.header("💵 રોકડ (Cash) વિગત")
    df_c = st.session_state.cash_data
    df_c['CLOSING'] = df_c['OPENING'] + df_c['IN'] - df_c['OUT']
    edited_cash = st.data_editor(df_c, num_rows="dynamic", use_container_width=True)
    st.session_state.cash_data = edited_cash
    st.success(f"કેશ ટોટલ: ₹ {edited_cash['CLOSING'].sum():,.0f}")

# --- 7. KHATABOOK SECTION ---
elif menu == "📖 ખાતાબુક":
    st.header("📖 શાખા મુજબ ખાતાબુક")
    df_k = st.session_state.khata_data
    df_k['CLOSING'] = df_k['OPENING'] + df_k['IN'] - df_k['OUT']
    edited_khata = st.data_editor(df_k, num_rows="dynamic", use_container_width=True)
    st.session_state.khata_data = edited_khata
    st.warning(f"ખાતાબુક ટોટલ: ₹ {edited_khata['CLOSING'].sum():,.0f}")

# --- 8. PARTY LEDGER ---
elif menu == "👥 પાર્ટી લેજર":
    st.header("👥 પાર્ટી લેણ-દેણ હિસાબ")
    df_p = st.session_state.party_data
    df_p['TOTAL'] = df_p['CURRENT'] + df_p['ADD'] - df_p['LESS']
    edited_party = st.data_editor(df_p, num_rows="dynamic", use_container_width=True)
    st.session_state.party_data = edited_party
    st.info(f"કુલ બાકી ઉઘરાણી: ₹ {edited_party['TOTAL'].sum():,.0f}")

st.sidebar.markdown("---")
st.sidebar.caption("વિકસિત: હર્ષ ડાયરી સોફ્ટવેર")
