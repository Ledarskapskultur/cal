# -*- coding: utf-8 -*-
"""
Streamlit – Bokningsformulär + Kontakt + Kanban-tavla

Kör lokalt:
  streamlit run streamlit_bokningsform_app_v3.py

Data lagras i ./data/*.csv
- bookings.csv  (bokningar)
- contacts.csv  (kontaktförfrågningar)

Obs: Kanban i Streamlit är enkel (ingen drag & drop). Du kan byta status
på kort via en select och appen sparar tillbaka.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from datetime import date, time, datetime
from typing import Literal

import pandas as pd
import streamlit as st
import requests

APP_TITLE = "Bokningar"
DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "bookings.csv"
CONTACTS_FILE = DATA_DIR / "contacts.csv"

# Make.com webhook (kan sättas i .streamlit/secrets.toml)
DEFAULT_MAKE_URL = st.secrets.get(
    "MAKE_WEBHOOK_URL",
    "https://hook.eu2.make.com/b3errrh3g6qttaxya7b8ge1egggwiqs6",
)
DEFAULT_MAKE_HEADER_NAME = st.secrets.get("MAKE_HEADER_NAME", "")
DEFAULT_MAKE_HEADER_VALUE = st.secrets.get("MAKE_HEADER_VALUE", "")

KANBAN_STATI: tuple[Literal["Ny", "Pågående", "Klar", "Arkiv"], ...] = (
    "Ny",
    "Pågående",
    "Klar",
    "Arkiv",
)

# -------- Hjälpfunktioner -------- #
def ensure_data_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        df = pd.DataFrame(
            columns=[
                "id",
                "skapad",
                "kund",
                "uppdrag",
                "datum",
                "tid",
                "plats",
                "ersattning",
                "status",  # Kanban-status
            ]
        )
        df.to_csv(DATA_FILE, index=False, encoding="utf-8")
    if not CONTACTS_FILE.exists():
        cf = pd.DataFrame(
            columns=[
                "id",
                "skapad",
                "namn",
                "telefon",
                "foretag",
                "mail",
                "kommentar",
                "status",  # Kanban-status
            ]
        )
        cf.to_csv(CONTACTS_FILE, index=False, encoding="utf-8")


def load_bookings() -> pd.DataFrame:
    ensure_data_store()
    try:
        df = pd.read_csv(DATA_FILE, dtype=str, encoding="utf-8")
    except Exception:
        df = pd.DataFrame(columns=["id","skapad","kund","uppdrag","datum","tid","plats","ersattning","status"])
    # Fallback status
    if "status" not in df.columns:
        df["status"] = "Ny"
    df["status"] = df["status"].fillna("Ny")
    return df


def load_contacts() -> pd.DataFrame:
    ensure_data_store()
    try:
        dfc = pd.read_csv(CONTACTS_FILE, dtype=str, encoding="utf-8")
    except Exception:
        dfc = pd.DataFrame(columns=["id","skapad","namn","telefon","foretag","mail","kommentar","status"])
    if "status" not in dfc.columns:
        dfc["status"] = "Ny"
    dfc["status"] = dfc["status"].fillna("Ny")
    return dfc


def save_bookings(df: pd.DataFrame) -> None:
    df.to_csv(DATA_FILE, index=False, encoding="utf-8")


def save_contacts(dfc: pd.DataFrame) -> None:
    dfc.to_csv(CONTACTS_FILE, index=False, encoding="utf-8")


def append_booking(row: dict) -> None:
    df = load_bookings()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_bookings(df)


def append_contact(row: dict) -> None:
    dfc = load_contacts()
    dfc = pd.concat([dfc, pd.DataFrame([row])], ignore_index=True)
    save_contacts(dfc)


def send_to_make(webhook_url: str, payload: dict, headers: dict | None = None) -> tuple[bool, str]:
    if not webhook_url:
        return False, "Ingen webhook-url angiven."
    try:
        resp = requests.post(webhook_url, json=payload, headers=headers or {}, timeout=10)
        if 200 <= resp.status_code < 300:
            return True, f"Webhook OK (status {resp.status_code})."
        return False, f"Webhook fel (status {resp.status_code}): {resp.text[:500]}"
    except Exception as e:
        return False, f"Webhook undantag: {e}"


def build_booking_payload(row: dict) -> dict:
    # Kombinera datum + tid till ISO (lokal, utan tzinfo)
    try:
        dt_local = datetime.strptime(f"{row['datum']} {row['tid']}", "%Y-%m-%d %H:%M")
        iso_start_local = dt_local.isoformat(timespec="minutes")
        epoch_ms = int(dt_local.timestamp() * 1000)
    except Exception:
        iso_start_local = None
        epoch_ms = None

    return {
        "type": "booking_created",
        "version": 1,
        "booking": row,
        "derived": {
            "start_local_iso": iso_start_local,
            "start_epoch_ms": epoch_ms,
        },
        "meta": {
            "sent_at": datetime.now().isoformat(timespec="seconds"),
            "app_title": APP_TITLE,
            "source": "streamlit",
        },
    }


def build_contact_payload(row: dict) -> dict:
    return {
        "type": "contact_created",
        "version": 1,
        "contact": row,
        "meta": {
            "sent_at": datetime.now().isoformat(timespec="seconds"),
            "app_title": APP_TITLE,
            "source": "streamlit",
        },
    }


# -------- UI & Layout -------- #
st.set_page_config(page_title=APP_TITLE, page_icon="📅", layout="wide")

st.title("📅 Bokningsverktyg")
st.caption("Bokningar, kontaktförfrågningar och en enkel kanban-tavla.")

# Sidomeny
with st.sidebar:
    st.header("Meny")
    page = st.radio(
        "Gå till",
        (
            "Ny post",
            "Kanban",
            "Alla bokningar",
            "Export / Import",
            "Inställningar",
        ),
        index=0,
    )

    with st.expander("Integrationer (Make.com)"):
        st.text("Skicka poster till ett Make-scenario via webhook.")
        st.session_state.setdefault("make_url", DEFAULT_MAKE_URL)
        st.session_state.setdefault("make_header_name", DEFAULT_MAKE_HEADER_NAME)
        st.session_state.setdefault("make_header_value", DEFAULT_MAKE_HEADER_VALUE)
        st.session_state["make_url"] = st.text_input("Webhook URL", value=st.session_state["make_url"], placeholder="https://hook.eu1.make.com/....")
        cols = st.columns(2)
        with cols[0]:
            st.session_state["make_header_name"] = st.text_input("Valfri header-namn", value=st.session_state["make_header_name"], placeholder="X-API-Key")
        with cols[1]:
            st.session_state["make_header_value"] = st.text_input("Valfri header-värde", value=st.session_state["make_header_value"], type="password")
        st.caption("Tips: Lägg dessa värden i secrets för drift.")

# -------- Sidor -------- #
if page == "Ny post":
    st.subheader("Lägg till ny bokning eller kontakt")

    tab_bokning, tab_kontakt = st.tabs(["➕ Bokning", "📇 Kontakt / Frågor"])

    with tab_bokning:
        with st.form(key="booking_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                kund = st.text_input("Kund *", placeholder="Företag/Person")
                datum = st.date_input("Datum *", value=date.today(), format="YYYY-MM-DD")
                plats = st.text_input("Plats *", placeholder="Adress/Ort")
            with col2:
                uppdrag = st.text_input("Uppdrag *", placeholder="Ex. Möte, Workshop, Gig")
                tid = st.time_input("Tid *", value=time(9, 0), step=300)
                ersattning = st.text_input("Ersättning", placeholder="Ex. 4500 SEK eller timpris")
            submitted = st.form_submit_button("Spara bokning", type="primary")

        if submitted:
            errors = []
            if not kund.strip():
                errors.append("Kund saknas.")
            if not uppdrag.strip():
                errors.append("Uppdrag saknas.")
            if not plats.strip():
                errors.append("Plats saknas.")
            if errors:
                st.error("\n".join(errors))
            else:
                booking_id = str(uuid.uuid4())
                now_iso = datetime.now().isoformat(timespec="seconds")
                row = {
                    "id": booking_id,
                    "skapad": now_iso,
                    "kund": kund.strip(),
                    "uppdrag": uppdrag.strip(),
                    "datum": str(datum),
                    "tid": tid.strftime("%H:%M"),
                    "plats": plats.strip(),
                    "ersattning": ersattning.strip(),
                    "status": "Ny",
                }
                append_booking(row)
                st.success("Bokningen sparades.")

                # Skicka till Make
                webhook_url = st.session_state.get("make_url") or DEFAULT_MAKE_URL
                headers = {}
                if st.session_state.get("make_header_name") and st.session_state.get("make_header_value"):
                    headers[st.session_state["make_header_name"]] = st.session_state["make_header_value"]
                payload = build_booking_payload(row)
                ok, msg = send_to_make(webhook_url, payload, headers=headers)
                st.info(msg if ok else msg)

                with st.expander("Visa sparad post"):
                    st.json(row)

    with tab_kontakt:
        with st.form(key="contact_form", clear_on_submit=True):
            cname = st.text_input("Namn *", placeholder="För- och efternamn")
            cphone = st.text_input("Telefon", placeholder="+46...")
            ccompany = st.text_input("Företag", placeholder="Företagsnamn")
            cemail = st.text_input("Mail *", placeholder="namn@domän.se")
            ccomment = st.text_area("Kommentar / frågor", placeholder="Skriv din fråga eller kommentar här...", height=120)
            csubmitted = st.form_submit_button("Skicka förfrågan", type="secondary")

        if csubmitted:
            cerrs = []
            if not cname.strip():
                cerrs.append("Namn saknas.")
            if not cemail.strip():
                cerrs.append("Mail saknas.")
            if cerrs:
                st.error("\n".join(cerrs))
            else:
                cid = str(uuid.uuid4())
                now_iso = datetime.now().isoformat(timespec="seconds")
                crow = {
                    "id": cid,
                    "skapad": now_iso,
                    "namn": cname.strip(),
                    "telefon": cphone.strip(),
                    "foretag": ccompany.strip(),
                    "mail": cemail.strip(),
                    "kommentar": ccomment.strip(),
                    "status": "Ny",
                }
                append_contact(crow)
                st.success("Tack! Din förfrågan är skickad.")

                webhook_url = st.session_state.get("make_url") or DEFAULT_MAKE_URL
                headers = {}
                if st.session_state.get("make_header_name") and st.session_state.get("make_header_value"):
                    headers[st.session_state["make_header_name"]] = st.session_state["make_header_value"]
                cpayload = build_contact_payload(crow)
                ok, msg = send_to_make(webhook_url, cpayload, headers=headers)
                st.info(msg if ok else msg)

elif page == "Kanban":
    st.subheader("Kanban – Bokningar & Kontakter")
    df = load_bookings()
    dfc = load_contacts()

    # Sammanställ en gemensam vy
    bk = df.copy()
    if not bk.empty:
        bk["typ"] = "Bokning"
        bk["titel"] = bk["kund"].fillna("") + " – " + bk["uppdrag"].fillna("")
        bk["beskrivning"] = (
            "📅 " + bk["datum"].fillna("") + " " + bk["tid"].fillna("") + "\n📍 " + bk["plats"].fillna("") + ("\n💰 " + bk["ersattning"]) .fillna("")
        )
    ct = dfc.copy()
    if not ct.empty:
        ct["typ"] = "Kontakt"
        ct["titel"] = ct["namn"].fillna("") + " – " + ct["foretag"].fillna("")
        ct["beskrivning"] = (
            "📞 " + ct["telefon"].fillna("") + "\n✉️ " + ct["mail"].fillna("") + "\n" + ct["kommentar"].fillna("")
        )

    all_items = pd.concat([bk, ct], ignore_index=True) if not bk.empty or not ct.empty else pd.DataFrame()

    cols = st.columns(len(KANBAN_STATI))
    for i, status in enumerate(KANBAN_STATI):
        with cols[i]:
            st.markdown(f"### {status}")
            subset = all_items[all_items["status"] == status] if not all_items.empty else pd.DataFrame()
            if subset.empty:
                st.caption("(inget)")
            else:
                for _, row in subset.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['titel']}**")
                        st.caption(row.get("typ", ""))
                        st.markdown(f"<pre style='white-space:pre-wrap'>{row['beskrivning']}</pre>", unsafe_allow_html=True)
                        new_status = st.selectbox(
                            "Byt status",
                            KANBAN_STATI,
                            index=KANBAN_STATI.index(row.get("status", "Ny")) if row.get("status", "Ny") in KANBAN_STATI else 0,
                            key=f"status_{row['typ']}_{row['id']}",
                        )
                        if new_status != row.get("status", "Ny"):
                            if row["typ"] == "Bokning":
                                df.loc[df["id"] == row["id"], "status"] = new_status
                                save_bookings(df)
                            else:
                                dfc.loc[dfc["id"] == row["id"], "status"] = new_status
                                save_contacts(dfc)
                            st.experimental_rerun()

elif page == "Alla bokningar":
    st.subheader("Samtliga bokningar")
    df = load_bookings()
    if df.empty:
        st.info("Inga bokningar sparade ännu.")
    else:
        # Sortera senaste överst
        if "skapad" in df.columns:
            df["skapad"] = pd.to_datetime(df["skapad"], errors="coerce")
            df = df.sort_values("skapad", ascending=False)
        st.dataframe(
            df.assign(skapad=df["skapad"].dt.strftime("%Y-%m-%d %H:%M:%S") if "skapad" in df else None),
            use_container_width=True,
            hide_index=True,
        )

elif page == "Export / Import":
    st.subheader("Export / Import")
    df = load_bookings()

    # Export
    csv_bytes = df.to_csv(index=False, encoding="utf-8").encode("utf-8")
    st.download_button(
        label="Ladda ner CSV",
        data=csv_bytes,
        file_name="bookings.csv",
        mime="text/csv",
    )

    st.divider()

    # Import
    uploaded = st.file_uploader("Importera CSV", type=["csv"]) 
    if uploaded is not None:
        try:
            new_df = pd.read_csv(uploaded, dtype=str, encoding="utf-8")
            required_cols = {"id", "skapad", "kund", "uppdrag", "datum", "tid", "plats", "ersattning", "status"}
            lower = {c.lower() for c in new_df.columns}
            if not required_cols.issubset(lower):
                st.error("CSV saknar nödvändiga kolumner (inkl. status).")
            else:
                new_df.columns = [c.lower() for c in new_df.columns]
                new_df = new_df[["id", "skapad", "kund", "uppdrag", "datum", "tid", "plats", "ersattning", "status"]]
                save_bookings(new_df)
                st.success("CSV importerad och sparad.")
        except Exception as e:
            st.error(f"Kunde inte läsa CSV: {e}")

elif page == "Inställningar":
    st.subheader("Inställningar")
    ensure_data_store()
    st.code(str(DATA_FILE.resolve()))
    st.code(str(CONTACTS_FILE.resolve()))
    st.markdown(
        """
        **Tips**
        - Lägg till filtrering/sök i Kanban.
        - Koppla statusbyte till Make-webhook (t.ex. skicka händelser vid uppdatering).
        - Bygg *Alla kontakter*-vy om du vill granska inkommande leads separat.
        """
    )
