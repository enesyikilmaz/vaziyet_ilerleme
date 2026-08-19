import streamlit as st
import pandas as pd
import os
import re
import math
from datetime import datetime
import ezdxf

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

# --- DXF'TEN SVG ÜRETME MODÜLÜ ---
def process_dxf_to_svg(dxf_path, output_svg_path):
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    except Exception as e:
        return False, f"DXF okuma hatası: {e}"

    texts = []
    polygons = []

    # 1. Metinleri (TEXT ve MTEXT) Bul
    for entity in msp.query('TEXT MTEXT'):
        text_val = entity.dxf.text.strip()
        if not text_val or len(text_val) > 10: continue
        
        insert = entity.dxf.insert
        texts.append({"name": text_val, "x": insert.x, "y": insert.y})

    # 2. Şekilleri (POLYLINE ve LWPOLYLINE) Bul
    for entity in msp.query('LWPOLYLINE POLYLINE'):
        points = []
        if entity.dxftype() == 'LWPOLYLINE':
            points = [(p[0], p[1]) for p in entity.get_points('xy')]
        else:
            points = [(p.dxf.location.x, p.dxf.location.y) for p in entity.vertices]
        
        if len(points) > 2:
            cx = sum([p[0] for p in points]) / len(points)
            cy = sum([p[1] for p in points]) / len(points)
            polygons.append({"points": points, "cx": cx, "cy": cy})

    if not texts: return False, "DXF içinde blok isimleri (metin) bulunamadı."
    if not polygons: return False, "DXF içinde blok sınırları (polyline) bulunamadı."

    # 3. Eşleştirme (Mekansal Analiz) ve Sınırları Belirleme
    matched_blocks = []
    all_x, all_y = [], []
    
    for t in texts:
        closest_poly = None
        min_dist = float('inf')
        for p in polygons:
            dist = math.hypot(t["x"] - p["cx"], t["y"] - p["cy"])
            if dist < min_dist:
                min_dist = dist
                closest_poly = p
        
        if closest_poly:
            matched_blocks.append({"id": t["name"], "points": closest_poly["points"]})
            all_x.extend([pt[0] for pt in closest_poly["points"]])
            all_y.extend([pt[1] for pt in closest_poly["points"]])

    if not matched_blocks: return False, "Yazılar ile şekiller eşleştirilemedi."

    # 4. Koordinatları SVG'ye Uydurma (Normalizasyon ve Y Ekseni Çevirme)
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    cad_width = max_x - min_x
    cad_height = max_y - min_y
    
    svg_view_width = 800
    svg_view_height = 600
    
    # Orantılı ölçekleme
    scale = min(svg_view_width / (cad_width or 1), svg_view_height / (cad_height or 1)) * 0.9
    
    x_offset = (svg_view_width - (cad_width * scale)) / 2
    y_offset = (svg_view_height - (cad_height * scale)) / 2

    svg_content = f'<svg viewBox="0 0 {svg_view_width} {svg_view_height}" xmlns="http://www.w3.org/2000/svg">\n'
    svg_content += '<g stroke="#000000" stroke-width="2" fill="none">\n'
    
    eslesenler = []
    for mb in matched_blocks:
        svg_pts = []
        for px, py in mb["points"]:
            sx = ((px - min_x) * scale) + x_offset
            # SVG'de Y ekseni aşağı doğru artar, bu yüzden CAD'in Y eksenini ters çeviriyoruz
            sy = svg_view_height - (((py - min_y) * scale) + y_offset)
            svg_pts.append(f"{sx},{sy}")
            
        points_str = " ".join(svg_pts)
        svg_content += f'  <polygon id="{mb["id"]}" points="{points_str}" />\n'
        
        # Etiketleri (A, B, C) SVG ortasına yazdıralım
        tcx = sum([float(p.split(',')[0]) for p in svg_pts]) / len(svg_pts)
        tcy = sum([float(p.split(',')[1]) for p in svg_pts]) / len(svg_pts)
        svg_content += f'  <text x="{tcx}" y="{tcy}" font-family="Arial" font-size="20" font-weight="bold" fill="#000" text-anchor="middle" dominant-baseline="middle" pointer-events="none">{mb["id"]}</text>\n'
        eslesenler.append(mb["id"])

    svg_content += '</g>\n</svg>'

    # Üretilen SVG'yi kaydet
    with open(output_svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
        
    return True, f"Başarı! {len(eslesenler)} blok eşleştirildi ve SVG oluşturuldu: {', '.join(eslesenler)}"

# --- ARAYÜZ (SEKMELER) ---
tab1, tab2, tab3 = st.tabs(["📝 Veri Girişi", "📊 Yönetici Raporu", "⚙️ Ayarlar (DXF)"])

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
            st.warning(f"Bu parsel için görsel henüz üretilmedi. Lütfen 'Ayarlar (DXF)' sekmesinden DXF dosyasını işleyin.")

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
                    # Alttan yukarı dolgu (Y1=100%, Y2=0%)
                    defs += f'<linearGradient id="{grad_id}" x1="0%" y1="100%" x2="0%" y2="0%"><stop offset="{num_val}%" stop-color="#90EE90" /><stop offset="{num_val}%" stop-color="#ffffff" /></linearGradient>\n'
                    styles += f"#{b} {{ fill: url(#{grad_id}) !important; stroke: #000000 !important; }}\n"
            
            defs += "</defs>\n</style>\n"
            modified_svg = re.sub(r'(<svg[^>]*>)', r'\1' + defs + styles, base_svg, count=1, flags=re.IGNORECASE)
            
            st.markdown(f"#### {rap_yuklenici} | {rap_proje} | {rap_parsel} Parsel | {imalat_adi}")
            st.components.v1.html(modified_svg, height=450)
            st.markdown("<hr>", unsafe_allow_html=True)
    else:
        st.error("Rapor oluşturulabilmesi için öncelikle DXF dosyasının işlenmesi gerekiyor.")

with tab3:
    st.header("Sistem Ayarları (DXF İşleyici)")
    st.info("AutoCAD'den aldığınız .dxf dosyasını sisteme entegre edip uygulamanın okuyabileceği akıllı görseli (SVG) oluşturmak için bu ekranı kullanın.")
    
    dxf_dosyalari = [f for f in os.listdir() if f.endswith(".dxf")]
    if dxf_dosyalari:
        secilen_dxf = st.selectbox("İşlem Yapılacak DXF Dosyası:", dxf_dosyalari)
        
        # Dosya isminden Parsel adını tahmin et (Örn: "8 Parsel.dxf" -> "8 Parsel.svg")
        hedef_isim = secilen_dxf.replace(".dxf", ".svg")
        
        if st.button("🚀 DXF'i İşle ve Akıllı SVG Üret"):
            basarili, mesaj = process_dxf_to_svg(secilen_dxf, hedef_isim)
            if basarili:
                st.success(mesaj)
                st.balloons()
            else:
                st.error(mesaj)
    else:
        st.warning("Klasörde hiç .dxf dosyası bulunamadı. Lütfen GitHub'a AutoCAD DXF dosyalarınızı yükleyin.")