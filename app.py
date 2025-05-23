
import streamlit as st
import pandas as pd
from itertools import combinations
from collections import Counter

st.set_page_config(page_title="Option Attach‑Rate Explorer", layout="wide")
st.title("Option Attach‑Rate Explorer")

st.markdown(
    """Upload an **order‑lines** file exported from your ERP/warehouse system.

**Required columns (any case / spaces ok)**  
- `CO_NUM` – order number  
- `CO_LINE` – line number (`1` must be the base machine)  
- `ITEM` – item / part code  
Optional but recommended:  
- `DESCRIPTION` – part description  
- `Final FC` – family code of the base line  
- `Final PC` – product code of the base line  

The app can analyse attach‑rates by:

* Machine item code (default)  
* Final family code (Final FC)  
* Final product code (Final PC)  
""")

uploaded = st.file_uploader("📤  Upload .csv or .xlsx", type=["csv","xlsx"])
if uploaded is None:
    st.stop()

# ---------- Load ----------
if uploaded.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded)
else:
    df = pd.read_excel(uploaded)

df.columns = df.columns.str.strip()

# Flexible column mapping ------------------------------------------------
def map_col(regex, default=None):
    for c in df.columns:
        if pd.Series(c).str.replace(' ','_',regex=False,case=False).str.contains(regex,case=False,regex=True).any():
            return c
    return default

col_num  = map_col(r"co[_]?num")
col_line = map_col(r"co[_]?line")
col_item = map_col(r"item")
col_desc = map_col(r"desc")
col_fc   = map_col(r"final[_ ]?fc")
col_pc   = map_col(r"final[_ ]?pc")

needed = [col_num, col_line, col_item]
if any(c is None for c in needed):
    st.error(f"Missing required columns: {needed}")
    st.stop()

df = df.rename(columns={col_num:'CO_NUM',col_line:'CO_LINE',col_item:'ITEM'})
if col_fc: df = df.rename(columns={col_fc:'FINAL_FC'})
if col_pc: df = df.rename(columns={col_pc:'FINAL_PC'})
if col_desc: df = df.rename(columns={col_desc:'DESCRIPTION'})

# ---------- Build base/option tables ----------
base = df.loc[df['CO_LINE']==1,['CO_NUM','ITEM']]
base = base.rename(columns={'ITEM':'BASE_MACHINE'})
if 'FINAL_FC' in df.columns:
    base['BASE_FC'] = df.loc[df['CO_LINE']==1,'FINAL_FC'].values
if 'FINAL_PC' in df.columns:
    base['BASE_PC'] = df.loc[df['CO_LINE']==1,'FINAL_PC'].values

opts = df.loc[df['CO_LINE']!=1, ['CO_NUM','ITEM']]

merged = base.merge(opts, on='CO_NUM', how='left', suffixes=('','_OPT'))

# ---------- User selects grouping key ----------
grouping_options = {'Machine item code':'BASE_MACHINE'}
if 'BASE_FC' in base.columns:
    grouping_options['Final family code (FC)']='BASE_FC'
if 'BASE_PC' in base.columns:
    grouping_options['Final product code (PC)']='BASE_PC'

sel_group_label = st.selectbox("Analyse attach‑rates by …", list(grouping_options.keys()))
gcol = grouping_options[sel_group_label]

attach = (merged.groupby([gcol,'ITEM'])['CO_NUM']
                .nunique()
                .reset_index(name='Order_Count'))

total_orders = (base.groupby(gcol)['CO_NUM']
                    .nunique()
                    .rename('Total_Orders')
                    .reset_index())

attach = attach.merge(total_orders,on=gcol)
attach['Attach_Rate'] = attach['Order_Count']/attach['Total_Orders']

# ---------- UI filter ----------
key_list = sorted(total_orders[gcol].dropna().unique())
sel_key = st.text_input("🔍  Filter / type to pick", "").strip().lower()
filtered_keys = [k for k in key_list if sel_key in str(k).lower()]
sel_value = st.selectbox("Select value", filtered_keys)

if sel_value is None:
    st.stop()

min_rate = st.slider("Min attach rate",0.0,1.0,0.1,0.05)
top_n = st.number_input("Show top N options",1,200,20,1)

subset = (attach.query(f"{gcol} == @sel_value and Attach_Rate >= @min_rate")
                .sort_values('Attach_Rate',ascending=False)
                .head(int(top_n)))

st.subheader(f"Top options for **{sel_value}**")
st.dataframe(subset[['ITEM','Attach_Rate','Order_Count','Total_Orders']])

# ---------- Pair analysis ----------
orders_for_key = merged[merged[gcol]==sel_value].groupby('CO_NUM')['ITEM'].apply(set)
from collections import Counter
from itertools import combinations
pair_counter = Counter()
for items in orders_for_key:
    for p in combinations(sorted(items),2):
        pair_counter[p]+=1
pair_df = pd.DataFrame([{'Pair':f"{a}, {b}", 'Count':c} for (a,b),c in pair_counter.items()])
if not pair_df.empty:
    pair_df['Support'] = pair_df['Count']/len(orders_for_key)
    pair_df = pair_df.sort_values('Count',ascending=False).head(int(top_n))
    st.subheader("Frequent option pairs")
    st.dataframe(pair_df)

# ---------- Downloads ----------
st.markdown("### 📥 Downloads")
csv_full = attach.to_csv(index=False).encode()
st.download_button("Download full attach‑rate table (all keys)",csv_full,"attach_rates_full.csv","text/csv")

csv_key = subset.to_csv(index=False).encode()
st.download_button(f"Download attach‑rates for {sel_value}",csv_key,f"{sel_value}_attach_rates.csv","text/csv")

if not pair_df.empty:
    st.download_button(f"Download option pairs for {sel_value}",pair_df.to_csv(index=False).encode(),f"{sel_value}_pair_counts.csv","text/csv")
