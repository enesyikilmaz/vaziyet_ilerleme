import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime

# Sayfa Ayarları
st.set_page_config(page_title="Şantiye İlerleme Takip", layout="wide", page_icon="🏗️")

# --- VERİ OKUMA VE ÖNBELLEĞE ALMA ---
@st.cache_data
def load_master_data():
    df_blok = pd.read_excel("Blok İsimleri.xlsx")
    df_imalat = pd.read_excel("İmalat İsimleri.xlsx")
    return df_blok, df_imalat

df_blok, df_imalat = load_master_data()

# --- VERİTABANI (LOG) SİMÜLASYONU ---
LOG_FILE = "santiye_log.csv"
if not os.path.exists(LOG_FILE):
    # Eğer daha önce girilmiş veri yoksa boş tablo oluştur
    df_log = pd.DataFrame(columns=["Tarih", "Yüklenici", "Proje", "Parsel", "Blok", "İmalat", "İlerleme"])
    df_log.to_csv(LOG_FILE, index=False)

def load_logs():
    return pd.read_csv(LOG_FILE)

def save_log(yuklenici, proje, parsel, blok, imalat, ilerleme):
    # Yeni girilen veriyi log dosyasına alt satır olarak ekle
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df = pd.DataFrame([[now, yuklenici, proje, parsel, blok, imalat, ilerleme]], 
                      columns=["Tarih", "Yüklenici", "Proje", "Parsel", "Blok", "İmalat", "İlerleme"])
    df.to_csv(LOG_FILE, mode='a', header=False, index=False)

def get_latest_progress(parsel, blok, imalat):
    df_log = load_logs()
    # Bu blok ve imalat için geçmiş kayıtları süz
    mask = (df_log["Parsel"] == int(parsel)) & (df_log["Blok"] == str(blok)) & (df_log["İmalat"] == imalat)
    filtered = df_log[mask]
    if not filtered.empty:
        return filtered.iloc[-1]["İlerleme"] # En son girilen değeri döndür
    return "YOK" # Hiç girilmediyse varsayılan

# Değer Haritası (Kıyaslama ve Validasyon için)
VAL_MAP = {"YOK": -1, "%0": 0, "%25": 25, "%50": 50, "%75": 75, "%100": 100}

# --- SEKMELER (ARAYÜZ) ---
tab1, tab2 = st.tabs(["📝 Veri Girişi", "📊 Yönetici Görsel Raporu"])

with tab1:
    st.header("Saha İmalat İlerleme Veri Girişi")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Bölge Seçimi")
        yukleniciler = df_blok["Yüklenici Firma"].unique()
        secilen_yuklenici = st.selectbox("Yüklenici Adı", yukleniciler)
        
        projeler = df_blok[df_blok["Yüklenici Firma"] == secilen_yuklenici]["Proje Adı"].unique()
        secilen_proje = st.selectbox("Proje Adı", projeler)
        
        parseller = df_blok[(df_blok["Yüklenici Firma"] == secilen_yuklenici) & (df_blok["Proje Adı"] == secilen_proje)]["Parsel Adı"].unique()
        secilen_parsel = st.selectbox("Parsel Adı", parseller)
        
        bloklar = df_blok[(df_blok["Yüklenici Firma"] == secilen_yuklenici) & 
                          (df_blok["Proje Adı"] == secilen_proje) & 
                          (df_blok["Parsel Adı"] == secilen_parsel)]["Blok Adı"].unique()
        
        secilen_blok = st.selectbox("Blok Adı", ["Lütfen Seçiniz..."] + list(bloklar))
    
    with col2:
        st.subheader(f"📍 {secilen_parsel} Parsel Vaziyet Planı")
        svg_path = f"{secilen_parsel} Parsel.svg"
        if os.path.exists(svg_path):
            with open(svg_path, "r", encoding="utf-8") as f:
                st.components.v1.html(f.read(), height=400)
        else:
            st.warning(f"Sistemde '{svg_path}' bulunamadı. Lütfen klasöre ekleyin.")

    st.divider()
    
    if secilen_blok != "Lütfen Seçiniz...":
        st.subheader(f"🛠️ {secilen_blok} Blok Veri Giriş Ekranı")
        
        with st.form("veri_giris_formu"):
            giris_verileri = {}
            
            # Excel'deki İmalatları tek tek form elemanı olarak listele
            for index, row in df_imalat.iterrows():
                imalat_adi = row["İMALATIN ADI"]
                son_deger = get_latest_progress(secilen_parsel, secilen_blok, imalat_adi)
                
                options = list(VAL_MAP.keys())
                default_idx = options.index(son_deger) if son_deger in options else 0
                
                # Form Elemanı
                giris_verileri[imalat_adi] = {
                    "old": son_deger,
                    "new": st.selectbox(f"{imalat_adi} (Mahal: {row['BULUNDUĞU MAHAL']})", options, index=default_idx)
                }
            
            st.markdown("<br>", unsafe_allow_html=True)
            kaydet = st.form_submit_button("💾 VERİLERİ KAYDET", use_container_width=True)
            
            if kaydet:
                hata_var = False
                # Hata Kontrolü (% düşüş var mı?)
                for imalat, veriler in giris_verileri.items():
                    old_val = VAL_MAP[veriler["old"]]
                    new_val = VAL_MAP[veriler["new"]]
                    
                    if new_val < old_val and new_val != -1: 
                        st.error(f"HATA! {imalat} için İLERLEME, SON GİRİLEN DEĞERDEN ({veriler['old']}) DÜŞÜK OLAMAZ!")
                        hata_var = True
                        
                if not hata_var:
                    degisiklik_yapildi_mi = False
                    for imalat, veriler in giris_verileri.items():
                        if veriler["new"] != veriler["old"]: 
                            save_log(secilen_yuklenici, secilen_proje, secilen_parsel, secilen_blok, imalat, veriler["new"])
                            degisiklik_yapildi_mi = True
                    
                    if degisiklik_yapildi_mi:
                        st.success("Veriler başarıyla log sistemine kaydedildi! Raporlar güncellendi.")
                    else:
                        st.info("Herhangi bir ilerleme değişikliği yapılmadı.")

with tab2:
    st.header("Rapor Ekranı")
    
    col3, col4, col5 = st.columns(3)
    rap_yuklenici = col3.selectbox("Rapor - Yüklenici", yukleniciler)
    rap_proje = col4.selectbox("Rapor - Proje", df_blok[df_blok["Yüklenici Firma"] == rap_yuklenici]["Proje Adı"].unique())
    rap_parsel = col5.selectbox("Rapor - Parsel", df_blok[(df_blok["Yüklenici Firma"] == rap_yuklenici) & (df_blok["Proje Adı"] == rap_proje)]["Parsel Adı"].unique())
    
    st.divider()
    st.markdown("### 📌 Lejant:")
    st.markdown("⬜ **YOK (İmalat Yok)** &nbsp;&nbsp;|&nbsp;&nbsp; 🟥 **%0 (Başlanmadı)** &nbsp;&nbsp;|&nbsp;&nbsp; 🟨🟩 **%25-%75 (Kısmi Dolgu-Devam Ediyor)** &nbsp;&nbsp;|&nbsp;&nbsp; 🟩 **%100 (Tamamlandı)**")
    st.divider()
    
    parsel_bloklari = df_blok[(df_blok["Parsel Adı"] == rap_parsel)]["Blok Adı"].unique()
    df_log_all = load_logs()
    
    rap_svg_path = f"{rap_parsel} Parsel.svg"
    if not os.path.exists(rap_svg_path):
        st.error("Rapor oluşturulabilmesi için SVG dosyası eksik.")
    else:
        with open(rap_svg_path, "r", encoding="utf-8") as f:
            base_svg = f.read()
            
        for index, row in df_imalat.iterrows():
            imalat_adi = row["İMALATIN ADI"]
            
            # Her bir blok için son ilerleme değerini hesapla
            blok_degerleri = {}
            for b in parsel_bloklari:
                mask = (df_log_all["Parsel"] == rap_parsel) & (df_log_all["Blok"] == str(b)) & (df_log_all["İmalat"] == imalat_adi)
                filt = df_log_all[mask]
                if not filt.empty:
                    blok_degerleri[b] = filt.iloc[-1]["İlerleme"]
                else:
                    blok_degerleri[b] = "YOK"
            
            # SVG İçine Dinamik CSS ve Gradient Gömme İşlemi
            defs = "<defs>\n"
            styles = "<style>\n"
            
            for b, val in blok_degerleri.items():
                # stroke-width ve color ile blok sınırlarını belirginleştiriyoruz
                if val == "YOK":
                    styles += f"#{b} {{ fill: #ffffff !important; stroke: #000000 !important; stroke-width: 2px; }}\n"
                elif val == "%0":
                    styles += f"#{b} {{ fill: #ff0000 !important; stroke: #000000 !important; stroke-width: 2px; }}\n"
                elif val == "%100":
                    styles += f"#{b} {{ fill: #006400 !important; stroke: #000000 !important; stroke-width: 2px; }}\n"
                else: 
                    # %25, %50, %75 için Kısmi dolgu (Aşağıdan yukarıya bardak gibi dolar)
                    num_val = int(val.replace('%', ''))
                    grad_id = f"grad_{b}_{num_val}"
                    defs += f'''
                    <linearGradient id="{grad_id}" x1="0%" y1="100%" x2="0%" y2="0%">
                        <stop offset="{num_val}%" stop-color="#90EE90" />
                        <stop offset="{num_val}%" stop-color="#ffffff" />
                    </linearGradient>
                    '''
                    styles += f"#{b} {{ fill: url(#{grad_id}) !important; stroke: #000000 !important; stroke-width: 2px; }}\n"
            
            defs += "</defs>\n"
            styles += "</style>\n"
            
            # Dinamik kodları orijinal SVG'nin içine (ilk tag'den sonra) yerleştir
            modified_svg = re.sub(r'(<svg[^>]*>)', r'\1' + defs + styles, base_svg, count=1, flags=re.IGNORECASE)
            
            st.markdown(f"#### {rap_yuklenici} | {rap_proje} | {rap_parsel} Parsel")
            st.markdown(f"**İmalat:** {imalat_adi} - ({row['BULUNDUĞU MAHAL']})")
            
            st.components.v1.html(modified_svg, height=450)
            st.markdown("<hr>", unsafe_allow_html=True)