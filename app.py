import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="IDL Stats", layout="wide")
st.title("IDL Stats")

# --- Helper Functions ---
def detect_data_type(df):
    """Determine if the CSV is a Competition or League file."""
    has_division = "Division" in df.columns and df["Division"].notna().any()
    has_date = "Date" in df.columns and df["Date"].notna().any()

    if has_division and not has_date:
        return "League"
    else:
        return "Competition"

# Keeping the function name from the fix to ensure cache stability
@st.cache_data(show_spinner="Loading and processing data...")
def load_data_v4_fix(data_folder):
    """
    Loads all CSVs, combines them, and performs heavy processing
    (Date parsing, Numeric conversion, and STATS CALCULATION) only once.
    """
    all_data = []

    if not os.path.exists(data_folder):
        return pd.DataFrame()

    for file in os.listdir(data_folder):
        if file.endswith(".csv"):
            file_path = os.path.join(data_folder, file)
            try:
                df = pd.read_csv(file_path)
                df["OriginalDate"] = df.get("Date", "")
                df["DataType"] = detect_data_type(df)
                all_data.append(df)
            except Exception as e:
                st.error(f"Error reading {file}: {e}")

    if not all_data:
        return pd.DataFrame()

    full_df = pd.concat(all_data, ignore_index=True)

    # 1. Process Season (League)
    if "Season" in full_df.columns:
        full_df["Season"] = pd.to_numeric(full_df["Season"], errors="coerce").astype("Int64")

    # 2. Parse Dates (Competition)
    full_df["ParsedDate"] = pd.NaT
    if "OriginalDate" in full_df.columns:
        date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %m %Y"]
        for fmt in date_formats:
            mask_unparsed = full_df["ParsedDate"].isna()
            if mask_unparsed.any():
                temp_parsed = pd.to_datetime(
                    full_df.loc[mask_unparsed, "OriginalDate"],
                    format=fmt,
                    errors="coerce"
                )
                full_df.loc[mask_unparsed, "ParsedDate"] = temp_parsed

    full_df["Date_str"] = full_df["ParsedDate"].dt.strftime("%d-%b-%Y")
    full_df.loc[full_df["Date_str"].isna(), "Date_str"] = full_df["OriginalDate"].astype(str)

    # 3. Process Throw Columns & PRE-CALCULATE STATS
    throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]

    # Ensure numeric
    for c in throw_cols:
        full_df[c] = pd.to_numeric(full_df[c], errors="coerce")

    # --- Pre-calculate Stats ---
    # 180s
    full_df["Count180"] = full_df[throw_cols].isin([180]).sum(axis=1)
    # 140+
    full_df["Count140"] = full_df[throw_cols].apply(lambda row: ((row >= 140) & (row < 180)).sum(), axis=1)
    # 100+
    full_df["Count100"] = full_df[throw_cols].apply(lambda row: ((row >= 100) & (row < 140)).sum(), axis=1)

    # Calculate Last Throw (Potential Checkout)
    def get_last_score(row):
        valid = row[pd.notna(row) & (row > 0)]
        if not valid.empty:
            return valid.iloc[-1]
        return 0

    full_df["LegCheckout"] = full_df[throw_cols].apply(get_last_score, axis=1)

    # --- NEW: Total Darts Handling ---
    if "Total Darts" in full_df.columns:
        full_df["Total Darts"] = pd.to_numeric(full_df["Total Darts"], errors="coerce")

    # --- NEW: Total Scored (Sum of all throws) ---
    full_df["TotalScored"] = full_df[throw_cols].sum(axis=1)

    # --- NEW: First 9 Average Logic ---
    # Sum of first 3 throws (visits) / 3 (visits) -> This is average score per visit.
    # To get "3-dart average" for the first 9 darts, it is exactly the average of the first 3 visits.
    f9_cols = ["Throw_1", "Throw_2", "Throw_3"]
    # Filter only columns that exist
    f9_cols = [c for c in f9_cols if c in full_df.columns]
    full_df["First9Sum"] = full_df[f9_cols].sum(axis=1)
    full_df["First9Count"] = full_df[f9_cols].count(axis=1)
    full_df["First9Avg"] = full_df.apply(
        lambda r: r["First9Sum"] / r["First9Count"] if r["First9Count"] > 0 else np.nan,
        axis=1
    )

    # --- NEW: Visit Standard Deviation (Consistency) ---
    full_df["VisitStdDev"] = full_df[throw_cols].std(axis=1)

    return full_df

# --- Load Data ---
data_folder = "data"
full_df = load_data_v4_fix(data_folder)

if full_df.empty:
    st.warning("No CSV files found in the data folder or folder is missing.")
    st.stop()

# Identify throw columns dynamically
throw_cols = [col for col in full_df.columns if col.startswith("Throw_")]

if "Player" not in full_df.columns or not throw_cols:
    st.error("CSV files must have 'Player' column and throw columns like 'Throw_1', 'Throw_2'.")
    st.stop()

# --- SAFETY CHECK: Recalculate if columns missing ---
if "Count180" not in full_df.columns:
    full_df["Count180"] = full_df[throw_cols].isin([180]).sum(axis=1)
    full_df["Count140"] = full_df[throw_cols].apply(lambda row: ((row >= 140) & (row < 180)).sum(), axis=1)
    full_df["Count100"] = full_df[throw_cols].apply(lambda row: ((row >= 100) & (row < 140)).sum(), axis=1)

    def get_last_score(row):
        valid = row[pd.notna(row) & (row > 0)]
        if not valid.empty:
            return valid.iloc[-1]
        return 0
    full_df["LegCheckout"] = full_df[throw_cols].apply(get_last_score, axis=1)

# ==========================================
# SIDEBAR: FILTERS & NAVIGATION
# ==========================================
with st.sidebar:
    st.header("⚙️ Configuration")
    data_mode = st.radio("Select Competition Type", ["🏆 Grand Prix", "🏅 League"])

    st.markdown("---")

    # --- Filter Dataset Logic ---
    if data_mode == "🏆 Grand Prix":
        active_df = full_df[full_df["DataType"] == "Competition"].copy()
        active_df["Venue"] = active_df["Venue"].astype(str)
        active_df["Competition"] = active_df["Venue"] + " - " + active_df["Date_str"]

        options_df = (
            active_df[["Competition", "ParsedDate"]]
            .drop_duplicates()
            .sort_values("ParsedDate", ascending=False, na_position="last")
            .reset_index(drop=True)
        )

        if options_df.empty:
            st.warning("No Grand Prix data found.")
            st.stop()

        # Create list and add "All Competitions" option
        comp_list = options_df["Competition"].tolist()
        comp_list.insert(0, "All Competitions")

        selected_label = st.selectbox("Select a competition", comp_list)

        # --- NEW: Logic for All Competitions ---
        if selected_label == "All Competitions":
            filtered_df = active_df.copy()
        else:
            filtered_df = active_df[active_df["Competition"] == selected_label].copy()

    else:
        # --- LEAGUE DATA PROCESSING ---
        active_df = full_df[full_df["DataType"] == "League"].copy()

        active_df["Venue"] = active_df.get("Venue", pd.Series(dtype='str')).astype(str)
        active_df["Season"] = active_df["Season"].astype(str)
        active_df["Division"] = active_df["Division"].astype(str)

        # 1. Select Venue
        unique_venues = sorted(active_df["Venue"].unique())
        if not unique_venues:
            st.warning("No League venues found.")
            st.stop()
        selected_venue = st.selectbox("📍 Select League/Venue", unique_venues)
        venue_df = active_df[active_df["Venue"] == selected_venue]

        # 2. Select Season
        unique_seasons = venue_df["Season"].unique()
        try:
            unique_seasons = sorted(unique_seasons, key=lambda x: int(x), reverse=True)
        except ValueError:
            unique_seasons = sorted(unique_seasons, reverse=True)
        selected_season = st.selectbox("📅 Select Season", unique_seasons)
        season_df = venue_df[venue_df["Season"] == selected_season]

        # 3. Select Division (With "All Divisions")
        unique_divisions = sorted(season_df["Division"].unique())
        unique_divisions.insert(0, "All Divisions")

        selected_division = st.selectbox("🏆 Select Division", unique_divisions)

        if selected_division == "All Divisions":
            filtered_df = season_df.copy()
        else:
            filtered_df = season_df[season_df["Division"] == selected_division].copy()

        selected_label = f"{selected_venue} - S{selected_season} - {selected_division}"

# ==========================================
# MAIN PAGE: TABS
# ==========================================

# Create the tabs
tab1, tab2, tab3, tab4 = st.tabs(["🎯 180s", "🎣 Checkouts", "👇 Lowest Legs", "🧪 Experimental Stats"])

# ------------------------------------------
# TAB 1: 180s
# ------------------------------------------
with tab1:
    player_stats = filtered_df.groupby("Player")[["Count180", "Count140", "Count100"]].sum().reset_index()

    player_stats.rename(columns={
        "Count180": "180s",
        "Count140": "140+",
        "Count100": "100+"
    }, inplace=True)

    total_180s = int(player_stats["180s"].sum()) if not player_stats.empty else 0

    player_stats = player_stats.sort_values(by=["180s", "140+", "100+"], ascending=[False, False, False])

    st.subheader(f"Total 180s - {total_180s}")
    st.dataframe(player_stats, hide_index=True)

    # --- Bottom Chart Section ---
    overall_df = active_df.copy()
    st.markdown("---")

    if data_mode == "🏅 League":
        comp_group = overall_df.groupby(["Player", "Venue", "Division", "Season"])["Count180"].sum().reset_index()
        comp_group.rename(columns={"Count180": "180s"}, inplace=True)
        comp_group = comp_group.sort_values("180s", ascending=False).head(5).reset_index(drop=True)

        st.subheader("**Most 180s in a League Season**")

        if not comp_group.empty:
            chart_data = comp_group.copy()
            chart_data['Unique_ID'] = chart_data['Player'] + '_' + chart_data['Season'].astype(str)
            chart_data = chart_data.iloc[::-1].reset_index(drop=True)

            fig = go.Figure(go.Bar(
                x=chart_data["180s"],
                y=chart_data["Unique_ID"],
                orientation='h',
                text=chart_data["180s"],
                textposition='outside',
                hovertemplate='<b>%{customdata[0]}</b><br>' +
                              '180s: %{x}<br>' +
                              'Venue: %{customdata[1]}<br>' +
                              'Division: %{customdata[2]}<br>' +
                              'Season: %{customdata[3]}<extra></extra>',
                customdata=chart_data[["Player", "Venue", "Division", "Season"]].values,
                marker=dict(color='#1f77b4')
            ))
            fig.update_yaxes(ticktext=chart_data["Player"], tickvals=chart_data["Unique_ID"])
            fig.update_layout(
                xaxis_title="", xaxis=dict(showticklabels=False, showgrid=False),
                yaxis_title="", height=300, margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No 180s recorded in League data.")

    else:
        # Grand Prix Logic
        comp_group = overall_df.groupby(["Player", "Venue", "Date_str"])["Count180"].sum().reset_index()
        comp_group.rename(columns={"Count180": "180s"}, inplace=True)
        comp_group = comp_group.sort_values(["180s"], ascending=False).head(5).reset_index(drop=True)
        comp_group.rename(columns={"Date_str": "Date"}, inplace=True)

        st.subheader("**Most 180s in a Grand Prix**")

        if not comp_group.empty:
            chart_data = comp_group.copy()
            chart_data['Unique_ID'] = chart_data['Player'] + '_' + chart_data['Date']
            chart_data = chart_data.iloc[::-1].reset_index(drop=True)

            fig = go.Figure(go.Bar(
                x=chart_data["180s"],
                y=chart_data["Unique_ID"],
                orientation='h',
                text=chart_data["180s"],
                textposition='outside',
                hovertemplate='<b>%{customdata[0]}</b><br>' +
                              '180s: %{x}<br>' +
                              'Venue: %{customdata[1]}<br>' +
                              'Date: %{customdata[2]}<extra></extra>',
                customdata=chart_data[["Player", "Venue", "Date"]].values,
                marker=dict(color='#1f77b4')
            ))
            fig.update_yaxes(ticktext=chart_data["Player"], tickvals=chart_data["Unique_ID"])
            fig.update_layout(
                xaxis_title="", xaxis=dict(showticklabels=False, showgrid=False),
                yaxis_title="", height=300, margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
             st.info("No 180s recorded in Grand Prix data.")

# ------------------------------------------
# TAB 2: Checkouts
# ------------------------------------------
with tab2:
    winners_df = filtered_df[filtered_df["Result"].str.upper() == "WON"].copy()

    if winners_df.empty:
        st.info("No winning legs found — cannot calculate checkouts.")
    else:
        winners_df = winners_df[winners_df["LegCheckout"] > 0]

        cols_to_keep = ["Player", "LegCheckout"]
        if "URL" in winners_df.columns: cols_to_keep.append("URL")

        top5_checkouts = winners_df[cols_to_keep]
        top5_checkouts.rename(columns={"LegCheckout": "Checkout"}, inplace=True)

        top5_checkouts = top5_checkouts.sort_values("Checkout", ascending=False).head(5).reset_index(drop=True)

        st.subheader(f"Highest Checkouts")

        column_config = {}
        if "URL" in top5_checkouts.columns:
            column_config["URL"] = st.column_config.LinkColumn("Match Link", display_text="View Match")

        st.dataframe(top5_checkouts, column_config=column_config, hide_index=True)

    # --- 170 Club ---
    st.markdown("---")
    st.markdown("## 🎣 The Big Fish")

    winners_all = active_df[active_df["Result"].str.upper() == "WON"].copy()
    winners_all = winners_all[winners_all["LegCheckout"] == 170]

    if data_mode == "🏅 League":
        cols_170 = ["Player", "Division", "Season"]
        if "URL" in winners_all.columns: cols_170.append("URL")
        max_170_df = winners_all[cols_170].drop_duplicates()
        max_170_df = max_170_df.sort_values(by="Season", ascending=False).reset_index(drop=True)
    else:
        cols_gp = ["Player", "Venue", "Date_str", "ParsedDate"]
        if "URL" in winners_all.columns: cols_gp.append("URL")
        max_170_df = winners_all[cols_gp].drop_duplicates()
        max_170_df = max_170_df.sort_values("ParsedDate", ascending=False, na_position="last").reset_index(drop=True)

        cols_display = ["Player", "Venue", "Date_str"]
        if "URL" in max_170_df.columns: cols_display.append("URL")
        max_170_df = max_170_df[cols_display]
        max_170_df.rename(columns={"Date_str":"Date"}, inplace=True)

    if not max_170_df.empty:
        cfg_170 = {}
        if "URL" in max_170_df.columns:
            cfg_170["URL"] = st.column_config.LinkColumn("Match Link", display_text="View Match")
        st.dataframe(max_170_df, column_config=cfg_170, hide_index=True)
    else:
        st.info("No 170 checkouts recorded.")

# ------------------------------------------
# TAB 3: Lowest Legs
# ------------------------------------------
with tab3:
    winners_df = filtered_df[filtered_df["Result"].str.upper() == "WON"].copy()
    winners_overall = active_df[active_df["Result"].str.upper() == "WON"].copy()

    # Selected Competition
    if winners_df.empty:
        st.info("No winning legs found for this selection.")
    else:
        winners_df["Total Darts"] = pd.to_numeric(winners_df["Total Darts"], errors="coerce")

        lowest_per_player = winners_df.sort_values(["Total Darts", "LegCheckout"], ascending=[True, False])
        lowest_per_player = lowest_per_player.groupby("Player", as_index=False).first()
        lowest_per_player = lowest_per_player.sort_values(["Total Darts", "LegCheckout"], ascending=[True, False])

        cols_to_keep = ["Player", "Total Darts"]
        if "URL" in lowest_per_player.columns: cols_to_keep.append("URL")

        top5_lowest = lowest_per_player[cols_to_keep].head(5).reset_index(drop=True)
        top5_lowest.rename(columns={"Total Darts":"Darts Thrown"}, inplace=True)

        st.subheader(f"Lowest Legs — {selected_label}")

        column_config = {}
        if "URL" in top5_lowest.columns:
            column_config["URL"] = st.column_config.LinkColumn("Match Link", display_text="View Match")

        st.dataframe(top5_lowest, column_config=column_config, hide_index=True)

    # Overall Lowest Legs
    st.markdown("---")
    if winners_overall.empty:
        st.info("No winning legs found overall.")
    else:
        winners_overall["Total Darts"] = pd.to_numeric(winners_overall["Total Darts"], errors="coerce")
        all_lowest = winners_overall.sort_values(["Total Darts", "LegCheckout"], ascending=[True,False])

        if data_mode == "🏅 League":
            cols = ["Player", "Total Darts", "Venue", "Division", "Season"]
            ll_table_title = "**Lowest Leg in a League Season**"
        else:
            cols = ["Player", "Total Darts", "Venue", "Date_str"]
            ll_table_title = "**Lowest Leg in a Grand Prix**"

        if "URL" in all_lowest.columns: cols.append("URL")

        top5_overall = all_lowest[cols].head(5).reset_index(drop=True)
        top5_overall.rename(columns={"Total Darts":"Darts Thrown", "Date_str":"Date"}, inplace=True)

        st.subheader(ll_table_title)

        column_config = {}
        if "URL" in top5_overall.columns:
            column_config["URL"] = st.column_config.LinkColumn("Match Link", display_text="View Match")

        st.dataframe(top5_overall, column_config=column_config, hide_index=True)

# ------------------------------------------
# TAB 4: EXPERIMENTAL STATS
# ------------------------------------------
with tab4:
    st.header(f"Experimental Statistics: {selected_label}")

    # --- 1. 3-Dart Average & First 9 Average ---
    st.subheader("📊 Player Averages")

    # Calculate Overall 3-Dart Average per player
    # Average = Sum of All Throws / Sum of All Darts Thrown * 3
    # Need to group by player and sum totals

    avg_stats = filtered_df.groupby("Player").apply(
        lambda x: pd.Series({
            "TotalScore": x["TotalScored"].sum(),
            "TotalDarts": x["Total Darts"].sum(),
            "AvgFirst9": x["First9Avg"].mean(), # Average of the averages
            "Matches": len(x),
            "Wins": (x["Result"].str.upper() == "WON").sum()
        })
    ).reset_index()

    # Avoid division by zero
    avg_stats["3DartAvg"] = avg_stats.apply(
        lambda r: (r["TotalScore"] / r["TotalDarts"]) * 3 if r["TotalDarts"] > 0 else 0, axis=1
    )

    avg_stats["WinRate"] = (avg_stats["Wins"] / avg_stats["Matches"]) * 100

    display_stats = avg_stats[["Player", "3DartAvg", "AvgFirst9", "WinRate", "Matches"]].copy()
    display_stats = display_stats.sort_values("3DartAvg", ascending=False).reset_index(drop=True)

    st.dataframe(
        display_stats,
        column_config={
            "3DartAvg": st.column_config.NumberColumn("3-Dart Avg", format="%.2f"),
            "AvgFirst9": st.column_config.NumberColumn("First 9 Avg", format="%.2f"),
            "WinRate": st.column_config.ProgressColumn("Win Rate (%)", format="%.1f%%", min_value=0, max_value=100),
        },
        hide_index=True
    )

    st.markdown("---")

    # --- 2. Consistency (Standard Deviation) ---
    st.subheader("🎯 Consistency (Standard Deviation of Visit Scores)")
    st.caption("Lower value means more consistent scoring. Higher value means more fluctuation.")

    consistency_df = filtered_df.groupby("Player")["VisitStdDev"].mean().reset_index()
    consistency_df.rename(columns={"VisitStdDev": "ConsistencyScore"}, inplace=True)
    consistency_df = consistency_df.sort_values("ConsistencyScore", ascending=True).head(10) # Top 10 most consistent

    fig_cons = px.bar(
        consistency_df,
        x="ConsistencyScore",
        y="Player",
        orientation='h',
        title="Top 10 Most Consistent Players (Lowest Std Dev)",
        text_auto='.2f'
    )
    fig_cons.update_layout(yaxis={'categoryorder':'total descending'})
    st.plotly_chart(fig_cons, use_container_width=True)

    st.markdown("---")

    # --- 3. Win Rate Over Time ---
    st.subheader("📈 Performance Over Time")

    # Select a player to view details
    player_list = sorted(filtered_df["Player"].unique())
    selected_player = st.selectbox("Select Player for Trend Analysis", player_list)

    player_history = active_df[active_df["Player"] == selected_player].copy()

    # Determine time axis
    if data_mode == "🏆 Grand Prix":
        # Group by Date
        time_col = "ParsedDate"
        time_label = "Date"
        player_history = player_history.sort_values("ParsedDate")
    else:
        # Group by Season
        time_col = "Season"
        time_label = "Season"
        player_history = player_history.sort_values("Season")

    # Group by time unit and calculate win rate
    trend_df = player_history.groupby(time_col).apply(
        lambda x: pd.Series({
            "WinRate": (x["Result"].str.upper() == "WON").mean() * 100,
            "3DartAvg": (x["TotalScored"].sum() / x["Total Darts"].sum()) * 3 if x["Total Darts"].sum() > 0 else 0
        })
    ).reset_index()

    if not trend_df.empty:
        # Create dual-axis chart
        fig_trend = go.Figure()

        # Win Rate Line
        fig_trend.add_trace(go.Scatter(
            x=trend_df[time_col], y=trend_df["WinRate"],
            name="Win Rate (%)", mode='lines+markers', line=dict(color='green')
        ))

        # Average Line
        fig_trend.add_trace(go.Scatter(
            x=trend_df[time_col], y=trend_df["3DartAvg"],
            name="3-Dart Avg", mode='lines+markers', line=dict(color='blue'), yaxis="y2"
        ))

        fig_trend.update_layout(
            title=f"Win Rate & Average Over Time: {selected_player}",
            xaxis_title=time_label,
            yaxis=dict(title="Win Rate (%)", range=[0, 105]),
            yaxis2=dict(title="3-Dart Avg", overlaying="y", side="right"),
            legend=dict(x=0.01, y=0.99)
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Not enough history for trend analysis.")

    st.markdown("---")

    # --- 4. Head-to-Head Matrix ---
    st.subheader("⚔️ Head-to-Head Record")

    # Filter for selected player matches
    h2h_df = active_df[active_df["Player"] == selected_player].copy()

    if not h2h_df.empty and "Opponent" in h2h_df.columns:
        # Calculate wins vs each opponent
        opponent_stats = h2h_df.groupby("Opponent").apply(
            lambda x: pd.Series({
                "Games": len(x),
                "Wins": (x["Result"].str.upper() == "WON").sum(),
                "Losses": (x["Result"].str.upper() == "LOST").sum()
            })
        ).reset_index()

        opponent_stats["WinRate"] = (opponent_stats["Wins"] / opponent_stats["Games"]) * 100
        opponent_stats = opponent_stats.sort_values("Games", ascending=False).head(20) # Top 20 rivals

        fig_h2h = px.bar(
            opponent_stats,
            x="Opponent",
            y=["Wins", "Losses"],
            title=f"Head-to-Head: {selected_player} vs Top Rivals",
            barmode='stack',
            color_discrete_map={"Wins": "green", "Losses": "red"}
        )
        st.plotly_chart(fig_h2h, use_container_width=True)
    else:
        st.info("No opponent data available.")
