import streamlit as st
import pandas as pd
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as pe
import io
import base64

# --- ARAYÜZ VE BAŞLIK ---
st.set_page_config(page_title="Kanal Kazısı Yaklaşık Maliyet", layout="wide")

# --- ÖZEL RENK PALETİ VE CSS ---
st.markdown(
    """
    <style>
    /* Ana Arka Plan */
    [data-testid="stAppViewContainer"] {
        background-color: #E4E0E1;
    }
    /* Sol Menü Arka Planı */
    [data-testid="stSidebar"] {
        background-color: #D6C0B3;
    }
    /* Metin ve Başlık Renkleri */
    h1, h2, h3, h4, p, label, .stMarkdown {
        color: #493628 !important;
    }
    /* HESAPLA Butonu Özel Tasarımı */
    div[data-testid="stButton"] > button {
        background-color: #493628 !important;
        border: none !important;
        font-weight: bold !important;
        padding: 10px 20px !important;
        border-radius: 5px !important;
        width: auto !important; 
    }
    div[data-testid="stButton"] > button, div[data-testid="stButton"] > button p {
        color: #FFFFFF !important;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: #AB886D !important;
    }
    div[data-testid="stButton"] > button:hover p {
        color: #FFFFFF !important;
    }
    /* Bilgi ve Uyarı Kutuları Arka Planı */
    .stAlert {
        background-color: rgba(214, 192, 179, 0.4) !important;
        color: #493628 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Kanal Kazısı Yaklaşık Maliyet Hesaplama")

def format_currency(value):
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"₺{formatted}"

def format_quantity(value):
    formatted = f"{value:.2f}"
    return formatted.replace('.', ',')

def cizim_olustur(ic_cap_mm, dis_cap_m, derinlik, taban_genisligi, zemin_tipi):
    fig, ax = plt.subplots(figsize=(6, 8), facecolor='#E4E0E1')
    
    kum_h = 0.10 + dis_cap_m + 0.30 
    
    if derinlik > 1.50:
        ust_genislik = taban_genisligi + 2 * (derinlik / 3)
        kum_ust_genislik = taban_genisligi + 2 * (kum_h / 3)
    else:
        ust_genislik = taban_genisligi
        kum_ust_genislik = taban_genisligi
        
    if "Sert Zemin" in zemin_tipi:
        dolgu_color = '#d3d3d3' 
        dolgu_hatch = 'O'       
        dolgu_label = "Kırmataş Geri Dolgu"
        zemin_cizgi = 'black'
        dolgu_text_color = '#493628'
    else:
        dolgu_color = '#AB886D' 
        dolgu_hatch = '+'       
        dolgu_label = "Kazıdan Çıkan Toprak\n(Geri Dolgu)"
        zemin_cizgi = '#493628'
        dolgu_text_color = '#493628'

    dolgu_poly = patches.Polygon([
        (-kum_ust_genislik/2, kum_h), (kum_ust_genislik/2, kum_h),
        (ust_genislik/2, derinlik), (-ust_genislik/2, derinlik)
    ], closed=True, facecolor=dolgu_color, edgecolor='#493628', hatch=dolgu_hatch, linewidth=1.5)
    ax.add_patch(dolgu_poly)
    
    yatak_poly = patches.Polygon([
        (-taban_genisligi/2, 0), (taban_genisligi/2, 0),
        (kum_ust_genislik/2, kum_h), (-kum_ust_genislik/2, kum_h)
    ], closed=True, facecolor='#D6C0B3', edgecolor='#493628', hatch='.', linewidth=1.5)
    ax.add_patch(yatak_poly)
    
    pipe_center_y = 0.10 + (dis_cap_m / 2)
    pipe_outer = patches.Circle((0, pipe_center_y), dis_cap_m/2, facecolor='#f0f0f0', edgecolor='#493628', linewidth=2)
    pipe_inner = patches.Circle((0, pipe_center_y), (ic_cap_mm/2000), facecolor='white', edgecolor='#493628', linewidth=1)
    ax.add_patch(pipe_outer)
    ax.add_patch(pipe_inner)
    
    ax.plot([-ust_genislik/2 - 0.5, ust_genislik/2 + 0.5], [derinlik, derinlik], color=zemin_cizgi, linewidth=3)
    
    beyaz_gölge = [pe.withStroke(linewidth=4, foreground='#E4E0E1')]
    
    ax.text(0, derinlik + 0.15, zemin_tipi.upper(), ha='center', fontweight='bold', fontsize=12, color=zemin_cizgi)
    ax.text(0, pipe_center_y, f"Ø{ic_cap_mm}", ha='center', va='center', fontweight='bold', fontsize=11, color='#493628', path_effects=beyaz_gölge)
    
    yataklama_y_konumu = 0.10 + dis_cap_m + 0.15
    ax.text(0, yataklama_y_konumu, "Yataklama\n& Gömlekleme", ha='center', va='center', fontsize=10, fontweight='bold', color='#493628', path_effects=beyaz_gölge)
    
    dolgu_y_konumu = kum_h + (derinlik - kum_h)/2
    ax.text(0, dolgu_y_konumu, dolgu_label, ha='center', va='center', fontsize=11, fontweight='bold', color=dolgu_text_color, path_effects=beyaz_gölge)
    
    ax.annotate('', xy=(-ust_genislik/2 - 0.2, 0), xytext=(-ust_genislik/2 - 0.2, derinlik), arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
    ax.text(-ust_genislik/2 - 0.3, derinlik/2, f"HT = {derinlik:.2f} m", va='center', ha='right', color='red', rotation=90, fontweight='bold', path_effects=beyaz_gölge)
    
    ax.annotate('', xy=(-taban_genisligi/2, -0.15), xytext=(taban_genisligi/2, -0.15), arrowprops=dict(arrowstyle='<->', color='blue', lw=1.5))
    ax.text(0, -0.25, f"Taban = {taban_genisligi:.2f} m", ha='center', va='top', color='blue', fontweight='bold', path_effects=beyaz_gölge)
    
    if derinlik > 1.50:
        ax.text(ust_genislik/2 + 0.1, derinlik/2, "1/3\nŞev", ha='left', va='center', color='#493628', fontweight='bold', path_effects=beyaz_gölge)
    
    ax.set_aspect('equal')
    ax.axis('off')
    ax.autoscale_view()
    
    return fig

file_path = "Altyapı Birim Fiyatlar_2.xlsx"

try:
    df_fiyatlar = pd.read_excel(file_path)
    sabit_sutunlar = ['SIRA NO', 'POZ NO', 'İŞ KALEMİNİN ADI VE KISA AÇIKLAMASI', 'BİRİMİ']
    donem_sutunlari = [col for col in df_fiyatlar.columns if col not in sabit_sutunlar]
    secilen_donem = donem_sutunlari[0]
    poz_listesi = df_fiyatlar['POZ NO'].astype(str).tolist()
    
    st.sidebar.header("1. Metraj Parametreleri")
    
    uzunluk = st.sidebar.number_input("Hat Uzunluğu (m)", min_value=0.0, value=100.0, step=1.0)
    
    # max_value kaldırıldı (Önbellek çökmesini engellemek için)
    derinlik = st.sidebar.number_input("Ortalama Kazı Derinliği (m)", min_value=0.0, value=2.0, step=1.0)
    st.sidebar.caption("⚠️ *10m üzeri kazılar özel iksa/güvenlik projesi gerektirir.*")
    
    zemin_tipi = st.sidebar.selectbox("Zemin Tipi", ["Yeşil Alan", "Sert Zemin (Asfalt/Beton)"])
    boru_caplari = [300, 400, 500, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400]
    ic_cap_mm = st.sidebar.selectbox("Boru İç Çapı (mm)", boru_caplari)

    st.sidebar.header("2. Nakliye Mesafeleri (km)")
    mesafe_kazi = st.sidebar.number_input("Kazı Döküm Mesafesi (km)", min_value=0.0, value=12.0, step=1.0)
    mesafe_boru = st.sidebar.number_input("Boru Nakliye Mesafesi (km)", min_value=0.0, value=12.0, step=1.0)
    mesafe_kirmatas = st.sidebar.number_input("Kırmataş/Kum Nakliye Mesafesi (km)", min_value=0.0, value=14.0, step=1.0)
    
    st.sidebar.header("3. Maliyet Ayarları")
    kar_orani = st.sidebar.number_input("Yüklenici Kârı (%)", min_value=0.0, value=15.0, step=1.0)
    k_carpan = 1 + (kar_orani / 100)
    
    with st.sidebar.expander("Gelişmiş Nakliye Katsayıları"):
        K_katsayisi = st.number_input("Taşıt Katsayısı (K)", value=2048.01)
        A_katsayisi = st.number_input("Zorluk Katsayısı (A)", value=1.75)
        kirmata_yogunluk = st.number_input("Kırmataş Yoğunluğu (t/m³)", value=1.60)
        beton_yogunluk = st.number_input("Beton Boru Yoğunluğu (t/m³)", value=2.40)

    kazi_pozu = "KGM 14.210"
    kum_pozu = "43.610.1053"
    dolgu_pozu = "43.610.1064" if "Sert Zemin" in zemin_tipi else "43.610.1004"
    hasir_celik_pozu = "43.665.1011"
    
    boru_poz_sozlugu = {
        300: "43.526.1123", 400: "43.526.1124", 500: "43.526.1125", 600: "43.526.1126",
        800: "43.526.1162", 1000: "43.526.1163", 1200: "43.526.1164", 1400: "43.526.1165",
        1600: "43.526.1201", 1800: "43.526.1202", 2000: "43.526.1203", 2200: "43.526.1204", 
        2400: "43.526.1205"
    }
    boru_pozu = boru_poz_sozlugu.get(ic_cap_mm)

    if st.button("HESAPLA", type="primary"):
        # YENİ KONTROL: Algoritma içinden derinlik kontrolü
        if derinlik > 10.0:
            st.error("⚠️ HATA: İş güvenliği ve teknik standartlar gereği ortalama kazı derinliği maksimum 10 metre olabilir. Daha derin kazılar için özel iksa veya kademeli kazı projesi gereklidir. Lütfen derinliği azaltın.")
        else:
            gerekli_pozlar = [kazi_pozu, kum_pozu, dolgu_pozu, boru_pozu]
            if ic_cap_mm >= 800:
                gerekli_pozlar.append(hasir_celik_pozu)
                
            eksik_pozlar = [poz for poz in gerekli_pozlar if poz not in poz_listesi]
            
            if eksik_pozlar:
                st.error(f"⚠️ Hata: 'Altyapı Birim Fiyatlar_2.xlsx' dosyasında şu otomatik pozlar bulunamadı: {', '.join(eksik_pozlar)}")
            else:
                et_kalinlikleri_mm = {300: 50, 400: 50, 500: 60, 600: 70, 800: 90, 1000: 110, 1200: 130, 1400: 150, 1600: 170, 1800: 180, 2000: 200, 2200: 220, 2400: 240}
                et_kalinligi = et_kalinlikleri_mm.get(ic_cap_mm, ic_cap_mm * 0.1)
                dis_cap_mm = ic_cap_mm + (2 * et_kalinligi)
                dis_cap_m = dis_cap_mm / 1000.0

                # Çalışma payı eklendi (Boru dış çapı + 100 cm)
                taban_genisligi = dis_cap_m + 1.00
                ortalama_genislik = taban_genisligi + (derinlik / 3) if derinlik > 1.50 else taban_genisligi

                kazi_hacmi = ortalama_genislik * derinlik * uzunluk
                boru_hacmi_dis = math.pi * ((dis_cap_m / 2) ** 2) * uzunluk
                kum_dolgu_yuksekligi = 0.10 + dis_cap_m + 0.30
                kum_ortalama_genislik = taban_genisligi + (kum_dolgu_yuksekligi / 3) if derinlik > 1.50 else taban_genisligi
                kum_dolgu_hacmi_brut = kum_ortalama_genislik * kum_dolgu_yuksekligi * uzunluk
                kum_dolgu_hacmi_net = kum_dolgu_hacmi_brut - boru_hacmi_dis
                tuvenan_dolgu_hacmi = kazi_hacmi - kum_dolgu_hacmi_brut

                hasir_celik_miktari_ton = 0
                if ic_cap_mm >= 800:
                    donati_capi_m = (ic_cap_mm + et_kalinligi) / 1000.0
                    hasir_celik_alani_m2 = (math.pi * donati_capi_m) * uzunluk
                    hasir_celik_miktari_ton = (hasir_celik_alani_m2 * 2.95) / 1000.0 

                nakliye_kazi_miktari = kazi_hacmi - (tuvenan_dolgu_hacmi if dolgu_pozu == "43.610.1004" else 0)
                fiyat_SNBF_27A = 1.25 * K_katsayisi * ((0.00046 * math.sqrt(mesafe_kazi * 1000)) - 0.0046) + 29.28 + 80.00 if mesafe_kazi > 0 else 0
                boru_malzeme_hacmi = math.pi * (((dis_cap_m/2)**2) - ((ic_cap_mm/2000)**2)) * uzunluk
                nakliye_boru_ton = boru_malzeme_hacmi * beton_yogunluk
                fiyat_SNBF_BF = A_katsayisi * K_katsayisi * ((0.0007 * mesafe_boru) + 0.01) * 1.0 if mesafe_boru > 0 else 0
                nakliye_kirmatas_miktari = kum_dolgu_hacmi_net + (tuvenan_dolgu_hacmi if dolgu_pozu == "43.610.1064" else 0)
                fiyat_SNBF_14 = A_katsayisi * K_katsayisi * ((0.0007 * mesafe_kirmatas) + 0.01) * kirmata_yogunluk + 29.28 if mesafe_kirmatas > 0 else 0

                hesap_kalemleri = [
                    {"İşlem": "Kazı", "Poz": kazi_pozu, "Miktar (Sayısal)": kazi_hacmi, "Birim": "m³"},
                    {"İşlem": f"Boru Döşeme (Ø{ic_cap_mm} mm)", "Poz": boru_pozu, "Miktar (Sayısal)": uzunluk, "Birim": "m"},
                    {"İşlem": "Yataklama (Kırmataş/Kum)", "Poz": kum_pozu, "Miktar (Sayısal)": kum_dolgu_hacmi_net, "Birim": "m³"},
                    {"İşlem": "Geri Dolgu", "Poz": dolgu_pozu, "Miktar (Sayısal)": tuvenan_dolgu_hacmi, "Birim": "m³"}
                ]
                if hasir_celik_miktari_ton > 0:
                    hesap_kalemleri.append({"İşlem": "Boru İçi Hasır Çelik Donatı", "Poz": hasir_celik_pozu, "Miktar (Sayısal)": hasir_celik_miktari_ton, "Birim": "ton"})

                maliyet_tablosu_gorsel = []
                maliyet_tablosu_excel = [] 
                
                def satir_hesapla(islem, poz, miktar, birim, karsiz_fiyat):
                    if miktar > 0 and karsiz_fiyat > 0:
                        karli_fiyat = karsiz_fiyat * k_carpan
                        karsiz_tutar = miktar * karsiz_fiyat
                        karli_tutar = miktar * karli_fiyat
                        
                        maliyet_tablosu_gorsel.append({
                            "İşlem Adı": islem, "Poz No": poz, 
                            "Miktar": format_quantity(miktar), "Birim": birim,
                            "Kârsız Birim Fiyat": format_currency(karsiz_fiyat), 
                            "Kârlı Birim Fiyat": format_currency(karli_fiyat), 
                            "Kârsız Tutar": format_currency(karsiz_tutar),
                            "Kârlı Tutar": format_currency(karli_tutar)
                        })
                        
                        maliyet_tablosu_excel.append({
                            "İşlem Adı": islem, "Poz No": poz, 
                            "Miktar": miktar, "Birim": birim,
                            "Kârsız Birim Fiyat (TL)": karsiz_fiyat, 
                            "Kârlı Birim Fiyat (TL)": karli_fiyat, 
                            "Kârsız Tutar (TL)": karsiz_tutar,
                            "Kârlı Tutar (TL)": karli_tutar
                        })
                        return karsiz_tutar, karli_tutar
                    return 0.0, 0.0

                genel_toplam_karsiz = 0.0
                genel_toplam_karli = 0.0

                for kalem in hesap_kalemleri:
                    karsiz_bf = df_fiyatlar[df_fiyatlar['POZ NO'].astype(str) == kalem["Poz"]].iloc[0][secilen_donem]
                    karsiz_t, karli_t = satir_hesapla(kalem["İşlem"], kalem["Poz"], kalem["Miktar (Sayısal)"], kalem["Birim"], karsiz_bf)
                    genel_toplam_karsiz += karsiz_t
                    genel_toplam_karli += karli_t
                    
                karsiz_t, karli_t = satir_hesapla("Kazı Hafriyat Nakliyesi", "SNBF.27-A", nakliye_kazi_miktari, "m³", fiyat_SNBF_27A)
                genel_toplam_karsiz += karsiz_t
                genel_toplam_karli += karli_t
                
                karsiz_t, karli_t = satir_hesapla("Boru Nakliyesi", "SNBF.BF", nakliye_boru_ton, "ton", fiyat_SNBF_BF)
                genel_toplam_karsiz += karsiz_t
                genel_toplam_karli += karli_t
                
                karsiz_t, karli_t = satir_hesapla("Kırmataş/Kum Nakliyesi", "SNBF.14", nakliye_kirmatas_miktari, "m³", fiyat_SNBF_14)
                genel_toplam_karsiz += karsiz_t
                genel_toplam_karli += karli_t

                maliyet_tablosu_gorsel.append({
                    "İşlem Adı": "TOPLAM", "Poz No": "", 
                    "Miktar": "", "Birim": "",
                    "Kârsız Birim Fiyat": "", 
                    "Kârlı Birim Fiyat": "", 
                    "Kârsız Tutar": format_currency(genel_toplam_karsiz),
                    "Kârlı Tutar": format_currency(genel_toplam_karli)
                })

                st.divider()
                donati_bilgisi = f" | Hasır Çelik: {format_quantity(hasir_celik_miktari_ton)} Ton" if hasir_celik_miktari_ton > 0 else " | Hasır Çelik: Yok"
                st.info(f"📐 **Metraj Detayları:** İç Çap: Ø{ic_cap_mm} mm | Dış Çap: Ø{dis_cap_mm} mm | Boru Ağırlığı: {format_quantity(nakliye_boru_ton)} Ton{donati_bilgisi}")
                
                col1, col2 = st.columns([7, 4])
                
                with col1:
                    df_sonuc_gorsel = pd.DataFrame(maliyet_tablosu_gorsel)
                    df_sonuc_gorsel.index = df_sonuc_gorsel.index + 1 
                    
                    def style_last_row(row):
                        if row.name == df_sonuc_gorsel.index[-1]:
                            return ['background-color: transparent; color: black; font-weight: bold; font-size: 1.15em;'] * len(row)
                        return [''] * len(row)

                    styled_df = df_sonuc_gorsel.style.set_properties(
                        subset=['İşlem Adı'], **{'text-align': 'left'}
                    ).set_properties(
                        subset=['Poz No', 'Birim'], **{'text-align': 'center'}
                    ).set_properties(
                        subset=['Miktar', 'Kârsız Birim Fiyat', 'Kârlı Birim Fiyat', 'Kârsız Tutar', 'Kârlı Tutar'], **{'text-align': 'right'}
                    ).apply(style_last_row, axis=1)
                    
                    styled_df = styled_df.set_table_styles([
                        {'selector': 'th', 'props': [('background-color', '#493628'), ('color', '#E4E0E1'), ('font-weight', 'bold'), ('text-align', 'center')]}
                    ])
                    
                    st.dataframe(styled_df, use_container_width=True)
                    
                    df_sonuc_excel = pd.DataFrame(maliyet_tablosu_excel)
                    df_sonuc_excel.index = df_sonuc_excel.index + 1
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_sonuc_excel.to_excel(writer, sheet_name='Yaklaşık Maliyet Raporu')
                    b64 = base64.b64encode(buffer.getvalue()).decode()
                    
                    excel_href = f'''
                    <div style="margin-top: 5px;">
                        <a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" 
                           download="Altyapi_Yaklasik_Maliyet_Raporu.xlsx" 
                           style="display: inline-block; background-color: #217346; color: white; padding: 10px 20px; 
                                  text-decoration: none; border-radius: 5px; font-weight: bold;">
                           📗 Excel Olarak İndir
                        </a>
                    </div>
                    '''
                    st.markdown(excel_href, unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.success(f"### 📈 GENEL TOPLAM (%{kar_orani} kârlı): {format_currency(genel_toplam_karli)}")
                    
                    if uzunluk > 0:
                        metretul_maliyeti = genel_toplam_karli / uzunluk
                        metretul_maliyeti_str = format_currency(metretul_maliyeti).replace('₺', '').strip()
                        st.info(f"### 📏 Metretül Maliyeti: {metretul_maliyeti_str} TL/m")
                    
                with col2:
                    fig = cizim_olustur(ic_cap_mm, dis_cap_m, derinlik, taban_genisligi, zemin_tipi)
                    st.pyplot(fig)

except FileNotFoundError:
    st.error(f"⚠️ HATA: '{file_path}' dosyası bulunamadı. Lütfen Excel dosyasını GitHub deponuza yüklediğinizden emin olun.")
except Exception as e:
    st.error(f"⚠️ Kritik bir hata oluştu: {e}")