import streamlit as st
import pandas as pd
import os

st.title("Darts League - 180s Tracker")

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

    # Identify throw columns dynamically
    throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]

    if "Player" in full_df.columns and throw_cols:
        # Count 180s for each player
        full_df["180s_in_leg"] = full_df[throw_cols].apply(lambda row: sum(score == 180 for score in row if pd.notna(score)), axis=1)
        player_180s = full_df.groupby("Player")["180s_in_leg"].sum().reset_index()
        player_180s = player_180s.sort_values(by="180s_in_leg", ascending=False)

        st.subheader("Total 180s by Player")
        st.table(player_180s)
    else:
        st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
else:
    st.warning("No CSV files found in the data folder.")
