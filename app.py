import streamlit as st
import pandas as pd
import os

st.title("IDL GP Stats")

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
    # Calculate 180s for the full dataset (all competitions)
        full_df["180s"] = full_df[throw_cols].apply(
            lambda row: sum(score == 180 for score in row if pd.notna(score)), axis=1
        )

    # Group by competition and player to find total 180s per competition
        comp_180s = (
            full_df.groupby(["Competition", "Player"])["180s"].sum().reset_index()
        )

    # Find the single highest 180 total in any competition
        max_180_row = comp_180s.loc[comp_180s["180s"].idxmax()]
        max_180s = int(max_180_row["180s"])
        top_player = max_180_row["Player"]
        top_comp = max_180_row["Competition"]

        st.markdown(
            f"🏆 **Most 180s in a single competition:** {top_player} — {max_180s} (at {top_comp})"
        )

    # Identify throw columns dynamically
    throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]

    if "Player" in full_df.columns and throw_cols:
        # Dropdown for competition selection
        competitions = full_df["Competition"].unique()
        selected_comp = st.selectbox("Select a competition", competitions)

        comp_df = full_df[full_df["Competition"] == selected_comp]

        # Count 180s and 140-179 scores for each player
        comp_df["180s"] = comp_df[throw_cols].apply(
            lambda row: sum(score == 180 for score in row if pd.notna(score)), axis=1
        )
        comp_df["140_179"] = comp_df[throw_cols].apply(
            lambda row: sum(140 <= score <= 179 for score in row if pd.notna(score)), axis=1
        )
        comp_df["100_139"] = comp_df[throw_cols].apply(
            lambda row: sum(100 <= score <= 139 for score in row if pd.notna(score)), axis=1
        )

        # Group by player
        player_stats = comp_df.groupby("Player")[["180s", "140_179", "100_139"]].sum().reset_index()

        # Total 180s in competition
        total_180s = player_stats["180s"].sum()

        # Sort by 180s first, then 140-179
        player_stats = player_stats.sort_values(by=["180s", "140_179", "100_139"], ascending=[False, False, False])

        # Sort top 5 in table
        player_stats = player_stats.head(5)

        st.subheader(f"Total 180s - {total_180s}")

        styled_df = player_stats.style.background_gradient(
            subset=["180s"],
            cmap="Greens",   # built-in light→dark green gradient
            low=0.25, high=1    # adjust brightness range (0–1)
        )
        st.dataframe(styled_df, hide_index=True)

        # Display table without index
        #st.dataframe(player_stats, hide_index=True)
    else:
        st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
else:
    st.warning("No CSV files found in the data folder.")





