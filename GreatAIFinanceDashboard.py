import streamlit as st
import pandas as pd
import datetime

# ---------- Stub Functions ----------
def save_to_dynamodb(transaction):
    st.success(f"Saved transaction: {transaction}")

def call_bedrock_summary(data):
    return "AI Summary: In March, revenue was $18,400. Payroll was the largest expense ($8,200, 45% of costs). Net profit: $6,500."

def generate_pdf_report(month, year):
    return f"https://s3.amazonaws.com/your-bucket/{month}-{year}-report.pdf"

def fetch_transactions(month, year):
    sample = [
        {"Date": "2025-03-01", "Description": "Consulting Revenue", "Amount": 9200, "Type": "Income", "Category": "Revenue"},
        {"Date": "2025-03-05", "Description": "Payroll", "Amount": 8200, "Type": "Expense", "Category": "Payroll"},
        {"Date": "2025-03-10", "Description": "Electricity Bill", "Amount": 326, "Type": "Expense", "Category": "Utilities"},
    ]
    return pd.DataFrame(sample)

# ---------- Streamlit UI ----------
st.set_page_config(page_title="AI Finance Dashboard", layout="wide")
st.title("🏦 AI-Powered Finance Dashboard")

tabs = st.tabs(["Overview", "Add Transaction", "Generate / View Reports"])

# --- TAB 1: Overview (Dashboard Summary) ---
with tabs[0]:
    st.header("🏠 Dashboard Overview")

    month, year = "March", 2025
    df = fetch_transactions(month, year)

    st.subheader(f"📑 Report Summary for {month} {year}")
    st.dataframe(df)

    st.subheader("📊 Charts")
    st.bar_chart(df.groupby("Type")["Amount"].sum())
    st.line_chart(df.groupby("Date")["Amount"].sum())

    st.subheader("🤖 AI Insights")
    summary = call_bedrock_summary(df)
    st.info(summary)

# --- TAB 2: Add Transaction ---
with tabs[1]:
    st.header("➕ Add New Transaction")

    with st.form("add_transaction_form"):
        date = st.date_input("Date", datetime.date.today())
        description = st.text_input("Description")
        amount = st.number_input("Amount", min_value=0.0, step=0.01)
        txn_type = st.selectbox("Type", ["Income", "Expense"])
        category = st.text_input("Category (leave blank for AI auto-tag)")
        receipt = st.file_uploader("Upload Receipt", type=["jpg", "png", "pdf"])

        submitted = st.form_submit_button("Save Transaction")
        if submitted:
            transaction = {
                "Date": str(date),
                "Description": description,
                "Amount": amount,
                "Type": txn_type,
                "Category": category if category else "AI-Auto",
                "Receipt": receipt.name if receipt else None
            }
            save_to_dynamodb(transaction)

# --- TAB 3: View / Generate Reports ---
with tabs[2]:
    st.header("📂 Generate / View Reports")

    year = st.selectbox("Select Year", [2025, 2024, 2023])
    month = st.selectbox("Select Month", ["March", "February", "January"])

    if st.button("🔍 Show Report"):
        df = fetch_transactions(month, year)
        st.dataframe(df)

        st.subheader("📊 Charts")
        st.bar_chart(df.groupby("Type")["Amount"].sum())
        st.line_chart(df.groupby("Date")["Amount"].sum())

        summary = call_bedrock_summary(df)
        st.info(summary)

    if st.button("📄 Generate Report Now (PDF)"):
        pdf_url = generate_pdf_report(month, year)
        st.success(f"Report generated! [Download PDF]({pdf_url})")
