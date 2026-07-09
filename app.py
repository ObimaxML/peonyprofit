import streamlit as st
import math
import random
import pandas as pd
import datetime
from io import BytesIO

# ---------- Config / Constants ----------
LOGO_URL = "https://cdn.abacus.ai/images/0b225e54-01c0-4c83-b1bf-70edd9fe4e70.png"
STICKERS_PER_SHEET = 81
COMP_SIZES = ["50g", "100g", "200g", "250g", "500g", "1kg", "2kg", "5kg"]
VARIANT_MAP = {"50g": 50, "100g": 100, "200g": 200, "250g": 250, "500g": 500, "1kg": 1000, "2kg": 2000, "5kg": 5000}
DEFAULT_PRICES = {"50g": 3.00, "100g": 6.00, "200g": 12.00, "250g": 15.00, "500g": 28.00, "1kg": 50.00, "2kg": 95.00, "5kg": 220.0}
OUR_BRAND = "Peony Fresh"
PAYMENT_METHODS = ["Cash", "EFT", "Card", "SnapScan", "Zapper", "Credit (30 days)", "Other"]

# Pre-filled competitor prices (typical South African retail/market levels; sources: Makro, PnP, PriceShare, PriceCheck)
INITIAL_COMPETITORS = [
    {"name": "Omo Multi-Active", "prices": {"50g": None, "100g": 5.50, "200g": None, "250g": 12.00, "500g": 22.00, "1kg": 40.00, "2kg": 75.00, "5kg": 210.00}},
    {"name": "Sunlight 2-in-1",  "prices": {"50g": None, "100g": 4.50, "200g": None, "250g": 11.50, "500g": 21.00, "1kg": 38.00, "2kg": 68.00, "5kg": 185.00}},
    {"name": "Maq",              "prices": {"50g": None, "100g": 4.00, "200g": None, "250g": 10.00, "500g": 18.00, "1kg": 32.00, "2kg": 60.00, "5kg": 160.00}},
    {"name": "Surf Bright",      "prices": {"50g": None, "100g": 4.00, "200g": None, "250g": 9.50,  "500g": 19.00, "1kg": 35.00, "2kg": 62.00, "5kg": 170.00}},
    {"name": "Ariel Auto",       "prices": {"50g": None, "100g": 6.00, "200g": None, "250g": 14.00, "500g": 25.00, "1kg": 45.00, "2kg": 85.00, "5kg": 230.00}},
]

# ---------- Session State Initialization ----------
if "history" not in st.session_state:
    st.session_state["history"] = []
if "variants_list" not in st.session_state:
    st.session_state["variants_list"] = [
        {"size": "250g", "price": DEFAULT_PRICES.get("250g", 15.0), "spaza": True, "sticker_req": True, "qty": 1}
    ]
if "prospects" not in st.session_state:
    st.session_state["prospects"] = []
if "competitors" not in st.session_state:
    st.session_state["competitors"] = INITIAL_COMPETITORS.copy()
if "scenario_result" not in st.session_state:
    st.session_state["scenario_result"] = None
if "scenario_type" not in st.session_state:
    st.session_state["scenario_type"] = None
if "edit_prospect_idx" not in st.session_state:
    st.session_state["edit_prospect_idx"] = None

# ---------- Helper Functions ----------
def add_variant():
    st.session_state["variants_list"].append({"size": "250g", "price": DEFAULT_PRICES.get("250g", 15.0), "spaza": True, "sticker_req": True, "qty": 1})

def remove_variant(idx):
    st.session_state["variants_list"].pop(idx)
    # cleanup keys possibly created
    for k in [f"size_{idx}", f"price_{idx}", f"qty_{idx}", f"spaza_{idx}", f"sticker_{idx}"]:
        st.session_state.pop(k, None)

def move_variant_up(idx):
    lst = st.session_state["variants_list"]
    if idx > 0:
        lst[idx], lst[idx-1] = lst[idx-1], lst[idx]

def move_variant_down(idx):
    lst = st.session_state["variants_list"]
    if idx < len(lst)-1:
        lst[idx], lst[idx+1] = lst[idx+1], lst[idx]

def add_competitor(name="New Competitor"):
    st.session_state["competitors"].append({"name": name, "prices": {s: None for s in COMP_SIZES}})

def remove_competitor(idx):
    st.session_state["competitors"].pop(idx)

# Core compute_profit returns other_cpu to avoid KeyError
def compute_profit(variants, bucket_cost, num_buckets, plastic_packs_cost,
                   labor_cost, other_overhead_per_unit, cost_per_sticker_sheet,
                   transport_cost, delivery_cost, storage_cost, total_grams_available):
    total_units = sum(v.get("qty", 0) for v in variants)
    total_grams_used = sum(v.get("grams_used", 0) for v in variants)
    leftover_grams = total_grams_available - total_grams_used

    stickered_units = sum(v.get("qty", 0) for v in variants if v.get("sticker_req"))
    sheets_req = math.ceil(stickered_units / STICKERS_PER_SHEET) if stickered_units > 0 else 0
    total_sticker_cost = sheets_req * cost_per_sticker_sheet
    sticker_cpu = total_sticker_cost / stickered_units if stickered_units > 0 else 0

    total_raw_material_cost = bucket_cost * num_buckets
    total_packaging_cost = plastic_packs_cost * total_units
    total_labor_cost = labor_cost * total_units
    total_other_cost = other_overhead_per_unit * total_units
    total_logistics_cost = transport_cost + delivery_cost + storage_cost

    grand_total_cost = (total_raw_material_cost + total_packaging_cost +
                        total_labor_cost + total_other_cost + total_sticker_cost + total_logistics_cost)
    grand_revenue = sum(v.get("qty", 0) * v.get("price", 0) for v in variants)
    grand_profit = grand_revenue - grand_total_cost
    grand_margin = (grand_profit / grand_revenue * 100) if grand_revenue > 0 else 0
    mat_cpu = total_raw_material_cost / total_units if total_units > 0 else 0
    log_cpu = total_logistics_cost / total_units if total_units > 0 else 0

    perf_data = []
    for v in variants:
        cpu = (mat_cpu + plastic_packs_cost + labor_cost + other_overhead_per_unit +
               log_cpu + (sticker_cpu if v.get("sticker_req") else 0))
        rev = v.get("qty", 0) * v.get("price", 0)
        cost = v.get("qty", 0) * cpu
        prof = rev - cost
        margin_v = (prof / rev * 100) if rev > 0 else 0
        perf_data.append({
            "Size": v.get("size"),
            "Units": v.get("qty", 0),
            "Material Used": f"{v.get('grams_used',0):,}g",
            "Spaza Sale": "Yes" if v.get("spaza") else "No",
            "Sticker": "Yes" if v.get("sticker_req") else "No",
            "Price/Unit (R)": v.get("price", 0),
            "Cost/Unit (R)": round(cpu, 2),
            "Revenue (R)": round(rev, 2),
            "Profit (R)": round(prof, 2),
            "Margin (%)": f"{margin_v:.1f}%",
        })

    return {
        "total_units": total_units,
        "total_grams_used": total_grams_used,
        "leftover_grams": leftover_grams,
        "stickered_units": stickered_units,
        "sheets_req": sheets_req,
        "total_sticker_cost": total_sticker_cost,
        "sticker_cpu": sticker_cpu,
        "total_raw_material_cost": total_raw_material_cost,
        "total_packaging_cost": total_packaging_cost,
        "total_labor_cost": total_labor_cost,
        "total_other_cost": total_other_cost,
        "other_cpu": other_overhead_per_unit,
        "total_logistics_cost": total_logistics_cost,
        "grand_total_cost": grand_total_cost,
        "grand_revenue": grand_revenue,
        "grand_profit": grand_profit,
        "grand_margin": grand_margin,
        "mat_cpu": mat_cpu,
        "log_cpu": log_cpu,
        "perf_data": perf_data
    }

# Random allocation helper (keeps other_overhead_per_unit in CPU calc)
def random_allocate(variants_config, total_grams_available, plastic_packs_cost,
                    labor_cost, other_overhead_per_unit, cost_per_sticker_sheet, mode):
    n = len(variants_config)
    if n == 0:
        return []
    scored = []
    for v in variants_config:
        grams = VARIANT_MAP[v["size"]]
        sticker_unit_cost = (cost_per_sticker_sheet / STICKERS_PER_SHEET) if v.get("sticker_req") else 0
        variable_cpu = plastic_packs_cost + labor_cost + other_overhead_per_unit + sticker_unit_cost
        rev_per_gram = v["price"] / grams if grams > 0 else 0
        cost_per_gram = variable_cpu / grams if grams > 0 else 0
        profit_per_gram = rev_per_gram - cost_per_gram
        margin_per_gram = (profit_per_gram / rev_per_gram * 100) if rev_per_gram > 0 else 0
        score = margin_per_gram if mode == "optimal" else profit_per_gram
        scored.append({**v, "grams": grams, "score": max(score, 0.01),
                       "profit_per_gram": profit_per_gram, "margin_per_gram": margin_per_gram})

    weights = [s["score"] for s in scored]
    total_weight = sum(weights)
    base_fractions = [w / total_weight for w in weights]
    noise = [random.random() for _ in range(n)]
    noise_sum = sum(noise)
    noise_fractions = [x / noise_sum for x in noise]
    blend = 0.6
    blended = [blend * base_fractions[i] + (1 - blend) * noise_fractions[i] for i in range(n)]
    total_blended = sum(blended)
    final_fractions = [b / total_blended for b in blended]

    allocated = []
    remaining = total_grams_available
    for i, s in enumerate(scored):
        if i == len(scored) - 1:
            grams_for_variant = remaining
        else:
            grams_for_variant = int(final_fractions[i] * total_grams_available)
            grams_for_variant = (grams_for_variant // s["grams"]) * s["grams"]
            grams_for_variant = min(grams_for_variant, remaining)
        qty = grams_for_variant // s["grams"] if s["grams"] > 0 else 0
        grams_used = qty * s["grams"]
        remaining -= grams_used
        allocated.append({**s, "qty": int(qty), "grams_used": int(grams_used)})
    return allocated

def run_scenario(mode, variants_config, bucket_cost, num_buckets, plastic_packs_cost,
                 labor_cost, other_overhead_per_unit, cost_per_sticker_sheet, transport_cost, delivery_cost,
                 storage_cost, total_grams_available):
    allocated = random_allocate(variants_config, total_grams_available,
                                plastic_packs_cost, labor_cost, other_overhead_per_unit, cost_per_sticker_sheet, mode)
    result_variants = [{
        "size": a["size"], "qty": a["qty"], "price": a["price"],
        "spaza": a.get("spaza", True), "sticker_req": a.get("sticker_req", True), "grams_used": a["grams_used"]
    } for a in allocated]
    calc = compute_profit(result_variants, bucket_cost, num_buckets, plastic_packs_cost,
                          labor_cost, other_overhead_per_unit, cost_per_sticker_sheet,
                          transport_cost, delivery_cost, storage_cost, total_grams_available)
    calc["allocation"] = allocated
    calc["mode"] = mode
    return calc

# Excel export builder includes competitors and cost breakdown
def build_excel(calc_snapshot, agent_name, calc_date):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([{
            "Agent": agent_name or "—",
            "Date": str(calc_date),
            "Total Units": calc_snapshot.get("total_units", 0),
            "Revenue (R)": calc_snapshot.get("grand_revenue", 0),
            "Profit (R)": calc_snapshot.get("grand_profit", 0),
            "Margin (%)": calc_snapshot.get("grand_margin", 0)
        }]).to_excel(writer, sheet_name="Summary", index=False)

        pd.DataFrame(calc_snapshot.get("perf_data", [])).to_excel(writer, sheet_name="Variant Performance", index=False)

        pd.DataFrame(calc_snapshot.get("cost_breakdown", [])).to_excel(writer, sheet_name="Cost Breakdown", index=False)

        # Competitors
        pd.DataFrame([{
            "Competitor": c["name"],
            **{s: c["prices"].get(s) for s in COMP_SIZES}
        } for c in st.session_state["competitors"]]).to_excel(writer, sheet_name="Competitors", index=False)

        if st.session_state["prospects"]:
            pd.DataFrame(st.session_state["prospects"]).to_excel(writer, sheet_name="Prospects", index=False)
    output.seek(0)
    return output

# Render the unit economics guide for a chosen variant
def render_pricing_guide_for_variant(variant, bucket_cost, plastic_packs_cost, labor_cost,
                                    other_overhead_per_unit, cost_per_sticker_sheet,
                                    transport_cost, delivery_cost, storage_cost,
                                    num_buckets, total_units):
    st.subheader(f"📖 Unit Economics Guide — {variant['size']} (Peony Fresh)")

    v_grams = VARIANT_MAP[variant["size"]]
    packs_per_bucket = 5000 / v_grams if v_grams > 0 else 0
    powder_cpu = (bucket_cost / packs_per_bucket) if packs_per_bucket > 0 else 0
    sticker_cpu = cost_per_sticker_sheet / STICKERS_PER_SHEET
    base_cost = powder_cpu + sticker_cpu + plastic_packs_cost

    total_logistics = transport_cost + delivery_cost + storage_cost
    if total_units > 0:
        log_cpu = total_logistics / total_units
    else:
        assumed_units = num_buckets * packs_per_bucket if packs_per_bucket > 0 else 0
        log_cpu = total_logistics / assumed_units if assumed_units > 0 else 0

    full_cost = base_cost + labor_cost + other_overhead_per_unit + log_cpu

    st.markdown("#### 1️⃣ Base Product & Packaging Cost")
    base_df = pd.DataFrame([
        {"Item": f"{variant['size']} Pack (Powder portion)", "Calculation": f"R{bucket_cost:.2f} ÷ {int(packs_per_bucket) if packs_per_bucket>0 else 0}", "Cost (R)": round(powder_cpu, 2)},
        {"Item": "Sticker", "Calculation": f"R{cost_per_sticker_sheet:.2f} ÷ {STICKERS_PER_SHEET}", "Cost (R)": round(sticker_cpu, 2)},
        {"Item": "Plastic Bag", "Calculation": "per unit", "Cost (R)": round(plastic_packs_cost, 2)},
        {"Item": "Base Total", "Calculation": "", "Cost (R)": round(base_cost, 2)},
    ])
    st.dataframe(base_df, use_container_width=True, hide_index=True)

    st.markdown("#### 2️⃣ Full Cost per Pack (including Overheads)")
    full_df = pd.DataFrame([
        {"Item": "Base Total", "Cost (R)": round(base_cost, 2)},
        {"Item": "Labour", "Cost (R)": round(labor_cost, 2)},
        {"Item": "Other Overhead", "Cost (R)": round(other_overhead_per_unit, 2)},
        {"Item": "Logistics (per unit share)", "Cost (R)": round(log_cpu, 2)},
        {"Item": "Total Cost", "Cost (R)": round(full_cost, 2)},
    ])
    st.dataframe(full_df, use_container_width=True, hide_index=True)

    st.markdown("#### 3️⃣ Your Price vs Competitors")
    comp_rows = []
    for c in st.session_state["competitors"]:
        comp_price = c["prices"].get(variant["size"])
        comp_rows.append({"Brand": c["name"], "Price (R)": f"R{comp_price:.2f}" if comp_price not in (None, "") else "—"})
    comp_rows.insert(0, {"Brand": f"⭐ {OUR_BRAND} (Your Price)", "Price (R)": f"R{variant['price']:.2f}"})
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

    st.markdown("#### 4️⃣ Suggested Wholesale Prices (based on Peony cost)")
    wholesale_rows = []
    for margin in [0.15, 0.23, 0.29, 0.35]:
        price = full_cost / (1 - margin) if (1 - margin) > 0 else 0
        profit = price - full_cost
        wholesale_rows.append({
            "Sell to Spaza (R)": f"R{price:.2f}",
            "Profit per Pack (R)": f"R{profit:.2f}",
            "Margin": f"{margin*100:.0f}%"
        })
    st.dataframe(pd.DataFrame(wholesale_rows), use_container_width=True, hide_index=True)

    st.markdown("#### 5️⃣ Profit per 5kg Bag (pack count depends on size)")
    bag_packs = int(5000 / v_grams) if v_grams>0 else 0
    bag_rows = []
    for wp in [10.0, 11.0, 12.0, 13.0]:
        bag_revenue = wp * bag_packs
        bag_cost = full_cost * bag_packs
        bag_profit = bag_revenue - bag_cost
        bag_margin = (bag_profit / bag_revenue) * 100 if bag_revenue > 0 else 0
        bag_rows.append({
            "Wholesale Price (R)": f"R{wp:.2f}",
            "Bag Revenue (R)": f"R{bag_revenue:.2f}",
            "Bag Cost (R)": f"R{bag_cost:.2f}",
            "Bag Profit (R)": f"R{bag_profit:.2f}",
            "Bag Margin": f"{bag_margin:.1f}%"
        })
    st.dataframe(pd.DataFrame(bag_rows), use_container_width=True, hide_index=True)

    st.markdown("#### 6️⃣ Suggested Retail Price (Spaza)")
    retail_rows = []
    for wp in [10.0, 11.0, 12.0, 13.0]:
        retail_low = wp * 1.20
        retail_high = wp * 1.30
        retail_rows.append({
            "Your Selling Price (R)": f"R{wp:.2f}",
            "Suggested Retail (R)": f"R{retail_low:.0f} – R{retail_high:.0f}",
            "Spaza Margin": "20–30%"
        })
    st.dataframe(pd.DataFrame(retail_rows), use_container_width=True, hide_index=True)

    st.info("Formula: Selling Price = Product Cost + Labour + Transport + Other Costs + Desired Profit")

# ---------- App UI ----------
def main():
    st.set_page_config(page_title="Peony Fresh — Profit Calculator", layout="wide")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:20px;margin-bottom:10px;">'
        f'<img src="{LOGO_URL}" width="90"/>'
        f'<h1 style="margin:0;">Peony Fresh — Product Profit Calculator</h1></div>',
        unsafe_allow_html=True
    )
    st.divider()

    # Sidebar: settings separated into sections
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

        with st.expander("📦 Packaging, Labour & Overhead", expanded=True):
            plastic_packs_cost = st.number_input("Unit Pack Cost (R)", min_value=0.0, value=0.70)
            labor_cost = st.number_input("Unit Labour Cost (R)", min_value=0.0, value=0.80)
            other_overhead_per_unit = st.number_input("Other Overhead per Unit (R)", min_value=0.0, value=0.40, help="Electricity, tape, wastage, etc.")

        with st.expander("🏷️ Stickers", expanded=False):
            cost_per_sticker_sheet = st.number_input("Cost per Sticker Sheet (R) — e.g. 81 stickers", min_value=0.0, value=170.0)

        with st.expander("🚚 Logistics", expanded=False):
            transport_cost = st.number_input("Transport (Total R)", min_value=0.0, value=0.0)
            delivery_cost = st.number_input("Delivery (Total R)", min_value=0.0, value=0.0)
            storage_cost = st.number_input("Storage (Total R)", min_value=0.0, value=0.0)

        st.divider()
        st.subheader("🛒 Product Variants")
        variants_list = st.session_state["variants_list"]

        grams_allocated = 0
        final_variants = []
        main_variant = variants_list[0] if variants_list else {"size": "250g", "price": DEFAULT_PRICES.get("250g", 15.0), "qty": 1}
        for i, v in enumerate(variants_list):
            with st.container():
                c_h, c_u, c_d, c_r = st.columns([3, 1, 1, 1])
                c_h.markdown(f"**Variant {i + 1}**")
                if c_u.button("▲", key=f"up_{i}", disabled=(i == 0)):
                    move_variant_up(i); st.rerun()
                if c_d.button("▼", key=f"dn_{i}", disabled=(i == len(variants_list) - 1)):
                    move_variant_down(i); st.rerun()
                if c_r.button("🗑", key=f"rm_{i}", disabled=(len(variants_list) == 1)):
                    remove_variant(i); st.rerun()

                size = st.selectbox(
                    "Size",
                    list(VARIANT_MAP.keys()),
                    index=list(VARIANT_MAP.keys()).index(v["size"]),
                    key=f"size_{i}"
                )
                current_size = st.session_state[f"size_{i}"]
                v_grams = VARIANT_MAP[current_size]
                max_units = max(0, (total_grams_available - grams_allocated) // v_grams)

                col_spaza, col_sticker, col_q, col_p = st.columns(4)
                spaza = col_spaza.checkbox("Spaza?", value=v.get("spaza", True), key=f"spaza_{i}")
                sticker = col_sticker.checkbox("Sticker?", value=v.get("sticker_req", True), key=f"sticker_{i}")
                
                # Fix for max_value error
                current_qty = int(v.get("qty", 1))
                max_units_final = max(current_qty, int(max_units))  # Ensure max_value is at least current qty
                
                qty = col_q.number_input(
                    f"Units (Max {int(max_units)})",
                    min_value=0, max_value=max_units_final,
                    value=current_qty, step=1, key=f"qty_{i}"
                )
                price = col_p.number_input(
                    "Price (R)", min_value=0.0, value=float(v.get("price", DEFAULT_PRICES.get(current_size, 15.0))),
                    step=0.50, key=f"price_{i}"
                )

                variants_list[i]["size"] = current_size
                variants_list[i]["price"] = price
                variants_list[i]["spaza"] = spaza
                variants_list[i]["sticker_req"] = sticker
                variants_list[i]["qty"] = qty

                grams_used = qty * v_grams
                grams_allocated += grams_used
                final_variants.append({
                    "size": current_size, "qty": qty, "price": price,
                    "spaza": spaza, "sticker_req": sticker, "grams_used": grams_used
                })

                if i == 0:
                    main_variant = variants_list[i]

        st.button("➕ Add Variant", on_click=add_variant, disabled=(len(variants_list) >= 6), use_container_width=True)
        if len(variants_list) >= 6:
            st.caption("Maximum 6 variants reached.")

        st.divider()
        st.subheader("🏷️ Competitor Prices")
        st.caption("Add competitor names and their prices for standard sizes. These appear in the Pricing Guide.")
        for idx, comp in enumerate(st.session_state["competitors"]):
            with st.expander(f"Competitor {idx+1}: {comp['name']}", expanded=False):
                c1, c2 = st.columns([3,1])
                new_name = c1.text_input("Brand Name", value=comp["name"], key=f"comp_name_{idx}")
                if new_name != comp["name"]:
                    st.session_state["competitors"][idx]["name"] = new_name
                price_cols = st.columns(len(COMP_SIZES))
                for j, s in enumerate(COMP_SIZES):
                    current_val = comp["prices"].get(s)
                    # default to 0.0 if None for input control
                    entered = price_cols[j].number_input(s, min_value=0.0, value=float(current_val) if current_val not in (None,"") else 0.0, key=f"comp_{idx}_{s}")
                    st.session_state["competitors"][idx]["prices"][s] = entered
                if st.button("Remove Competitor", key=f"rm_comp_{idx}"):
                    remove_competitor(idx)
                    st.rerun()
        if st.button("➕ Add Competitor"):
            add_competitor(f"Competitor {len(st.session_state['competitors'])+1}")
            st.rerun()

    # ---------- CALCULATIONS ----------
    calc = compute_profit(
        final_variants, bucket_cost, num_buckets, plastic_packs_cost,
        labor_cost, other_overhead_per_unit, cost_per_sticker_sheet,
        transport_cost, delivery_cost, storage_cost, total_grams_available
    )

    # prepare cost_breakdown (adds Units column)
    cost_breakdown = [
        {"Expense": "Raw Material", "Units": calc["total_units"], "Total (R)": round(calc["total_raw_material_cost"], 2), "CPU (R)": round(calc["mat_cpu"], 2)},
        {"Expense": "Packaging",    "Units": calc["total_units"], "Total (R)": round(calc["total_packaging_cost"], 2),    "CPU (R)": round(plastic_packs_cost, 2)},
        {"Expense": "Labor",        "Units": calc["total_units"], "Total (R)": round(calc["total_labor_cost"], 2),        "CPU (R)": round(labor_cost, 2)},
        {"Expense": "Other Overhead","Units": calc["total_units"], "Total (R)": round(calc["total_other_cost"],2),       "CPU (R)": round(calc["other_cpu"], 2)},
        {"Expense": "Stickers",     "Units": calc["stickered_units"], "Total (R)": round(calc["total_sticker_cost"], 2),   "CPU (R)": round(calc["sticker_cpu"], 2)},
        {"Expense": "Logistics",    "Units": calc["total_units"], "Total (R)": round(calc["total_logistics_cost"], 2), "CPU (R)": round(calc["log_cpu"], 2)},
        {"Expense": "TOTAL",        "Units": calc["total_units"], "Total (R)": round(calc["grand_total_cost"], 2),
         "CPU (R)": round(calc["grand_total_cost"] / calc["total_units"] if calc["total_units"] > 0 else 0, 2)},
    ]

    calc_snapshot = {
        "agent": agent_name or "—", "date": str(calc_date),
        "num_buckets": num_buckets, "total_units": calc["total_units"],
        "grand_revenue": round(calc["grand_revenue"], 2),
        "grand_total_cost": round(calc["grand_total_cost"], 2),
        "grand_profit": round(calc["grand_profit"], 2),
        "grand_margin": round(calc["grand_margin"], 2),
        "total_grams_used": calc["total_grams_used"],
        "leftover_grams": calc["leftover_grams"],
        "perf_data": calc["perf_data"],
        "cost_breakdown": cost_breakdown,
        "transport_cost": transport_cost,
        "delivery_cost": delivery_cost,
        "storage_cost": storage_cost,
        "total_logistics_cost": round(calc["total_logistics_cost"], 2),
        "log_cpu": calc["log_cpu"],
        "stickered_units": calc["stickered_units"],
        "sheets_req": calc["sheets_req"],
        "cost_per_sticker_sheet": cost_per_sticker_sheet,
        "total_sticker_cost": round(calc["total_sticker_cost"], 2),
        "sticker_cpu": calc["sticker_cpu"],
        "total_raw_material_cost": round(calc["total_raw_material_cost"], 2),
        "total_packaging_cost": round(calc["total_packaging_cost"], 2),
        "total_labor_cost": round(calc["total_labor_cost"], 2),
        "other_overhead_per_unit": other_overhead_per_unit,
        "total_other_cost": round(calc["total_other_cost"], 2),
        "other_cpu": calc["other_cpu"],
        "mat_cpu": round(calc["mat_cpu"], 2),
        "plastic_packs_cost": plastic_packs_cost,
        "labor_cost": labor_cost,
    }

    # ---------- TOP ACTION BAR ----------
    st.markdown(f"**Agent:** {agent_name or '—'} &nbsp;|&nbsp; **Date:** {calc_date}")
    b1, b2, b3, b4, _ = st.columns([1, 1, 1.5, 1.5, 1])

    with b1:
        if st.button("💾 Save"):
            st.session_state["history"].append(calc_snapshot)
            st.success("Saved!")

    with b2:
        excel_data = build_excel(calc_snapshot, agent_name, calc_date)
        st.download_button(
            "📥 Export Excel", excel_data,
            file_name=f"peony_profit_{calc_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with b3:
        if st.button("🎯 Optimal Profit", use_container_width=True):
            variants_config = [{
                "size": v["size"], "price": v["price"], "spaza": v["spaza"],
                "sticker_req": v["sticker_req"]
            } for v in final_variants]
            st.session_state["scenario_result"] = run_scenario(
                "optimal", variants_config, bucket_cost, num_buckets,
                plastic_packs_cost, labor_cost, other_overhead_per_unit, cost_per_sticker_sheet,
                transport_cost, delivery_cost, storage_cost, total_grams_available
            )
            st.session_state["scenario_type"] = "optimal"

    with b4:
        if st.button("🚀 Maximum Profit", use_container_width=True):
            variants_config = [{
                "size": v["size"], "price": v["price"], "spaza": v["spaza"],
                "sticker_req": v["sticker_req"]
            } for v in final_variants]
            st.session_state["scenario_result"] = run_scenario(
                "maximum", variants_config, bucket_cost, num_buckets,
                plastic_packs_cost, labor_cost, other_overhead_per_unit, cost_per_sticker_sheet,
                transport_cost, delivery_cost, storage_cost, total_grams_available
            )
            st.session_state["scenario_type"] = "maximum"

    st.divider()

    # If a scenario result exists, show guide for scenario allocation main variant
    if st.session_state["scenario_result"] is not None:
        result = st.session_state["scenario_result"]
        st.subheader(f"Scenario Result — {result.get('mode','')}")
        # Use the first allocated variant as the scenario main
        allocated = result.get("allocation", [])
        if allocated:
            scenario_main = {"size": allocated[0]["size"], "price": allocated[0].get("price", DEFAULT_PRICES.get(allocated[0]["size"], 0))}
            render_pricing_guide_for_variant(
                scenario_main, bucket_cost, plastic_packs_cost, labor_cost, other_overhead_per_unit,
                cost_per_sticker_sheet, transport_cost, delivery_cost, storage_cost, num_buckets, calc["total_units"]
            )
        if st.button("✖ Clear Scenario"):
            st.session_state["scenario_result"] = None
            st.session_state["scenario_type"] = None
            st.rerun()

    st.divider()

    # ---------- TABS ----------
    t_profit, t_guide, t_log, t_stick, t_prospects, t_history = st.tabs([
        "📊 Profit", "💰 Pricing Guide", "🚚 Logistics", "🏷️ Stickers", "👥 Prospects", "🗂️ History"
    ])

    with t_profit:
        st.subheader("Batch Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue", f"R{calc['grand_revenue']:,.2f}")
        m2.metric("Cost", f"R{calc['grand_total_cost']:,.2f}")
        m3.metric("Profit", f"R{calc['grand_profit']:,.2f}")
        m4.metric("Margin", f"{calc['grand_margin']:.1f}%")

        if calc['grand_margin'] >= 30:
            st.success(f"✅ Margin: **{calc['grand_margin']:.1f}%** — Healthy!")
        elif calc['grand_margin'] >= 10:
            st.warning(f"⚠️ Margin: **{calc['grand_margin']:.1f}%** — Moderate.")
        else:
            st.error(f"❌ Margin: **{calc['grand_margin']:.1f}%** — Low, review costs.")

        if calc['total_grams_used'] > total_grams_available:
            st.error(f"⚠️ Stock Overlimit: {calc['total_grams_used'] - total_grams_available:,}g deficit!")
        else:
            st.info(f"Inventory: {calc['total_grams_used']:,}g used | {calc['leftover_grams']:,}g remaining")

        st.divider()
        st.subheader("Variant Performance")
        st.dataframe(pd.DataFrame(calc["perf_data"]), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Cost Breakdown")
        st.table(pd.DataFrame(cost_breakdown))

    with t_guide:
        st.subheader("Unit Economics Guide")
        if final_variants:
            options = [f"{v['size']} — R{v['price']:.2f} — {v['qty']} units" for v in final_variants]
            sel = st.selectbox("Select Variant", options, index=0)
            sel_idx = options.index(sel)
            selected_variant = final_variants[sel_idx]
        else:
            st.info("No variants defined — using default 250g.")
            selected_variant = {"size": "250g", "price": DEFAULT_PRICES.get("250g", 15.0), "qty": 1}

        render_pricing_guide_for_variant(
            selected_variant, bucket_cost, plastic_packs_cost, labor_cost, other_overhead_per_unit,
            cost_per_sticker_sheet, transport_cost, delivery_cost, storage_cost, num_buckets, calc["total_units"]
        )

    with t_log:
        st.subheader("Logistics Costs")
        c1, c2, c3 = st.columns(3)
        c1.metric("Transport", f"R{transport_cost:.2f}")
        c2.metric("Delivery", f"R{delivery_cost:.2f}")
        c3.metric("Storage", f"R{storage_cost:.2f}")
        st.info(
            f"**Total:** R{calc['total_logistics_cost']:.2f} | "
            f"**Per Unit:** R{calc['log_cpu']:.2f} | "
            f"**% of Cost:** {(calc['total_logistics_cost'] / calc['grand_total_cost'] * 100 if calc['grand_total_cost'] > 0 else 0):.1f}%"
        )

    with t_stick:
        st.subheader("Sticker Requirements")
        s1, s2 = st.columns(2)
        s1.metric("Units Needing Stickers", calc["stickered_units"])
        s2.metric("Sheets to Order", calc["sheets_req"])
        s1, s2 = st.columns(2)
        s1.metric("Total Sticker Cost", f"R{calc['total_sticker_cost']:.2f}")
        s2.metric("Cost per Sticker", f"R{calc['sticker_cpu']:.2f}")
        st.info(
            f"**Stickers per Sheet:** {STICKERS_PER_SHEET} | "
            f"**Cost per Sheet:** R{cost_per_sticker_sheet:.2f}"
        )

    with t_prospects:
        st.subheader("Prospect Manager")
        st.info("Use the sidebar Prospect tools (if implemented) to add and manage prospects. (Light prospect UI available in earlier versions.)")

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

            hist_excel = build_excel(st.session_state["history"][-1], agent_name, calc_date)
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