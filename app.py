
import streamlit as st
import pandas as pd
from itertools import combinations
from collections import Counter, defaultdict
import re

st.set_page_config(page_title="Machine Association Explorer", layout="wide")
st.title("Machine ⇄ Option / Final FC / Final PC Explorer")

st.markdown("""
**Upload** your order‑lines export (`CO_NUM`, `CO_LINE`, `ITEM`, `DESCRIPTION`,
`Final FC`, `Final PC` … column names can vary in case/spacing).  
• `CO_LINE == 1` must be the base machine line.  
The app computes how frequently options (ITEM), Final FCs, or Final PCs are attached
to each machine model and shows common pairs.
""")

uploaded = st.file_uploader("Upload .csv or .xlsx", type=["csv","xlsx"])
if uploaded is None:
    st.stop()

# ------------------------------------------------------------------ load file
if uploaded.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded)
else:
    df = pd.read_excel(uploaded)
df.columns = df.columns.str.strip()

# flexible column detection
def find(regex):
    pat = re.compile(regex, re.I)
    for c in df.columns:
        if pat.fullmatch(c.replace(" ","_")):
            return c
    return None

col_map = {
    "CO_NUM":  find(r"co[_]?num"),
    "CO_LINE": find(r"co[_]?line"),
    "ITEM":    find(r"item"),
    "DESC":    find(r"description|desc.*"),
    "FC":      find(r"final[_]?fc"),
    "PC":      find(r"final[_]?pc")
}
missing = [k for k in ["CO_NUM","CO_LINE","ITEM","FC","PC"] if col_map[k] is None]
if missing:
    st.error(f"Missing columns {missing}. Found: {list(df.columns)}")
    st.stop()

df = df.rename(columns={v:k for k,v in col_map.items() if v})

# split machine vs options lines
machines = df.loc[df['CO_LINE']==1, ['CO_NUM','ITEM']].rename(columns={'ITEM':'Machine'})
# options lines keep ITEM, FC, PC
options  = df.loc[df['CO_LINE']!=1, ['CO_NUM','ITEM','FC','PC']]

merged = machines.merge(options, on='CO_NUM', how='left')

# --- choose analysis dimension
dim_choice = st.radio("Select the attribute to analyse:", ["ITEM (Option Code)","Final FC","Final PC"])
if dim_choice.startswith("ITEM"):
    attr_col = "ITEM"
    attr_label = "Option Code"
elif dim_choice.startswith("Final FC"):
    attr_col = "FC"
    attr_label = "Final FC"
else:
    attr_col = "PC"
    attr_label = "Final PC"

# build attach rates
attach = (merged.groupby(['Machine', attr_col])['CO_NUM']
                .nunique()
                .reset_index(name='Order_Count'))
total_orders = (machines.groupby('Machine')['CO_NUM']
                        .nunique()
                        .rename('Total_Orders')
                        .reset_index())
attach = attach.merge(total_orders, on='Machine')
attach['Attach_Rate'] = attach['Order_Count'] / attach['Total_Orders']

# UI filter
machine_list = sorted(attach['Machine'].unique())
search = st.text_input("🔎 Filter machine list").strip().lower()
filtered = [m for m in machine_list if search in m.lower()] or ["< no match >"]
sel_machine = st.selectbox("Select machine model", filtered)
if sel_machine == "< no match >":
    st.stop()

min_rate = st.slider("Minimum attach rate to display", 0.0,1.0,0.05,0.05)
top_n = st.number_input("Top N rows",1,500,20,1)

# show singles
singles = (attach.query("Machine == @sel_machine and Attach_Rate >= @min_rate")
                  .sort_values('Attach_Rate', ascending=False)
                  .head(int(top_n)))
st.subheader(f"Top {attr_label}s for {sel_machine}")
st.dataframe(singles[[attr_col,'Order_Count','Total_Orders','Attach_Rate']])

# download singles
csv_single = singles.to_csv(index=False).encode()
st.download_button("⬇️ Download this table as CSV", csv_single,
                   file_name=f"{sel_machine}_{attr_col}_attach_rates.csv",
                   mime="text/csv")

# --- pair analysis
st.subheader(f"Common pairs of {attr_label}s for {sel_machine}")
# build per order set of attributes
order_sets = (merged[merged['Machine']==sel_machine]
              .groupby('CO_NUM')[attr_col]
              .apply(lambda x: set(x.dropna())))

from collections import Counter
pair_counter = Counter()
for s in order_sets:
    for pair in combinations(sorted(s),2):
        pair_counter[pair]+=1
pair_df = pd.DataFrame([{'Pair': ', '.join(p),
                         'Count': c,
                         'Support': c/len(order_sets)} 
                        for p,c in pair_counter.items()]
                       ).sort_values('Count', ascending=False
                       ).head(int(top_n))
st.dataframe(pair_df)

csv_pairs = pair_df.to_csv(index=False).encode()
st.download_button("⬇️ Download pair table as CSV", csv_pairs,
                   file_name=f"{sel_machine}_{attr_col}_pairs.csv",
                   mime="text/csv")

# --- full attach export
csv_full = attach.to_csv(index=False).encode()
st.download_button("⬇️ Download full attach-rate table", csv_full,
                   file_name="attach_rates_full.csv",
                   mime="text/csv")
