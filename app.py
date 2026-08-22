import streamlit as st
import pandas as pd
import os
import re
import math
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client, Client

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Şantiye İlerleme Takip", layout="wide", page_icon="🏗️", initial_sidebar_state="expanded")

# --- SUPABASE BAĞLANTISI VE BOŞLUK TEMİZLİĞİ (.strip) ---
@st.cache_resource
def init_connection():
    # .strip() komutu, secrets içindeki görünmez enter ve boşlukları siler
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Veritabanı bağlantı hatası. Secrets ayarlarınızı kontrol edin.")
    st.stop()

# --- OTURUM YÖNETİMİ (SESSION) ---
if "user" not in st.session_state:
    st.session_state["user"] = None

# --- GİRİŞ EKRANI (LOGIN) ---
if st.session_state.get("user") is None:
    st.markdown("<h2 style='text-align: center; color: #2c3e50; margin-top: 50px;'>🔐 Şantiye Yönetim Paneli</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("#### Kullanıcı Girişi")
            email = st.text_input("E-Posta Adresiniz")
            sifre = st.text_input("Şifreniz", type="password")
            submit = st.form_submit_button("Giriş Yap", use_container_width=True)
            
            if submit:
                try:
                    res = supabase.table("kullanicilar").select("*").eq("email", email.strip()).eq("sifre", sifre).execute()
                    
                    if len(res.data) > 0:
                        st.session_state["user"] = res.data[0]
                        st.rerun() 
                    else:
                        st.error("Hatalı e-posta veya şifre!")
                except Exception as e:
                    st.error(f"Veritabanı erişim hatası: {e}")
    st.stop()

# ==========================================
# GİRİŞ YAPILDIKTAN SONRAKİ ANA UYGULAMA
# ==========================================

# --- VERİ OKUMA VE TEMİZLEME ---
@st.cache_data
def load_master_data():
    df_blok = pd.read_excel("Blok İsimleri.xlsx")
    df_imalat = pd.read_excel("İmalat İsimleri.xlsx")
    df_blok["Parsel Adı"] = df_blok["Parsel Adı"].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_blok["Blok Adı"] = df_blok["Blok Adı"].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    return df_blok, df_imalat

try:
    df_blok, df_imalat = load_master_data()
except Exception as e:
    st.error(f"Excel dosyaları okunamadı: {e}")
    st.stop()

# --- VERİTABANI İŞLEMLERİ (SUPABASE) ---
def load_logs():
    res = supabase.table("ilerleme_loglari").select("*").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return pd.DataFrame(columns=["Tarih", "Yüklenici", "Proje", "Parsel", "Blok", "İmalat", "İlerleme"])
    
    df = df.rename(columns={
        "tarih": "Tarih", "yuklenici": "Yüklenici", "proje": "Proje", 
        "parsel": "Parsel", "blok": "Blok", "imalat": "İmalat", "ilerleme": "İlerleme"
    })
    df["Parsel"] = df["Parsel"].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df["Blok"] = df["Blok"].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    return df

def save_log(yuklenici, proje, parsel, blok, imalat, ilerleme):
    p_str = str(parsel).replace('.0', '').strip()
    b_str = str(blok).replace('.0', '').strip()
    giren = st.session_state["user"]["email"]
    
    veri = {
        "yuklenici": yuklenici, "proje": proje, "parsel": p_str,
        "blok": b_str, "imalat": imalat, "ilerleme": ilerleme, "giren_kullanici": giren
    }
    supabase.table("ilerleme_loglari").insert(veri).execute()

def get_latest_progress(parsel, blok, imalat):
    df_log = load_logs()
    if df_log.empty: return "YOK"
    p_str = str(parsel).replace('.0', '').strip()
    b_str = str(blok).replace('.0', '').strip()
    
    mask = (df_log["Parsel"] == p_str) & (df_log["Blok"] == b_str) & (df_log["İmalat"] == imalat)
    filtered = df_log[mask]
    if not filtered.empty:
        return filtered.iloc[-1]["İlerleme"]
    return "YOK"

VAL_MAP = {"YOK": -1, "%0": 0, "%25": 25, "%50": 50, "%75": 75, "%100": 100}

# --- RESPONSIVE SVG RENDER FONKSİYONU ---
def render_responsive_svg(svg_string):
    svg_string = re.sub(r'(<svg[^>]*)width="[^"]*"', r'\1', svg_string, flags=re.IGNORECASE)
    svg_string = re.sub(r'(<svg[^>]*)height="[^"]*"', r'\1', svg_string, flags=re.IGNORECASE)
    
    if 'style="' in svg_string:
        svg_string = re.sub(r'(<svg[^>]*)style="([^"]*)"', r'\1style="\2; width:100%; height:auto; max-height: 680px;"', svg_string, flags=re.IGNORECASE)
    else:
        svg_string = re.sub(r'(<svg[^>]*)', r'\1 style="width:100%; height:auto; max-height: 680px;"', svg_string, count=1, flags=re.IGNORECASE)
    
    html_content = f"""
    <style>
        body {{ margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; background-color: transparent; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        .report-container {{ position: relative; width: 100%; max-width: 1000px; text-align: center; }}
        svg {{ max-width: 100%; height: auto; max-height: 680px; }}
        
        .legend-box {{ position: absolute; bottom: 20px; right: 20px; background: rgba(241, 242, 246, 0.95); padding: 12px 15px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); text-align: left; font-size: 12px; font-weight: 600; color: #2c3e50; border: 1px solid #ced6e0; }}
        .legend-item {{ display: flex; align-items: center; margin-bottom: 8px; }}
        .legend-item:last-child {{ margin-bottom: 0; }}
        .color-box {{ width: 16px; height: 16px; margin-right: 10px; border: 1px solid #7f8c8d; border-radius: 3px; }}
    </style>
    <div class="report-container">
        {svg_string}
        <div class="legend-box">
            <div class="legend-item"><div class="color-box" style="background: #d9d9d9;"></div> İMALAT YOK</div>
            <div class="legend-item"><div class="color-box" style="background: #ff4757;"></div> BAŞLANMADI</div>
            <div class="legend-item">
                <div class="color-box" style="background: linear-gradient(to top, #7bed9f 50%, #ffffff 50%);"></div>
                DEVAM EDİYOR
            </div>
            <div class="legend-item"><div class="color-box" style="background: #009432;"></div> TAMAMLANDI</div>
        </div>
    </div>
    """
    st.components.v1.html(html_content, height=730)

# --- SVG OTOMATİK ID EŞLEŞTİRME MODÜLÜ ---
def auto_assign_svg_ids(file_path):
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
            m = re.search(r'translate\(\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*\)', transform)
            if m: x, y = float(m.group(1)), float(m.group(2))
        
        if x is not None and y is not None:
            text_data.append({'name': clean_text, 'x': x, 'y': y})
            t.string = clean_text

    if not text_data: return False, "Metin bulunamadı."

    shapes = soup.find_all(['path', 'polygon', 'polyline'])
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
    return True, f"{len(eslesenler)} adet bloğa başarıyla ID atandı."

# ==========================================
# ARAYÜZ YARDIMCI FONKSİYONLARI
# ==========================================
def draw_info_row(label, options):
    col1, col2 = st.columns([2, 3])
    with col1:
        st.markdown(f"<div style='margin-top:6px; font-weight:600; font-size:13px; color:#2c3e50;'>{label}</div>", unsafe_allow_html=True)
    with col2:
        return st.selectbox(label, options, label_visibility="collapsed")

def draw_progress_row(label, options, default_idx):
    col1, col2 = st.columns([5, 4])
    with col1:
        st.markdown(f"<div style='margin-top:6px; text-align:right; font-size:13px; color:#7f8c8d; font-style:italic;'>{label}</div>", unsafe_allow_html=True)
    with col2:
        return st.selectbox(label, options, index=default_idx, label_visibility="collapsed")

# ==========================================
# YAN PANEL (SIDEBAR)
# ==========================================
with st.sidebar:
    st.success(f"👤 Hoş geldiniz, {st.session_state['user'].get('ad_soyad', 'Kullanıcı')}")
    if st.button("Çıkış Yap", use_container_width=True):
        st.session_state["user"] = None
        st.rerun()
    
    st.markdown("### 📋 PROJE BİLGİLERİ")
    yukleniciler = df_blok["Yüklenici Firma"].unique()
    secilen_yuklenici = draw_info_row("YÜKLENİCİ", yukleniciler)
    
    projeler = df_blok[df_blok["Yüklenici Firma"] == secilen_yuklenici]["Proje Adı"].unique()
    secilen_proje = draw_info_row("PROJE", projeler)
    
    parseller = df_blok[(df_blok["Yüklenici Firma"] == secilen_yuklenici) & (df_blok["Proje Adı"] == secilen_proje)]["Parsel Adı"].unique()
    secilen_parsel = draw_info_row("PARSEL", parseller)
    
    bloklar = df_blok[(df_blok["Yüklenici Firma"] == secilen_yuklenici) & 
                      (df_blok["Proje Adı"] == secilen_proje) & 
                      (df_blok["Parsel Adı"] == secilen_parsel)]["Blok Adı"].unique()
    secilen_blok = draw_info_row("BLOK", ["Lütfen Seçiniz..."] + list(bloklar))
    
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

    if secilen_blok != "Lütfen Seçiniz...":
        st.markdown(f"### 🛠️ İLERLEME ORANLARI ({secilen_blok} BLOK)")
        
        with st.form("veri_giris_formu"):
            giris_verileri = {}
            gruplu_imalatlar = df_imalat.groupby("ALT KIRILIM")
            
            for kirilim, grup_df in gruplu_imalatlar:
                st.markdown(f"<strong style='color:#2980b9;'><u>{kirilim}</u></strong>", unsafe_allow_html=True)
                for index, row in grup_df.iterrows():
                    imalat_adi = row["İMALATIN ADI"]
                    son_deger = get_latest_progress(secilen_parsel, secilen_blok, imalat_adi)
                    options = list(VAL_MAP.keys())
                    default_idx = options.index(son_deger) if son_deger in options else 0
                    
                    giris_verileri[imalat_adi] = {
                        "old": son_deger,
                        "new": draw_progress_row(imalat_adi, options, default_idx)
                    }
            
            st.markdown("<br>", unsafe_allow_html=True)
            kaydet = st.form_submit_button("💾 VERİLERİ KAYDET", use_container_width=True)
            
            if kaydet:
                hata_var = False
                for imalat, veriler in giris_verileri.items():
                    if VAL_MAP[veriler["new"]] < VAL_MAP[veriler["old"]] and VAL_MAP[veriler["new"]] != -1: 
                        st.error(f"HATA! {imalat} ilerlemesi düşürülemez!")
                        hata_var = True
                        
                if not hata_var:
                    degisildi_mi = False
                    for imalat, veriler in giris_verileri.items():
                        if veriler["new"] != veriler["old"]: 
                            save_log(secilen_yuklenici, secilen_proje, secilen_parsel, secilen_blok, imalat, veriler["new"])
                            degisildi_mi = True
                    if degisildi_mi:
                        st.success("Kayıt Başarılı! Rapor güncellendi.")
                    else:
                        st.info("Değişiklik yapılmadı.")

# ==========================================
# ANA EKRAN (MAIN) - RAPOR & PDF
# ==========================================
tab1, tab2 = st.tabs(["📊 Canlı Vaziyet Raporu", "⚙️ Sistem Ayarları (SVG)"])

with tab1:
    parsel_bloklari = df_blok[(df_blok["Parsel Adı"] == secilen_parsel)]["Blok Adı"].unique()
    df_log_all = load_logs()
    rap_svg_path = f"{secilen_parsel} Parsel.svg"
    
    if os.path.exists(rap_svg_path):
        with open(rap_svg_path, "r", encoding="utf-8") as f:
            base_svg = f.read()
            
        full_html = """
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap');
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: transparent; margin: 0; padding: 10px; }
            .action-bar { text-align: right; margin-bottom: 20px; position: sticky; top: 10px; z-index: 1000; }
            .print-btn { background-color: #e74c3c; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.2); transition: 0.3s; }
            .print-btn:hover { background-color: #c0392b; transform: scale(1.02); }
            .page-container { background: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); margin-bottom: 40px; position: relative; max-width: 1100px; margin-left: auto; margin-right: auto; }
            .header-titles { text-align: center; margin-bottom: 20px; }
            .header-titles h4 { color: #57606f; margin: 0 0 5px 0; font-size: 16px; }
            .header-titles h2 { color: #2c3e50; margin: 0 0 5px 0; font-size: 26px; text-transform: uppercase; }
            .header-titles h5 { color: #7f8c8d; margin: 0; font-size: 14px; font-weight: normal; }
            .svg-wrapper { text-align: center; width: 100%; display: flex; justify-content: center; }
            .svg-wrapper svg { max-width: 100%; height: auto; max-height: 550px; }
            .legend-box { position: absolute; bottom: 30px; right: 30px; background: rgba(241, 242, 246, 0.95); padding: 12px 15px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: left; font-size: 12px; font-weight: 600; color: #2c3e50; border: 1px solid #ced6e0; }
            .legend-item { display: flex; align-items: center; margin-bottom: 8px; }
            .legend-item:last-child { margin-bottom: 0; }
            .color-box { width: 16px; height: 16px; margin-right: 10px; border: 1px solid #7f8c8d; border-radius: 3px; }
            @media print {
                @page { margin: 0; size: auto; }
                body { padding: 0; background-color: #ffffff; -webkit-print-color-adjust: exact; }
                .action-bar { display: none !important; }
                .page-container { box-shadow: none; border-radius: 0; padding: 0; margin: 0; width: 100vw; height: 100vh; page-break-after: always; page-break-inside: avoid; display: block; position: relative; box-sizing: border-box; padding-top: 15mm; }
                .page-container:last-child { page-break-after: avoid; }
                .svg-wrapper { margin-top: 10mm; }
                .svg-wrapper svg { max-height: 70vh !important; }
                .legend-box { bottom: 15mm; right: 15mm; box-shadow: none; border: 1px solid #000; }
            }
        </style>
        </head>
        <body>
            <div class="action-bar"><button class="print-btn" onclick="window.print()">🖨️ PDF OLARAK İNDİR</button></div>
        """
        
        for index, row in df_imalat.iterrows():
            imalat_adi = row["İMALATIN ADI"]
            kirilim_adi = row["ALT KIRILIM"]
            mahal = row["BULUNDUĞU MAHAL"]
            
            uid = f"svg_vaziyet_{index}"
            blok_degerleri = {}
            for b in parsel_bloklari:
                mask = (df_log_all["Parsel"] == str(secilen_parsel).replace('.0', '').strip()) & \
                       (df_log_all["Blok"] == str(b).replace('.0', '').strip()) & \
                       (df_log_all["İmalat"] == imalat_adi)
                filt = df_log_all[mask]
                blok_degerleri[b] = filt.iloc[-1]["İlerleme"] if not filt.empty else "YOK"
            
            svg_string = re.sub(r'(<svg[^>]*)width="[^"]*"', r'\1', base_svg, flags=re.IGNORECASE)
            svg_string = re.sub(r'(<svg[^>]*)height="[^"]*"', r'\1', svg_string, flags=re.IGNORECASE)
            modified_svg = svg_string
            
            for b in parsel_bloklari:
                modified_svg = re.sub(rf'id="{re.escape(b)}"', f'id="{b}_{uid}"', modified_svg)
            
            defs = "<defs>\n"
            styles = "<style type='text/css'>\n"
            
            for b, val in blok_degerleri.items():
                unique_b = f"{b}_{uid}"
                if val == "YOK":
                    styles += f"#{unique_b} {{ fill: #d9d9d9 !important; stroke: #000000 !important; stroke-width: 3px; }}\n"
                elif val == "%0":
                    styles += f"#{unique_b} {{ fill: #ff4757 !important; stroke: #000000 !important; stroke-width: 3px; }}\n"
                elif val == "%100":
                    styles += f"#{unique_b} {{ fill: #009432 !important; stroke: #000000 !important; stroke-width: 3px; }}\n"
                else: 
                    num_val = int(str(val).replace('%', ''))
                    grad_id = f"grad_{unique_b}_{num_val}"
                    defs += f'<linearGradient id="{grad_id}" x1="0%" y1="100%" x2="0%" y2="0%"><stop offset="{num_val}%" stop-color="#7bed9f" /><stop offset="{num_val}%" stop-color="#ffffff" /></linearGradient>\n'
                    styles += f"#{unique_b} {{ fill: url(#{grad_id}) !important; stroke: #000000 !important; stroke-width: 3px; }}\n"
            
            defs += "</defs>\n</style>\n"
            modified_svg = re.sub(r'(<svg[^>]*>)', r'\1' + defs + styles, modified_svg, count=1, flags=re.IGNORECASE)
            
            full_html += f"""
            <div class="page-container">
                <div class="header-titles">
                    <h4>{secilen_yuklenici} | {secilen_proje} | {secilen_parsel} PARSEL</h4>
                    <h2>{imalat_adi}</h2>
                    <h5><b>{kirilim_adi}</b> - <i>{mahal}</i></h5>
                </div>
                <div class="svg-wrapper">{modified_svg}</div>
                <div class="legend-box">
                    <div class="legend-item"><div class="color-box" style="background: #d9d9d9;"></div> İMALAT YOK</div>
                    <div class="legend-item"><div class="color-box" style="background: #ff4757;"></div> BAŞLANMADI</div>
                    <div class="legend-item"><div class="color-box" style="background: linear-gradient(to top, #7bed9f 50%, #ffffff 50%);"></div> DEVAM EDİYOR</div>
                    <div class="legend-item"><div class="color-box" style="background: #009432;"></div> TAMAMLANDI</div>
                </div>
            </div>
            """
        full_html += "</body></html>"
        st.components.v1.html(full_html, height=850, scrolling=True)
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
            if basarili: st.success(mesaj)
            else: st.error(mesaj)
    else:
        st.warning("Klasörde hiç .svg dosyası bulunamadı.")