import streamlit as st
import yfinance as yf
from prophet import Prophet
import plotly.graph_objs as go
import pandas as pd
from datetime import date, timedelta
import io
import uuid
import os
import plotly.io as pio
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Temporary storage for forecast data
FORECAST_STORAGE = {}

# List of popular Indian stocks for dropdown
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

# Streamlit page configuration
st.set_page_config(page_title="StockPulse: Forecast", layout="wide")

# Custom CSS for animated gradient background and styling
st.markdown("""
<style>
.stApp {
    background: linear-gradient(to right, #0a1733, #000000, #0a1733);
    background-size: 200% 100%;
    animation: gradientShift 15s ease infinite;
    min-height: 100vh;
    color: #ffffff;
}
@keyframes gradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
h1, h2, h3, h4, h5, h6 {
    color: #ffffff;
    font-family: 'Poppins', sans-serif;
}
.stButton>button {
    background: linear-gradient(90deg, #3b82f6, #0a1733);
    color: white;
    border: none;
    border-radius: 0.5rem;
    padding: 0.5rem 1rem;
}
.stTextInput>div>input, .stSelectbox>div>select, .stNumberInput>div>input {
    background: #1e293b;
    color: #ffffff;
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 0.5rem;
}
.stCheckbox>label {
    color: #ffffff;
}
.stMetric {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 0.5rem;
    padding: 0.5rem;
}
.analysis-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 0.5rem;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.analysis-card h3 {
    margin-top: 0;
    color: #ffffff;
}
.analysis-card p {
    margin: 0.5rem 0;
    color: #d1d5db;
    font-family: 'Poppins', sans-serif;
}
.recommendation-buy {
    color: #10b981;
    font-weight: bold;
}
.recommendation-sell {
    color: #ef4444;
    font-weight: bold;
}
.recommendation-hold {
    color: #facc15;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# Title
st.title("StockPulse: Advanced Stock Forecasting")

# Cache yfinance data
@st.cache_data(ttl=3600)
def fetch_stock_data(ticker, start_date, end_date):
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        return data if not data.empty else None
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {str(e)}")
        return None

@st.cache_data(ttl=3600)
def fetch_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.info, stock.quarterly_financials
    except Exception as e:
        logger.error(f"Error fetching info for {ticker}: {str(e)}")
        return None, None

# Input form
st.header("Stock Selection")
with st.form(key="stock_form"):
    col1, col2 = st.columns(2)
    with col1:
        ticker1 = st.text_input("Stock Symbol (e.g., RELIANCE or AAPL; .NS added for Indian stocks)", "")
        stock_select1 = st.selectbox("Select Stock", [""] + list(POPULAR_STOCKS.keys()), index=0, key="stock1")
        if stock_select1:
            ticker1 = POPULAR_STOCKS[stock_select1]
        if ticker1 and ticker1.strip():
            if '.' not in ticker1 and not any(ticker1.lower() in s.lower() for s in POPULAR_STOCKS.values()):
                st.warning("Invalid ticker. Try a popular stock or ensure correct format (e.g., RELIANCE or AAPL).")
    with col2:
        period_type = st.selectbox("Prediction Period", ["Days", "Months", "Years"])
        if period_type == "Days":
            period_value = st.number_input("Days (1-90)", min_value=1, max_value=90, value=30)
        elif period_type == "Months":
            period_value = st.selectbox("Months", list(range(1, 13)), index=0)
        else:  # Years
            period_value = st.selectbox("Years", list(range(1, 5)), index=0)
        start_date = st.date_input("Historical Data Start Date", value=date.today() - timedelta(days=5*365), min_value=date(2000, 1, 1), max_value=date.today())
    
    st.subheader("Chart Options")
    col3, col4 = st.columns(2)
    with col3:
        show_historical = st.checkbox("Show Historical Data", value=True)
        show_forecast = st.checkbox("Show Forecast", value=True)
        show_bounds = st.checkbox("Show Confidence Bounds", value=True)
    with col4:
        show_ma = st.checkbox("Show 50-day Moving Average", value=False)
        show_rsi = st.checkbox("Show RSI", value=False)
        confidence_level = st.slider("Forecast Confidence Interval (%)", 50, 95, 80, step=5)
    
    submit_button = st.form_submit_button("Generate Forecast")

# Function to calculate technical indicators
def calculate_technicals(data):
    try:
        sma = SMAIndicator(data['Close'], window=50).sma_indicator()
        rsi = RSIIndicator(data['Close'], window=14).rsi()
        return sma, rsi
    except Exception as e:
        logger.warning(f"Error calculating technicals: {str(e)}")
        return None, None

# Function to calculate profit per month
def calculate_profit_per_month(financials):
    try:
        if financials is None or financials.empty:
            return None
        earnings = financials.loc['Net Income'] if 'Net Income' in financials.index else None
        if earnings is None:
            return None
        earnings_df = pd.DataFrame({
            'Date': pd.to_datetime(earnings.index),
            'Net Income': earnings.values
        })
        earnings_df.set_index('Date', inplace=True)
        monthly_profit = earnings_df.resample('ME').sum()
        return monthly_profit['Net Income']
    except Exception as e:
        logger.warning(f"Error calculating profit per month: {str(e)}")
        return None

# Function to analyze fundamental metrics and provide recommendation
def analyze_stock(stock_info, historical_data, financials):
    try:
        analysis = {"fundamental": {}, "recommendation": "Hold"}
        
        pe_ratio = float(stock_info["pe_ratio"]) if stock_info["pe_ratio"] != "N/A" and stock_info["pe_ratio"] != "" else None
        industry_avg_pe = 25
        if pe_ratio is not None:
            if pe_ratio < industry_avg_pe:
                analysis["fundamental"]["P/E Ratio"] = f"P/E ratio ({pe_ratio:.2f}) is below industry average ({industry_avg_pe}), suggesting potential undervaluation."
                pe_score = 1
            elif pe_ratio > industry_avg_pe + 5:
                analysis["fundamental"]["P/E Ratio"] = f"P/E ratio ({pe_ratio:.2f}) is above industry average ({industry_avg_pe}), suggesting potential overvaluation."
                pe_score = -1
            else:
                analysis["fundamental"]["P/E Ratio"] = f"P/E ratio ({pe_ratio:.2f}) is close to industry average ({industry_avg_pe})."
                pe_score = 0
        else:
            analysis["fundamental"]["P/E Ratio"] = "P/E ratio data unavailable."
            pe_score = 0
        
        dividend_yield = float(stock_info["dividend_yield"].replace("%", "")) if stock_info["dividend_yield"] != "N/A" and stock_info["dividend_yield"] != "" else None
        if dividend_yield is not None:
            if dividend_yield > 2:
                analysis["fundamental"]["Dividend Yield"] = f"Dividend yield ({dividend_yield:.2f}%) is attractive for income investors."
                dividend_score = 1
            else:
                analysis["fundamental"]["Dividend Yield"] = f"Dividend yield ({dividend_yield:.2f}%) is moderate or low."
                dividend_score = 0
        else:
            analysis["fundamental"]["Dividend Yield"] = "Dividend yield data unavailable."
            dividend_score = 0
        
        market_cap = None
        if stock_info["market_cap"] != "N/A" and stock_info["market_cap"] != "":
            try:
                market_cap_str = stock_info["market_cap"].split()[0]
                market_cap = float(market_cap_str.replace('B', ''))
            except (ValueError, IndexError):
                market_cap = None
        if market_cap is not None:
            if market_cap > 100:
                analysis["fundamental"]["Market Cap"] = f"Market cap ({market_cap:.2f}B) indicates a large, stable company."
                market_cap_score = 1
            else:
                analysis["fundamental"]["Market Cap"] = f"Market cap ({market_cap:.2f}B) indicates a smaller company, potentially higher risk."
                market_cap_score = 0
        else:
            analysis["fundamental"]["Market Cap"] = "Market cap data unavailable."
            market_cap_score = 0
        
        sector = stock_info["sector"] if stock_info["sector"] != "N/A" else "Unknown"
        analysis["fundamental"]["Sector"] = f"Sector: {sector}"
        
        total_score = pe_score + dividend_score + market_cap_score
        if total_score >= 2 or (pe_score == 1 and dividend_score == 1):
            analysis["recommendation"] = "Buy"
            analysis["recommendation_reason"] = "The stock shows strong fundamental signals (low P/E, high dividend yield, large market cap), suggesting it may be undervalued."
        elif total_score <= -1 and pe_score == -1:
            analysis["recommendation"] = "Sell"
            analysis["recommendation_reason"] = "The stock shows weak fundamental signals (high P/E), suggesting it may be overvalued."
        else:
            analysis["recommendation"] = "Hold"
            analysis["recommendation_reason"] = "The stock has mixed fundamental signals, suggesting no clear buy or sell opportunity at this time."
        
        return analysis
    except Exception as e:
        logger.warning(f"Error analyzing stock: {str(e)}")
        return {
            "fundamental": {
                "P/E Ratio": "P/E ratio data unavailable.",
                "Dividend Yield": "Dividend yield data unavailable.",
                "Market Cap": "Market cap data unavailable.",
                "Sector": "Sector: Unknown"
            },
            "recommendation": "Hold",
            "recommendation_reason": f"Unable to analyze stock due to data issues: {str(e)}"
        }

# Function to generate forecast and plot
def generate_forecast(ticker, period_type, period_value, start_date, confidence_level):
    if not ticker:
        return None, None, None, None, None
    
    ticker = ticker.strip().upper()
    if '.' not in ticker:
        ticker = f"{ticker}.NS"
    
    stock_info = {'ticker': ticker}
    
    try:
        end_date = date.today().strftime("%Y-%m-%d")
        start_date_str = start_date.strftime("%Y-%m-%d")
        data = fetch_stock_data(ticker, start_date_str, end_date)
        if data is None or len(data) < 2:
            raise ValueError(f"No or insufficient data found for stock symbol {ticker}")
        
        info, financials = fetch_stock_info(ticker)
        if info is None:
            raise ValueError(f"Unable to fetch stock information for {ticker}")
        
        stock_info = {
            "ticker": ticker,
            "name": info.get("longName", ticker),
            "price": f"{info.get('regularMarketPrice', 'N/A')} {info.get('currency', '')}",
            "market_cap": f"{info.get('marketCap', 'N/A') / 1e9:.2f}B {info.get('currency', '')}" if isinstance(info.get('marketCap'), (int, float)) else "N/A",
            "sector": info.get("sector", "N/A"),
            "pe_ratio": f"{info.get('trailingPE', 'N/A'):.2f}" if isinstance(info.get('trailingPE'), (int, float)) else "N/A",
            "dividend_yield": f"{info.get('dividendYield', 'N/A') * 100:.2f}%" if isinstance(info.get('dividendYield'), (int, float)) else "N/A"
        }
    except Exception as e:
        return None, f"Error loading data for symbol {ticker}: {str(e)}", None, None, None
    
    try:
        if period_type == "Days":
            period = period_value
            if not 1 <= period <= 90:
                raise ValueError("Days must be between 1 and 90.")
        elif period_type == "Months":
            period = period_value * 30
        else:  # Years
            period = period_value * 365
    except ValueError as e:
        return None, f"Invalid period value: {str(e)}", None, None, None
    
    df_train = data[['Close']].reset_index()
    df_train.columns = ["ds", "y"]
    df_train['y'] = pd.to_numeric(df_train['y'], errors='coerce')
    df_train = df_train.dropna(subset=['y'])
    
    if df_train.shape[0] < 2:
        return None, "Not enough data to generate a forecast.", None, None, None
    
    try:
        m = Prophet(interval_width=confidence_level/100.0)
        m.fit(df_train)
        future = m.make_future_dataframe(periods=period)
        forecast = m.predict(future)
        
        forecast_data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        forecast_data.columns = ['Date', 'Forecast', 'Lower Bound', 'Upper Bound']
        
        forecast_id = str(uuid.uuid4())
        FORECAST_STORAGE[forecast_id] = forecast_data
        
        sma, rsi = calculate_technicals(data)
        
        fig = go.Figure()
        
        if show_historical:
            fig.add_trace(go.Scatter(
                x=df_train['ds'], y=df_train['y'],
                mode='lines', name='Historical',
                line=dict(color='#3b82f6'),
                hovertemplate='%{y:.2f}<br>%{x|%Y-%m-%d}',
                yaxis='y2'
            ))
        
        if show_forecast:
            fig.add_trace(go.Scatter(
                x=forecast['ds'], y=forecast['yhat'],
                mode='lines', name='Forecast',
                line=dict(color='#60a5fa', dash='solid'),
                hovertemplate='%{y:.2f}<br>%{x|%Y-%m-%d}',
                yaxis='y2'
            ))
        
        if show_bounds and show_forecast:
            fig.add_trace(go.Scatter(
                x=forecast['ds'], y=forecast['yhat_upper'],
                mode='lines', name='Upper Bound',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip',
                yaxis='y2'
            ))
            fig.add_trace(go.Scatter(
                x=forecast['ds'], y=forecast['yhat_lower'],
                mode='lines', name='Lower Bound',
                line=dict(width=0),
                fill='tonexty',
                fillcolor='rgba(59, 130, 246, 0.2)',
                showlegend=True,
                hovertemplate='Lower: %{y:.2f}<br>%{x|%Y-%m-%d}',
                yaxis='y2'
            ))
        
        if show_ma and sma is not None:
            fig.add_trace(go.Scatter(
                x=data.index, y=sma,
                mode='lines', name='50-day MA',
                line=dict(color='#facc15', width=1.5),
                hovertemplate='MA: %{y:.2f}<br>%{x|%Y-%m-%d}',
                yaxis='y2'
            ))
        
        if show_rsi and rsi is not None:
            fig.add_trace(go.Scatter(
                x=data.index, y=rsi,
                mode='lines', name='RSI (14)',
                line=dict(color='#ec4899', width=1.5),
                hovertemplate='RSI: %{y:.2f}<br>%{x|%Y-%m-%d}',
                yaxis='y1'
            ))
        
        fig.update_layout(
            title=f"{stock_info['name']} Forecast for {period_value} {period_type}",
            xaxis_title='Date',
            yaxis=dict(
                title='RSI' if show_rsi else '',
                side='left',
                range=[0, 100] if show_rsi else None,
                showgrid=False
            ),
            yaxis2=dict(
                title='Stock Price',
                side='right',
                overlaying='y',
                showgrid=True,
                gridcolor='rgba(255, 255, 255, 0.1)'
            ),
            template='plotly_dark',
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor='rgba(0, 0, 0, 0.9)',
                font=dict(color='white', family='Poppins', size=13),
                bordercolor='#3b82f6'
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=60, b=20),
            font=dict(family="Poppins", color="#ffffff"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)')
        )
        
        return stock_info, None, forecast_data, fig, data, financials
    
    except Exception as e:
        logger.error(f"Error generating forecast for {ticker}: {str(e)}")
        return None, f"Error generating forecast: {str(e)}", None, None, None, None

# Function to generate earnings plot (Net Income only)
def generate_earnings_plot(stock_info, financials):
    if financials is None or financials.empty:
        return None
    
    try:
        earnings = financials.loc['Net Income'] if 'Net Income' in financials.index else None
        
        if earnings is None:
            return None
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=earnings.index,
            y=earnings,
            name='Net Income',
            marker_color='#3b82f6',
            hovertemplate='Net Income: %{y:,.0f}<br>%{x|%Y-%m-%d}'
        ))
        
        fig.update_layout(
            title=f"{stock_info['name']} Quarterly Earnings",
            xaxis_title='Date',
            yaxis=dict(
                title='Net Income',
                side='left',
                showgrid=False
            ),
            template='plotly_dark',
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor='rgba(0, 0, 0, 0.9)',
                font=dict(color='white', family='Poppins', size=13),
                bordercolor='#3b82f6'
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=60, b=20),
            font=dict(family="Poppins", color="#ffffff"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)')
        )
        
        return fig
    except Exception as e:
        logger.warning(f"Error generating earnings plot: {str(e)}")
        return None

# Function to generate profit per month plot
def generate_profit_per_month_plot(stock_info, financials):
    if financials is None or financials.empty:
        return None
    
    try:
        monthly_profit = calculate_profit_per_month(financials)
        
        if monthly_profit is None or monthly_profit.empty:
            return None
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=monthly_profit.index,
            y=monthly_profit,
            name='Monthly Profit',
            marker_color='#10b981',
            hovertemplate='Profit: %{y:,.0f}<br>%{x|%Y-%m}'
        ))
        
        fig.update_layout(
            title=f"{stock_info['name']} Monthly Profit",
            xaxis_title='Month',
            yaxis=dict(
                title='Net Income',
                side='left',
                showgrid=False
            ),
            template='plotly_dark',
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor='rgba(0, 0, 0, 0.9)',
                font=dict(color='white', family='Poppins', size=13),
                bordercolor='#3b82f6'
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=60, b=20),
            font=dict(family="Poppins", color="#ffffff"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)')
        )
        
        return fig
    except Exception as e:
        logger.warning(f"Error generating profit per month plot: {str(e)}")
        return None

# Process form submission
if submit_button:
    if not ticker1:
        st.error("Please enter or select a stock symbol.")
    else:
        with st.spinner("Generating forecast..."):
            stock_info1, error1, forecast_data1, fig1, historical_data1, financials1 = generate_forecast(
                ticker1, period_type, period_value, start_date, confidence_level
            )
            
            if error1:
                st.error(error1)
                suggestions = [symbol for name, symbol in POPULAR_STOCKS.items() if ticker1.replace('.NS', '').lower() in symbol.lower() or ticker1.replace('.NS', '').lower() in name.lower()]
                if suggestions:
                    st.warning(f"Did you mean: {', '.join([f'{s}.NS' for s in suggestions])}?")
            elif stock_info1:
                st.subheader("Stock Analysis and Recommendation")
                analysis = analyze_stock(stock_info1, historical_data1, financials1)
                
                recommendation_class = {
                    "Buy": "recommendation-buy",
                    "Sell": "recommendation-sell",
                    "Hold": "recommendation-hold"
                }.get(analysis["recommendation"], "recommendation-hold")
                
                st.markdown(f"""
                <div class="analysis-card">
                    <h3>Fundamental Analysis</h3>
                    <p><strong>P/E Ratio:</strong> {analysis["fundamental"]["P/E Ratio"]}</p>
                    <p><strong>Dividend Yield:</strong> {analysis["fundamental"]["Dividend Yield"]}</p>
                    <p><strong>Market Cap:</strong> {analysis["fundamental"]["Market Cap"]}</p>
                    <p><strong>Sector:</strong> {analysis["fundamental"]["Sector"]}</p>
                    <p><strong>Recommendation:</strong> <span class="{recommendation_class}">{analysis["recommendation"]}</span></p>
                    <p><strong>Reason:</strong> {analysis["recommendation_reason"]}</p>
                    <p><em>Note: This recommendation is based on automated analysis and should not be considered financial advice. Consult a financial advisor before making investment decisions.</em></p>
                </div>
                """, unsafe_allow_html=True)
                
                st.subheader(stock_info1['name'])
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Current Price", stock_info1['price'])
                col2.metric("Market Cap", stock_info1['market_cap'])
                col3.metric("Sector", stock_info1['sector'])
                col4.metric("P/E Ratio", stock_info1['pe_ratio'])
                col5.metric("Dividend Yield", stock_info1['dividend_yield'])
                
                st.subheader("Forecast")
                if fig1:
                    st.plotly_chart(fig1, use_container_width=True, key="forecast_chart")
                    st.button("Reset Chart Zoom", on_click=lambda: st.session_state.update({"forecast_chart": {}}))
                
                try:
                    folder = "pridiction of the stock"
                    os.makedirs(folder, exist_ok=True)
                    image_name = f"{date.today().strftime('%Y-%m-%d')}_{stock_info1['ticker'].replace('.NS', '')}.png"
                    image_path = os.path.join(folder, image_name)
                    pio.write_image(fig1, file=image_path, format='png', width=1200, height=600)
                    st.write(f"Graph saved as {image_name}")
                except Exception as e:
                    st.warning(f"Error saving image: {str(e)}")
                
                if forecast_data1 is not None:
                    buffer = io.StringIO()
                    forecast_data1.to_csv(buffer, index=False)
                    buffer.seek(0)
                    st.download_button(
                        label="Download Forecast (CSV)",
                        data=buffer.getvalue(),
                        file_name=f"{stock_info1['ticker']}_forecast.csv",
                        mime="text/csv"
                    )
                    if FORECAST_STORAGE:
                        FORECAST_STORAGE.pop(list(FORECAST_STORAGE.keys())[0], None)
                
                st.subheader("Historical Data")
                if historical_data1 is not None:
                    st.dataframe(historical_data1[['Open', 'High', 'Low', 'Close', 'Volume']].tail(10))
                    buffer = io.StringIO()
                    historical_data1.to_csv(buffer)
                    buffer.seek(0)
                    st.download_button(
                        label="Download Historical Data (CSV)",
                        data=buffer.getvalue(),
                        file_name=f"{stock_info1['ticker']}_historical.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("Historical data unavailable.")
                
                st.subheader("Quarterly Earnings")
                earnings_fig = generate_earnings_plot(stock_info1, financials1)
                if earnings_fig:
                    st.plotly_chart(earnings_fig, use_container_width=True, key="earnings_chart")
                    st.button("Reset Earnings Chart Zoom", on_click=lambda: st.session_state.update({"earnings_chart": {}}))
                else:
                    st.warning("Unable to generate earnings data.")
                
                st.subheader("Monthly Profit")
                profit_month_fig = generate_profit_per_month_plot(stock_info1, financials1)
                if profit_month_fig:
                    st.plotly_chart(profit_month_fig, use_container_width=True, key="profit_month_chart")
                    st.button("Reset Monthly Profit Chart Zoom", on_click=lambda: st.session_state.update({"profit_month_chart": {}}))
                else:
                    st.warning("Unable to generate monthly profit data.")
                
                if financials1 is not None and not financials1.empty:
                    earnings_data = financials1.loc['Net Income'] if 'Net Income' in financials1.index else None
                    if earnings_data is not None:
                        earnings_df = pd.DataFrame({
                            'Date': earnings_data.index,
                            'Net Income': earnings_data.values
                        })
                        st.subheader("Recent Earnings")
                        st.dataframe(earnings_df)