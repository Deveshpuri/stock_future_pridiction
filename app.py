import streamlit as st
import yfinance as yf
from prophet import Prophet
import plotly.graph_objs as go
import pandas as pd
from datetime import date
import io
import uuid
import os
import plotly.io as pio

# Set page configuration
st.set_page_config(page_title="StockPulse: Forecast", layout="wide")

# Custom CSS to mimic the original design
st.markdown("""
<style>
    body {
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #0a1733, #000000);
        color: #ffffff;
    }
    .stApp {
        background: transparent;
    }
    .main-container {
        max-width: 1200px;
        margin: auto;
        padding: 2rem;
    }
    .card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border-radius: 1rem;
        padding: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: transform 0.3s ease;
    }
    .card:hover {
        transform: translateY(-5px);
    }
    .glow-input, .glow-select {
        background: #1e293b !important;
        border: 2px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 0.5rem !important;
        padding: 0.75rem !important;
        color: #ffffff !important;
    }
    .glow-input:focus, .glow-select:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 10px rgba(59, 130, 246, 0.5) !important;
    }
    .glow-button {
        background: linear-gradient(90deg, #3b82f6, #0a1733) !important;
        border: none !important;
        border-radius: 0.5rem !important;
        padding: 0.75rem 1.5rem !important;
        color: white !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease !important;
    }
    .glow-button:hover {
        transform: scale(1.05) !important;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.7) !important;
    }
    .stSpinner > div {
        border: 4px solid rgba(255, 255, 255, 0.2);
        border-top: 4px solid #3b82f6;
        border-radius: 50%;
        width: 32px;
        height: 32px;
        animation: spin 1s linear infinite;
        margin: 1rem auto;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .fade-in {
        animation: fadeIn 0.5s ease-in;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .title {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(to right, #60a5fa, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

# Temporary storage for forecast data
if 'FORECAST_STORAGE' not in st.session_state:
    st.session_state.FORECAST_STORAGE = {}

# List of popular Indian stocks
POPULAR_STOCKS = {
    "Reliance Industries": "RELIANCE",
    "Tata Consultancy Services": "TCS",
    "Infosys": "INFY",
    "HDFC Bank": "HDFCBANK",
    "ICICI Bank": "ICICIBANK",
    "Wipro": "WIPRO",
    "Bharti Airtel": "BHARTIARTL",
    "Asian Paints": "ASIANPAINT",
    "Hindustan Unilever": "HINDUNILVR",
    "Bajaj Finance": "BAJFINANCE"
}

def main():
    # Main container
    with st.container():
        st.markdown('<div class="main-container">', unsafe_allow_html=True)
        
        # Title
        st.markdown('<h1 class="title fade-in">StockPulse</h1>', unsafe_allow_html=True)
        
        # Theme toggle (simplified)
        theme = st.session_state.get('theme', 'dark')
        if st.checkbox("Light Theme", value=theme == 'light'):
            st.session_state.theme = 'light'
        else:
            st.session_state.theme = 'dark'

        # Form
        with st.form(key="stock_form", clear_on_submit=False):
            st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
            
            # Stock input and selection
            col1, col2 = st.columns(2)
            with col1:
                ticker = st.text_input("Stock Symbol (e.g., RELIANCE or AAPL; .NS added for Indian stocks)", 
                                     key="ticker", 
                                     placeholder="Enter stock symbol").strip().upper()
            with col2:
                stock_select = st.selectbox("Select a stock", 
                                           [""] + list(POPULAR_STOCKS.keys()), 
                                           format_func=lambda x: x if x else "Select a stock",
                                           key="stock_select")
                if stock_select:
                    ticker = POPULAR_STOCKS[stock_select]
                    st.session_state.ticker = ticker
            
            # Prediction period
            col3, col4 = st.columns(2)
            with col3:
                period_type = st.selectbox("Prediction Period", ["days", "months", "years"], key="period_type")
            with col4:
                if period_type == "days":
                    period_value = st.number_input("Days", min_value=1, max_value=90, value=30, key="period_days")
                elif period_type == "months":
                    period_value = st.selectbox("Months", list(range(1, 13)), key="period_months")
                else:
                    period_value = st.selectbox("Years", list(range(1, 5)), key="period_years")
            
            submit_button = st.form_submit_button("Generate Forecast", type="primary")
            
            st.markdown('</div>', unsafe_allow_html=True)

        # Process form submission
        if submit_button and ticker:
            with st.spinner("Generating forecast..."):
                # Calculate period
                try:
                    if period_type == "days":
                        period = period_value
                    elif period_type == "months":
                        period = period_value * 30
                    else:
                        period = period_value * 365
                except ValueError as e:
                    st.error(f"Invalid period value: {str(e)}")
                    return

                # Add .NS for Indian stocks
                if '.' not in ticker:
                    ticker = f"{ticker}.NS"

                stock_info = {'ticker': ticker}

                # Fetch stock data
                try:
                    end_date = date.today().strftime("%Y-%m-%d")
                    data = yf.download(ticker, start="2018-01-01", end=end_date, progress=False)
                    if data.empty:
                        raise ValueError(f"No data found for stock symbol {ticker}")
                    
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    stock_info = {
                        "ticker": ticker,
                        "name": info.get("longName", ticker),
                        "price": f"{info.get('regularMarketPrice', 'N/A')} {info.get('currency', '')}",
                        "market_cap": f"{info.get('marketCap', 'N/A') / 1e9:.2f}B {info.get('currency', '')}" if isinstance(info.get('marketCap'), (int, float)) else "N/A",
                        "sector": info.get("sector", "N/A")
                    }
                except Exception as e:
                    st.error(f"Error loading data for symbol {ticker}: {str(e)}")
                    suggestions = [symbol for name, symbol in POPULAR_STOCKS.items() if ticker.replace('.NS', '').lower() in symbol.lower() or ticker.replace('.NS', '').lower() in name.lower()]
                    suggestions = [f"{s}.NS" for s in suggestions]
                    if suggestions:
                        st.warning(f"Did you mean: {', '.join(suggestions)}?")
                    return

                # Prepare data for Prophet
                df_train = data[['Close']].reset_index()
                df_train.columns = ["ds", "y"]
                df_train['y'] = pd.to_numeric(df_train['y'], errors='coerce')
                df_train = df_train.dropna(subset=['y'])

                if df_train.shape[0] < 2:
                    st.error("Not enough data to generate a forecast.")
                    return

                # Generate forecast
                try:
                    m = Prophet()
                    m.fit(df_train)
                    future = m.make_future_dataframe(periods=period)
                    forecast = m.predict(future)

                    forecast_data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
                    forecast_data.columns = ['Date', 'Forecast', 'Lower Bound', 'Upper Bound']

                    forecast_id = str(uuid.uuid4())
                    st.session_state.FORECAST_STORAGE[forecast_id] = forecast_data

                    # Create Plotly figure
                    fig = go.Figure()

                    fig.add_trace(go.Scatter(
                        x=df_train['ds'], y=df_train['y'],
                        mode='lines', name='Historical',
                        line=dict(color='#3b82f6'),
                        hovertemplate='%{y:.2f}<br>%{x|%Y-%m-%d}'
                    ))

                    fig.add_trace(go.Scatter(
                        x=forecast['ds'], y=forecast['yhat'],
                        mode='lines', name='Forecast',
                        line=dict(color='#60a5fa'),
                        hovertemplate='%{y:.2f}<br>%{x|%Y-%m-%d}'
                    ))

                    fig.add_trace(go.Scatter(
                        x=forecast['ds'], y=forecast['yhat_upper'],
                        mode='lines', name='Upper Bound',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'
                    ))

                    fig.add_trace(go.Scatter(
                        x=forecast['ds'], y=forecast['yhat_lower'],
                        mode='lines', name='Lower Bound',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor='rgba(59, 130, 246, 0.2)',
                        showlegend=True,
                        hovertemplate='Lower: %{y:.2f}<br>%{x|%Y-%m-%d}'
                    ))

                    fig.update_layout(
                        title=f"{stock_info['name']} Forecast for {period_value} {period_type.capitalize()}",
                        xaxis_title='Date',
                        yaxis_title='Stock Price',
                        template='plotly_dark' if st.session_state.theme == 'dark' else 'plotly_white',
                        hovermode='x unified',
                        hoverlabel=dict(
                            bgcolor='rgba(0, 0, 0, 0.9)',
                            font=dict(color='white', family='Poppins, sans-serif'),
                            bordercolor='#3b82f6'
                        ),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        margin=dict(l=20, r=20, t=60, b=20),
                        font=dict(family="Poppins, sans-serif", color="#ffffff"),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)'),
                        yaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)')
                    )

                    # Display stock info
                    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
                    st.subheader(stock_info['name'])
                    col5, col6, col7 = st.columns(3)
                    with col5:
                        st.markdown(f"**Current Price**: {stock_info['price']}")
                    with col6:
                        st.markdown(f"**Market Cap**: {stock_info['market_cap']}")
                    with col7:
                        st.markdown(f"**Sector**: {stock_info['sector']}")
                    st.markdown('</div>', unsafe_allow_html=True)

                    # Display plot
                    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)

                    # Save plot as image
                    try:
                        folder = "pridiction of the stock"
                        os.makedirs(folder, exist_ok=True)
                        image_name = f"{date.today().strftime('%Y-%m-%d')}_{ticker.replace('.NS', '')}.png"
                        image_path = os.path.join(folder, image_name)
                        pio.write_image(fig, file=image_path, format='png', width=1200, height=600)
                        st.write(f"Graph saved as {image_name}")
                    except Exception as e:
                        st.warning(f"Error saving image: {str(e)}")
                        image_path = "Failed to save image"

                    # Download forecast button
                    buffer = io.StringIO()
                    forecast_data.to_csv(buffer, index=False)
                    buffer.seek(0)
                    st.download_button(
                        label="Download Forecast (CSV)",
                        data=buffer.getvalue(),
                        file_name=f"{ticker}_forecast.csv",
                        mime="text/csv",
                        key="download_button"
                    )

                    # Clean up storage
                    del st.session_state.FORECAST_STORAGE[forecast_id]
                    
                    st.markdown('</div>', unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error generating forecast: {str(e)}")

if __name__ == "__main__":
    main()