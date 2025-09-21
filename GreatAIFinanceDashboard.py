import streamlit as st
import pandas as pd
import boto3
import json
import datetime
import requests  

# ----------------- API Gateway (for hackathon) -----------------
BASE_URL = "https://iabu6nhilc.execute-api.ap-southeast-5.amazonaws.com/Hackathon"

def invoke_lambda_http(func_name, payload):
    """Call Lambda via API Gateway (hackathon-friendly, no AWS creds needed)"""
    routes = {
        "ListTransactionsLambda": ("GET", "/transactions"),
        "AddTransactionLambda": ("POST", "/transactions"),
        "UpdateTransactionLambda": ("PUT", "/transactions"),
        "DeleteTransactionLambda": ("DELETE", "/transactions"),
        "CsvImportLambda": ("POST", "/csvimport"),
        "GenerateReportLambda": ("POST", "/report"),
    }

    method, route = routes.get(func_name, ("POST", "/unknown"))
    url = f"{BASE_URL}{route}"

    if method == "GET":
        r = requests.get(url, params=payload)
    elif method == "PUT":
        r = requests.put(url, json=payload)
    elif method == "DELETE":
        r = requests.delete(url, json=payload)
    else:  # POST
        r = requests.post(url, json=payload)

    try:
        return r.json()
    except Exception:
        return {"error": r.text}

# ----------------- AWS Lambda Client (keep original) -----------------
lambda_client = boto3.client("lambda", region_name="ap-southeast-5")

def invoke_lambda_boto3(func_name, payload):
    """Helper to call AWS Lambda (boto3 way, requires IAM creds)"""
    response = lambda_client.invoke(
        FunctionName=func_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    return json.loads(response["Payload"].read())

# ----------------- Switch to API Gateway for Hackathon -----------------
invoke_lambda = invoke_lambda_http  # overwrite here

# ----------------- Streamlit UI -----------------
st.set_page_config(page_title="AI Finance Dashboard", page_icon="📊", layout="wide")
st.title("🏦 AI-Powered Finance Dashboard")

tabs = st.tabs(["Overview", "Transactions", "Generate / View Reports"])

# --- TAB 1: Overview (latest month/year auto) ---
with tabs[0]:
    st.markdown("## 🏠 Dashboard Overview")

    try:
        txns = invoke_lambda("ListTransactionsLambda", {})
        df = pd.DataFrame(txns)
    except Exception as e:
        st.error(f"Error fetching transactions: {e}")
        df = pd.DataFrame()

    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        latest_date = df["Date"].max()
        month = latest_date.strftime("%B")
        year = latest_date.strftime("%Y")

        st.markdown(f"### 📑 Report Summary for {month} {year}")
        st.dataframe(df)

        st.subheader("📊 Charts")
        st.bar_chart(df.groupby("Type")["Amount"].sum())
        st.bar_chart(df.groupby("Category")["Amount"].sum())

        st.subheader("🤖 Insights")
        st.info(f"Revenue: {df[df['Type']=='Income']['Amount'].sum()} | "
                f"Expenses: {df[df['Type']=='Expense']['Amount'].sum()}")
    else:
        st.warning("No transactions available.")

# --- TAB 2: Transactions ---
with tabs[1]:
    st.markdown("## 💳 Manage Transactions")
    txn_tabs = st.tabs(["📋 View All", "➕ Add", "✏️ Update", "❌ Delete", "📤 Import CSV"])

    # View All
    with txn_tabs[0]:
        st.subheader("📋 Current Transactions")
        try:
            txns = invoke_lambda("ListTransactionsLambda", {})
            df = pd.DataFrame(txns)
            st.dataframe(df)
        except:
            st.warning("No transactions available.")

    # Add
    with txn_tabs[1]:
        st.subheader("➕ Add New Transaction")
        with st.form("add_txn"):
            date = st.date_input("Date", datetime.date.today())
            desc = st.text_input("Description")
            amt = st.number_input("Amount", min_value=0.0, step=0.01)
            ttype = st.selectbox("Type", ["Income", "Expense"])
            cat = st.text_input("Category (leave blank for AI auto-tag)")
            receipt = st.file_uploader("Upload Receipt", type=["jpg", "jpeg", "png", "pdf"])

            if st.form_submit_button("Save Transaction"):
                payload = {
                    "date": str(date),
                    "description": desc,
                    "amount": amt,
                    "type": ttype,
                    "category": cat,
                }
                if receipt:
                    payload["receipt_name"] = receipt.name
                    payload["receipt_bytes"] = receipt.getvalue().decode("latin1")
                res = invoke_lambda("AddTransactionLambda", payload)
                st.success(res.get("message", "Transaction added."))

    # Update
    with txn_tabs[2]:
        st.subheader("✏️ Update Transaction")
        txn_id = st.text_input("Enter Transaction ID")
        if txn_id:
            txns = invoke_lambda("ListTransactionsLambda", {})
            df = pd.DataFrame(txns)

            if not df.empty and txn_id in df["TransactionID"].values:
                txn = df[df["TransactionID"] == txn_id].iloc[0]
                with st.form("update_txn"):
                    date = st.date_input("Date", pd.to_datetime(txn["Date"]))
                    desc = st.text_input("Description", txn["Description"])
                    amt = st.number_input("Amount", value=float(txn["Amount"]), step=0.01)
                    ttype = st.selectbox("Type", ["Income", "Expense"], index=0 if txn["Type"]=="Income" else 1)
                    cat = st.text_input("Category", txn["Category"])

                    submitted = st.form_submit_button("Update Transaction")
                    if submitted:
                        updates = {}
                        if str(date) != txn["Date"]: updates["Date"] = str(date)
                        if desc != txn["Description"]: updates["Description"] = desc
                        if float(amt) != float(txn["Amount"]): updates["Amount"] = amt
                        if ttype != txn["Type"]: updates["Type"] = ttype
                        if cat != txn["Category"]: updates["Category"] = cat

                        if updates:
                            res = invoke_lambda("UpdateTransactionLambda", {
                                "transaction_id": txn_id,
                                "updates": updates
                            })
                            st.success(res.get("message", "Transaction updated."))
                        else:
                            st.info("No changes made.")
            else:
                st.warning("Transaction ID not found.")

    # Delete
    with txn_tabs[3]:
        st.subheader("❌ Delete Transaction")
        del_id = st.text_input("Transaction ID to delete")
        if st.button("Delete"):
            res = invoke_lambda("DeleteTransactionLambda", {"transaction_id": del_id})
            st.warning(res.get("message", f"Transaction {del_id} deleted."))

    # Import CSV
    with txn_tabs[4]:
        st.subheader("📤 Upload Transactions CSV")
        csv_file = st.file_uploader("Upload CSV", type=["csv"])
        if csv_file:
            csv_df = pd.read_csv(csv_file)

            # ✅ Convert to JSON-safe types
            transactions = json.loads(
                csv_df.to_json(orient="records", date_format="iso")
            )

            res = invoke_lambda("CsvImportLambda", {
                "transactions": transactions
            })
            st.success(res.get("message", "CSV imported."))

# --- TAB 3: Reports ---
with tabs[2]:
    st.markdown("## 📄 Generate / View Reports")
    year = st.selectbox("Select Year", [2025, 2024, 2023])
    month = st.selectbox("Select Month", [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ])
    st.markdown(f"### 📑 Report Summary for {month} {year}")

    if st.button("🔍 Show Report"):
        res = invoke_lambda("ListTransactionsLambda", {"month": month, "year": year})
        df = pd.DataFrame(res) if res else pd.DataFrame()

        if not df.empty:
            st.dataframe(df)
            st.subheader("📊 Charts")
            col1, col2 = st.columns(2)

            with col1:
                st.bar_chart(df.groupby("Type")["Amount"].sum())

            with col2:
                expenses = df[df["Type"] == "Expense"]
                if not expenses.empty:
                    exp_data = expenses.groupby("Category")["Amount"].sum()
                    st.write("### 🥧 Expense Breakdown")
                    st.plotly_chart(
                        {
                            "data": [{"type": "pie", "labels": exp_data.index, "values": exp_data.values}],
                            "layout": {"title": "Expenses by Category"}
                        }
                    )

            st.line_chart(df.groupby("Date")["Amount"].sum())
            revenue = df[df["Type"] == "Income"]["Amount"].sum()
            expenses_total = df[df["Type"] == "Expense"]["Amount"].sum()
            net = revenue - expenses_total

            st.markdown(
                f"""
                <div style="background-color:#f0f2f6; padding:12px; border-radius:10px;">
                <b>AI Summary:</b><br>
                In <b>{month}</b>, revenue was <b style="color:green;">${revenue:,.0f}</b>. <br>
                Total expenses were <b style="color:red;">${expenses_total:,.0f}</b>. <br>
                Net profit: <b style="color:blue;">${net:,.0f}</b>.
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button("📄 Generate Report Now (PDF)"):
                pdf_res = invoke_lambda("GenerateReportLambda", {"month": month, "year": year})
                url = pdf_res.get("report_url")
                if url:
                    st.success(f"Report ready! [💾 Download PDF]({url})")
                else:
                    st.error("Failed to generate PDF.")
        else:
            st.warning("No transactions for this period.")
