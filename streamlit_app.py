import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Page Configuration for Mobile & Desktop
st.set_page_config(page_title="Business Pro Manager", layout="wide")

# Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# ડેટા લોડ કરવાનું ફંક્શન
def load_data(sheet_name):
    try:
        # worksheet=sheet_name નો ઉપયોગ કરીને ચોક્કસ ટેબ માંથી ડેટા લાવવો
        return conn.read(worksheet=sheet_name, ttl="0s")
    except Exception as e:
        return pd.DataFrame()

st.title("🛡️ બિઝનેસ મેનેજમેન્ટ સોફ્ટવેર")

# સાઈડબાર મેનુ
menu = st.sidebar.radio("મેનુ પસંદ કરો", 
    ["📊 ડેશબોર્ડ", "🏦 બેંક & કેશ", "📦 સ્ટોક મેનેજમેન્ટ", "🏭 મેન્યુફેક્ચરિંગ", "👥 પાર્ટી લેજર"])

# --- ૧. બેંક & કેશ ---
if menu == "🏦 બેંક & કેશ":
    st.header("🏦 બેંક અને રોકડ એન્ટ્રી")
    df = load_data("Bank")
    if not df.empty:
        df['CLOSING'] = df['OPENING'] + df.get('IN', 0) - df.get('OUT', 0)
        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("Save Bank Data"):
            conn.update(worksheet="Bank", data=edited)
            st.success("બેંક વિગત સેવ થઈ ગઈ!")
    else:
        st.error("Google Sheet માં 'Bank' નામની ટેબ ચેક કરો.")

# --- ૨. સ્ટોક મેનેજમેન્ટ (STOCK ALL) ---
elif menu == "📦 સ્ટોક મેનેજમેન્ટ":
    st.header("📦 સ્ટોક (Inventory) મેનેજમેન્ટ")
    df_s = load_data("Stock")
    if not df_s.empty:
        df_s['CLOSING'] = df_s['OPENING'] + df_s.get('DAILY IN', 0) - df_s.get('DAILY OUT', 0)
        edited_s = st.data_editor(df_s, num_rows="dynamic", use_container_width=True)
        if st.button("Update Stock"):
            conn.update(worksheet="Stock", data=edited_s)
            st.success("સ્ટોક અપડેટ થયો!")
    else:
        st.error("Google Sheet માં 'Stock' નામની ટેબ ચેક કરો.")

# --- ૩. મેન્યુફેક્ચરિંગ ---
elif menu == "🏭 મેન્યુફેક્ચરિંગ":
    st.header("🏭 પ્રોડક્શન / મેન્યુફેક્ચરિંગ વિગત")
    df_m = load_data("MFG")
    if not df_m.empty:
        edited_m = st.data_editor(df_m, num_rows="dynamic", use_container_width=True)
        if st.button("Save Production Data"):
            conn.update(worksheet="MFG", data=edited_m)
            st.success("મેન્યુફેક્ચરિંગ ડેટા સેવ થયો!")
    else:
        st.error("Google Sheet માં 'MFG' નામની ટેબ ચેક કરો.")

# --- ૪. પાર્ટી લેજર ---
elif menu == "👥 પાર્ટી લેજર":
    st.header("👥 પાર્ટી લેણ-દેણ")
    df_p = load_data("Party")
    if not df_p.empty:
        df_p['TOTAL'] = df_p['BAL'] + df_p.get('ADD', 0) - df_p.get('LESS', 0)
        edited_p = st.data_editor(df_p, num_rows="dynamic", use_container_width=True)
        if st.button("Save Ledger"):
            conn.update(worksheet="Party", data=edited_p)
            st.success("પાર્ટી હિસાબ સેવ થયો!")
    else:
        st.error("Google Sheet માં 'Party' નામની ટેબ ચેક કરો.")

# --- ૫. ડેશબોર્ડ ---
else:
    st.header("📈 બિઝનેસ ડેશબોર્ડ")
    st.write("Google Sheets માંથી લાઈવ માહિતી લોડ થઈ રહી છે.")
    
    # Dashboard summary logic
    st.info("નોંધ: ડેટા ઉમેરવા માટે અથવા જોવા માટે સાઈડબારમાંથી વિભાગ પસંદ કરો.")
    st.write("તમારા સ્ટોક અને રોકડની વિગતો જોવા માટે સંબંધિત મેનુમાં જાઓ.")
