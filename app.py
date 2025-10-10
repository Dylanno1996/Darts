import streamlit as st
import pandas as pd
import os

st.title("Darts League - 180s Tracker")

# Folder containing CSV files
data_folder = "data"
all_data = []

# Load all CSVs
for file in os.listdir(data_folder):
    if file.endswith(".csv"):
        df = pd.read_csv(os.path.join(data_folder, file))
        df["Competition"] = file.replace(".csv", "")
        all_data.append(df)

if all_data:
    full_df = pd.concat(all_data, ignore_index=True)

    # Check if '180s' column exists
    if "180s" in full_df.columns and "Player" in full_df.columns:
        # Group by Player and sum 180s
        player_180s = full_df.groupby("Player")["180s"].sum().reset_index()
        player_180s = player_180s.sort_values(by="180s", ascending=False)

        st.subheader("Total 180s by Player")
        st.table(player_180s)
    else:
        st.error("CSV files must have 'Player' and '180s' columns.")
else:
    st.warning("No CSV files found in the data folder.")
