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
    st.set_page_config(page_title="Product Profit Calculator", layout="wide")

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:20px; margin-bottom:10px;">
            <img src="{LOGO_URL}" width="160"/>
            <h1 style="margin:0; font-size:2rem;">Product Profit Calculator</h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.divider()

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Inputs")

        st.subheader("Inventory")
        bucket_cost = st.number_input("Cost of one 5kg Bucket (R)", min_value=0.0, value=95.0)
        num_buckets = st.number_input("Number of 5kg Buckets purchased", min_value=1, value=1, step=1)
        total_grams_available = num_buckets * 5 * 1000

        st.subheader("Packaging & Labor (Per Unit)")
        plastic_packs_cost = st.number_input("Plastic Pack cost per unit (R)", min_value=0.0, value=0.50)
        labor_cost = st.number_input("Labor cost per unit (R)", min_value=0.0, value=2.0)

        st.subheader("Stickers")
        cost_per_sticker_sheet = st.number_input("Cost per Sticker Sheet (R)", min_value=0.0, value=180.0)

        st.subheader("Logistics Costs")
        transport_cost = st.number_input("Total Transport Cost (R)", min_value=0.0, value=0.0)
        delivery_cost = st.number_input("Total Delivery Cost (R)", min_value=0.0, value=0.0)
        storage_cost = st.number_input("Total Storage Cost (R)", min_value=0.0, value=0.0)

        st.divider()
        st.subheader("Product Variants")
        st.caption(f"Available: **{total_grams_available:,}g** ({num_buckets * 5}kg) from {num_buckets} bucket(s)")
        num_variants = st.number_input("How many different sizes?", min_value=1, max_value=6, value=1, step=1)

        variants = []
        grams_allocated = 0

        for i in range(int(num_variants)):
            st.markdown(f"**Variant {i+1}**")
            v_size = st.selectbox("Size", list(VARIANT_MAP.keys()), key=f"v_size_{i}")
            v_grams = VARIANT_MAP[v_size]
            max_units = (total_grams_available - grams_allocated) // v_grams

            col_q, col_p, col_s = st.columns(3)
            with col_q:
                qty = st.number_input(
                    f"Units (Max {int(max_units)})",
                    min_value=0,
                    max_value=int(max_units) if max_units > 0 else 0,
                    value=int(max_units) if max_units > 0 else 0,
                    step=1,
                    key=f"v_qty_{i}"
                )
            with col_p:
                price = st.number_input("Price (R)", min_value=0.0, value=10.0, key=f"v_price_{i}")
            with col_s:
                sticker_req = st.selectbox(
                    "Sticker?",
                    ["Yes", "No"],
                    index=0 if v_size != "5kg" else 1,
                    key=f"v_stick_{i}"
                )

            grams_used = qty * v_grams
            grams_allocated += grams_used
            variants.append({
                "size": v_size,
                "qty": qty,
                "price": price,
                "sticker_req": sticker_req == "Yes",
                "grams_used": grams_used
            })

    # --- CALCULATIONS ---
    total_units = sum(v["qty"] for v in variants)
    total_grams_used = sum(v["grams_used"] for v in variants)
    leftover_grams = total_grams_available - total_grams_used

    # Sticker
    stickered_units = sum(v["qty"] for v in variants if v["sticker_req"])
    sheets_req = math.ceil(stickered_units / STICKERS_PER_SHEET) if stickered_units > 0 else 0
    total_sticker_cost = sheets_req * cost_per_sticker_sheet
    sticker_cpu = total_sticker_cost / stickered_units if stickered_units > 0 else 0

    # Totals
    total_raw_material_cost = bucket_cost * num_buckets
    total_packaging_cost = plastic_packs_cost * total_units
    total_labor_cost = labor_cost * total_units
    total_logistics_cost = transport_cost + delivery_cost + storage_cost

    grand_total_cost = (
        total_raw_material_cost +
        total_packaging_cost +
        total_labor_cost +
        total_sticker_cost +
        total_logistics_cost
    )

    grand_revenue = sum(v["qty"] * v["price"] for v in variants)
    grand_profit = grand_revenue - grand_total_cost
    grand_margin = (grand_profit / grand_revenue * 100) if grand_revenue > 0 else 0

    mat_cpu = total_raw_material_cost / total_units if total_units > 0 else 0
    log_cpu = total_logistics_cost / total_units if total_units > 0 else 0

    # --- TABS ---
    t_profit, t_log, t_stick = st.tabs(["📊 Profit Analysis", "🚚 Logistics", "🏷️ Sticker Yield"])

    with t_profit:
        st.subheader("Batch Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Revenue", f"R{grand_revenue:,.2f}")
        m2.metric("Total Cost", f"R{grand_total_cost:,.2f}")
        m3.metric("Total Profit", f"R{grand_profit:,.2f}")
        m4.metric("Overall Margin", f"{grand_margin:.1f}%")

        if grand_margin >= 30:
            st.success(f"✅ Profit Margin: **{grand_margin:.1f}%** — Healthy!")
        elif grand_margin >= 10:
            st.warning(f"⚠️ Profit Margin: **{grand_margin:.1f}%** — Moderate.")
        else:
            st.error(f"❌ Profit Margin: **{grand_margin:.1f}%** — Low, review costs.")

        if total_grams_used > total_grams_available:
            st.error(f"⚠️ STOCK ALERT: Exceeded available material by {total_grams_used - total_grams_available}g!")
        else:
            st.info(f"Material used: **{total_grams_used:,}g** of **{total_grams_available:,}g** | Leftover: **{leftover_grams:,}g**")

        st.divider()
        st.subheader("Variant Performance")

        perf_data = []
        for v in variants:
            cpu = mat_cpu + plastic_packs_cost + labor_cost + log_cpu + (sticker_cpu if v["sticker_req"] else 0)
            rev = v["qty"] * v["price"]
            cost = v["qty"] * cpu
            prof = rev - cost
            margin = (prof / rev * 100) if rev > 0 else 0

            unit_pct = (v["qty"] / total_units * 100) if total_units > 0 else 0
            material_pct = (v["grams_used"] / total_grams_available * 100) if total_grams_available > 0 else 0
            revenue_pct = (rev / grand_revenue * 100) if grand_revenue > 0 else 0
            profit_pct = (prof / grand_profit * 100) if grand_profit > 0 else 0

            perf_data.append({
                "Size": v["size"],
                "Units": v["qty"],
                "% of Units": f"{unit_pct:.1f}%",
                "Material Used": f"{v['grams_used']:,}g",
                "% of Material": f"{material_pct:.1f}%",
                "Sticker": "✅" if v["sticker_req"] else "❌",
                "Price/Unit": f"R{v['price']:.2f}",
                "Cost/Unit": f"R{cpu:.2f}",
                "Revenue": f"R{rev:,.2f}",
                "% of Revenue": f"{revenue_pct:.1f}%",
                "Profit": f"R{prof:,.2f}",
                "% of Profit": f"{profit_pct:.1f}%",
                "Margin": f"{margin:.1f}%"
            })

        st.dataframe(pd.DataFrame(perf_data), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Actual Cost Breakdown (Whole Batch)")
        st.table({
            "Expense": ["Material", "Packs", "Labor", "Stickers", "Logistics", "TOTAL"],
            "Total Cost (R)": [
                f"R{total_raw_material_cost:,.2f}",
                f"R{total_packaging_cost:,.2f}",
                f"R{total_labor_cost:,.2f}",
                f"R{total_sticker_cost:,.2f}",
                f"R{total_logistics_cost:,.2f}",
                f"R{grand_total_cost:,.2f}"
            ],
            "% of Total Cost": [
                f"{total_raw_material_cost / grand_total_cost * 100 if grand_total_cost > 0 else 0:.1f}%",
                f"{total_packaging_cost / grand_total_cost * 100 if grand_total_cost > 0 else 0:.1f}%",
                f"{total_labor_cost / grand_total_cost * 100 if grand_total_cost > 0 else 0:.1f}%",
                f"{total_sticker_cost / grand_total_cost * 100 if grand_total_cost > 0 else 0:.1f}%",
                f"{total_logistics_cost / grand_total_cost * 100 if grand_total_cost > 0 else 0:.1f}%",
                "100%"
            ],
            "Cost Per Unit (avg)": [
                f"R{mat_cpu:.2f}",
                f"R{plastic_packs_cost:.2f}",
                f"R{labor_cost:.2f}",
                f"R{sticker_cpu:.2f} (stickered only)",
                f"R{log_cpu:.2f}",
                f"R{grand_total_cost / total_units:.2f}" if total_units > 0 else "R0.00"
            ]
        })

    with t_log:
        st.header("🚚 Logistics Breakdown")
        l1, l2, l3 = st.columns(3)
        l1.metric("Transport", f"R{transport_cost:.2f}")
        l2.metric("Delivery", f"R{delivery_cost:.2f}")
        l3.metric("Storage", f"R{storage_cost:.2f}")
        st.divider()
        st.info(
            f"**Total Logistics:** R{total_logistics_cost:.2f}  \n"
            f"**Per Unit (avg):** R{log_cpu:.2f}  \n"
            f"**% of Total Cost:** {(total_logistics_cost / grand_total_cost * 100) if grand_total_cost > 0 else 0:.1f}%"
        )

    with t_stick:
        st.header("🏷️ Sticker Requirements")
        s1, s2, s3 = st.columns(3)
        s1.metric("Units Needing Stickers", stickered_units)
        s2.metric("Sheets to Order", sheets_req)
        s3.metric("Total Sticker Cost", f"R{total_sticker_cost:.2f}")
        st.divider()
        st.info(
            f"**Stickers per Sheet:** {STICKERS_PER_SHEET}  \n"
            f"**Cost per Sheet:** R{cost_per_sticker_sheet:.2f}  \n"
            f"**Cost per Sticker:** R{sticker_cpu:.2f}  \n"
        )
        st.caption(
            f"Sheet: {SHEET_SIZE_CM}cm × {SHEET_SIZE_CM}cm | "
            f"Sticker: {STICKER_SIZE_CM}cm × {STICKER_SIZE_CM}cm | "
            f"{STICKERS_PER_ROW} × {STICKERS_PER_ROW} = {STICKERS_PER_SHEET} per sheet"
        )

if __name__ == "__main__":
    main()