import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="IDL GP Stats", layout="centered")

st.title("IDL GP Stats")

# --- Load all CSV data ---
data_folder = "data"
all_data = []

for file in os.listdir(data_folder):
    if file.endswith(".csv"):
        df = pd.read_csv(os.path.join(data_folder, file))
        df["OriginalDate"] = df.get("Date", "")
        all_data.append(df)

if not all_data:
    st.warning("No CSV files found in the data folder.")
    st.stop()

full_df = pd.concat(all_data, ignore_index=True)

# --- Parse Date Column ---
if "OriginalDate" in full_df.columns:
    full_df["ParsedDate"] = pd.NaT
    date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %m %Y"]
    for fmt in date_formats:
        mask_unparsed = full_df["ParsedDate"].isna()
        if mask_unparsed.any():
            full_df.loc[mask_unparsed, "ParsedDate"] = pd.to_datetime(
                full_df.loc[mask_unparsed, "OriginalDate"],
                format=fmt,
                errors="coerce"
            )
    full_df["Date_str"] = full_df["ParsedDate"].dt.strftime("%d-%b-%Y")
    full_df.loc[full_df["Date_str"].isna(), "Date_str"] = full_df["OriginalDate"].astype(str)
else:
    full_df["ParsedDate"] = pd.NaT
    full_df["Date_str"] = ""

# --- Create Competition Label ---
full_df["Venue"] = full_df["Venue"].astype(str)
full_df["Competition"] = full_df["Venue"] + " - " + full_df["Date_str"]

# --- Sort competitions ---
full_df = full_df.sort_values("ParsedDate", ascending=False, na_position="last")
competitions_df = (
    full_df[["Competition", "ParsedDate"]]
    .drop_duplicates()
    .sort_values("ParsedDate", ascending=False, na_position="last")
    .reset_index(drop=True)
)

selected_comp = st.selectbox("Select a competition", competitions_df["Competition"].tolist())

# --- Identify throw columns dynamically ---
throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]
for c in throw_cols:
    full_df[c] = pd.to_numeric(full_df[c], errors="coerce")

if not ("Player" in full_df.columns and throw_cols):
    st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
    st.stop()

# --- Navigation Sidebar ---
page = st.sidebar.radio("📊 Select Page", ["🎯 180s Stats", "🎣 Checkout Stats"])

# ==================================================================
# 🎯 PAGE 1 — 180s Stats
# ==================================================================
if page == "🎯 180s Stats":

    # Calculate 180s
    full_df["180s"] = full_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and score == 180), axis=1
    )

    comp_df = full_df[full_df["Competition"] == selected_comp].copy()
    comp_df["180s"] = comp_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and score == 180), axis=1
    )
    comp_df["140_179"] = comp_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and 140 <= score <= 179), axis=1
    )
    comp_df["100_139"] = comp_df[throw_cols].apply(
        lambda row: sum(1 for score in row if pd.notna(score) and 100 <= score <= 139), axis=1
    )

    player_stats = comp_df.groupby("Player")[["180s", "140_179", "100_139"]].sum().reset_index()
    player_stats.rename(columns={"140_179": "140+", "100_139": "100+"}, inplace=True)

    total_180s = int(player_stats["180s"].sum()) if not player_stats.empty else 0
    player_stats = player_stats.sort_values(by=["180s", "140+", "100+"], ascending=[False, False, False])
    top5_stats = player_stats.head(5).reset_index(drop=True)

    # --- Display main table right below dropdown ---
    st.subheader(f"Top 5 Players — {selected_comp}")
    st.dataframe(top5_stats, hide_index=True)
    st.caption(f"Total 180s in this competition: {total_180s}")

    # --- 180s Highlights at the bottom ---
    comp_180s = full_df.groupby(["Competition", "Player"])["180s"].sum().reset_index()

    if not comp_180s.empty:
        max_180_row = comp_180s.loc[comp_180s["180s"].idxmax()]
        max_180s = int(max_180_row["180s"])
        top_player = max_180_row["Player"]
        top_comp = max_180_row["Competition"]

        total_180s_all = comp_180s.groupby("Player")["180s"].sum().reset_index()
        max_total_row = total_180s_all.loc[total_180s_all["180s"].idxmax()]
        top_total_player = max_total_row["Player"]
        top_total_180s = int(max_total_row["180s"])

        tournament_totals = comp_180s.groupby("Competition")["180s"].sum().reset_index()
        top_tournament_row = tournament_totals.loc[tournament_totals["180s"].idxmax()]
        top_tournament = top_tournament_row["Competition"]
        top_tournament_180s = int(top_tournament_row["180s"])

        st.markdown("---")
        st.markdown("## 🎯 180s Highlights")
        st.markdown("🏆 **Most 180s in a Single Competition:**")
        st.markdown(f"### &nbsp;&nbsp;&nbsp;&nbsp;{max_180s} — {top_player} ({top_comp})")

        st.markdown("🎯 **Most 180s Across All Competitions:**")
        st.markdown(f"### &nbsp;&nbsp;&nbsp;&nbsp;{top_total_180s} — {top_total_player}")

        st.markdown("📍 **Most 180s at a Single Tournament:**")
        st.markdown(f"### &nbsp;&nbsp;&nbsp;&nbsp;{top_tournament_180s} — {top_tournament}")


# ==================================================================
# 🎣 PAGE 2 — Checkout Stats
# ==================================================================
elif page == "🎣 Checkout Stats":

    winners_df = full_df[full_df["Result"].str.upper() == "WON"].copy()

    if winners_df.empty:
        st.info("No winning legs found — cannot calculate checkouts.")
        st.stop()

    # Extract last throw as checkout
    def get_checkout(row):
        throws = [score for score in row[throw_cols] if pd.notna(score) and score > 0]
        return throws[-1] if len(throws) > 0 else None

    winners_df["Checkout"] = winners_df.apply(get_checkout, axis=1)
    winners_df = winners_df.dropna(subset=["Checkout"])
    winners_df["Checkout"] = pd.to_numeric(winners_df["Checkout"], errors="coerce")

    comp_winners = winners_df[winners_df["Competition"] == selected_comp].copy()

    if comp_winners.empty:
        st.info(f"No winning legs found for {selected_comp}.")
        st.stop()

    # --- Main Table (top 5 checkouts in selected comp) ---
    top5_checkouts = (
        comp_winners[["Player", "Checkout"]]
        .sort_values("Checkout", ascending=False)
        .head(5)
        .reset_index(drop=True)
    )

    st.subheader(f"Top 5 Checkouts — {selected_comp}")
    st.dataframe(top5_checkouts, hide_index=True)

    # --- 170 Checkout Club (all time, not filtered) ---
    st.markdown("---")
    st.markdown("## 🎣 The Big Fish")

    max_170_df = winners_df[winners_df["Checkout"] == 170][["Player", "Venue", "ParsedDate"]].copy()
    max_170_df = max_170_df.sort_values("ParsedDate", ascending=False)
    max_170_df["Date"] = max_170_df["ParsedDate"].dt.strftime("%d-%b-%Y")
    max_170_df = max_170_df[["Player", "Venue", "Date"]]

    if not max_170_df.empty:
        st.dataframe(max_170_df, hide_index=True)
    else:
        st.info("No 170 checkouts recorded this season.")

