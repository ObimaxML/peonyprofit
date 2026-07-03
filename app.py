import streamlit as st
import math
import random
import pandas as pd
import datetime
from io import BytesIO

LOGO_URL = "https://cdn.abacus.ai/images/0b225e54-01c0-4c83-b1bf-70edd9fe4e70.png"

SHEET_SIZE_CM = 100
STICKER_SIZE_CM = 9
STICKERS_PER_ROW = SHEET_SIZE_CM // STICKER_SIZE_CM
STICKERS_PER_SHEET = STICKERS_PER_ROW ** 2  # 121

VARIANT_MAP = {"100g": 100, "200g": 200, "500g": 500, "1kg": 1000, "2kg": 2000, "5kg": 5000}
DEFAULT_PRICES = {"100g": 5.00, "200g": 12.00, "500g": 21.00, "1kg": 38.00, "2kg": 60.00, "5kg": 135.0}

# ── Session State Init ──
if "history" not in st.session_state:
    st.session_state["history"] = []
if "scenario_result" not in st.session_state:
    st.session_state["scenario_result"] = None
if "scenario_type" not in st.session_state:
    st.session_state["scenario_type"] = None
if "variants_list" not in st.session_state:
    st.session_state["variants_list"] = [
        {"size": "100g", "price": DEFAULT_PRICES["100g"], "sticker_req": False}
    ]


def add_variant():
    default_size = "100g"
    st.session_state["variants_list"].append(
        {"size": default_size, "price": DEFAULT_PRICES[default_size], "sticker_req": False}
    )


def remove_variant(idx):
    st.session_state["variants_list"].pop(idx)
    for key in [f"size_{idx}", f"price_{idx}", f"qty_{idx}", f"sticker_{idx}"]:
        st.session_state.pop(key, None)


def move_variant_up(idx):
    lst = st.session_state["variants_list"]
    if idx > 0:
        lst[idx], lst[idx - 1] = lst[idx - 1], lst[idx]


def move_variant_down(idx):
    lst = st.session_state["variants_list"]
    if idx < len(lst) - 1:
        lst[idx], lst[idx + 1] = lst[idx + 1], lst[idx]


def on_size_change(idx):
    new_size = st.session_state[f"size_{idx}"]
    new_price = DEFAULT_PRICES.get(new_size, 10.0)
    st.session_state["variants_list"][idx]["size"] = new_size
    st.session_state["variants_list"][idx]["price"] = new_price
    st.session_state[f"price_{idx}"] = new_price


def compute_profit(variants, bucket_cost, num_buckets, plastic_packs_cost,
                   labor_cost, cost_per_sticker_sheet, transport_cost,
                   delivery_cost, storage_cost, total_grams_available):
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

    grand_total_cost = (total_raw_material_cost + total_packaging_cost +
                        total_labor_cost + total_sticker_cost + total_logistics_cost)
    grand_revenue = sum(v["qty"] * v["price"] for v in variants)
    grand_profit = grand_revenue - grand_total_cost
    grand_margin = (grand_profit / grand_revenue * 100) if grand_revenue > 0 else 0
    mat_cpu = total_raw_material_cost / total_units if total_units > 0 else 0
    log_cpu = total_logistics_cost / total_units if total_units > 0 else 0

    perf_data = []
    for v in variants:
        cpu = mat_cpu + plastic_packs_cost + labor_cost + log_cpu + (sticker_cpu if v["sticker_req"] else 0)
        rev = v["qty"] * v["price"]
        cost = v["qty"] * cpu
        prof = rev - cost
        margin_v = (prof / rev * 100) if rev > 0 else 0
        perf_data.append({
            "Size": v["size"], "Units": v["qty"],
            "Material Used": f"{v['grams_used']:,}g",
            "Sticker": "Yes" if v["sticker_req"] else "No",
            "Price/Unit (R)": v["price"], "Cost/Unit (R)": round(cpu, 2),
            "Revenue (R)": round(rev, 2), "Profit (R)": round(prof, 2),
            "Margin (%)": f"{margin_v:.1f}%",
            "% Revenue": f"{(rev / grand_revenue * 100 if grand_revenue > 0 else 0):.1f}%",
            "% Profit": f"{(prof / grand_profit * 100 if grand_profit != 0 else 0):.1f}%"
        })

    return {
        "total_units": total_units, "total_grams_used": total_grams_used,
        "leftover_grams": leftover_grams, "stickered_units": stickered_units,
        "sheets_req": sheets_req, "total_sticker_cost": total_sticker_cost,
        "sticker_cpu": sticker_cpu, "total_raw_material_cost": total_raw_material_cost,
        "total_packaging_cost": total_packaging_cost, "total_labor_cost": total_labor_cost,
        "total_logistics_cost": total_logistics_cost, "grand_total_cost": grand_total_cost,
        "grand_revenue": grand_revenue, "grand_profit": grand_profit,
        "grand_margin": grand_margin, "mat_cpu": mat_cpu, "log_cpu": log_cpu,
        "perf_data": perf_data
    }


def random_allocate(variants_config, total_grams_available, plastic_packs_cost,
                    labor_cost, cost_per_sticker_sheet, mode):
    """
    Randomly distribute total_grams_available across variants.
    Each click produces a different split. Guided by mode:
      - 'optimal': weights random splits toward higher-margin variants
      - 'maximum': weights random splits toward higher absolute profit/gram variants
    """
    n = len(variants_config)
    if n == 0:
        return []

    # Score each variant
    scored = []
    for v in variants_config:
        grams = VARIANT_MAP[v["size"]]
        sticker_unit_cost = (cost_per_sticker_sheet / STICKERS_PER_SHEET) if v["sticker_req"] else 0
        variable_cpu = plastic_packs_cost + labor_cost + sticker_unit_cost
        rev_per_gram = v["price"] / grams
        cost_per_gram = variable_cpu / grams
        profit_per_gram = rev_per_gram - cost_per_gram
        margin_per_gram = (profit_per_gram / rev_per_gram * 100) if rev_per_gram > 0 else 0
        score = margin_per_gram if mode == "optimal" else profit_per_gram
        scored.append({**v, "grams": grams, "score": max(score, 0.01),
                       "profit_per_gram": profit_per_gram, "margin_per_gram": margin_per_gram})

    # Generate random weights biased toward the mode's score
    weights = [s["score"] for s in scored]
    total_weight = sum(weights)
    base_fractions = [w / total_weight for w in weights]

    # Add randomness: perturb fractions with Dirichlet-like noise
    noise = [random.random() for _ in range(n)]
    noise_sum = sum(noise)
    noise_fractions = [x / noise_sum for x in noise]

    # Blend: 60% score-guided + 40% pure random (tweak to taste)
    blend = 0.6
    blended = [blend * base_fractions[i] + (1 - blend) * noise_fractions[i] for i in range(n)]
    total_blended = sum(blended)
    final_fractions = [b / total_blended for b in blended]

    # Allocate grams according to blended fractions
    allocated = []
    remaining = total_grams_available
    for i, s in enumerate(scored):
        if i == len(scored) - 1:
            # Last variant gets whatever is left
            grams_for_variant = remaining
        else:
            grams_for_variant = int(final_fractions[i] * total_grams_available)
            # Snap down to nearest whole unit
            grams_for_variant = (grams_for_variant // s["grams"]) * s["grams"]
            grams_for_variant = min(grams_for_variant, remaining)

        qty = grams_for_variant // s["grams"]
        grams_used = qty * s["grams"]
        remaining -= grams_used
        allocated.append({
            **s,
            "qty": int(qty),
            "grams_used": int(grams_used),
        })

    return allocated


def run_scenario(mode, variants_config, bucket_cost, num_buckets, plastic_packs_cost,
                 labor_cost, cost_per_sticker_sheet, transport_cost, delivery_cost,
                 storage_cost, total_grams_available):

    allocated = random_allocate(
        variants_config, total_grams_available,
        plastic_packs_cost, labor_cost, cost_per_sticker_sheet, mode
    )

    result_variants = [{
        "size": a["size"], "qty": a["qty"], "price": a["price"],
        "sticker_req": a["sticker_req"], "grams_used": a["grams_used"]
    } for a in allocated]

    calc = compute_profit(result_variants, bucket_cost, num_buckets, plastic_packs_cost,
                          labor_cost, cost_per_sticker_sheet, transport_cost,
                          delivery_cost, storage_cost, total_grams_available)
    calc["allocation"] = allocated
    calc["mode"] = mode
    return calc


def build_excel(calc, agent_name, calc_date, history, plastic_packs_cost, labor_cost):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([{
            "Agent": agent_name, "Date": str(calc_date),
            "Total Units": calc["total_units"],
            "Total Revenue (R)": calc["grand_revenue"],
            "Total Cost (R)": calc["grand_total_cost"],
            "Total Profit (R)": calc["grand_profit"],
            "Margin (%)": round(calc["grand_margin"], 2),
            "Material Used (g)": calc["total_grams_used"],
            "Leftover (g)": calc["leftover_grams"],
        }]).to_excel(writer, sheet_name="Batch Summary", index=False)

        pd.DataFrame(calc["perf_data"]).to_excel(writer, sheet_name="Variant Performance", index=False)

        pd.DataFrame([
            {"Expense": "Raw Material", "Total (R)": calc["total_raw_material_cost"], "CPU (R)": round(calc["mat_cpu"], 2)},
            {"Expense": "Packaging",    "Total (R)": calc["total_packaging_cost"],    "CPU (R)": round(plastic_packs_cost, 2)},
            {"Expense": "Labor",        "Total (R)": calc["total_labor_cost"],        "CPU (R)": round(labor_cost, 2)},
            {"Expense": "Stickers",     "Total (R)": calc["total_sticker_cost"],      "CPU (R)": round(calc["sticker_cpu"], 2)},
            {"Expense": "Logistics",    "Total (R)": calc["total_logistics_cost"],    "CPU (R)": round(calc["log_cpu"], 2)},
            {"Expense": "TOTAL",        "Total (R)": calc["grand_total_cost"],
             "CPU (R)": round(calc["grand_total_cost"] / calc["total_units"] if calc["total_units"] > 0 else 0, 2)},
        ]).to_excel(writer, sheet_name="Cost Breakdown", index=False)

        pd.DataFrame([{
            "Transport (R)": calc.get("transport_cost", 0),
            "Delivery (R)": calc.get("delivery_cost", 0),
            "Storage (R)": calc.get("storage_cost", 0),
            "Total Logistics (R)": calc["total_logistics_cost"],
            "Per Unit (R)": round(calc["log_cpu"], 2),
        }]).to_excel(writer, sheet_name="Logistics", index=False)

        pd.DataFrame([{
            "Stickered Units": calc["stickered_units"],
            "Sheets Required": calc["sheets_req"],
            "Total Sticker Cost (R)": calc["total_sticker_cost"],
            "Cost per Sticker (R)": round(calc["sticker_cpu"], 2),
            "Stickers per Sheet": STICKERS_PER_SHEET,
        }]).to_excel(writer, sheet_name="Stickers", index=False)

        if history:
            pd.DataFrame([{
                "Agent": h.get("agent", ""), "Date": h.get("date", ""),
                "Units": h.get("total_units", 0),
                "Revenue (R)": h.get("grand_revenue", 0),
                "Profit (R)": h.get("grand_profit", 0),
                "Margin (%)": h.get("grand_margin", 0),
            } for h in history]).to_excel(writer, sheet_name="Saved History", index=False)

    output.seek(0)
    return output


def render_scenario_result(result, label, grand_revenue, grand_total_cost, grand_profit, grand_margin):
    st.success(f"✅ {label} scenario calculated!")

    st.subheader(f"{label} — Projected Metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Projected Revenue", f"R{result['grand_revenue']:,.2f}",
              delta=f"R{result['grand_revenue'] - grand_revenue:+,.2f}")
    m2.metric("Projected Cost", f"R{result['grand_total_cost']:,.2f}",
              delta=f"R{result['grand_total_cost'] - grand_total_cost:+,.2f}")
    m3.metric("Projected Profit", f"R{result['grand_profit']:,.2f}",
              delta=f"R{result['grand_profit'] - grand_profit:+,.2f}")
    m4.metric("Projected Margin", f"{result['grand_margin']:.1f}%",
              delta=f"{result['grand_margin'] - grand_margin:+.1f}%")

    st.divider()
    st.subheader("📦 Proposed Unit Allocation")
    st.caption("Randomised allocation of material across variants — click again for a new split.")
    alloc_rows = [{
        "Size": a["size"],
        "Proposed Units": a["qty"],
        "Grams Allocated": f"{a['grams_used']:,}g",
        "Selling Price (R)": a["price"],
        "Sticker": "Yes" if a["sticker_req"] else "No",
        "Profit/gram (R)": round(a["profit_per_gram"], 4),
        "Margin/gram (%)": f"{a['margin_per_gram']:.2f}%",
        "Est. Revenue (R)": round(a["qty"] * a["price"], 2),
    } for a in result["allocation"]]
    alloc_df = pd.DataFrame(alloc_rows)
    st.dataframe(alloc_df, use_container_width=True, hide_index=True)

    alloc_chart = alloc_df[alloc_df["Proposed Units"] > 0][["Size", "Proposed Units"]].set_index("Size")
    if not alloc_chart.empty:
        st.bar_chart(alloc_chart)

    st.divider()
    st.subheader("📊 Current vs Scenario")
    comp_df = pd.DataFrame([
        {"Metric": "Revenue (R)",  "Current": f"R{grand_revenue:,.2f}",    "Scenario": f"R{result['grand_revenue']:,.2f}",    "Diff": f"R{result['grand_revenue'] - grand_revenue:+,.2f}"},
        {"Metric": "Cost (R)",     "Current": f"R{grand_total_cost:,.2f}", "Scenario": f"R{result['grand_total_cost']:,.2f}", "Diff": f"R{result['grand_total_cost'] - grand_total_cost:+,.2f}"},
        {"Metric": "Profit (R)",   "Current": f"R{grand_profit:,.2f}",     "Scenario": f"R{result['grand_profit']:,.2f}",     "Diff": f"R{result['grand_profit'] - grand_profit:+,.2f}"},
        {"Metric": "Margin (%)",   "Current": f"{grand_margin:.1f}%",      "Scenario": f"{result['grand_margin']:.1f}%",      "Diff": f"{result['grand_margin'] - grand_margin:+.1f}%"},
    ])
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

    st.bar_chart(pd.DataFrame({
        "Metric": ["Revenue", "Cost", "Profit"],
        "Current (R)": [grand_revenue, grand_total_cost, grand_profit],
        f"{label} (R)": [result["grand_revenue"], result["grand_total_cost"], result["grand_profit"]]
    }).set_index("Metric"))

    st.divider()
    st.subheader("📈 Variant Performance (Scenario)")
    st.dataframe(pd.DataFrame(result["perf_data"]), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🪣 Material Usage")
    mu1, mu2 = st.columns(2)
    mu1.metric("Total Used", f"{result['total_grams_used']:,}g")
    mu2.metric("Leftover", f"{result['leftover_grams']:,}g")


def main():
    st.set_page_config(page_title="Product Profit Calculator", layout="wide")

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:20px;margin-bottom:10px;">'
        f'<img src="{LOGO_URL}" width="100"/>'
        f'<h1 style="margin:0;">Product Profit Calculator</h1></div>',
        unsafe_allow_html=True
    )
    st.divider()

    # ── SIDEBAR ──
    with st.sidebar:
        st.header("⚙️ Settings")

        with st.expander("👤 Session Info", expanded=True):
            agent_name = st.text_input("Agent Name", value="")
            calc_date = st.date_input("Date", value=datetime.date.today())

        with st.expander("🪣 Inventory", expanded=True):
            bucket_cost = st.number_input("Cost of 5kg Bucket (R)", min_value=0.0, value=95.0)
            num_buckets = st.number_input("Buckets Purchased", min_value=1, value=1, step=1)
            total_grams_available = num_buckets * 5000
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

        variants_list = st.session_state["variants_list"]
        grams_allocated = 0
        final_variants = []

        for i, v in enumerate(variants_list):
            with st.container(border=True):
                c_h, c_u, c_d, c_r = st.columns([3, 1, 1, 1])
                c_h.markdown(f"**Variant {i + 1}**")
                if c_u.button("▲", key=f"up_{i}", disabled=(i == 0)):
                    move_variant_up(i); st.rerun()
                if c_d.button("▼", key=f"dn_{i}", disabled=(i == len(variants_list) - 1)):
                    move_variant_down(i); st.rerun()
                if c_r.button("🗑", key=f"rm_{i}", disabled=(len(variants_list) == 1)):
                    remove_variant(i); st.rerun()

                st.selectbox(
                    "Size",
                    list(VARIANT_MAP.keys()),
                    index=list(VARIANT_MAP.keys()).index(
                        st.session_state["variants_list"][i]["size"]
                    ),
                    key=f"size_{i}",
                    on_change=on_size_change,
                    args=(i,)
                )

                current_size = st.session_state[f"size_{i}"]
                current_price = st.session_state["variants_list"][i]["price"]
                v_grams = VARIANT_MAP[current_size]
                max_units = max(0, (total_grams_available - grams_allocated) // v_grams)

                col_q, col_p = st.columns(2)

                qty = col_q.number_input(
                    f"Units (Max {int(max_units)})",
                    min_value=0,
                    max_value=int(max_units),
                    value=min(int(max_units), 1),
                    step=1,
                    key=f"qty_{i}"
                )

                price = col_p.number_input(
                    "Price (R)",
                    min_value=0.0,
                    value=float(current_price),
                    step=0.50,
                    key=f"price_{i}"
                )

                sticker = st.toggle(
                    "Sticker?",
                    value=st.session_state["variants_list"][i].get("sticker_req", False),
                    key=f"sticker_{i}"
                )

                variants_list[i]["size"] = current_size
                variants_list[i]["price"] = price
                variants_list[i]["sticker_req"] = sticker

                grams_used = qty * v_grams
                grams_allocated += grams_used
                final_variants.append({
                    "size": current_size, "qty": qty, "price": price,
                    "sticker_req": sticker, "grams_used": grams_used
                })

        st.button(
            "➕ Add Variant",
            on_click=add_variant,
            disabled=(len(variants_list) >= 6),
            use_container_width=True
        )
        if len(variants_list) >= 6:
            st.caption("Maximum 6 variants reached.")

    # ── CALCULATIONS ──
    calc = compute_profit(
        final_variants, bucket_cost, num_buckets, plastic_packs_cost,
        labor_cost, cost_per_sticker_sheet, transport_cost,
        delivery_cost, storage_cost, total_grams_available
    )

    grand_revenue        = calc["grand_revenue"]
    grand_total_cost     = calc["grand_total_cost"]
    grand_profit         = calc["grand_profit"]
    grand_margin         = calc["grand_margin"]
    total_units          = calc["total_units"]
    total_grams_used     = calc["total_grams_used"]
    leftover_grams       = calc["leftover_grams"]
    mat_cpu              = calc["mat_cpu"]
    log_cpu              = calc["log_cpu"]
    stickered_units      = calc["stickered_units"]
    sheets_req           = calc["sheets_req"]
    total_sticker_cost   = calc["total_sticker_cost"]
    sticker_cpu          = calc["sticker_cpu"]
    total_logistics_cost = calc["total_logistics_cost"]
    total_raw_mat_cost   = calc["total_raw_material_cost"]
    total_pack_cost      = calc["total_packaging_cost"]
    total_labor_cost     = calc["total_labor_cost"]

    cost_breakdown = [
        {"Expense": "Raw Material", "Total (R)": round(total_raw_mat_cost, 2),   "CPU (R)": round(mat_cpu, 2)},
        {"Expense": "Packaging",    "Total (R)": round(total_pack_cost, 2),      "CPU (R)": round(plastic_packs_cost, 2)},
        {"Expense": "Labor",        "Total (R)": round(total_labor_cost, 2),     "CPU (R)": round(labor_cost, 2)},
        {"Expense": "Stickers",     "Total (R)": round(total_sticker_cost, 2),   "CPU (R)": round(sticker_cpu, 2)},
        {"Expense": "Logistics",    "Total (R)": round(total_logistics_cost, 2), "CPU (R)": round(log_cpu, 2)},
        {"Expense": "TOTAL",        "Total (R)": round(grand_total_cost, 2),
         "CPU (R)": round(grand_total_cost / total_units if total_units > 0 else 0, 2)},
    ]

    calc_snapshot = {
        "agent": agent_name or "—", "date": str(calc_date),
        "num_buckets": num_buckets, "total_units": total_units,
        "grand_revenue": round(grand_revenue, 2),
        "grand_total_cost": round(grand_total_cost, 2),
        "grand_profit": round(grand_profit, 2),
        "grand_margin": round(grand_margin, 2),
        "total_grams_used": total_grams_used,
        "leftover_grams": leftover_grams,
        "perf_data": calc["perf_data"],
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
        "total_raw_material_cost": round(total_raw_mat_cost, 2),
        "total_packaging_cost": round(total_pack_cost, 2),
        "total_labor_cost": round(total_labor_cost, 2),
        "mat_cpu": round(mat_cpu, 2),
        "plastic_packs_cost": plastic_packs_cost,
        "labor_cost": labor_cost,
    }

    # ── TOP ACTION BAR ──
    st.markdown(f"**Agent:** {agent_name or '—'} &nbsp;|&nbsp; **Date:** {calc_date}")
    b1, b2, b3, b4, _ = st.columns([1, 1, 1.5, 1.5, 1])

    with b1:
        if st.button("💾 Save"):
            st.session_state["history"].append(calc_snapshot)
            st.success("Saved!")

    with b2:
        excel_data = build_excel(
            calc_snapshot, agent_name, calc_date,
            st.session_state["history"], plastic_packs_cost, labor_cost
        )
        st.download_button(
            "📥 Export", excel_data,
            file_name=f"peony_profit_{calc_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with b3:
        if st.button("🎯 Optimal Profit", use_container_width=True):
            variants_config = [{"size": v["size"], "price": v["price"], "sticker_req": v["sticker_req"]} for v in final_variants]
            st.session_state["scenario_result"] = run_scenario(
                "optimal", variants_config, bucket_cost, num_buckets,
                plastic_packs_cost, labor_cost, cost_per_sticker_sheet,
                transport_cost, delivery_cost, storage_cost, total_grams_available
            )
            st.session_state["scenario_type"] = "optimal"

    with b4:
        if st.button("🚀 Maximum Profit", use_container_width=True):
            variants_config = [{"size": v["size"], "price": v["price"], "sticker_req": v["sticker_req"]} for v in final_variants]
            st.session_state["scenario_result"] = run_scenario(
                "maximum", variants_config, bucket_cost, num_buckets,
                plastic_packs_cost, labor_cost, cost_per_sticker_sheet,
                transport_cost, delivery_cost, storage_cost, total_grams_available
            )
            st.session_state["scenario_type"] = "maximum"

    st.divider()

    # ── SCENARIO RESULTS ──
    if st.session_state["scenario_result"] is not None:
        result = st.session_state["scenario_result"]
        stype = st.session_state["scenario_type"]
        label = "🎯 Optimal Profit" if stype == "optimal" else "🚀 Maximum Profit"

        with st.container(border=True):
            render_scenario_result(
                result, label,
                grand_revenue, grand_total_cost, grand_profit, grand_margin
            )
            if st.button("✖ Clear Scenario"):
                st.session_state["scenario_result"] = None
                st.session_state["scenario_type"] = None
                st.rerun()

        st.divider()

    # ── TABS ──
    t_profit, t_log, t_stick, t_history = st.tabs([
        "📊 Profit", "🚚 Logistics", "🏷️ Stickers", "🗂️ History"
    ])

    with t_profit:
        st.subheader("Batch Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue", f"R{grand_revenue:,.2f}")
        m2.metric("Cost", f"R{grand_total_cost:,.2f}")
        m3.metric("Profit", f"R{grand_profit:,.2f}")
        m4.metric("Margin", f"{grand_margin:.1f}%")

        if grand_margin >= 30:
            st.success(f"✅ Margin: **{grand_margin:.1f}%** — Healthy!")
        elif grand_margin >= 10:
            st.warning(f"⚠️ Margin: **{grand_margin:.1f}%** — Moderate.")
        else:
            st.error(f"❌ Margin: **{grand_margin:.1f}%** — Low, review costs.")

        if total_grams_used > total_grams_available:
            st.error(f"⚠️ Stock Overlimit: {total_grams_used - total_grams_available:,}g deficit!")
        else:
            st.info(f"Inventory: {total_grams_used:,}g used | {leftover_grams:,}g remaining")

        st.divider()
        st.subheader("Variant Performance")
        st.dataframe(pd.DataFrame(calc["perf_data"]), use_container_width=True, hide_index=True)

        chart_df = pd.DataFrame([{
            "Size": r["Size"], "Profit (R)": r["Profit (R)"], "Revenue (R)": r["Revenue (R)"]
        } for r in calc["perf_data"]])
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Profit by Variant")
            st.bar_chart(chart_df.set_index("Size")[["Profit (R)"]])
        with c2:
            st.subheader("Revenue by Variant")
            st.bar_chart(chart_df.set_index("Size")[["Revenue (R)"]])

        with st.expander("📱 Mobile Cards"):
            for row in calc["perf_data"]:
                st.markdown(f"**{row['Size']}** | Margin: {row['Margin (%)']}")
                mc1, mc2 = st.columns(2)
                mc1.metric("Revenue", f"R{row['Revenue (R)']:,.2f}")
                mc2.metric("Profit", f"R{row['Profit (R)']:,.2f}")
                st.divider()

        st.divider()
        st.subheader("Cost Breakdown")
        st.table(pd.DataFrame(cost_breakdown))

    with t_log:
        st.subheader("Logistics Costs")
        c1, c2, c3 = st.columns(3)
        c1.metric("Transport", f"R{transport_cost:.2f}")
        c2.metric("Delivery", f"R{delivery_cost:.2f}")
        c3.metric("Storage", f"R{storage_cost:.2f}")
        st.info(
            f"**Total:** R{total_logistics_cost:.2f} | "
            f"**Per Unit:** R{log_cpu:.2f} | "
            f"**% of Cost:** {(total_logistics_cost / grand_total_cost * 100 if grand_total_cost > 0 else 0):.1f}%"
        )

    with t_stick:
        st.subheader("Sticker Requirements")
        s1, s2 = st.columns(2)
        s1.metric("Units Needing Stickers", stickered_units)
        s2.metric("Sheets to Order", sheets_req)
        s1, s2 = st.columns(2)
        s1.metric("Total Sticker Cost", f"R{total_sticker_cost:.2f}")
        s2.metric("Cost per Sticker", f"R{sticker_cpu:.2f}")
        st.info(
            f"**Stickers per Sheet:** {STICKERS_PER_SHEET} | "
            f"**Cost per Sheet:** R{cost_per_sticker_sheet:.2f}"
        )

    with t_history:
        st.subheader("Saved Calculations")
        if st.session_state["history"]:
            hist_rows = [{
                "Agent": h.get("agent", ""), "Date": h.get("date", ""),
                "Units": h.get("total_units", 0),
                "Revenue (R)": f"R{h['grand_revenue']:,.2f}",
                "Profit (R)": f"R{h['grand_profit']:,.2f}",
                "Margin (%)": f"{h['grand_margin']:.1f}%"
            } for h in st.session_state["history"]]
            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)

            hist_excel = build_excel(
                st.session_state["history"][-1], agent_name, calc_date,
                st.session_state["history"], plastic_packs_cost, labor_cost
            )
            st.download_button(
                "📥 Export Full History", hist_excel,
                file_name=f"peony_history_{calc_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            if st.button("🗑️ Clear History"):
                st.session_state["history"] = []
                st.rerun()
        else:
            st.info("No saved calculations yet.")


if __name__ == "__main__":
    main()