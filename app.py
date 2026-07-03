import streamlit as st
import math
import pandas as pd

LOGO_URL = "https://cdn.abacus.ai/images/0b225e54-01c0-4c83-b1bf-70edd9fe4e70.png"

SHEET_SIZE_CM = 100
STICKER_SIZE_CM = 9
STICKERS_PER_ROW = SHEET_SIZE_CM // STICKER_SIZE_CM
STICKERS_PER_SHEET = STICKERS_PER_ROW ** 2  # 121

VARIANT_MAP = {"100g": 100, "200g": 200, "500g": 500, "1kg": 1000, "2kg": 2000, "5kg": 5000}

def main():
    # Keep Wide Layout for Desktop
    st.set_page_config(page_title="Product Profit Calculator", layout="wide")

    # Responsive Header
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:20px; margin-bottom:10px;">
            <img src="{LOGO_URL}" width="120"/>
            <h1 style="margin:0; font-size:1.8rem;">Product Profit Calculator</h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.divider()

    # --- SIDEBAR (Best for Desktop) ---
    with st.sidebar:
        st.header("⚙️ Global Settings")
        
        with st.expander("🪣 Inventory", expanded=True):
            bucket_cost = st.number_input("Cost of 5kg Bucket (R)", min_value=0.0, value=95.0)
            num_buckets = st.number_input("Buckets Purchased", min_value=1, value=1, step=1)
            total_grams_available = num_buckets * 5 * 1000
            st.caption(f"Stock: {total_grams_available:,}g")

        with st.expander("📦 Labor & Packaging", expanded=True):
            plastic_packs_cost = st.number_input("Unit Pack Cost (R)", min_value=0.0, value=0.50)
            labor_cost = st.number_input("Unit Labor Cost (R)", min_value=0.0, value=2.0)

        with st.expander("🏷️ Stickers & Logistics", expanded=False):
            cost_per_sticker_sheet = st.number_input("Cost/Sticker Sheet (R)", min_value=0.0, value=180.0)
            transport_cost = st.number_input("Transport (Total R)", min_value=0.0, value=0.0)
            delivery_cost = st.number_input("Delivery (Total R)", min_value=0.0, value=0.0)
            storage_cost = st.number_input("Storage (Total R)", min_value=0.0, value=0.0)

        st.divider()
        st.subheader("🛒 Set Variants")
        num_variants = st.number_input("How many sizes?", min_value=1, max_value=6, value=1, step=1)

        variants = []
        grams_allocated = 0
        for i in range(int(num_variants)):
            st.markdown(f"**# Variant {i+1}**")
            v_size = st.selectbox("Size", list(VARIANT_MAP.keys()), key=f"v_size_{i}")
            v_grams = VARIANT_MAP[v_size]
            max_units = (total_grams_available - grams_allocated) // v_grams

            c1, c2 = st.columns(2)
            with c1:
                qty = st.number_input(f"Units (Max {int(max_units)})", 0, int(max_units) if max_units > 0 else 0, int(max_units) if max_units > 0 else 0, key=f"v_qty_{i}")
            with c2:
                price = st.number_input("Price (R)", 0.0, value=10.0, key=f"v_price_{i}")
            
            sticker_req = st.toggle("Sticker Needed?", value=(v_size != "5kg"), key=f"v_stick_{i}")

            grams_used = qty * v_grams
            grams_allocated += grams_used
            variants.append({"size": v_size, "qty": qty, "price": price, "sticker_req": sticker_req, "grams_used": grams_used})

    # --- CALCULATIONS ---
    total_units = sum(v["qty"] for v in variants)
    total_grams_used = sum(v["grams_used"] for v in variants)
    leftover_grams = total_grams_available - total_grams_used

    stickered_units = sum(v["qty"] for v in variants if v["sticker_req"])
    sheets_req = math.ceil(stickered_units / STICKERS_PER_SHEET) if stickered_units > 0 else 0
    total_sticker_cost = sheets_req * cost_per_sticker_sheet
    sticker_cpu = total_sticker_cost / stickered_units if stickered_units > 0 else 0

    total_raw_material_cost = bucket_cost * num_buckets
    total_pkg_lab_cost = (plastic_packs_cost + labor_cost) * total_units
    total_logistics_cost = transport_cost + delivery_cost + storage_cost

    grand_total_cost = total_raw_material_cost + total_pkg_lab_cost + total_sticker_cost + total_logistics_cost
    grand_revenue = sum(v["qty"] * v["price"] for v in variants)
    grand_profit = grand_revenue - grand_total_cost
    grand_margin = (grand_profit / grand_revenue * 100) if grand_revenue > 0 else 0
    
    mat_cpu = total_raw_material_cost / total_units if total_units > 0 else 0
    log_cpu = total_logistics_cost / total_units if total_units > 0 else 0

    # --- MAIN UI ---
    t_profit, t_log, t_stick = st.tabs(["📊 Profit & Performance", "🚚 Logistics", "🏷️ Stickers"])

    with t_profit:
        # Metrics - Stays in 4 columns on Desktop, stacks on Mobile automatically
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue", f"R{grand_revenue:,.2f}")
        m2.metric("Total Cost", f"R{grand_total_cost:,.2f}")
        m3.metric("Profit", f"R{grand_profit:,.2f}")
        m4.metric("Margin", f"{grand_margin:.1f}%")

        st.divider()
        
        # 🟢 DESKTOP VIEW: Full performance table
        st.subheader("Variant Performance (Desktop View)")
        perf_data = []
        for v in variants:
            cpu = mat_cpu + plastic_packs_cost + labor_cost + log_cpu + (sticker_cpu if v["sticker_req"] else 0)
            rev = v["qty"] * v["price"]
            prof = rev - (v["qty"] * cpu)
            
            perf_data.append({
                "Size": v["size"], "Units": v["qty"], "% Units": f"{(v['qty']/total_units*100):.1f}%" if total_units > 0 else "0%",
                "Material": f"{v['grams_used']:,}g", "Sticker": "✅" if v["sticker_req"] else "❌",
                "Price": f"R{v['price']:.2f}", "Cost/U": f"R{cpu:.2f}", "Profit": f"R{prof:,.2f}",
                "Margin": f"{(prof/rev*100) if rev > 0 else 0:.1f}%",
                "% Revenue": f"{(rev/grand_revenue*100):.1f}%" if grand_revenue > 0 else "0%",
                "% Profit": f"{(prof/grand_profit*100):.1f}%" if grand_profit > 0 else "0%"
            })
        st.dataframe(pd.DataFrame(perf_data), use_container_width=True, hide_index=True)

        # 📱 MOBILE HELPER: Performance cards (Easier for phones)
        with st.expander("📱 Tap for Mobile-Friendly Variant Cards"):
            for row in perf_data:
                st.info(f"**{row['Size']}** | Units: {row['Units']} | Margin: {row['Margin']}")
                c_a, c_b = st.columns(2)
                c_a.write(f"Profit: **{row['Profit']}**")
                c_b.write(f"Rev Share: {row['% Revenue']}")

        st.divider()
        
        # Cost Breakdown Table
        st.subheader("Actual Batch Costs")
        cost_df = pd.DataFrame({
            "Source": ["Raw Material", "Lab/Pack", "Stickers", "Logistics", "TOTAL"],
            "Total Cost": [f"R{total_raw_material_cost:,.2f}", f"R{total_pkg_lab_cost:,.2f}", f"R{total_sticker_cost:,.2f}", f"R{total_logistics_cost:,.2f}", f"R{grand_total_cost:,.2f}"],
            "% share": [f"{(total_raw_material_cost/grand_total_cost*100):.1f}%", f"{(total_pkg_lab_cost/grand_total_cost*100):.1f}%", f"{(total_sticker_cost/grand_total_cost*100):.1f}%", f"{(total_logistics_cost/grand_total_cost*100):.1f}%", "100%"],
            "Avg Cost/U": [f"R{mat_cpu:.2f}", f"R{plastic_packs_cost+labor_cost:.2f}", f"R{sticker_cpu:.2f}", f"R{log_cpu:.2f}", f"R{grand_total_cost/total_units:.2f}" if total_units > 0 else "R0"]
        })
        st.table(cost_df)

    with t_log:
        st.subheader("Logistics Breakdown")
        l1, l2, l3 = st.columns(3)
        l1.metric("Transport", f"R{transport_cost:.2f}")
        l2.metric("Delivery", f"R{delivery_cost:.2f}")
        l3.metric("Storage", f"R{storage_cost:.2f}")
        st.info(f"Inventory Check: **{total_grams_used:,}g** used. **{leftover_grams:,}g** leftover.")

    with t_stick:
        st.subheader("Sticker Yields")
        s1, s2 = st.columns(2)
        s1.write(f"Stickered Units: **{stickered_units}**")
        s2.write(f"Sheets Required: **{sheets_req}**")
        st.success(f"Individual sticker cost: R{sticker_cpu:.2f}")

if __name__ == "__main__":
    main()