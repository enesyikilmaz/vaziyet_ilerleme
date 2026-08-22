# --- GİRİŞ EKRANI (LOGIN) ---
if st.session_state["user"] is None:
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
                    # Supabase'den kullanıcı sorgulama
                    res = supabase.table("kullanicilar").select("*").eq("email", email).eq("sifre", sifre).execute()
                    
                    if len(res.data) > 0:
                        st.session_state["user"] = res.data[0]
                        st.rerun() # Başarılı girişte sayfayı yenile ve sistemi aç
                    else:
                        st.error("Hatalı e-posta veya şifre!")
                except Exception as e:
                    # Eğer veritabanı kaynaklı bir API hatası olursa ekrana düzgünce yazdır
                    st.error(f"Veritabanı bağlantı hatası: {e}")
    st.stop() # Kullanıcı giriş yapmadıysa uygulamanın geri kalanını çalıştırma