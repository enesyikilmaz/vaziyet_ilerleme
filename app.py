import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Şantiye İlerleme Takip", layout="wide", page_icon="🏗️", initial_sidebar_state="expanded")

# --- VERİ OKUMA ---
@st.cache_data
def load_master_data():
    df_blok = pd.read_excel("Blok İsimleri.xlsx")
    df_imalat = pd.read_excel("İmalat İsimleri.xlsx")
    return df_blok, df_imalat

try:
    df_blok, df_imalat = load_master_data()
except Exception as e:
    st.error(f"Excel dosyaları okunamadı: {e}")
    st.stop()

# --- LOG (GEÇMİŞ) SİSTEMİ ---
LOG_FILE = "santiye_log.csv"
if not os.path.exists(LOG_FILE):
    df_log = pd.DataFrame(columns=["Tarih", "Yüklenici", "Proje", "Parsel", "Blok", "İmalat", "İlerleme"])
    df_log.to_csv(LOG_FILE, index=False)

def load_logs():
    return pd.read_csv(LOG_FILE)

def save_log(yuklenici, proje, parsel, blok, imalat, ilerleme):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df = pd.DataFrame([[now, yuklenici, proje, parsel, blok, imalat, ilerleme]], 
                      columns=["Tarih", "Yüklenici", "Proje", "Parsel", "Blok", "İmalat", "İlerleme"])
    df.to_csv(LOG_FILE, mode='a', header=False, index=False)

def get_latest_progress(parsel, blok, imalat):
    df_log = load_logs()
    mask = (df_log["Parsel"] == int(parsel)) & (df_log["Blok"] == str(blok)) & (df_log["İmalat"] == imalat)
    filtered = df_log[mask]
    if not filtered.empty:
        return filtered.iloc[-1]["İlerleme"]
    return "YOK"

VAL_MAP = {"YOK": -1, "%0": 0, "%25": 25, "%50": 50, "%75": 75, "%100": 100}

# --- RESPONSIVE SVG RENDER FONKSİYONU ---
def render_responsive_svg(svg_string):
    """SVG'nin içindeki hardcoded boyutları temizleyip ekrana tam sığmasını sağlar."""
    # Sabit width ve height değerlerini temizle
    svg_string = re.sub(r'(<svg[^>]*)width="[^"]*"', r'\1', svg_string, flags=re.IGNORECASE)
    svg_string = re.sub(r'(<svg[^>]*)height="[^"]*"', r'\1', svg_string, flags=re.IGNORECASE)
    
    # CSS Style ile %100 genişlik ve otomatik yükseklik ver
    if 'style="' in svg_string:
        svg_string = re.sub(r'(<svg[^>]*)style="([^"]*)"', r'\1style="\2; width:100%; height:auto; max-height: 75vh;"', svg_string, flags=re.IGNORECASE)
    else:
        svg_string = re.sub(r'(<svg[^>]*)', r'\1 style="width:100%; height:auto; max-height: 75vh;"', svg_string, count=1, flags=re.IGNORECASE)
    
    st.markdown(f'<div style="text-align:center; padding: 20px;">{svg_string}</div>', unsafe_allow_html=True)

# --- SVG OTOMATİK ID EŞLEŞTİRME MODÜLÜ (Ayarlar için) ---
def auto_assign_svg_ids(file_path):
    def extract_coordinates(shape_tag):
        coords = []
        if shape_tag.name in ['polygon', 'polyline']:
            pts = shape_tag.get('points', '').replace(',', ' ').split()
            coords = [float(p) for p in pts if p.strip().replace('.','',1).replace('-','',1).isdigit()]
        elif shape_tag.name == 'path':
            d = shape_tag.get('d', '')
            import re
            coords = [float(p) for p in re.findall(r'-?\d+\.?\d*', d)]
        if not coords or len(coords) < 2: return None
        x_coords = coords[0::2]
        y_coords = coords[1::2]
        if not x_coords or not y_coords: return None
        return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords))

    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'xml')
    
    texts = soup.find_all(['text', 'tspan'])
    text_data = []
    
    for t in texts:
        raw_text = t.text.strip()
        clean_text = re.sub(r'\\[A-Za-z0-9~]+;', '', raw_text).strip()
        if not clean_text or len(clean_text) > 5: continue
        
        transform = t.get('transform') or (t.parent.get('transform') if t.parent else "")
        x, y = None, None
        if 'translate' in transform:
            import re
            m = re.search(r'translate\(\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*\)', transform)
            if m:
                x, y = float(m.group(1)), float(m.group(2))
        
        if x is not None and y is not None:
            text_data.append({'name': clean_text, 'x': x, 'y': y})
            t.string = clean_text

    if not text_data: return False, "Metin bulunamadı."

    shapes = soup.find_all(['path', 'polygon', 'polyline'])
    import math
    shape_data = [{'tag': s, 'cx': extract_coordinates(s)[0], 'cy': extract_coordinates(s)[1]} for s in shapes if extract_coordinates(s)]
            
    eslesenler = []
    for td in text_data:
        closest_shape = min(shape_data, key=lambda sd: math.hypot(td['x'] - sd['cx'], td['y'] - sd['cy']), default=None)
        if closest_shape:
            closest_shape['tag']['id'] = td['name']
            closest_shape['tag']['fill'] = "none"
            closest_shape['tag']['stroke'] = "#000"
            closest_shape['tag']['stroke-width'] = "3"
            eslesenler.append(td['name'])
            
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    return True, f"{len(eslesenler)} adet bloğa ID atandı: {', '.join(eslesenler)}"


# ==========================================
# YAN PANEL (SIDEBAR) - VERİ GİRİŞ EKRANI
# ==========================================
with st.sidebar:
    st.header("📋 PROJE BİLGİLERİ")
    
    yukleniciler = df_blok["Yüklenici Firma"].unique()
    secilen_yuklenici = st.selectbox("YÜKLENİCİ", yukleniciler)
    
    projeler = df_blok[df_blok["Yüklenici Firma"] == secilen_yuklenici]["Proje Adı"].unique()
    secilen_proje = st.selectbox("PROJE", projeler)
    
    parseller = df_blok[(df_blok["Yüklenici Firma"] == secilen_yuklenici) & (df_blok["Proje Adı"] == secilen_proje)]["Parsel Adı"].unique()
    secilen_parsel = st.selectbox("PARSEL", parseller)
    
    bloklar = df_blok[(df_blok["Yüklenici Firma"] == secilen_yuklenici) & 
                      (df_blok["Proje Adı"] == secilen_proje) & 
                      (df_blok["Parsel Adı"] == secilen_parsel)]["Blok Adı"].unique()
    secilen_blok = st.selectbox("BLOK", ["Lütfen Seçiniz..."] + list(bloklar))
    
    st.divider()

    if secilen_blok != "Lütfen Seçiniz...":
        st.header(f"🛠️ İLERLEME ORANLARI ({secilen_blok} BLOK)")
        
        with st.form("veri_giris_formu"):
            giris_verileri = {}
            
            # Alt kırılımlara göre gruplama (Örn: DÖŞEME KAPLAMA, DUVAR KAPLAMA)
            gruplu_imalatlar = df_imalat.groupby("ALT KIRILIM")
            
            for kirilim, grup_df in gruplu_imalatlar:
                st.markdown(f"**<u>{kirilim}</u>**", unsafe_allow_html=True)
                
                for index, row in grup_df.iterrows():
                    imalat_adi = row["İMALATIN ADI"]
                    son_deger = get_latest_progress(secilen_parsel, secilen_blok, imalat_adi)
                    options = list(VAL_MAP.keys())
                    default_idx = options.index(son_deger) if son_deger in options else 0
                    
                    giris_verileri[imalat_adi] = {
                        "old": son_deger,
                        "new": st.selectbox(f"{imalat_adi}", options, index=default_idx, label_visibility="collapsed")
                    }
                    st.caption(f"↳ *{imalat_adi}*") # İmalat adını küçük ve şık şekilde altın yazar
            
            st.markdown("<br>", unsafe_allow_html=True)
            kaydet = st.form_submit_button("💾 VERİLERİ KAYDET", use_container_width=True)
            
            if kaydet:
                hata_var = False
                for imalat, veriler in giris_verileri.items():
                    if VAL_MAP[veriler["new"]] < VAL_MAP[veriler["old"]] and VAL_MAP[veriler["new"]] != -1: 
                        st.error(f"HATA! {imalat} ilerlemesi ({veriler['old']}) değerinden düşük olamaz!")
                        hata_var = True
                        
                if not hata_var:
                    degisildi_mi = False
                    for imalat, veriler in giris_verileri.items():
                        if veriler["new"] != veriler["old"]: 
                            save_log(secilen_yuklenici, secilen_proje, secilen_parsel, secilen_blok, imalat, veriler["new"])
                            degisildi_mi = True
                    if degisildi_mi:
                        st.success("Kayıt Başarılı! Sağdaki rapor güncellendi.")
                    else:
                        st.info("Değişiklik yapılmadı.")


# ==========================================
# ANA EKRAN (MAIN) - CANLI YÖNETİCİ RAPORU
# ==========================================
tab1, tab2 = st.tabs(["📊 Canlı Vaziyet Raporu", "⚙️ Sistem Ayarları (SVG)"])

with tab1:
    # Lejant Alanı
    st.markdown("""
    <div style='background-color: #f1f2f6; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold;'>
        <span style='margin-right: 20px;'>⬛ İMALAT YOK</span>
        <span style='margin-right: 20px;'>🟥 %0 (BAŞLANMADI)</span>
        <span style='margin-right: 20px;'>🟩⬜ %25-%75 (DEVAM EDİYOR)</span>
        <span>🟩 %100 (TAMAMLANDI)</span>
    </div>
    <br>
    """, unsafe_allow_html=True)
    
    parsel_bloklari = df_blok[(df_blok["Parsel Adı"] == secilen_parsel)]["Blok Adı"].unique()
    df_log_all = load_logs()
    rap_svg_path = f"{secilen_parsel} Parsel.svg"
    
    if os.path.exists(rap_svg_path):
        with open(rap_svg_path, "r", encoding="utf-8") as f:
            base_svg = f.read()
            
        for index, row in df_imalat.iterrows():
            imalat_adi = row["İMALATIN ADI"]
            kirilim_adi = row["ALT KIRILIM"]
            mahal = row["BULUNDUĞU MAHAL"]
            
            blok_degerleri = {}
            for b in parsel_bloklari:
                mask = (df_log_all["Parsel"] == secilen_parsel) & (df_log_all["Blok"] == str(b)) & (df_log_all["İmalat"] == imalat_adi)
                filt = df_log_all[mask]
                blok_degerleri[b] = filt.iloc[-1]["İlerleme"] if not filt.empty else "YOK"
            
            defs = "<defs>\n"
            styles = "<style>\n"
            for b, val in blok_degerleri.items():
                if val == "YOK":
                    styles += f"#{b} {{ fill: #2c3e50 !important; stroke: #000000 !important; stroke-width: 3px; }}\n" # Siyah/Koyu Gri
                elif val == "%0":
                    styles += f"#{b} {{ fill: #ff4757 !important; stroke: #000000 !important; stroke-width: 3px; }}\n" # Kırmızı
                elif val == "%100":
                    styles += f"#{b} {{ fill: #2ed573 !important; stroke: #000000 !important; stroke-width: 3px; }}\n" # Yeşil
                else: 
                    num_val = int(val.replace('%', ''))
                    grad_id = f"grad_{b}_{num_val}"
                    defs += f'<linearGradient id="{grad_id}" x1="0%" y1="100%" x2="0%" y2="0%"><stop offset="{num_val}%" stop-color="#2ed573" /><stop offset="{num_val}%" stop-color="#ffffff" /></linearGradient>\n'
                    styles += f"#{b} {{ fill: url(#{grad_id}) !important; stroke: #000000 !important; stroke-width: 3px; }}\n"
            
            defs += "</defs>\n</style>\n"
            modified_svg = re.sub(r'(<svg[^>]*>)', r'\1' + defs + styles, base_svg, count=1, flags=re.IGNORECASE)
            
            # Dinamik Rapor Başlıkları
            st.markdown(f"<h4 style='text-align: center; color: #57606f;'>{secilen_yuklenici} &nbsp;|&nbsp; {secilen_proje} &nbsp;|&nbsp; {secilen_parsel} PARSEL</h4>", unsafe_allow_html=True)
            st.markdown(f"<h2 style='text-align: center; margin-top: -10px;'>{imalat_adi}</h2>", unsafe_allow_html=True)
            st.markdown(f"<h5 style='text-align: center; color: #747d8c; margin-top: -15px;'>{kirilim_adi} - <i>{mahal}</i></h5>", unsafe_allow_html=True)
            
            # Tam Ekrana Oturan SVG Çizimi
            render_responsive_svg(modified_svg)
            
            st.markdown("<hr style='border: 2px solid #dfe4ea;'>", unsafe_allow_html=True)
    else:
        st.info("👈 Soldaki panelden seçim yapabilirsiniz. İlgili parselin görseli yüklendiğinde burada renklendirilmiş raporlar listelenecektir.")

with tab2:
    st.header("⚙️ Sistem Ayarları (SVG İşleyici)")
    st.info("AutoCAD'den aldığınız yeni bir vaziyet planını sisteme tanıttığınızda 'Otomatik İsimlendir' işlemini buradan yapabilirsiniz.")
    
    svg_dosyalari = [f for f in os.listdir() if f.endswith(".svg")]
    if svg_dosyalari:
        secilen_svg = st.selectbox("İşlem Yapılacak SVG Dosyası:", svg_dosyalari)
        
        if st.button("🚀 SVG'yi İşle ve Otomatik İsimlendir"):
            basarili, mesaj = auto_assign_svg_ids(secilen_svg)
            if basarili:
                st.success(mesaj)
            else:
                st.error(mesaj)
    else:
        st.warning("Klasörde hiç .svg dosyası bulunamadı.")