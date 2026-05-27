import streamlit as st
import requests

st.title("Zomet Admin Dashboard")
key = st.text_input("License Key")
plan = st.selectbox("Plan", ["demo", "weekly", "monthly", "yearly"])

if st.button("Create License"):
    # Kirim request ke API utama Anda
    res = requests.post(
        "https://zomet-production.up.railway.app/create-license", 
        json={"license_key": key}, 
        params={"plan": plan},
        headers={"x-api-key": "rahasia-dari-desktop-ke-server"}
    )
    if res.status_code == 200:
        st.success("Lisensi berhasil dibuat!")
    else:
        st.error("Gagal!")