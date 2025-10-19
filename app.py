# -*- coding: utf-8 -*-
"""
Streamlit – Bokningsformulär med sidomeny

Kör lokalt:
  streamlit run streamlit_bokningsform_app.py

Placera filen i din GitHub/Streamlit-app. Data sparas i ./data/bookings.csv
(Notera: filsystemet är temporärt på Streamlit Cloud – byt till extern datakälla vid behov.)
"""
from __future__ import annotations

import uuid
from pathlib import Path
from datetime import date, time, datetime

import pandas as pd
import streamlit as st
import requests

APP_TITLE = "Bokningar"
DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "bookings.csv"
# Make.com webhook (kan sättas i .streamlit/secrets.toml)
DEFAULT_MAKE_URL = st.secrets.get("MAKE_WEBHOOK_URL", "https://hook.eu2.make.com/b3errrh3g6qttaxya7b8ge1egggwiqs6")
DEFAULT_MAKE_HEADER_NAME = st.secrets.get("MAKE_HEADER_NAME", "")
DEFAULT_MAKE_HEADER_VALUE = st.secrets.get("MAKE_HEADER_VALUE", "")

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
            ]
        )
        df.to_csv(DATA_FILE, index=False, encoding="utf-8")


def load_bookings() -> pd.DataFrame:
    ensure_data_store()
    try:
        df = pd.read_csv(DATA_FILE, dtype=str, encoding="utf-8")
    except Exception:
        # Fallback om filen är tom/trasig
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
            ]
        )
    return df


def append_booking(row: dict) -> None:
    df = load_bookings()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False, encoding="utf-8")


def send_to_make(webhook_url: str, payload: dict, headers: dict | None = None) -> tuple[bool, str]:
    """Skicka JSON till Make.com webhook. Returnerar (ok, message)."""
    if not webhook_url:
        return False, "Ingen webhook-url angiven."
    try:
        resp = requests.post(webhook_url, json=payload, headers=headers or {}, timeout=10)
        if 200 <= resp.status_code < 300:
            return True, f"Webhook OK (status {resp.status_code})."
        return False, f"Webhook fel (status {resp.status_code}): {resp.text[:500]}"
    except Exception as e:
        return False, f"Webhook undantag: {e}"


# -------- UI & Layout -------- #
st.set_page_config(page_title=APP_TITLE, page_icon="📅", layout="centered")

# Minimal stil för renare formulär
st.markdown(
    """
    <style>
      .small-muted { color: #6b7280; font-size: 0.9rem; }
      .success-badge { background:#10b98122; padding:0.3rem 0.6rem; border-radius:0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📅 Bokningsformulär")
st.caption("En enkel grund som du kan bygga vidare på – lagrar lokalt i CSV.")

# Sidomeny
with st.sidebar:
    st.header("Meny")
    page = st.radio(
        "Gå till",
        (
            "Ny bokning",
            "Alla bokningar",
            "Export / Import",
            "Inställningar",
        ),
        index=0,
    )
    st.markdown("<p class='small-muted'>Den här menyn är förberedd för framtida sidor.</p>", unsafe_allow_html=True)

    with st.expander("Integrationer (Make.com)"):
        st.text("Skicka bokningar till ett Make-scenario via webhook.")
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
if page == "Ny bokning":
    st.subheader("Lägg till ny bokning")

    with st.form(key="booking_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            kund = st.text_input("Kund *", placeholder="Företag/Person")
            datum = st.date_input("Datum *", value=date.today(), format="YYYY-MM-DD")
            plats = st.text_input("Plats *", placeholder="Adress/Ort")
        with col2:
            uppdrag = st.text_input("Uppdrag *", placeholder="Ex. Möte, Workshop, Gig")
            tid = st.time_input("Tid *", value=time(9, 0), step=300)  # 5-min steg
            ersattning = st.text_input("Ersättning", placeholder="Ex. 4500 SEK eller timpris")

        st.markdown("<span class='small-muted'>Fält markerade med * är obligatoriska.</span>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Spara bokning", type="primary")

    if submitted:
        # Validering
        errors = []
        if not kund.strip():
            errors.append("Kund saknas.")
        if not uppdrag.strip():
            errors.append("Uppdrag saknas.")
        if not plats.strip():
            errors.append("Plats saknas.")
        if not isinstance(datum, date):
            errors.append("Datum är ogiltigt.")
        if not isinstance(tid, time):
            errors.append("Tid är ogiltig.")

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
            }
            append_booking(row)
            st.success("Bokningen sparades.")

            # --- Skicka till Make.com webhook om satt ---
            webhook_url = st.session_state.get("make_url") or DEFAULT_MAKE_URL
            headers = {}
            if st.session_state.get("make_header_name") and st.session_state.get("make_header_value"):
                headers[st.session_state["make_header_name"]] = st.session_state["make_header_value"]

            ok, msg = send_to_make(webhook_url, row, headers=headers)
            if ok:
                st.info(f"Skickat till Make: {msg}")
            else:
                st.warning(f"Kunde inte skicka till Make: {msg}")
            with st.expander("Visa sparad post"):
                st.json(row)

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
            # Grundläggande kolumnkontroll
            required_cols = {"id", "skapad", "kund", "uppdrag", "datum", "tid", "plats", "ersattning"}
            if not required_cols.issubset(set(map(str.lower, new_df.columns))):
                st.error("CSV saknar nödvändiga kolumner.")
            else:
                # Normalisera kolumnnamn till rätt ordning/format
                new_df.columns = [c.lower() for c in new_df.columns]
                new_df = new_df[["id", "skapad", "kund", "uppdrag", "datum", "tid", "plats", "ersattning"]]
                new_df.to_csv(DATA_FILE, index=False, encoding="utf-8")
                st.success("CSV importerad och sparad.")
        except Exception as e:
            st.error(f"Kunde inte läsa CSV: {e}")

elif page == "Inställningar":
    st.subheader("Inställningar")
    st.write("Här kan du framöver lägga till t.ex. standardvärden och integrationer mot andra system, m.m.")

    # Visa sökväg till datafilen
    ensure_data_store()
    st.code(str(DATA_FILE.resolve()))

    st.markdown(
        """
        **Tips för nästa steg**
        - Byt lagring från CSV till en extern datakälla (t.ex. databas).
        - Lägg till filter/sök i vyn *Alla bokningar*.
        - Koppla formuläret till e-post/SMS-bekräftelse via Power Automate.
        - Lägg till fältvalidering (t.ex. datum i framtiden, format på ersättning).
        """
    )
