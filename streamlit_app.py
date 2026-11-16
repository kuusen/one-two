import math
import requests
import streamlit as st

st.set_page_config(page_title="Калькулятор позиции", page_icon="📊", layout="centered")
st.title("Калькулятор позиции", anchor=False)

# ---------- Загрузка списков ----------

@st.cache_data(ttl=600)
def load_stocks():
    """Список акций TQBR: [(secid, shortname, lotsize), ...]"""
    url = (
        "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/"
        "securities.json?iss.meta=off&iss.only=securities"
        "&securities.columns=SECID,SHORTNAME,LOTSIZE"
    )
    try:
        r = requests.get(url, timeout=15)
        block = r.json().get("securities", {})
        cols = block.get("columns", [])
        data = block.get("data", [])
        idx = {name: i for i, name in enumerate(cols)}
        result = []
        for row in data:
            secid = row[idx["SECID"]]
            name = row[idx["SHORTNAME"]] or secid
            lotsize = row[idx["LOTSIZE"]] or 1
            result.append((secid, name, int(lotsize)))
        return result
    except Exception:
        return []

@st.cache_data(ttl=600)
def load_futures():
    """Список фьючерсов RFUD: [(secid, shortname, stepprice), ...]"""
    url = (
        "https://iss.moex.com/iss/engines/futures/markets/forts/boards/RFUD/"
        "securities.json?iss.meta=off&iss.only=securities"
        "&securities.columns=SECID,SHORTNAME,STEPPRICE"
    )
    try:
        r = requests.get(url, timeout=15)
        block = r.json().get("securities", {})
        cols = block.get("columns", [])
        data = block.get("data", [])
        idx = {name: i for i, name in enumerate(cols)}
        result = []
        for row in data:
            secid = row[idx["SECID"]]
            name = row[idx["SHORTNAME"]] or secid
            stepprice = row[idx["STEPPRICE"]]
            if stepprice:
                result.append((secid, name, float(stepprice)))
        return result
    except Exception:
        return []

stocks = load_stocks()
futures = load_futures()

# ---------- Формируем опции ----------

options = []

for secid, name, lotsize in stocks:
    options.append({
        "label": f"{secid} — {name} (акция)",
        "secid": secid,
        "type": "stock",
        "lotsize": lotsize,
    })

for secid, name, stepprice in futures:
    options.append({
        "label": f"{secid} — {name} (фьючерс)",
        "secid": secid,
        "type": "futures",
        "step_price": stepprice,
    })

options.sort(key=lambda x: x["label"])
labels = [o["label"] for o in options]

# ---------- Выбор инструмента ----------

selected_label = st.selectbox(
    "Выберите тикер",
    options=labels if labels else ["— список недоступен —"],
    index=0,
    help="Список подгружается с MOEX ISS и кэшируется на 10 минут.",
)
selected = next((o for o in options if o["label"] == selected_label), None)

# ---------- Форма ----------

with st.form("calc"):
    st.markdown("Параметры расчёта", anchors=False)

    stop_rub = st.number_input("Размер стопа, ₽", min_value=0.01, value=1000.0, step=100.0)

    if selected and selected["type"] == "futures":
        ticks = st.number_input("Стоп в тиках", min_value=1, value=10, step=1)
        rub_to_stop = None
        lotsize = None
    else:
        rub_to_stop = st.number_input(
            "Рублей до стопа",
            min_value=0.01,
            value=0.37,
            step=0.01,
            format="%.2f",
            help="Разница между ценой покупки и ценой стопа в рублях (на 1 бумагу)"
        )
        lotsize = selected["lotsize"] if selected else 1
        st.caption(f"Размер лота: {lotsize}")

    submitted = st.form_submit_button("Рассчитать", use_container_width=True)

# ---------- Расчёт ----------

if submitted:
    if selected is None:
        st.error("Инструмент не выбран.")
        st.stop()

    if selected["type"] == "futures":
        # Логика для фьючерсов
        step_price = selected["step_price"]

        if step_price and step_price > 0:
            st.success(f"Инструмент: **{selected['label']}** · шаг цены = **{step_price} ₽**")
            qty_raw = stop_rub / (ticks * step_price)
            qty = math.floor(qty_raw)

            st.metric("Количество контрактов", f"{qty}")
            st.caption(f"Точное значение до округления: {qty_raw:.4f}")

            if qty < 1:
                st.warning("Размер стопа слишком мал — округлённое количество меньше 1.")

            with st.expander("Показать расчёт"):
                st.write("**Формула:** `qty = stop_rub / (ticks × step_price)`")
                st.write(f"`qty = {stop_rub} / ({ticks} × {step_price}) = {qty_raw:.4f} → {qty}`")
        else:
            st.error("Шаг цены не определён в базе MOEX.")

    else:
        # Логика для акций
        if rub_to_stop <= 0:
            st.error("Значение «Рублей до стопа» должно быть положительным.")
            st.stop()

        qty_lots_raw = stop_rub / (rub_to_stop * lotsize)
        qty_lots = math.floor(qty_lots_raw)
        qty_shares = qty_lots * lotsize

        st.success(f"Инструмент: **{selected['label']}** · лот = **{lotsize}**")
        st.metric("Количество лотов", f"{qty_lots}")
        st.caption(f"Количество бумаг: {qty_shares}")

        if qty_lots < 1:
            st.warning("Размер стопа слишком мал — округлённое количество лотов меньше 1.")

        with st.expander("Показать расчёт"):
            st.write("**Формула:** `qty_lots = stop_rub / (rub_to_stop × lotsize)`")
            st.write(f"`qty_lots = {stop_rub} / ({rub_to_stop:.2f} × {lotsize}) = {qty_lots_raw:.4f} → {qty_lots}`")
            st.write(f"`qty_shares = {qty_lots} × {lotsize} = {qty_shares}`")
