import streamlit as st
import pandas as pd
import io
import json
import random
from datetime import datetime

# ----------------------------------------
# Core session_state initialization
# ----------------------------------------

def ensure_session_state():
    if "stats" not in st.session_state:
        st.session_state.stats = []

    if "lineup" not in st.session_state:
        st.session_state.lineup = []

    if "lineup_select" not in st.session_state:
        st.session_state.lineup_select = []

    if "last_selected_player" not in st.session_state:
        st.session_state.last_selected_player = "Reset selection (use new name field)"

    if "last_new_name_input" not in st.session_state:
        st.session_state.last_new_name_input = ""

    if "add_merge_selector" not in st.session_state:
        st.session_state.add_merge_selector = "Reset selection (use new name field)"

    if "add_new_name_input" not in st.session_state:
        st.session_state.add_new_name_input = ""

    if "fasttap_player" not in st.session_state:
        st.session_state.fasttap_player = None

    if "last_play" not in st.session_state:
        st.session_state.last_play = None


# ----------------------------------------
# Player lookup
# ----------------------------------------

def get_player_by_name(name: str):
    for p in st.session_state.stats:
        if p["Player"] == name:
            return p
    return None


# ----------------------------------------
# Ensure all fields exist (includes GF + GA + T + I)
# ----------------------------------------

def ensure_player_fields(player: dict):
    defaults = {
        "Goals_For": 0,
        "Assists": 0,
        "Shots": 0,
        "Saves": 0,
        "Goals_Against": 0,
        "Tackles": 0,
        "Interceptions": 0,
    }
    for k, v in defaults.items():
        if k not in player:
            player[k] = v


# ----------------------------------------
# Add / Merge logic (OVERWRITE MODE)
# ----------------------------------------

def merge_or_add_player(stats_list, entry):
    existing = get_player_by_name(entry["Player"])

    if existing is None:
        ensure_player_fields(entry)
        stats_list.append(entry)
        return "added"

    ensure_player_fields(existing)
    ensure_player_fields(entry)

    existing["Goals_For"] = entry["Goals_For"]
    existing["Assists"] = entry["Assists"]
    existing["Shots"] = entry["Shots"]
    existing["Saves"] = entry["Saves"]
    existing["Goals_Against"] = entry["Goals_Against"]
    existing["Tackles"] = entry["Tackles"]
    existing["Interceptions"] = entry["Interceptions"]

    return "merged"


# ----------------------------------------
# Fast Tap logic (ADDITIVE MODE)
# ----------------------------------------

def record_fast_tap(player_name: str, field: str, delta: int):
    player = get_player_by_name(player_name)
    if player is None:
        player = {
            "Player": player_name,
            "Goals_For": 0,
            "Assists": 0,
            "Shots": 0,
            "Saves": 0,
            "Goals_Against": 0,
            "Tackles": 0,
            "Interceptions": 0,
        }
        st.session_state.stats.append(player)

    ensure_player_fields(player)

    player[field] = max(0, player[field] + delta)

    # GF tap also increments Shots
    if field == "Goals_For" and delta > 0:
        player["Shots"] = max(0, player["Shots"] + delta)

    st.session_state.last_play = {
        "player": player_name,
        "field": field,
        "delta": delta,
    }


# ----------------------------------------
# Undo last Fast Tap (INLINE MESSAGE VERSION)
# ----------------------------------------

def undo_last_play(undo_msg):
    lp = st.session_state.last_play
    if not lp:
        undo_msg.warning("No action to undo.")
        return

    player = get_player_by_name(lp["player"])
    if player is None:
        st.session_state.last_play = None
        return

    ensure_player_fields(player)

    # Undo GF + Sh logic
    if lp["field"] == "Goals_For" and lp["delta"] > 0:
        player["Goals_For"] = max(0, player["Goals_For"] - lp["delta"])
        player["Shots"] = max(0, player["Shots"] - lp["delta"])
    else:
        player[lp["field"]] = max(0, player[lp["field"]] - lp["delta"])

    st.session_state.last_play = None
    undo_msg.info("Last action undone.")


# ----------------------------------------
# Build stats dataframe (GF + GA + T + I)
# ----------------------------------------

def build_stats_dataframe():
    rows = []
    for p in st.session_state.stats:
        ensure_player_fields(p)
        rows.append({
            "Player": p["Player"],
            "GF": p["Goals_For"],
            "A": p["Assists"],
            "Sh": p["Shots"],
            "S": p["Saves"],
            "GA": p["Goals_Against"],
            "T": p["Tackles"],
            "I": p["Interceptions"],
        })
    if not rows:
        return pd.DataFrame(columns=["Player", "GF", "A", "Sh", "S", "GA", "T", "I"])
    return pd.DataFrame(rows)


# ----------------------------------------
# App setup
# ----------------------------------------

st.set_page_config(
    page_title="Unified Soccer Stats & Fast Tap",
    layout="centered",
)

ensure_session_state()

st.title("⚽ Unified Soccer Stats & Fast Tap")

DEFAULT_PLAYERS = ["Theo", "Kekoa"]

tab_lineup, tab_add_merge, tab_game, tab_export, tab_faq = st.tabs(
    [
        "Lineup Setup",
        "Add / Merge Players",
        "Fast Tap Game Mode",
        "Export / Merge Season",
        "FAQ / Formulas",
    ]
)

# ----------------------------------------
# TAB 1 — Lineup Setup
# ----------------------------------------
with tab_lineup:
    st.header("📋 Lineup Setup")

    added_players = [p["Player"] for p in st.session_state.stats]
    all_players = sorted(set(DEFAULT_PLAYERS + added_players))

    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("💾 Save Lineup"):
            st.session_state.lineup = st.session_state.lineup_select
            st.success("Lineup saved successfully.")

    with col2:
        st.multiselect(
            "Select players for the lineup (alphabetical):",
            options=all_players,
            key="lineup_select"
        )

    st.write("Current lineup (alphabetical):")
    st.write(", ".join(sorted(st.session_state.lineup)) or "No players yet.")


# ----------------------------------------
# TAB 2 — Add / Merge Players (OVERWRITE MODE)
# ----------------------------------------
with tab_add_merge:
    st.header("➕ Add or Merge Player Stats")

    lineup_names = st.session_state.lineup
    existing_names = [p["Player"] for p in st.session_state.stats]
    combined_names = sorted(set(lineup_names + existing_names))

    name_options = ["Reset selection (use new name field)"] + combined_names

    last_selected_dropdown = st.session_state.add_merge_selector

    if last_selected_dropdown != "Reset selection (use new name field)":
        st.session_state.add_new_name_input = ""

    new_name_input = st.text_input(
        "New player name (if adding someone new):",
        key="add_new_name_input",
    )

    selected_option = st.selectbox(
        "Choose an existing player or reset:",
        options=name_options,
        key="add_merge_selector",
    )

    reset_needed = False

    if selected_option != st.session_state.last_selected_player:
        reset_needed = True

    if selected_option == "Reset selection (use new name field)":
        if new_name_input.strip() != st.session_state.last_new_name_input.strip():
            reset_needed = True

    if reset_needed:
        reset_keys = ["soc_gf", "soc_a", "soc_sh", "soc_s", "soc_ga", "soc_t", "soc_i"]
        for k in reset_keys:
            if k in st.session_state:
                st.session_state[k] = 0

        st.session_state.last_selected_player = selected_option
        st.session_state.last_new_name_input = new_name_input

    if selected_option == "Reset selection (use new name field)":
        name = st.session_state.add_new_name_input.strip()
    else:
        name = selected_option.strip()

    st.subheader("Player Stats")

    gf = st.number_input("Goals For (GF)", min_value=0, step=1, key="soc_gf")
    a = st.number_input("Assists (A)", min_value=0, step=1, key="soc_a")
    sh = st.number_input("Shots on Target (Sh)", min_value=0, step=1, key="soc_sh")
    s_saves = st.number_input("Saves (S)", min_value=0, step=1, key="soc_s")
    ga = st.number_input("Goals Against (GA)", min_value=0, step=1, key="soc_ga")
    tackles = st.number_input("Tackles (T)", min_value=0, step=1, key="soc_t")
    interceptions = st.number_input("Interceptions (I)", min_value=0, step=1, key="soc_i")

    if st.button("➕ Add / Merge Player Stats"):
        if selected_option == "Reset selection (use new name field)":
            raw_new_name = new_name_input
            if raw_new_name != raw_new_name.strip():
                st.error("Please enter first name only (no trailing spaces).")
                st.stop()

        if not name:
            st.error("Please select a player or enter a new player name.")
        else:
            is_new = get_player_by_name(name) is None

            total_stats = gf + a + sh + s_saves + ga + tackles + interceptions
            if is_new and total_stats == 0:
                st.error("Please enter stats for a new player.")
            else:
                entry = {
                    "Player": name,
                    "Goals_For": gf,
                    "Assists": a,
                    "Shots": sh,
                    "Saves": s_saves,
                    "Goals_Against": ga,
                    "Tackles": tackles,
                    "Interceptions": interceptions,
                }

                result = merge_or_add_player(st.session_state.stats, entry)

                if name not in st.session_state.lineup:
                    st.session_state.lineup.append(name)
                    st.session_state.lineup = sorted(st.session_state.lineup)

                if result == "added":
                    st.success(f"Added stats for {name}.")
                else:
                    st.success(f"Merged stats for {name}.")

    if st.session_state.stats:
        st.subheader("📊 Current Player Stats")
        df = build_stats_dataframe()
        st.table(df)


# ----------------------------------------
# TAB 3 — Fast Tap Game Mode (ADDITIVE MODE)
# ----------------------------------------
with tab_game:
    st.header("⚡ Fast Tap Game Mode")

    if not st.session_state.lineup:
        st.warning("No players in lineup. Add players in the Lineup Setup tab first.")
    else:
        fasttap_player = st.selectbox(
            "Select player to track in Fast Tap:",
            options=st.session_state.lineup,
            key="fasttap_player",
        )

        if fasttap_player:
            st.write(f"Recording stats for: **{fasttap_player}**")

            # Create undo message placeholder (prevents layout shift)
            undo_msg = st.empty()

            # Button grid
            col1, col2, col3 = st.columns(3)
            col4, col5, col6 = st.columns(3)
            col7, col8, col9 = st.columns(3)

            # Row 1
            with col1:
                if st.button("⚽ Goal"):
                    record_fast_tap(fasttap_player, "Goals_For", 1)
                    undo_msg.empty()
            with col2:
                if st.button("🎯 Assist"):
                    record_fast_tap(fasttap_player, "Assists", 1)
                    undo_msg.empty()
            with col3:
                if st.button("🎯 Shot on Target"):
                    record_fast_tap(fasttap_player, "Shots", 1)
                    undo_msg.empty()

            # Row 2
            with col4:
                if st.button("🧤 Save"):
                    record_fast_tap(fasttap_player, "Saves", 1)
                    undo_msg.empty()
            with col5:
                if st.button("❌ Goal Against"):
                    record_fast_tap(fasttap_player, "Goals_Against", 1)
                    undo_msg.empty()
            with col6:
                if st.button("↩️ Undo Last Action"):
                    undo_last_play(undo_msg)

            # Row 3
            with col7:
                if st.button("🛑 Tackle"):
                    record_fast_tap(fasttap_player, "Tackles", 1)
                    undo_msg.empty()
            with col8:
                if st.button("🕵️ Interception"):
                    record_fast_tap(fasttap_player, "Interceptions", 1)
                    undo_msg.empty()

            # Current stats display
            p = get_player_by_name(fasttap_player)
            if p:
                ensure_player_fields(p)
                st.subheader("Current Stats for Selected Player")
                st.write(
                    f"GF: {p['Goals_For']} | A: {p['Assists']} | "
                    f"Sh: {p['Shots']} | S: {p['Saves']} | GA: {p['Goals_Against']} | "
                    f"T: {p['Tackles']} | I: {p['Interceptions']}"
                )


# ----------------------------------------
# TAB 4 — Export Summary File + Season Save/Load
# ----------------------------------------
with tab_export:
    st.header("📤 Export Summary & Season Save/Load")

    df = build_stats_dataframe()

    if not df.empty:
        st.subheader("Preview")
        st.table(df)

        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="💾 Download CSV",
            data=csv_data,
            file_name="soccer_stats_summary.csv",
            mime="text/csv",
        )

        buffer = io.StringIO()
        buffer.write("Soccer Stats Summary\n\n")
        for _, row in df.iterrows():
            buffer.write(
                f"{row['Player']}: "
                f"GF={row['GF']}, A={row['A']}, Sh={row['Sh']}, "
                f"S={row['S']}, GA={row['GA']}, "
                f"T={row['T']}, I={row['I']}\n"
            )
        txt_data = buffer.getvalue().encode("utf-8")

        st.download_button(
            label="📝 Download TXT Summary",
            data=txt_data,
            file_name="soccer_stats_summary.txt",
            mime="text/plain",
        )

        st.subheader("💾 Season Save")

        season_data = {
            "stats": st.session_state.stats,
            "lineup": st.session_state.lineup,
            "lineup_select": st.session_state.lineup_select,
            "last_play": st.session_state.last_play,
        }

        season_json = json.dumps(season_data, indent=4)
        season_filename = (
            f"season_soccer_{random.randint(1, 1_000_000)}_"
            f"{datetime.now().strftime('%m-%d-%y')}.json"
        )

        st.download_button(
            label="💾 Download Season JSON",
            data=season_json,
            file_name=season_filename,
            mime="application/json"
        )

    else:
        st.warning("No stats available to export yet. Play a game or add stats first.")

    st.subheader("📁 Season Load")

    uploaded_season = st.file_uploader("📂 Load Season JSON", type=["json"])

    if uploaded_season is not None:
        try:
            loaded = json.load(uploaded_season)

            if "stats" not in loaded:
                st.error("Invalid season file. Missing required 'stats' field.")
            else:
                stats = loaded.get("stats", [])

                lineup_from_file = loaded.get("lineup", [])
                if not lineup_from_file:
                    lineup_from_file = sorted(
                        {p.get("Player", "") for p in stats if p.get("Player")}
                    )

                st.session_state.stats = stats
                st.session_state.lineup = lineup_from_file
                st.session_state.last_play = loaded.get("last_play", None)

                st.success("Season loaded — stats and lineup restored.")

        except Exception as e:
            st.error(f"Error loading season file: {e}")


# ----------------------------------------
# TAB 5 — FAQ / Formulas
# ----------------------------------------
with tab_faq:
    st.header("❓ FAQ / Formulas")

    st.markdown(
        """
## 📘 What does each stat mean?

- **⚽ Goals For (GF):** Number of goals scored by the player.  
- **🎯 Assists (A):** Number of times the player assisted a goal.  
- **🎯 Shots on Target (Sh):** Shots that were on target (including goals).  
- **🧤 Saves (S):** Saves made by the player (typically goalkeeper).  
- **❌ Goals Against (GA):** Goals conceded while the player is in goal.  
- **🛑 Tackles (T):** A defensive challenge where the player wins the ball.  
- **🕵️ Interceptions (I):** When a player anticipates and cuts off a pass.

---

## ➕ Add / Merge Players — Manual Entry (Overwrite Mode)

This tab is designed for **manual stat entry**.

- 🆕 Entering stats for a **new player** creates a new record.  
- ✏️ Entering stats for an **existing player** **overwrites** their totals with the values you typed.  
- 🔄 Switching players or typing a new name resets the input fields to zero.  
- ✋ **No automatic logic is applied here** — you can enter any values you want.

This mode is ideal for corrections, bulk updates, or entering stats after a match.

---

## ⚡ Fast Tap Game Mode — Live Scoring (Additive Mode)

This mode is built for **real‑time, event‑based scoring**.

Tap buttons to record live events:

- ⚽ Goal (adds **1 GF + 1 Sh**)  
- 🎯 Assist  
- 🎯 Shot on Target  
- 🧤 Save  
- ❌ Goal Against  
- 🛑 Tackle  
- 🕵️ Interception  
- ↩️ Undo reverses the last tap.

Fast Tap **adds** to existing totals because each tap represents a real match event.

---

## 🧠 Why the two modes behave differently

- **Fast Tap** = live scoring with automatic soccer logic  
- **Add / Merge** = manual control for editing or entering stats after the fact  

This separation keeps live scoring fast and accurate while giving you full flexibility for manual updates.

---

## 📤 Exporting & Season Save/Load

The Export tab lets you:

- 📄 Download a **CSV** file  
- 📝 Download a **TXT** summary  
- 💾 Save a full season (stats + lineup)  
- 📂 Load a saved season to restore everything  
"""
    )
