import streamlit as st
import sqlite3
import re
from datetime import datetime
import pandas as pd
import plotly.express as px

DB_NAME = "ai_accounting.db"

def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS chart_of_accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, account_code TEXT UNIQUE, account_name TEXT UNIQUE, account_type TEXT, category TEXT, currency TEXT DEFAULT 'PKR', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_system INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS journal_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_number TEXT UNIQUE, date DATE, description TEXT, reference TEXT, total_amount DECIMAL(15,2), currency TEXT DEFAULT 'PKR', exchange_rate DECIMAL(10,4) DEFAULT 1.0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS journal_lines (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER, account_id INTEGER, debit DECIMAL(15,2) DEFAULT 0, credit DECIMAL(15,2) DEFAULT 0, description TEXT, FOREIGN KEY (entry_id) REFERENCES journal_entries(id), FOREIGN KEY (account_id) REFERENCES chart_of_accounts(id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS gst_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER, gst_type TEXT, tax_rate DECIMAL(5,2), taxable_amount DECIMAL(15,2), gst_amount DECIMAL(15,2), FOREIGN KEY (entry_id) REFERENCES journal_entries(id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS exchange_rates (id INTEGER PRIMARY KEY AUTOINCREMENT, from_currency TEXT, to_currency TEXT, rate DECIMAL(10,6), date DATE, UNIQUE(from_currency, to_currency, date))")
    conn.commit(); conn.close()

def setup_default_coa():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    accounts = [("1001", "Cash", "Asset", "Current Asset", "PKR", 1), ("1002", "Bank", "Asset", "Current Asset", "PKR", 1), ("1003", "Accounts Receivable", "Asset", "Current Asset", "PKR", 1), ("1004", "Inventory", "Asset", "Current Asset", "PKR", 1), ("1005", "Prepaid Expenses", "Asset", "Current Asset", "PKR", 1), ("1101", "Machinery", "Asset", "Fixed Asset", "PKR", 1), ("1102", "Furniture & Fixtures", "Asset", "Fixed Asset", "PKR", 1), ("1103", "Building", "Asset", "Fixed Asset", "PKR", 1), ("1104", "Vehicles", "Asset", "Fixed Asset", "PKR", 1), ("1105", "Computer Equipment", "Asset", "Fixed Asset", "PKR", 1), ("1201", "Accumulated Depreciation", "Asset", "Contra Asset", "PKR", 1), ("2001", "Accounts Payable", "Liability", "Current Liability", "PKR", 1), ("2002", "Bank Loan", "Liability", "Long-term Liability", "PKR", 1), ("2003", "Salaries Payable", "Liability", "Current Liability", "PKR", 1), ("2004", "GST Payable", "Liability", "Current Liability", "PKR", 1), ("2005", "GST Input", "Liability", "Current Liability", "PKR", 1), ("2006", "GST Output", "Liability", "Current Liability", "PKR", 1), ("2007", "Advances from Customers", "Liability", "Current Liability", "PKR", 1), ("3001", "Owner Capital", "Equity", "Equity", "PKR", 1), ("3002", "Owner Drawings", "Equity", "Equity", "PKR", 1), ("3003", "Retained Earnings", "Equity", "Equity", "PKR", 1), ("4001", "Sales Revenue", "Revenue", "Operating Revenue", "PKR", 1), ("4002", "Service Revenue", "Revenue", "Operating Revenue", "PKR", 1), ("4003", "Sales Returns", "Revenue", "Contra Revenue", "PKR", 1), ("4004", "Discount Allowed", "Revenue", "Contra Revenue", "PKR", 1), ("4101", "Interest Income", "Revenue", "Non-Operating Revenue", "PKR", 1), ("4102", "Other Income", "Revenue", "Non-Operating Revenue", "PKR", 1), ("5001", "Cost of Goods Sold", "Expense", "Direct Expense", "PKR", 1), ("5002", "Salaries & Wages", "Expense", "Operating Expense", "PKR", 1), ("5003", "Rent Expense", "Expense", "Operating Expense", "PKR", 1), ("5004", "Utilities Expense", "Expense", "Operating Expense", "PKR", 1), ("5005", "Depreciation Expense", "Expense", "Operating Expense", "PKR", 1), ("5006", "Marketing Expense", "Expense", "Operating Expense", "PKR", 1), ("5007", "Office Supplies", "Expense", "Operating Expense", "PKR", 1), ("5008", "Travel Expense", "Expense", "Operating Expense", "PKR", 1), ("5009", "Insurance Expense", "Expense", "Operating Expense", "PKR", 1), ("5010", "Repairs & Maintenance", "Expense", "Operating Expense", "PKR", 1), ("5011", "Professional Fees", "Expense", "Operating Expense", "PKR", 1), ("5012", "Bank Charges", "Expense", "Operating Expense", "PKR", 1), ("5013", "Bad Debts", "Expense", "Operating Expense", "PKR", 1), ("5101", "Interest Expense", "Expense", "Non-Operating Expense", "PKR", 1), ("5102", "Income Tax Expense", "Expense", "Non-Operating Expense", "PKR", 1)]
    for acc in accounts:
        try: cursor.execute("INSERT OR IGNORE INTO chart_of_accounts VALUES (NULL,?,?,?,?,?,?,?)", (acc[0], acc[1], acc[2], acc[3], acc[4], datetime.now(), acc[5]))
        except: pass
    conn.commit(); conn.close()

class TransactionParser:
    def __init__(self): self.setup_rates()
    def setup_rates(self):
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); today = datetime.now().strftime('%Y-%m-%d')
        rates = [('USD','PKR',278.50,today),('EUR','PKR',301.20,today),('GBP','PKR',352.80,today),('AED','PKR',75.85,today),('SAR','PKR',74.25,today),('PKR','PKR',1.0,today)]
        for r in rates: cursor.execute("INSERT OR REPLACE INTO exchange_rates VALUES (NULL,?,?,?,?)", r)
        conn.commit(); conn.close()
    def extract_amount(self, text):
        text_lower = text.lower(); all_nums = re.findall(r'\b(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\b', text_lower); valid = []
        for n in all_nums:
            num = float(n.replace(',',''))
            if not (2020 <= num <= 2030): valid.append(num)
        k_matches = re.findall(r'\b(\d+(?:\.\d+)?)\s*k\b', text_lower)
        for k in k_matches: valid.append(float(k)*1000)
        curr_matches = re.findall(r'[$€£]\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?', text_lower)
        for c in curr_matches: valid.append(float(c.replace(',','')))
        return max(valid) if valid else 0.0
    def extract_currency(self, text):
        text_lower = text.lower(); curr_map = {'usd':'USD','$':'USD','dollar':'USD','eur':'EUR','€':'EUR','euro':'EUR','gbp':'GBP','£':'GBP','pound':'GBP','aed':'AED','dirham':'AED','sar':'SAR','riyal':'SAR','pkr':'PKR','rs':'PKR','rupee':'PKR','rupees':'PKR'}
        for k,v in curr_map.items():
            if k in text_lower: return v
        return 'PKR'
    def extract_gst(self, text, amount):
        text_lower = text.lower(); rate = 0; inclusive = True
        m = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:gst|vat|tax)', text_lower)
        if m: rate = float(m.group(1))
        if 'excluding' in text_lower and any(w in text_lower for w in ['gst','vat','tax']): inclusive = False
        if any(p in text_lower for p in ['plus gst','plus tax','plus vat']): inclusive = False
        if rate == 0 and any(w in text_lower for w in ['gst','vat','tax']): rate = 18
        if inclusive and rate > 0: taxable = amount / (1 + rate/100); gst_amt = amount - taxable
        else: taxable = amount; gst_amt = amount * (rate/100)
        return {'applicable':rate>0,'rate':rate,'taxable':round(taxable,2),'gst':round(gst_amt,2),'inclusive':inclusive}
    def classify(self, text):
        t = text.lower()
        if any(w in t for w in ['purchased','bought','acquired']):
            cr = 'Cash' if any(w in t for w in ['cash','paid cash']) else 'Accounts Payable'
            return {'type':'Purchase','dr':self.detect_asset(t),'cr':cr}
        if any(w in t for w in ['sold','sale']):
            dr = 'Cash' if any(w in t for w in ['cash','received cash']) else 'Accounts Receivable'
            return {'type':'Sale','dr':dr,'cr':'Sales Revenue'}
        if any(w in t for w in ['paid','payment']): return {'type':'Expense','dr':self.detect_expense(t),'cr':'Bank'}
        if any(w in t for w in ['received','collected']): return {'type':'Receipt','dr':'Cash','cr':'Accounts Receivable'}
        if any(w in t for w in ['invested','capital','introduced']): return {'type':'Investment','dr':'Cash','cr':'Owner Capital'}
        if any(w in t for w in ['loan','borrowed']): return {'type':'Loan','dr':'Bank','cr':'Bank Loan'}
        return {'type':'Unknown','dr':'Suspense Account','cr':'Suspense Account'}
    def detect_asset(self, text):
        assets = {'machine':'Machinery','machinery':'Machinery','equipment':'Computer Equipment','computer':'Computer Equipment','furniture':'Furniture & Fixtures','vehicle':'Vehicles','car':'Vehicles','building':'Building','land':'Land','inventory':'Inventory','stock':'Inventory','goods':'Inventory'}
        for k,v in assets.items():
            if k in text: return v
        return 'Inventory'
    def detect_expense(self, text):
        expenses = {'salary':'Salaries & Wages','wage':'Salaries & Wages','rent':'Rent Expense','utility':'Utilities Expense','electricity':'Utilities Expense','gas':'Utilities Expense','water':'Utilities Expense','marketing':'Marketing Expense','advertising':'Marketing Expense','office':'Office Supplies','stationery':'Office Supplies','travel':'Travel Expense','insurance':'Insurance Expense','repair':'Repairs & Maintenance','maintenance':'Repairs & Maintenance','professional':'Professional Fees','legal':'Professional Fees','audit':'Professional Fees','bank charge':'Bank Charges','interest':'Interest Expense','tax':'Income Tax Expense'}
        for k,v in expenses.items():
            if k in text: return v
        return 'Office Supplies'
    def parse(self, text):
        amt = self.extract_amount(text); curr = self.extract_currency(text); gst = self.extract_gst(text, amt); trans = self.classify(text)
        return {'text':text,'amount':amt,'currency':curr,'gst':gst,'trans':trans,'date':datetime.now().strftime('%Y-%m-%d'),'desc':text.title()}

class AccountingEngine:
    def __init__(self): self.parser = TransactionParser()
    def get_or_create_account(self, name, acc_type="Expense", category="Operating Expense"):
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
        cursor.execute("SELECT id FROM chart_of_accounts WHERE LOWER(account_name)=LOWER(?)", (name,))
        r = cursor.fetchone()
        if r: conn.close(); return r[0]
        cursor.execute("SELECT MAX(CAST(account_code AS INTEGER)) FROM chart_of_accounts WHERE account_code GLOB ?", (acc_type[0]+'*',))
        max_c = cursor.fetchone()[0]
        new_code = str((max_c or {'Asset':1000,'Liability':2000,'Equity':3000,'Revenue':4000,'Expense':5000}.get(acc_type,9000)) + 1)
        cursor.execute("INSERT INTO chart_of_accounts (account_code,account_name,account_type,category,currency,is_system) VALUES (?,?,?,?,?,0)", (new_code,name,acc_type,category,'PKR'))
        new_id = cursor.lastrowid; conn.commit(); conn.close(); return new_id
    def infer_type(self, name):
        n = name.lower()
        if any(w in n for w in ['cash','bank','receivable','inventory','prepaid','machine','furniture','building','vehicle','equipment']): return 'Asset'
        if any(w in n for w in ['payable','loan','salaries payable','gst','advance from']): return 'Liability'
        if any(w in n for w in ['capital','drawings','retained']): return 'Equity'
        if any(w in n for w in ['sales','revenue','income']): return 'Revenue'
        return 'Expense'
    def post_entry(self, parsed):
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
        curr = parsed['currency']
        cursor.execute("SELECT rate FROM exchange_rates WHERE from_currency=? AND to_currency='PKR' ORDER BY date DESC LIMIT 1", (curr,))
        r = cursor.fetchone(); rate = r[0] if r else 1.0; amt_pkr = parsed['amount'] * rate
        cursor.execute("SELECT COUNT(*) FROM journal_entries"); count = cursor.fetchone()[0] + 1
        entry_num = f"JV-{datetime.now().strftime('%Y%m%d')}-{count:04d}"
        cursor.execute("INSERT INTO journal_entries (entry_number,date,description,reference,total_amount,currency,exchange_rate) VALUES (?,?,?,?,?,?,?)", (entry_num,parsed['date'],parsed['desc'],'Business Transaction',amt_pkr,curr,rate))
        entry_id = cursor.lastrowid; lines = []; gst = parsed['gst']; trans = parsed['trans']
        if gst['applicable']:
            taxable = gst['taxable'] * rate; gst_amt = gst['gst'] * rate
            dr_id = self.get_or_create_account(trans['dr'], self.infer_type(trans['dr']))
            lines.append((entry_id, dr_id, taxable, 0, f"{trans['dr']} - Taxable"))
            gst_acc = 'GST Input' if trans['type'] in ['Purchase','Expense'] else 'GST Output'
            gst_id = self.get_or_create_account(gst_acc, 'Liability', 'Current Liability')
            lines.append((entry_id, gst_id, gst_amt, 0, f"GST @ {gst['rate']}%"))
            cr_id = self.get_or_create_account(trans['cr'], self.infer_type(trans['cr']))
            lines.append((entry_id, cr_id, 0, amt_pkr, trans['cr']))
            cursor.execute("INSERT INTO gst_transactions (entry_id,gst_type,tax_rate,taxable_amount,gst_amount) VALUES (?,?,?,?,?)", (entry_id, gst_acc, gst['rate'], taxable, gst_amt))
        else:
            dr_id = self.get_or_create_account(trans['dr'], self.infer_type(trans['dr']))
            lines.append((entry_id, dr_id, amt_pkr, 0, trans['dr']))
            cr_id = self.get_or_create_account(trans['cr'], self.infer_type(trans['cr']))
            lines.append((entry_id, cr_id, 0, amt_pkr, trans['cr']))
        cursor.executemany("INSERT INTO journal_lines (entry_id,account_id,debit,credit,description) VALUES (?,?,?,?,?)", lines)
        conn.commit(); conn.close()
        return {'entry_id':entry_id,'entry_num':entry_num,'lines':lines,'gst':gst['applicable'],'amt_pkr':amt_pkr,'rate':rate}

class Reports:
    def trial_balance(self):
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
        cursor.execute("SELECT coa.account_code, coa.account_name, coa.account_type, SUM(COALESCE(jl.debit,0)) as dr, SUM(COALESCE(jl.credit,0)) as cr FROM chart_of_accounts coa LEFT JOIN journal_lines jl ON coa.id=jl.account_id GROUP BY coa.id HAVING dr>0 OR cr>0 ORDER BY coa.account_code")
        rows = cursor.fetchall(); conn.close()
        return [{'code':r[0],'name':r[1],'type':r[2],'dr':r[3],'cr':r[4],'bal':r[3]-r[4]} for r in rows]
    def balance_sheet(self):
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
        cursor.execute("SELECT account_name, SUM(debit-credit) as bal FROM chart_of_accounts JOIN journal_lines ON chart_of_accounts.id=account_id WHERE account_type='Asset' GROUP BY account_id HAVING bal != 0")
        assets = {r[0]:r[1] for r in cursor.fetchall()}
        cursor.execute("SELECT account_name, SUM(credit-debit) as bal FROM chart_of_accounts JOIN journal_lines ON chart_of_accounts.id=account_id WHERE account_type='Liability' GROUP BY account_id HAVING bal != 0")
        liab = {r[0]:r[1] for r in cursor.fetchall()}
        cursor.execute("SELECT account_name, SUM(credit-debit) as bal FROM chart_of_accounts JOIN journal_lines ON chart_of_accounts.id=account_id WHERE account_type='Equity' GROUP BY account_id HAVING bal != 0")
        equity = {r[0]:r[1] for r in cursor.fetchall()}
        conn.close(); ta, tl, te = sum(assets.values()), sum(liab.values()), sum(equity.values())
        return {'assets':assets,'liab':liab,'equity':equity,'ta':ta,'tl':tl,'te':te,'bal':abs(ta-(tl+te))<<0.01}
    def profit_loss(self):
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
        cursor.execute("SELECT account_name, SUM(credit-debit) as bal FROM chart_of_accounts JOIN journal_lines ON chart_of_accounts.id=account_id WHERE account_type='Revenue' GROUP BY account_id HAVING bal != 0")
        rev = {r[0]:r[1] for r in cursor.fetchall()}
        cursor.execute("SELECT account_name, SUM(debit-credit) as bal FROM chart_of_accounts JOIN journal_lines ON chart_of_accounts.id=account_id WHERE account_type='Expense' GROUP BY account_id HAVING bal != 0")
        exp = {r[0]:r[1] for r in cursor.fetchall()}
        conn.close(); tr, te = sum(rev.values()), sum(exp.values())
        return {'rev':rev,'exp':exp,'tr':tr,'te':te,'np':tr-te,'margin':(tr-te)/tr*100 if tr>0 else 0}

st.set_page_config(page_title="AI Accounting System", page_icon="🤖", layout="wide")
st.markdown("<style>.main-header { font-size: 40px; font-weight: bold; color: #1f77b4; text-align: center; } .sub-header { font-size: 20px; color: #666; text-align: center; margin-bottom: 30px; }</style>", unsafe_allow_html=True)

if os.path.exists(DB_NAME): os.remove(DB_NAME)
init_database(); setup_default_coa()
engine = AccountingEngine()
reports = Reports()

demo_transactions = [
    "Purchased machine with cash payment of 25000",
    "Sold goods to Ahmed Traders on credit for 50000 including 18% GST",
    "Paid office rent of 15000 by bank transfer",
    "Received cash 30000 from customer Ali Enterprises",
    "Purchased inventory from XYZ Suppliers for 100000 on credit with GST",
    "Paid salaries to staff 75000 through bank",
    "Owner invested 500000 cash into business",
    "Bought computer equipment for 45000 cash",
    "Received 5000 USD from client in Dubai",
    "Paid 25k for marketing services",
]

for trans in demo_transactions:
    parsed = engine.parser.parse(trans)
    if parsed['amount'] > 0: engine.post_entry(parsed)

st.sidebar.title("🤖 AI Accounting")
page = st.sidebar.radio("Navigation", ["🏠 Home", "💬 Enter Transaction", "📋 Chart of Accounts", "📊 Trial Balance", "📈 Balance Sheet", "💰 Profit & Loss", "📜 Journal Ledger"])

if page == "🏠 Home":
    st.markdown('<div class="main-header">AI Accounting System</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Pakistan Edition | GST-Ready | Multi-Currency | Built for Non-Accountants</div>', unsafe_allow_html=True)
    bs = reports.balance_sheet(); pl = reports.profit_loss()
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("💰 Total Assets", f"PKR {bs['ta']:,.0f}")
    with col2: st.metric("📉 Total Liabilities", f"PKR {bs['tl']:,.0f}")
    with col3: st.metric("📈 Net Profit", f"PKR {pl['np']:,.0f}")
    with col4: st.metric("📊 Profit Margin", f"{pl['margin']:.1f}%")
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Assets vs Liabilities")
        chart_data = pd.DataFrame({'Category': ['Assets', 'Liabilities', 'Equity'], 'Amount': [bs['ta'], bs['tl'], bs['te']]})
        fig = px.bar(chart_data, x='Category', y='Amount', color='Category', text='Amount')
        fig.update_traces(texttemplate='PKR %{text:,.0f}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("💰 Revenue vs Expenses")
        chart_data = pd.DataFrame({'Category': ['Revenue', 'Expenses'], 'Amount': [pl['tr'], pl['te']]})
        fig = px.pie(chart_data, values='Amount', names='Category', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")
    st.subheader("📝 Recent Transactions")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT entry_number, date, description, total_amount, currency FROM journal_entries ORDER BY id DESC LIMIT 5", conn)
    conn.close(); st.dataframe(df, use_container_width=True)

elif page == "💬 Enter Transaction":
    st.header("💬 Enter Transaction in Plain English")
    st.info("Examples:\n- Purchased machine for 25000 cash\n- Sold goods for 50000 including 18% GST\n- Paid rent of 15000 by bank\n- Received 5000 USD from Dubai client")
    transaction = st.text_input("Your Transaction:", placeholder="e.g., Purchased inventory for 50000 cash")
    if st.button("🚀 Process Transaction", type="primary"):
        if transaction:
            parsed = engine.parser.parse(transaction)
            if parsed['amount'] <= 0: st.error("❌ Could not detect an amount. Please include a number.")
            else:
                result = engine.post_entry(parsed); st.success("✅ Transaction Recorded Successfully!")
                col1, col2 = st.columns(2)
                with col1: st.write(f"**Entry Number:** {result['entry_num']}"); st.write(f"**Amount:** {parsed['amount']:,.2f} {parsed['currency']}"); st.write(f"**In PKR:** {result['amt_pkr']:,.2f} PKR")
                with col2: st.write(f"**Date:** {parsed['date']}"); st.write(f"**Type:** {parsed['trans']['type']}")
                if parsed['gst']['applicable']: st.write(f"**GST:** {parsed['gst']['rate']}%")
                st.subheader("📒 Journal Entry")
                conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); journal_lines = []
                for line in result['lines']:
                    cursor.execute("SELECT account_name FROM chart_of_accounts WHERE id=?", (line[1],)); acc = cursor.fetchone()[0]
                    if line[2] > 0: journal_lines.append({"Account": f"Dr. {acc}", "Amount": f"{line[2]:,.2f}", "Type": "Debit"})
                    if line[3] > 0: journal_lines.append({"Account": f"Cr. {acc}", "Amount": f"{line[3]:,.2f}", "Type": "Credit"})
                conn.close(); st.table(pd.DataFrame(journal_lines))
        else: st.warning("Please enter a transaction first.")

elif page == "📋 Chart of Accounts":
    st.header("📋 Chart of Accounts")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT account_code, account_name, account_type, category, currency FROM chart_of_accounts ORDER BY account_code", conn)
    conn.close(); acc_type = st.selectbox("Filter by Account Type:", ["All"] + list(df['account_type'].unique()))
    if acc_type != "All": df = df[df['account_type'] == acc_type]
    st.dataframe(df, use_container_width=True)
    st.subheader("📊 Account Type Distribution")
    type_counts = df['account_type'].value_counts().reset_index(); type_counts.columns = ['Account Type', 'Count']
    fig = px.pie(type_counts, values='Count', names='Account Type'); st.plotly_chart(fig, use_container_width=True)

elif page == "📊 Trial Balance":
    st.header("📊 Trial Balance"); data = reports.trial_balance()
    if data:
        df = pd.DataFrame(data); df['balance'] = df['bal']; st.dataframe(df[['code', 'name', 'type', 'dr', 'cr', 'balance']], use_container_width=True)
        total_dr = df['dr'].sum(); total_cr = df['cr'].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Debit", f"PKR {total_dr:,.2f}"); col2.metric("Total Credit", f"PKR {total_cr:,.2f}"); col3.metric("Status", "✅ BALANCED" if abs(total_dr - total_cr) < 0.01 else "❌ NOT BALANCED")
        st.subheader("📈 Account Balances"); fig = px.bar(df, x='name', y='balance', color='type', title='Account Balances'); fig.update_layout(xaxis_tickangle=-45); st.plotly_chart(fig, use_container_width=True)
    else: st.info("No transactions yet. Go to 'Enter Transaction' to add some!")

elif page == "📈 Balance Sheet":
    st.header("📈 Balance Sheet"); bs = reports.balance_sheet()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Assets", f"PKR {bs['ta']:,.2f}"); col2.metric("Total Liabilities", f"PKR {bs['tl']:,.2f}"); col3.metric("Total Equity", f"PKR {bs['te']:,.2f}")
    st.write(f"**Status:** {'✅ BALANCED' if bs['bal'] else '❌ NOT BALANCED'}")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("💰 Assets")
        if bs['assets']: st.dataframe(pd.DataFrame(list(bs['assets'].items()), columns=['Account', 'Amount']), use_container_width=True)
        else: st.info("No assets recorded yet.")
    with col2:
        st.subheader("📉 Liabilities")
        if bs['liab']: st.dataframe(pd.DataFrame(list(bs['liab'].items()), columns=['Account', 'Amount']), use_container_width=True)
        else: st.info("No liabilities recorded yet.")
    st.subheader("📊 Assets Breakdown")
    if bs['assets']: fig = px.pie(values=list(bs['assets'].values()), names=list(bs['assets'].keys()), title='Asset Distribution'); st.plotly_chart(fig, use_container_width=True)

elif page == "💰 Profit & Loss":
    st.header("💰 Profit & Loss Statement"); pl = reports.profit_loss()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Revenue", f"PKR {pl['tr']:,.2f}"); col2.metric("Total Expenses", f"PKR {pl['te']:,.2f}"); col3.metric("Net Profit", f"PKR {pl['np']:,.2f}")
    st.write(f"**Profit Margin:** {pl['margin']:.2f}%"); col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 Revenue")
        if pl['rev']: st.dataframe(pd.DataFrame(list(pl['rev'].items()), columns=['Account', 'Amount']), use_container_width=True)
        else: st.info("No revenue recorded yet.")
    with col2:
        st.subheader("📉 Expenses")
        if pl['exp']: st.dataframe(pd.DataFrame(list(pl['exp'].items()), columns=['Account', 'Amount']), use_container_width=True)
        else: st.info("No expenses recorded yet.")
    st.subheader("📊 Revenue vs Expenses"); chart_data = pd.DataFrame({'Category': ['Revenue', 'Expenses'], 'Amount': [pl['tr'], pl['te']]})
    fig = px.bar(chart_data, x='Category', y='Amount', color='Category', text='Amount'); fig.update_traces(texttemplate='PKR %{text:,.0f}', textposition='outside'); st.plotly_chart(fig, use_container_width=True)

elif page == "📜 Journal Ledger":
    st.header("📜 Journal Ledger")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT je.entry_number, je.date, je.description, je.total_amount, je.currency, jl.debit, jl.credit, coa.account_name FROM journal_entries je JOIN journal_lines jl ON je.id = jl.entry_id JOIN chart_of_accounts coa ON jl.account_id = coa.id ORDER BY je.id DESC", conn)
    conn.close(); st.dataframe(df, use_container_width=True)
    st.subheader("📊 Transaction Summary"); total_transactions = df['entry_number'].nunique(); total_debit = df['debit'].sum(); total_credit = df['credit'].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Transactions", total_transactions); col2.metric("Total Debits", f"PKR {total_debit:,.2f}"); col3.metric("Total Credits", f"PKR {total_credit:,.2f}")