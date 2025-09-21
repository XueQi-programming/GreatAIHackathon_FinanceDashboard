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
    month_name = st.selectbox(
        "Select Month",
        ["January","February","March","April","May","June",
         "July","August","September","October","November","December"]
    )
    
    # Convert month name to number (for YYYY-MM)
    month_num = datetime.datetime.strptime(month_name, "%B").month
    month_key = f"{year}-{month_num:02d}"   # ensures "2025-09"

    if st.button("🔍 Show Report"):
        report_res = invoke_lambda("GenerateReportLambda", {"month": month_key})

        # Handle API Gateway "body"
        if "body" in report_res:
            try:
                body = json.loads(report_res["body"])
            except:
                body = {}
        else:
            body = report_res

        report = body.get("Report", {})
        summary_text = body.get("SummaryText", "")
        insights = body.get("InsightsList", [])
        pdf_url = body.get("PDFReport")
        json_url = body.get("JSONReport")

        if report:
            st.markdown(f"### 📑 Report Summary for {month_name} {year}")

            # Transactions table
            st.dataframe(report.get("Transactions", []))  # If you include transactions in Lambda

            # Charts
            st.subheader("📊 Charts")
            st.bar_chart([report["TotalIncome"], sum(report["TotalExpenses"].values())])

            # AI Summary
            if summary_text:
                st.subheader("🤖 AI Summary")
                st.info(summary_text)

            # Insights
            if insights:
                st.subheader("💡 Actionable Insights")
                for i in insights:
                    st.write(i)

            # Downloads
            if pdf_url or json_url:
                st.subheader("📥 Download Reports")
                if pdf_url:
                    st.markdown(f"[📄 PDF Report]({pdf_url})", unsafe_allow_html=True)
                if json_url:
                    st.markdown(f"[🗂 JSON Report]({json_url})", unsafe_allow_html=True)
        else:
            st.warning("No transactions for this period.")


