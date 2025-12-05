import io
import re
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

def extract_customer_number(path_string: str):
    """Extracts the customer number from ...FF/<CUSTOMER_NO>/... or ...FF\<CUSTOMER_NO>\..."""
    if pd.isna(path_string):
        return None

    s = str(path_string)
    m = re.search(r"FF[\\/](.*?)[\\/]", s)
    if m:
        return m.group(1)
    return None


def compute_report(df: pd.DataFrame) -> pd.DataFrame:
    # Columns by index (A=0, B=1, ..., J=9)
    amount_col = df.columns[6]    # Column G
    package_no_col = df.columns[3]   # Column D
    j_col = df.columns[9]         # Column J

    # Extract customer number
    df["Customer_Number"] = df[j_col].apply(extract_customer_number)

    # Normalize amount (e.g. "1.234,56" -> 1234.56)
    df["Amount_num"] = (
        df[amount_col]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    df["Amount_num"] = pd.to_numeric(df["Amount_num"], errors="coerce").fillna(0.0)

    df_customers = df.dropna(subset=["Customer_Number"])

    grouped = (
        df_customers
        .groupby("Customer_Number")
        .agg(
            Packages=(package_no_col, "nunique"),
            Rows=("Customer_Number", "size"),
            Total_Cost=("Amount_num", "sum")
        )
        .reset_index()
    )

    # Surcharges
    grouped["Energy_23_5"]        = grouped["Total_Cost"] * 0.235
    grouped["Season_Peak_1"]      = grouped["Total_Cost"] * 0.01
    grouped["Climate_Protect_2"]  = grouped["Total_Cost"] * 0.02

    grouped["Total_with_Surcharges"] = (
        grouped["Total_Cost"]
        + grouped["Energy_23_5"]
        + grouped["Season_Peak_1"]
        + grouped["Climate_Protect_2"]
    )

    # Average per package
    grouped["Average_per_Package"] = (
        grouped["Total_with_Surcharges"] / grouped["Packages"]
    )

    return grouped


# ---------------------------
# STREAMLIT APP
# ---------------------------

st.title("Customer Shipping Cost Report")

st.write("Upload your CSV file here (e.g., export from your system).")

uploaded_file = st.file_uploader("Choose a file", type=["csv"])

if uploaded_file is not None:
    # Try ; as separator (common in DE exports)
    try:
        df = pd.read_csv(uploaded_file, sep=";", dtype=str, encoding="latin1")
    except Exception:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, dtype=str)

    st.write("Preview of the imported file:")
    st.dataframe(df.head())

    if st.button("Start analysis"):
        try:
            result = compute_report(df)

            st.success("Analysis completed!")
            st.write("Result (preview):")
            st.dataframe(result.head())

            # Write Excel to memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                result.to_excel(writer, index=False, sheet_name="Report")
            output.seek(0)

            st.download_button(
                label="📥 Download Excel file",
                data=output,
                file_name="report_per_customer.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Error during analysis: {e}")
else:
    st.info("Please upload a CSV file.")
