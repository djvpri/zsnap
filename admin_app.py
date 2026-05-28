import streamlit as st
import requests
import random
import string

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

def generate_license_key(plan: str = ""):
    chars = string.ascii_uppercase + string.digits
    parts = ["".join(random.choices(chars, k=6)) for _ in range(3)]
    prefix = plan.upper() if plan else "ZOMET"
    return prefix + "-" + "-".join(parts)

check_login()

# =========================================================
# DASHBOARD
# =========================================================

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

st.title("Zomet Admin Dashboard")

if "generated_key" not in st.session_state:
    st.session_state.generated_key = ""

plan = st.selectbox("Plan", ["demo", "daily", "weekly", "monthly", "yearly"])

col1, col2 = st.columns([4, 1])
with col1:
    key = st.text_input("License Key", value=st.session_state.generated_key)
with col2:
    st.write("")
    if st.button("Generate"):
        st.session_state.generated_key = generate_license_key(plan)
        st.rerun()

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
            st.code(key.strip(), language=None)
        else:
            st.error(f"Gagal! Status {res.status_code}\n\n{res.text}")

    except requests.Timeout:
        st.error("Request timeout. Server terlalu lama merespon.")

    except Exception as e:
        st.error(f"Error: {str(e)}")

# =========================================================
# MASS GENERATE LICENSE
# =========================================================

st.divider()
st.subheader("Mass Generate License")

mass_plan = st.selectbox("Plan", ["demo", "daily", "weekly", "monthly", "yearly"], key="mass_plan")
quantity = st.number_input("Jumlah License", min_value=1, max_value=100, value=10, step=1)

if st.button("Generate & Create"):
    try:
        res = requests.post(
            "https://zomet-production.up.railway.app/bulk-create-licenses",
            json={"plan": mass_plan, "quantity": int(quantity)},
            headers={"x-api-key": st.secrets["API_KEY"]},
            timeout=30
        )

        if res.status_code == 200:
            result = res.json()
            st.success(f"{result['count']} lisensi berhasil dibuat!")
            st.caption("License Keys (klik ikon copy di pojok kanan):")
            st.code("\n".join(result["created"]), language=None)
        else:
            st.error(f"Gagal! Status {res.status_code}\n\n{res.text}")

    except requests.Timeout:
        st.error("Request timeout.")

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
            st.dataframe(data, use_container_width=True)

            st.divider()
            st.subheader("Hapus Lisensi")

            keys = [lic["license_key"] for lic in data]
            tab_single, tab_bulk = st.tabs(["Hapus Satu", "Hapus Banyak"])

            with tab_single:
                selected_key = st.selectbox("Pilih License Key", keys)
                confirm_single = st.checkbox(f'Konfirmasi hapus "{selected_key}"')

                if st.button("Hapus", type="primary", disabled=not confirm_single):
                    try:
                        del_res = requests.delete(
                            f"https://zomet-production.up.railway.app/delete-license/{selected_key}",
                            headers={"x-api-key": st.secrets["API_KEY"]},
                            timeout=15
                        )
                        if del_res.status_code == 200:
                            st.success(f"Lisensi {selected_key} berhasil dihapus!")
                            st.rerun()
                        else:
                            st.error(f"Gagal! Status {del_res.status_code}\n\n{del_res.text}")

                    except requests.Timeout:
                        st.error("Request timeout.")

                    except Exception as ex:
                        st.error(f"Error: {str(ex)}")

            with tab_bulk:
                selected_keys = st.multiselect("Pilih License Keys", keys)

                if selected_keys:
                    confirm_bulk = st.checkbox(f"Konfirmasi hapus {len(selected_keys)} lisensi")

                    if st.button("Hapus Semua yang Dipilih", type="primary", disabled=not confirm_bulk):
                        try:
                            del_res = requests.post(
                                "https://zomet-production.up.railway.app/bulk-delete-licenses",
                                json={"license_keys": selected_keys},
                                headers={"x-api-key": st.secrets["API_KEY"]},
                                timeout=30
                            )
                            if del_res.status_code == 200:
                                result = del_res.json()
                                st.success(f"{result['count']} lisensi berhasil dihapus!")
                                st.rerun()
                            else:
                                st.error(f"Gagal! Status {del_res.status_code}\n\n{del_res.text}")

                        except requests.Timeout:
                            st.error("Request timeout.")

                        except Exception as ex:
                            st.error(f"Error: {str(ex)}")
                else:
                    st.info("Pilih minimal satu license key.")
        else:
            st.info("Belum ada lisensi.")
    else:
        st.error(f"Gagal memuat daftar. Status {res.status_code}")

except requests.Timeout:
    st.error("Request timeout.")

except Exception as e:
    st.error(f"Error: {str(e)}")
