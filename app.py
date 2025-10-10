import streamlit as st
import pandas as pd
import os

st.title("Darts League - 180s Tracker by Competition")

data_folder = "data"
all_data = []

# Load all CSVs
for file in os.listdir(data_folder):
    if file.endswith(".csv"):
        df = pd.read_csv(os.path.join(data_folder, file))
        df["Competition"] = df["Venue"] + " - " + df["Date"]
        all_data.append(df)

if all_data:
    full_df = pd.concat(all_data, ignore_index=True)

    # Identify throw columns dynamically
    throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]

    if "Player" in full_df.columns and throw_cols:
        # Dropdown for competition selection
        competitions = full_df["Competition"].unique()
        selected_comp = st.selectbox("Select a competition", competitions)

        comp_df = full_df[full_df["Competition"] == selected_comp]

        # Count 180s for each player in selected competition
        comp_df["180s_in_leg"] = comp_df[throw_cols].apply(
            lambda row: sum(score == 180 for score in row if pd.notna(score)), axis=1
        )
        player_180s = comp_df.groupby("Player")["180s_in_leg"].sum().reset_index()

        # Filter players with at least 1 180
        player_180s = player_180s[player_180s["180s_in_leg"] > 0]
        player_180s = player_180s.sort_values(by="180s_in_leg", ascending=False)

        # Total 180s in competition
        total_180s = player_180s["180s_in_leg"].sum()

        st.subheader(f"Total 180s in {selected_comp}: {total_180s}")
        st.table(player_180s.style.hide(axis="index"))  # ✅ hides index
    else:
        st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
else:
    st.warning("No CSV files found in the data folder.")
