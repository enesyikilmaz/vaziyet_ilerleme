import streamlit as st
import pandas as pd
import os
import re
import math
from datetime import datetime
from bs4 import BeautifulSoup

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Şantiye İlerleme Takip", layout="wide", page_icon="🏗️")

# --- VERİ OKUMA VE ÖNBELLEĞE ALMA ---
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

# --- VERİTABANI (LOG) SİMÜLASYONU ---
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

# --- SVG OTOMATİK ID EŞLEŞTİRME MODÜLÜ ---
def extract_coordinates(shape_tag):
    coords = []
    if shape_tag.name in ['polygon', 'polyline']:
        pts = shape_tag.get('points', '').replace(',', ' ').split()
        coords = [float(p) for p in pts if p.strip().replace('.','',1).replace('-','',1).isdigit()]
    elif shape_tag.name == 'path':
        d = shape_tag.get('d', '')
        coords = [float(p) for p in re.findall(r'-?\d+\.?\d*', d)]
    
    if not coords or len(coords) < 2: return None
    
    x_coords = coords[0::2]
    y_coords = coords[1::2]
    if not x_coords or not y_coords: return None
    return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords))

def auto_assign_svg_ids(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'xml')
    
    # SVG'ye viewbox bazlı scale sağlamak için CSS ekleyelim (Responsive yapı)
    svg_tag = soup.find('svg')
    if svg_tag:
        svg_tag['style'] = "width: 100%; height: auto;"
    
    texts = soup.find_all(['text', 'tspan'])
    text_data = []
    
    for t in texts:
        raw_text = t.text.strip()
        # MTEXT içindeki \pxqc; gibi Autocad format kodlarını temizle
        clean_text = re.sub(r'\\[A-Za-z0-9~]+;', '', raw_text).strip()
        
        if not clean_text or len(clean_text) > 5: continue
        
        # Koordinatları transform="translate(X Y)" içinden al (Gönderdiğiniz koda göre uyarlanmıştır)
        transform = t.get('transform') or (t.parent.get('transform') if t.parent else "")
        x, y = None, None
        
        if 'translate' in transform:
            m = re.search(r'translate\(\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*\)', transform)
            if m:
                x, y = float(m.group(1)), float(m.group(2))
        
        if x is not None and y is not None:
            text_data.append({'name': clean_text, 'x': x, 'y': y})
            # Ekrandaki metni temiz haliyle güncelle
            t.string = clean_text

    if not text_data:
        return False, "Metin veya koordinat bulunamadı."

    shapes = soup.find_all(['path', 'polygon', 'polyline'])
    shape_data = []
    for s in shapes:
        centroid = extract_coordinates(s)
        if centroid:
            shape_data.append({'tag': s, 'cx': centroid[0], 'cy': centroid[1]})
            
    eslesenler = []
    for td in text_data:
        tx, ty = td['x'], td['y']
        closest_shape = None
        min_dist = float('inf')
        
        for sd in shape_data:
            dist = math.hypot(tx - sd['cx'], ty - sd['cy'])
            if dist < min_dist:
                min_dist = dist
                closest_shape = sd['tag']
        
        if closest_shape:
            # Hem ID atıyoruz hem de doldurma ve çizgi özelliklerini rapor için şimdiden belirliyoruz
            closest_shape['id'] = td['name']
            closest_shape['fill'] = "none" # Başlangıçta şeffaf
            closest_shape['stroke'] = "#000"
            closest_shape['stroke-width'] = "3"
            eslesenler.append(td['name'])
            
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))
        
    return True, f"Başarıyla {len(eslesenler)} adet bloğa ID atandı: {', '.join(eslesenler)}"

# --- ARAYÜZ (SEKMELER) ---
tab1, tab2, tab3 = st.tabs(["📝 Veri Girişi", "📊 Yönetici Raporu", "⚙️ Ayarlar (SVG)"])

with tab1:
    st.header("Saha İmalat İlerleme Veri Girişi")
    col1, col2 = st.columns([1, 2])
    
    with col1:
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
                st.components.v1.html(f.read(), height=450)
        else:
            st.warning(f"Sistemde '{svg_path}' bulunamadı.")

    st.divider()
    
    if secilen_blok != "Lütfen Seçiniz...":
        st.subheader(f"🛠️ {secilen_blok} Blok Veri Giriş Ekranı")
        with st.form("veri_giris_formu"):
            giris_verileri = {}
            for index, row in df_imalat.iterrows():
                imalat_adi = row["İMALATIN ADI"]
                son_deger = get_latest_progress(secilen_parsel, secilen_blok, imalat_adi)
                options = list(VAL_MAP.keys())
                default_idx = options.index(son_deger) if son_deger in options else 0
                
                giris_verileri[imalat_adi] = {
                    "old": son_deger,
                    "new": st.selectbox(f"{imalat_adi} ({row['BULUNDUĞU MAHAL']})", options, index=default_idx)
                }
            
            kaydet = st.form_submit_button("💾 VERİLERİ KAYDET", use_container_width=True)
            if kaydet:
                hata_var = False
                for imalat, veriler in giris_verileri.items():
                    old_val = VAL_MAP[veriler["old"]]
                    new_val = VAL_MAP[veriler["new"]]
                    if new_val < old_val and new_val != -1: 
                        st.error(f"HATA! {imalat} için İLERLEME, ({veriler['old']}) DEĞERİNDEN DÜŞÜK OLAMAZ!")
                        hata_var = True
                        
                if not hata_var:
                    degisildi_mi = False
                    for imalat, veriler in giris_verileri.items():
                        if veriler["new"] != veriler["old"]: 
                            save_log(secilen_yuklenici, secilen_proje, secilen_parsel, secilen_blok, imalat, veriler["new"])
                            degisildi_mi = True
                    if degisildi_mi:
                        st.success("Kayıt Başarılı!")
                    else:
                        st.info("Değişiklik yapılmadı.")

with tab2:
    st.header("Rapor Ekranı")
    col3, col4, col5 = st.columns(3)
    rap_yuklenici = col3.selectbox("Rapor - Yüklenici", yukleniciler)
    rap_proje = col4.selectbox("Rapor - Proje", df_blok[df_blok["Yüklenici Firma"] == rap_yuklenici]["Proje Adı"].unique())
    rap_parsel = col5.selectbox("Rapor - Parsel", df_blok[(df_blok["Yüklenici Firma"] == rap_yuklenici) & (df_blok["Proje Adı"] == rap_proje)]["Parsel Adı"].unique())
    
    st.markdown("### 📌 Lejant: ⬜ YOK | 🟥 %0 | 🟨🟩 %25-%75 (Kısmi) | 🟩 %100")
    st.divider()
    
    parsel_bloklari = df_blok[(df_blok["Parsel Adı"] == rap_parsel)]["Blok Adı"].unique()
    df_log_all = load_logs()
    rap_svg_path = f"{rap_parsel} Parsel.svg"
    
    if os.path.exists(rap_svg_path):
        with open(rap_svg_path, "r", encoding="utf-8") as f:
            base_svg = f.read()
            
        for index, row in df_imalat.iterrows():
            imalat_adi = row["İMALATIN ADI"]
            blok_degerleri = {}
            for b in parsel_bloklari:
                mask = (df_log_all["Parsel"] == rap_parsel) & (df_log_all["Blok"] == str(b)) & (df_log_all["İmalat"] == imalat_adi)
                filt = df_log_all[mask]
                blok_degerleri[b] = filt.iloc[-1]["İlerleme"] if not filt.empty else "YOK"
            
            defs = "<defs>\n"
            styles = "<style>\n"
            for b, val in blok_degerleri.items():
                if val == "YOK":
                    styles += f"#{b} {{ fill: #ffffff !important; stroke: #000000 !important; }}\n"
                elif val == "%0":
                    styles += f"#{b} {{ fill: #ff0000 !important; stroke: #000000 !important; }}\n"
                elif val == "%100":
                    styles += f"#{b} {{ fill: #006400 !important; stroke: #000000 !important; }}\n"
                else: 
                    num_val = int(val.replace('%', ''))
                    grad_id = f"grad_{b}_{num_val}"
                    defs += f'<linearGradient id="{grad_id}" x1="0%" y1="100%" x2="0%" y2="0%"><stop offset="{num_val}%" stop-color="#90EE90" /><stop offset="{num_val}%" stop-color="#ffffff" /></linearGradient>\n'
                    styles += f"#{b} {{ fill: url(#{grad_id}) !important; stroke: #000000 !important; }}\n"
            
            defs += "</defs>\n</style>\n"
            modified_svg = re.sub(r'(<svg[^>]*>)', r'\1' + defs + styles, base_svg, count=1, flags=re.IGNORECASE)
            
            st.markdown(f"#### {rap_yuklenici} | {rap_proje} | {rap_parsel} Parsel | {imalat_adi}")
            st.components.v1.html(modified_svg, height=600)
            st.markdown("<hr>", unsafe_allow_html=True)
    else:
        st.error("Rapor oluşturulabilmesi için öncelikle SVG dosyasının yüklenmesi gerekiyor.")

with tab3:
    st.header("Sistem Ayarları (SVG İşleyici)")
    st.info("AutoCAD'den aldığınız .svg dosyasındaki blokları otomatik eşleştirmek ve metinleri temizlemek için bu ekranı kullanın.")
    
    svg_dosyalari = [f for f in os.listdir() if f.endswith(".svg")]
    if svg_dosyalari:
        secilen_svg = st.selectbox("İşlem Yapılacak SVG Dosyası:", svg_dosyalari)
        
        if st.button("🚀 SVG'yi İşle ve Otomatik İsimlendir"):
            basarili, mesaj = auto_assign_svg_ids(secilen_svg)
            if basarili:
                st.success(mesaj)
                st.balloons()
            else:
                st.error(mesaj)
    else:
        st.warning("Klasörde hiç .svg dosyası bulunamadı.")