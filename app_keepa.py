import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
import plotly.express as px

# ========== KEEPPA CONFIG ==========
KEEPA_API_KEY = "bbtkbdtj3tmv6ua13f22nb8ncbmckfitsfk31pvruejet24dklp76kv1h4s7f49u"  # Replace with your actual key

# ========== ASIN Extractor ==========
def extract_asin(url):
    if "/dp/" in url:
        return url.split("/dp/")[1].split("/")[0].split("?")[0]
    elif "/gp/product/" in url:
        return url.split("/gp/product/")[1].split("/")[0].split("?")[0]
    return None

# ========== Fetch Data ==========
def fetch_keepa_data(asin):
    url = f"https://api.keepa.com/product?key={KEEPA_API_KEY}&domain=3&buybox=1&history=1&asin={asin}"
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Keepa API Error: {r.status_code} — {r.text}")
    return r.json()

# ========== Process Data ==========
def process_keepa_data(json_data):
    product = json_data['products'][0]
    price_data = product['csv'][1]  # BuyBox price history
    base = datetime.datetime(2011, 1, 1)
    timestamps = [base + datetime.timedelta(minutes=5 * i) for i in range(len(price_data))]
    df = pd.DataFrame({
        "date": timestamps[:len(price_data)],
        "price_raw": price_data[:len(timestamps)]
    })
    df = df[df["price_raw"] > 0]
    df["price"] = df["price_raw"] / 100
    return df

# ========== Streamlit App ==========
st.set_page_config(page_title="Amazon Price Drop Predictor")
st.title("Amazon Price Drop Predictor")

url = st.text_input("Paste Amazon Product Link:")

if url:
    asin = extract_asin(url)
    if not asin:
        st.error("Could not extract ASIN from URL.")
    else:
        st.info(f"ASIN: {asin}")
        try:
            raw_data = fetch_keepa_data(asin)
            df = process_keepa_data(raw_data)

            if df.empty:
                st.warning("No valid price data found.")
            else:
                # Show current price
                latest_price = df.iloc[-1]["price"]
                st.metric("Current Price", f"€{latest_price:.2f}")

                # 📉 7-Day Price Chart — even if price hasn't changed
                st.subheader("7-Day Price History")

                seven_days_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
                last_7_days = df[df["date"] > seven_days_ago]

                if not last_7_days.empty:
                    # Keep only last 7 days' data
                    chart_data = last_7_days
                else:
                    # Simulate a flat line using last known price
                    last_price = df.iloc[-1]["price"]
                    dates = pd.date_range(end=pd.Timestamp.now(), periods=7)
                    chart_data = pd.DataFrame({"date": dates, "price": [last_price]*7})
                    st.info("Price hasn't changed in the last 7 days — showing stable price.")

                # Plot chart
                fig = px.line(chart_data, x="date", y="price",
                              title="Price Over Last 7 Days",
                              labels={"price": "Price (€)", "date": "Date"})
                st.plotly_chart(fig, use_container_width=True)


                # Drop prediction (simple heuristic)
                df_recent = df.tail(10)
                price_std = df_recent["price"].std()
                drop_events = (df_recent["price"].diff() < -1).sum()

                st.subheader("Prediction")
                if price_std < 1.0 and drop_events == 0:
                    st.success("This product's price is very stable. A drop is unlikely.")
                elif drop_events >= 1:
                    st.warning("Recent price drops detected. A drop may be coming.")
                else:
                    st.info("No strong signal either way. Price may remain stable.")

        except Exception as e:
            st.error(f"Error: {e}")
