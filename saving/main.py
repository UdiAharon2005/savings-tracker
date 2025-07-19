from datetime import datetime, timedelta
import hashlib
import os
import sqlite3
import matplotlib.pyplot as plt
import streamlit as st

DB_FILE = "savings_data.db"

# --- DB Functions ---

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS savings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            name TEXT NOT NULL,
            initial_amount REAL,
            monthly_contribution REAL,
            years REAL,
            annual_return_percent REAL,
            final_amount REAL,
            date_saved TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            is_total INTEGER DEFAULT 0,
            current_total REAL
        )
    """)
    c.execute("PRAGMA table_info(deposits)")
    columns = [col[1] for col in c.fetchall()]
    if "is_total" not in columns:
        c.execute("ALTER TABLE deposits ADD COLUMN is_total INTEGER DEFAULT 0")
    if "current_total" not in columns:
        c.execute("ALTER TABLE deposits ADD COLUMN current_total REAL")
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def add_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
    return True

def authenticate_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == hash_password(password)

def save_deposit(user, date, amount, is_total, current_total):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO deposits (user, date, amount, is_total, current_total) VALUES (?, ?, ?, ?, ?)",
              (user, date, amount, int(is_total), current_total))
    conn.commit()
    conn.close()

def get_user_deposits(user):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, date, amount, is_total, current_total FROM deposits WHERE user = ? ORDER BY date", (user,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_deposit(deposit_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM deposits WHERE id=?", (deposit_id,))
    conn.commit()
    conn.close()

def delete_all_deposits(user):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM deposits WHERE user=?", (user,))
    conn.commit()
    conn.close()

# --- Initialize DB ---
init_db()

# --- UI ---
st.set_page_config(page_title="Savings Tracker", layout="centered")
st.title("\U0001F4B0 Savings Tracker")

# --- Session State ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "forecast_triggered" not in st.session_state:
    st.session_state.forecast_triggered = False
if "forecast_data" not in st.session_state:
    st.session_state.forecast_data = {}
if "just_added" not in st.session_state:
    st.session_state.just_added = False
if "just_deleted" not in st.session_state:
    st.session_state.just_deleted = False

if not st.session_state.logged_in:
    st.subheader("Login / Register")

    tab1, tab2 = st.tabs(["🔐 Login", "🆕 Register"])

    with tab1:
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if authenticate_user(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.success("Successfully logged in!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        new_user = st.text_input("Choose a username", key="new_user")
        new_pass = st.text_input("Choose a password", type="password", key="new_pass")
        if st.button("Register"):
            if add_user(new_user, new_pass):
                st.success("Registration successful! You can now log in.")
            else:
                st.error("Username already exists")

else:
    st.success(f"Welcome, {st.session_state.username} 👋")
    if st.button("🔓 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    user = st.session_state.username
    st.markdown("---")

    tab_main, tab_forecast = st.tabs(["📈 My Deposit History", "🔮 Forecast"])

    def compute_growth_monthly(initial, months, monthly_rate):
        return initial * ((1 + monthly_rate) ** months)

    def compute_growth(initial, monthly, years, annual_rate):
        amounts = []
        value = initial
        monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
        for i in range(years * 12):
            value = value * (1 + monthly_rate) + monthly
            amounts.append(value)
        return amounts

    with tab_main:
        st.subheader("Deposit Log")
        deposits = get_user_deposits(user)

        if st.session_state.just_added:
            st.success("Deposit added!")
            st.session_state.just_added = False
        if st.session_state.just_deleted:
            st.success("Deposit deleted!")
            st.session_state.just_deleted = False

        if deposits:
            for did, date, amount, is_total, current_total in deposits:
                label = f"{date} — ₪{amount:,.2f} ({'Total' if is_total else 'Added'})"
                if current_total:
                    label += f" — Now: ₪{current_total:,.2f}"
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.write(f"📅 {label}")
                with col2:
                    if st.button("Delete", key=f"del_{did}"):
                        delete_deposit(did)
                        st.session_state.just_deleted = True
                        st.rerun()
            if st.button("❌ Delete All Records"):
                delete_all_deposits(user)
                st.success("All deposit records deleted")
                st.rerun()
        else:
            st.info("No deposits found. Add your savings history below.")

        st.markdown("---")
        st.subheader("Add Deposit Record")
        new_date = st.date_input("Date")
        added_amount = st.number_input("Amount Added (₪)", min_value=0.0, step=100.0)
        current_total = st.number_input("Total Amount Now (Optional)", min_value=0.0, step=100.0)

        if st.button("Add Deposit"):
            is_total = current_total > 0
            save_deposit(user, new_date.isoformat(), added_amount, is_total, current_total if is_total else None)
            st.session_state.just_added = True
            st.rerun()

        if deposits:
            st.markdown("---")
            st.subheader("Deposit History Chart with Market Growth")
            deposits_sorted = sorted([(datetime.fromisoformat(d[1]), d[2], d[3], d[4]) for d in deposits])

            growth_rate = 0.06  # annual growth rate
            monthly_rate = (1 + growth_rate) ** (1 / 12) - 1

            graph_dates = []
            graph_values = []

            current_value = 0
            last_date = None

            for date, amount, is_total, current_total in deposits_sorted:
                if last_date:
                    months_between = (date.year - last_date.year) * 12 + (date.month - last_date.month)
                    for i in range(months_between):
                        current_value = compute_growth_monthly(current_value, 1, monthly_rate)
                        step_date = last_date + timedelta(days=30 * (i + 1))
                        graph_dates.append(step_date)
                        graph_values.append(current_value)
                if current_total:
                    current_value = current_total
                else:
                    current_value += amount
                graph_dates.append(date)
                graph_values.append(current_value)
                last_date = date

            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(graph_dates, graph_values, marker='o', color='black')
            ax.set_title("Savings History with Market Growth")
            ax.set_xlabel("Date")
            ax.set_ylabel("₪")
            ax.grid(True)
            if graph_dates:
                ax.annotate(f"₪{graph_values[-1]:,.2f}", (graph_dates[-1], graph_values[-1]),
                            textcoords="offset points", xytext=(0,10), ha='center', fontsize=9, color='black')
            st.pyplot(fig)

    with tab_forecast:
    st.subheader("Savings Forecast")
    deposits = get_user_deposits(user)

    if deposits:
        deposits_sorted = sorted([(datetime.fromisoformat(d[1]), d[2], d[3], d[4]) for d in deposits])
        hist_dates = [d[0] for d in deposits_sorted]

        cumulative = []
        total = 0
        for _, amt, is_total, current_total in deposits_sorted:
            if current_total:
                total = current_total
            elif is_total:
                total = amt
            else:
                total += amt
            cumulative.append(total)

        hist_cumulative = cumulative
        last_date = hist_dates[-1]
        last_amount = hist_cumulative[-1]

        st.markdown("---")
        st.subheader("Forecast Parameters")
        monthly = st.number_input("Monthly Contribution", min_value=0.0, value=500.0, step=100.0)
        years = st.number_input("Years", min_value=1, value=10)

        if st.button("Run Forecast"):
            months_forecast = 12 * years
            forecast_dates = [last_date + timedelta(days=30 * i) for i in range(1, months_forecast + 1)]

            no_growth_rate = 0.00
            mid_growth_rate = 0.04
            high_growth_rate = 0.08

            forecast_no_growth = compute_growth(last_amount, monthly, years, no_growth_rate)
            forecast_mid = compute_growth(last_amount, monthly, years, mid_growth_rate)
            forecast_high = compute_growth(last_amount, monthly, years, high_growth_rate)

            st.session_state.forecast_triggered = True
            st.session_state.forecast_data = {
                "hist_dates": hist_dates,
                "hist_cumulative": hist_cumulative,
                "forecast_dates": forecast_dates,
                "no_growth": forecast_no_growth,
                "mid": forecast_mid,
                "high": forecast_high
            }

        if st.session_state.forecast_triggered:
            data = st.session_state.forecast_data
            fig3, ax3 = plt.subplots(figsize=(10, 4))
            ax3.plot(data["hist_dates"], data["hist_cumulative"], color="black", label="History")
            ax3.plot(data["forecast_dates"], data["no_growth"], color="red", linestyle="--", label="0% Growth")
            ax3.plot(data["forecast_dates"], data["mid"], color="orange", linestyle="--", label="4% Growth")
            ax3.plot(data["forecast_dates"], data["high"], color="green", linestyle="--", label="8% Growth")

            ax3.set_title("Historical and Forecast Savings")
            ax3.set_xlabel("Date")
            ax3.set_ylabel("₪")
            ax3.legend()
            ax3.grid(True)
            st.pyplot(fig3)

            st.markdown("**Forecasted Savings after {} years:**".format(int(years)))
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"<span style='color:red'>0% Growth: ₪{data['no_growth'][-1]:,.2f}</span>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<span style='color:orange'>4% Growth: ₪{data['mid'][-1]:,.2f}</span>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<span style='color:green'>8% Growth: ₪{data['high'][-1]:,.2f}</span>", unsafe_allow_html=True)
    else:
        st.info("Add deposit history to run forecast.")
