import streamlit as st
import requests

# =========================================================
# AUTENTIKASI ADMIN
# =========================================================

def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("Zomet Admin — Login")

        password = st.text_input("Password Admin", type="password")

        if st.button("Login"):
            if password == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Password salah!")

        st.stop()

check_login()

# =========================================================
# DASHBOARD
# =========================================================

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

st.title("Zomet Admin Dashboard")

key = st.text_input("License Key")
plan = st.selectbox("Plan", ["demo", "daily", "weekly", "monthly", "yearly"])

if st.button("Create License"):

    if not key.strip():
        st.warning("License key tidak boleh kosong!")
        st.stop()

    try:
        res = requests.post(
            "https://zomet-production.up.railway.app/create-license",
            json={
                "license_key": key.strip(),
                "plan": plan
            },
            headers={"x-api-key": st.secrets["API_KEY"]},
            timeout=15
        )

        if res.status_code == 200:
            st.success("Lisensi berhasil dibuat!")
        else:
            st.error(f"Gagal! Status {res.status_code}\n\n{res.text}")

    except requests.Timeout:
        st.error("Request timeout. Server terlalu lama merespon.")

    except Exception as e:
        st.error(f"Error: {str(e)}")

# =========================================================
# DAFTAR LISENSI
# =========================================================

st.divider()
st.subheader("Daftar Lisensi")

if st.button("Refresh"):
    st.rerun()

try:
    res = requests.get(
        "https://zomet-production.up.railway.app/list-licenses",
        headers={"x-api-key": st.secrets["API_KEY"]},
        timeout=15
    )

    if res.status_code == 200:
        data = res.json()
        if data:
            st.dataframe(
                data,
                use_container_width=True
            )
        else:
            st.info("Belum ada lisensi.")
    else:
        st.error(f"Gagal memuat daftar. Status {res.status_code}")

except requests.Timeout:
    st.error("Request timeout.")

except Exception as e:
    st.error(f"Error: {str(e)}")
