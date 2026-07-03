import streamlit as st
import math
import pandas as pd
import datetime
from io import BytesIO

LOGO_URL = "https://cdn.abacus.ai/images/0b225e54-01c0-4c83-b1bf-70edd9fe4e70.png"

SHEET_SIZE_CM = 100
STICKER_SIZE_CM = 9
STICKERS_PER_ROW = SHEET_SIZE_CM // STICKER_SIZE_CM
STICKERS_PER_SHEET = STICKERS_PER_ROW ** 2  # 121

VARIANT_MAP = {"100g": 100, "200g": 200, "500g": 500, "1kg": 1000, "2kg": 2000, "5kg": 5000}

# ── Session State ──
if "history" not in st.session_state:
    st.session_state["history"] = []

def build_excel(calc):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: Batch Summary
        summary = pd.DataFrame([{
            "Agent": calc["agent"],
            "Date": calc["date"],
            "Buckets": calc["num_buckets"],
            "Total Units": calc["total_units"],
            "Total Revenue (R)": calc["grand_revenue"],
            "Total Cost (R)": calc["grand_total_cost"],
            "Total Profit (R)": calc["grand_profit"],
            "Margin (%)": round(calc["grand_margin"], 2),
            "Material Used (g)": calc["total_grams_used"],
            "Leftover (g)": calc["leftover_grams"],
        }])
        summary.to_excel(writer, sheet_name="Batch Summary", index=False)

        # Sheet 2: Variant Performance
        pd.DataFrame(calc["perf_data"]).to_excel(writer, sheet_name="Variant Performance", index=False)

        # Sheet 3: Cost Breakdown
        pd.DataFrame(calc["cost_breakdown"]).to_excel(writer, sheet_name="Cost Breakdown", index=False)

        # Sheet 4: Logistics
        logistics = pd.DataFrame([{
            "Transport (R)": calc["transport_cost"],
            "Delivery (R)": calc["delivery_cost"],
            "Storage (R)": calc["storage_cost"],
            "Total Logistics (R)": calc["total_logistics_cost"],
            "Per Unit (R)": round(calc["log_cpu"], 2),
        }])
        logistics.to_excel(writer, sheet_name="Logistics", index=False)

        # Sheet 5: Stickers
        stickers = pd.DataFrame([{
            "Stickered Units": calc["stickered_units"],
            "Sheets Required": calc["sheets_req"],
            "Cost per Sheet (R)": calc["cost_per_sticker_sheet"],
            "Total Sticker Cost (R)": calc["total_sticker_cost"],
            "Cost per Sticker (R)": round(calc["sticker_cpu"], 2),
            "Stickers per Sheet": STICKERS_PER_SHEET,
        }])
        stickers.to_excel(writer, sheet_name="Stickers", index=False)

        # Sheet 6: History
        if st.session_state["history"]:
            hist_rows = []
            for h in st.session_state["history"]:
                hist_rows.append({
                    "Agent": h["agent"],
                    "Date": h["date"],
                    "Buckets": h["num_buckets"],
                    "Total Units": h["total_units"],
                    "Revenue (R)": h["grand_revenue"],
                    "Cost (R)": h["grand_total_cost"],
                    "Profit (R)": h["grand_profit"],
                    "Margin (%)": round(h["grand_margin"], 2),
                })
            pd.DataFrame(hist_rows).to_excel(writer, sheet_name="Saved History", index=False)

    output.seek(0)
    return output


def main():
    st.set_page_config(page_title="Product Profit Calculator", layout="wide")

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

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Settings")

        with st.expander("👤 Session Info", expanded=True):
            agent_name = st.text_input("Agent Name", value="")
            calc_date = st.date_input("Date", value=datetime.date.today())

        with st.expander("🪣 Inventory", expanded=True):
            bucket_cost = st.number_input("Cost of 5kg Bucket (R)", min_value=0.0, value=95.0)
            num_buckets = st.number_input("Buckets Purchased", min_value=1, value=1, step=1)
            total_grams_available = num_buckets * 5 * 1000
            st.caption(f"Stock: **{total_grams_available:,}g** ({num_buckets * 5}kg)")

        with st.expander("📦 Labor & Packaging", expanded=True):
            plastic_packs_cost = st.number_input("Unit Pack Cost (R)", min_value=0.0, value=0.50)
            labor_cost = st.number_input("Unit Labor Cost (R)", min_value=0.0, value=2.0)

        with st.expander("🏷️ Stickers & Logistics", expanded=False):
            cost_per_sticker_sheet = st.number_input("Cost/Sticker Sheet (R)", min_value=0.0, value=180.0)
            transport_cost = st.number_input("Transport (Total R)", min_value=0.0, value=0.0)
            delivery_cost = st.number_input("Delivery (Total R)", min_value=0.0, value=0.0)
            storage_cost = st.number_input("Storage (Total R)", min_value=0.0, value=0.0)

        st.divider()
        st.subheader("🛒 Product Variants")
        num_variants = st.number_input("How many sizes?", min_value=1, max_value=6, value=1, step=1)

        variants = []
        grams_allocated = 0
        for i in range(int(num_variants)):
            st.markdown(f"**Variant {i+1}**")
            v_size = st.selectbox("Size", list(VARIANT_MAP.keys()), key=f"v_size_{i}")
            v_grams = VARIANT_MAP[v_size]
            max_units = (total_grams_available - grams_allocated) // v_grams

            c1, c2 = st.columns(2)
            with c1:
                qty = st.number_input(
                    f"Units (Max {int(max_units)})",
                    min_value=0,
                    max_value=int(max_units) if max_units > 0 else 0,
                    value=int(max_units) if max_units > 0 else 0,
                    step=1,
                    key=f"v_qty_{i}"
                )
            with c2:
                price = st.number_input("Price (R)", min_value=0.0, value=10.0, key=f"v_price_{i}")

            sticker_req = st.toggle("Sticker Needed?", value=(v_size != "5kg"), key=f"v_stick_{i}")

            grams_used = qty * v_grams
            grams_allocated += grams_used
            variants.append({
                "size": v_size, "qty": qty, "price": price,
                "sticker_req": sticker_req, "grams_used": grams_used
            })

    # --- CALCULATIONS ---
    total_units = sum(v["qty"] for v in variants)
    total_grams_used = sum(v["grams_used"] for v in variants)
    leftover_grams = total_grams_available - total_grams_used

    stickered_units = sum(v["qty"] for v in variants if v["sticker_req"])
    sheets_req = math.ceil(stickered_units / STICKERS_PER_SHEET) if stickered_units > 0 else 0
    total_sticker_cost = sheets_req * cost_per_sticker_sheet
    sticker_cpu = total_sticker_cost / stickered_units if stickered_units > 0 else 0

    total_raw_material_cost = bucket_cost * num_buckets
    total_packaging_cost = plastic_packs_cost * total_units
    total_labor_cost = labor_cost * total_units
    total_logistics_cost = transport_cost + delivery_cost + storage_cost

    grand_total_cost = (
        total_raw_material_cost + total_packaging_cost +
        total_labor_cost + total_sticker_cost + total_logistics_cost
    )

    grand_revenue = sum(v["qty"] * v["price"] for v in variants)
    grand_profit = grand_revenue - grand_total_cost
    grand_margin = (grand_profit / grand_revenue * 100) if grand_revenue > 0 else 0

    mat_cpu = total_raw_material_cost / total_units if total_units > 0 else 0
    log_cpu = total_logistics_cost / total_units if total_units > 0 else 0

    # Build perf_data
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
            "Sticker": "Yes" if v["sticker_req"] else "No",
            "Price/Unit (R)": v["price"],
            "Cost/Unit (R)": round(cpu, 2),
            "Revenue (R)": round(rev, 2),
            "% of Revenue": f"{revenue_pct:.1f}%",
            "Total Cost (R)": round(cost, 2),
            "Profit (R)": round(prof, 2),
            "% of Profit": f"{profit_pct:.1f}%",
            "Margin (%)": f"{margin:.1f}%"
        })

    # Build cost_breakdown
    cost_breakdown = [
        {"Expense": "Raw Material", "Total Cost (R)": round(total_raw_material_cost, 2), "% of Total": f"{total_raw_material_cost/grand_total_cost*100 if grand_total_cost > 0 else 0:.1f}%", "Cost/Unit (R)": round(mat_cpu, 2), "Note": f"{num_buckets} bucket(s)"},
        {"Expense": "Packaging",    "Total Cost (R)": round(total_packaging_cost, 2),    "% of Total": f"{total_packaging_cost/grand_total_cost*100 if grand_total_cost > 0 else 0:.1f}%",    "Cost/Unit (R)": round(plastic_packs_cost, 2), "Note": "per unit"},
        {"Expense": "Labor",        "Total Cost (R)": round(total_labor_cost, 2),        "% of Total": f"{total_labor_cost/grand_total_cost*100 if grand_total_cost > 0 else 0:.1f}%",        "Cost/Unit (R)": round(labor_cost, 2),         "Note": "per unit"},
        {"Expense": "Stickers",     "Total Cost (R)": round(total_sticker_cost, 2),      "% of Total": f"{total_sticker_cost/grand_total_cost*100 if grand_total_cost > 0 else 0:.1f}%",      "Cost/Unit (R)": round(sticker_cpu, 2),        "Note": "stickered units only"},
        {"Expense": "Logistics",    "Total Cost (R)": round(total_logistics_cost, 2),    "% of Total": f"{total_logistics_cost/grand_total_cost*100 if grand_total_cost > 0 else 0:.1f}%",    "Cost/Unit (R)": round(log_cpu, 2),            "Note": "split across all units"},
        {"Expense": "TOTAL",        "Total Cost (R)": round(grand_total_cost, 2),        "% of Total": "100%",                                                                                 "Cost/Unit (R)": round(grand_total_cost/total_units, 2) if total_units > 0 else 0, "Note": ""},
    ]

    # Snapshot for saving
    calc_snapshot = {
        "agent": agent_name or "—",
        "date": str(calc_date),
        "num_buckets": num_buckets,
        "total_units": total_units,
        "grand_revenue": round(grand_revenue, 2),
        "grand_total_cost": round(grand_total_cost, 2),
        "grand_profit": round(grand_profit, 2),
        "grand_margin": round(grand_margin, 2),
        "total_grams_used": total_grams_used,
        "leftover_grams": leftover_grams,
        "perf_data": perf_data,
        "cost_breakdown": cost_breakdown,
        "transport_cost": transport_cost,
        "delivery_cost": delivery_cost,
        "storage_cost": storage_cost,
        "total_logistics_cost": round(total_logistics_cost, 2),
        "log_cpu": log_cpu,
        "stickered_units": stickered_units,
        "sheets_req": sheets_req,
        "cost_per_sticker_sheet": cost_per_sticker_sheet,
        "total_sticker_cost": round(total_sticker_cost, 2),
        "sticker_cpu": sticker_cpu,
        "mat_cpu": mat_cpu,
    }

    # --- SAVE & EXPORT BAR ---
    st.markdown(f"**Agent:** {agent_name or '—'} &nbsp;|&nbsp; **Date:** {calc_date}")
    sa_col, dl_col, _ = st.columns([1, 1, 4])
    with sa_col:
        if st.button("💾 Save Calculation"):
            st.session_state["history"].append(calc_snapshot)
            st.success("Saved!")
    with dl_col:
        excel_data = build_excel(calc_snapshot)
        st.download_button(
            label="📥 Export to Excel",
            data=excel_data,
            file_name=f"peony_profit_{calc_date}_{agent_name or 'export'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.divider()

    # --- TABS ---
    t_profit, t_log, t_stick, t_history = st.tabs([
        "📊 Profit & Performance", "🚚 Logistics", "🏷️ Stickers", "🗂️ Saved History"
    ])

    # ── Profit Tab ──
    with t_profit:
        st.subheader("Batch Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue", f"R{grand_revenue:,.2f}")
        m2.metric("Total Cost", f"R{grand_total_cost:,.2f}")
        m3.metric("Profit", f"R{grand_profit:,.2f}")
        m4.metric("Margin", f"{grand_margin:.1f}%")

        if grand_margin >= 30:
            st.success(f"✅ Profit Margin: **{grand_margin:.1f}%** — Healthy!")
        elif grand_margin >= 10:
            st.warning(f"⚠️ Profit Margin: **{grand_margin:.1f}%** — Moderate.")
        else:
            st.error(f"❌ Profit Margin: **{grand_margin:.1f}%** — Low, review costs.")

        if total_grams_used > total_grams_available:
            st.error(f"⚠️ STOCK ALERT: Exceeded by {total_grams_used - total_grams_available:,}g!")
        else:
            st.info(f"Material: **{total_grams_used:,}g** used | **{leftover_grams:,}g** leftover")

        st.divider()
        st.subheader("Variant Performance")
        st.dataframe(pd.DataFrame(perf_data), use_container_width=True, hide_index=True)

        # Mobile cards
        with st.expander("📱 Mobile-Friendly Variant Cards"):
            for row in perf_data:
                with st.container():
                    st.markdown(f"**{row['Size']}** | {row['Units']} units | Margin: {row['Margin (%)']}")
                    c1, c2 = st.columns(2)
                    c1.metric("Revenue", f"R{row['Revenue (R)']:,.2f}")
                    c2.metric("Profit", f"R{row['Profit (R)']:,.2f}")
                    c1, c2 = st.columns(2)
                    c1.metric("% Revenue", row["% of Revenue"])
                    c2.metric("% Profit", row["% of Profit"])
                    st.caption(f"Material: {row['Material Used']} ({row['% of Material']}) | Sticker: {row['Sticker']}")
                    st.divider()

        st.divider()
        st.subheader("Actual Cost Breakdown")
        st.table(pd.DataFrame(cost_breakdown))

    # ── Logistics Tab ──
    with t_log:
        st.subheader("Logistics Breakdown")
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

    # ── Stickers Tab ──
    with t_stick:
        st.subheader("Sticker Requirements")
        s1, s2 = st.columns(2)
        s1.metric("Units Needing Stickers", stickered_units)
        s2.metric("Sheets to Order", sheets_req)
        s1, s2 = st.columns(2)
        s1.metric("Total Sticker Cost", f"R{total_sticker_cost:.2f}")
        s2.metric("Cost per Sticker", f"R{sticker_cpu:.2f}")
        st.divider()
        st.info(
            f"**Stickers per Sheet:** {STICKERS_PER_SHEET}  \n"
            f"**Cost per Sheet:** R{cost_per_sticker_sheet:.2f}"
        )
        st.caption(
            f"Sheet: {SHEET_SIZE_CM}cm × {SHEET_SIZE_CM}cm | "
            f"Sticker: {STICKER_SIZE_CM}cm × {STICKER_SIZE_CM}cm | "
            f"{STICKERS_PER_ROW} × {STICKERS_PER_ROW} = {STICKERS_PER_SHEET} per sheet"
        )

    # ── History Tab ──
    with t_history:
        st.subheader("🗂️ Saved Calculations")
        if not st.session_state["history"]:
            st.info("No saved calculations yet. Click **💾 Save Calculation** to save the current run.")
        else:
            hist_rows = []
            for h in st.session_state["history"]:
                hist_rows.append({
                    "Agent": h["agent"],
                    "Date": h["date"],
                    "Buckets": h["num_buckets"],
                    "Units": h["total_units"],
                    "Revenue (R)": f"R{h['grand_revenue']:,.2f}",
                    "Cost (R)": f"R{h['grand_total_cost']:,.2f}",
                    "Profit (R)": f"R{h['grand_profit']:,.2f}",
                    "Margin (%)": f"{h['grand_margin']:.1f}%",
                })
            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)

            if st.button("🗑️ Clear History"):
                st.session_state["history"] = []
                st.rerun()

            # Export full history
            if len(st.session_state["history"]) > 0:
                last = st.session_state["history"][-1]
                hist_excel = build_excel(last)
                st.download_button(
                    label="📥 Export Full History to Excel",
                    data=hist_excel,
                    file_name=f"peony_history_{calc_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    main()