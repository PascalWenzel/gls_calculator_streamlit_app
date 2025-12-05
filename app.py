import io
import re
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

def extract_kundennummer(path_string: str):
    """Extrahiert die Kundennummer aus ...FF/<KUNDENNR>/... oder ...FF\<KUNDENNR>\..."""
    if pd.isna(path_string):
        return None

    s = str(path_string)
    m = re.search(r"FF[\\/](.*?)[\\/]", s)
    if m:
        return m.group(1)
    return None


def berechne_auswertung(df: pd.DataFrame) -> pd.DataFrame:
    # Spalten anhand Index (A=0, B=1, ..., J=9)
    betrag_col = df.columns[6]    # Spalte G
    paketnr_col = df.columns[3]   # Spalte D
    j_col = df.columns[9]         # Spalte J

    # Kundennummer extrahieren
    df["Kundennummer"] = df[j_col].apply(extract_kundennummer)

    # Betrag normalisieren (z.B. "1.234,56" -> 1234.56)
    df["Betrag_num"] = (
        df[betrag_col]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    df["Betrag_num"] = pd.to_numeric(df["Betrag_num"], errors="coerce").fillna(0.0)

    df_kunden = df.dropna(subset=["Kundennummer"])

    grouped = (
        df_kunden
        .groupby("Kundennummer")
        .agg(
            Pakete=(paketnr_col, "nunique"),
            Zeilen=("Kundennummer", "size"),
            Kosten_gesamt=("Betrag_num", "sum")
        )
        .reset_index()
    )

    # Zuschläge
    grouped["Energie_23_5"]      = grouped["Kosten_gesamt"] * 0.235
    grouped["Season_Peak_1"]     = grouped["Kosten_gesamt"] * 0.01
    grouped["Klima_Protect_2"]   = grouped["Kosten_gesamt"] * 0.02

    grouped["Gesamt_mit_Zuschlaegen"] = (
        grouped["Kosten_gesamt"]
        + grouped["Energie_23_5"]
        + grouped["Season_Peak_1"]
        + grouped["Klima_Protect_2"]
    )
    # Durchschnitt pro Paket
    grouped["Durchschnitt_pro_Paket"] = (
        grouped["Gesamt_mit_Zuschlaegen"] / grouped["Pakete"]
    )


    return grouped


# ---------------------------
# STREAMLIT-APP
# ---------------------------

st.title("Kunden-Auswertung Versandkosten")

st.write("Lade hier die CSV-Datei hoch (z.B. Export aus deinem System).")

uploaded_file = st.file_uploader("Datei auswählen", type=["csv"])

if uploaded_file is not None:
    # Versuch mit ; als Trennzeichen (typisch in DE-Exporten)
    try:
        df = pd.read_csv(uploaded_file, sep=";", dtype=str, encoding="latin1")
    except Exception:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, dtype=str)

    st.write("Vorschau der eingelesenen Datei:")
    st.dataframe(df.head())

    if st.button("Auswertung starten"):
        try:
            result = berechne_auswertung(df)

            st.success("Auswertung fertig!")
            st.write("Ergebnis (Vorschau):")
            st.dataframe(result.head())

            # Excel in den Speicher schreiben
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                result.to_excel(writer, index=False, sheet_name="Auswertung")
            output.seek(0)

            st.download_button(
                label="📥 Excel-Datei herunterladen",
                data=output,
                file_name="auswertung_pro_kunde.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Fehler bei der Auswertung: {e}")
else:
    st.info("Bitte eine CSV-Datei hochladen.")
