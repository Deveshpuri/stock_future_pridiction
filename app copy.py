from flask import Flask, request, render_template_string, send_file
import yfinance as yf
from prophet import Prophet
import plotly.graph_objs as go
import pandas as pd
from datetime import date
import io
import uuid
import os
import plotly.io as pio

app = Flask(__name__)

# Temporary storage for forecast data
FORECAST_STORAGE = {}

# List of popular Indian stocks for dropdown and suggestions
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

# HTML template with updated design
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockPulse: Forecast</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Poppins', sans-serif;
            background: linear-gradient(135deg, #0a1733, #000000);
            color: #ffffff;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 1rem;
        }
        .container {
            max-width: 1200px;
            width: 100%;
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
            background: #1e293b;
            border: 2px solid rgba(255, 255, 255, 0.1);
            border-radius: 0.5rem;
            padding: 0.75rem;
            color: #ffffff;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }
        .glow-input:focus, .glow-select:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
            outline: none;
        }
        .glow-select option {
            background: #1e293b;
            color: #ffffff;
        }
        .glow-button {
            background: linear-gradient(90deg, #3b82f6, #0a1733);
            border: none;
            border-radius: 0.5rem;
            padding: 0.75rem 1.5rem;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .glow-button:hover {
            transform: scale(1.05);
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.7);
        }
        .glow-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.2);
            border-top: 4px solid #3b82f6;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            animation: spin 1s linear infinite;
            margin: 1rem auto;
            display: none;
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
        .invalid {
            border-color: #ef4444 !important;
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);
        }
        .plotly .hoverlayer .hovertext {
            background-color: rgba(0, 0, 0, 0.9) !important;
            color: white !important;
            border: 2px solid #3b82f6 !important;
            padding: 10px !important;
            font-family: 'Poppins', sans-serif !important;
            font-size: 13px !important;
            z-index: 10000 !important;
        }
        .plotly .hoverlayer .spike {
            stroke: #3b82f6 !important;
        }
        .light .plotly .hoverlayer .hovertext {
            background-color: rgba(255, 255, 255, 0.95) !important;
            color: #0a1733 !important;
            border: 2px solid #3b82f6 !important;
        }
        .theme-toggle {
            position: relative;
            width: 60px;
            height: 34px;
        }
        .theme-toggle input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.2);
            transition: 0.4s;
            border-radius: 34px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%23ffffff" stroke-width="2"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>') no-repeat center;
            background-size: 20px;
            transition: 0.4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background: rgba(59, 130, 246, 0.5);
        }
        input:checked + .slider:before {
            transform: translateX(26px);
            background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%230a1733"><path d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>') no-repeat center;
            background-size: 20px;
        }
    </style>
</head>
<body class="dark">
    <div class="container mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-3xl sm:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-blue-800 fade-in">StockPulse</h1>
            <label class="theme-toggle">
                <input type="checkbox" id="themeToggle" {% if theme == 'light' %}checked{% endif %}>
                <span class="slider"></span>
            </label>
        </div>
        <div class="card fade-in">
            <form id="stockForm" method="POST" class="space-y-6">
                <input type="hidden" name="theme" value="{{ theme }}">
                <div>
                    <label for="ticker" class="block text-sm font-medium text-gray-200">Stock Symbol (e.g., RELIANCE or AAPL; .NS added for Indian stocks)</label>
                    <div class="flex space-x-4 mt-2">
                        <input type="text" id="ticker" name="ticker" placeholder="Enter stock symbol"
                               class="glow-input flex-1" required>
                        <select id="stockSelect" name="stockSelect" onchange="document.getElementById('ticker').value = this.value"
                                class="glow-select flex-1">
                            <option value="">Select a stock</option>
                            {% for name, symbol in popular_stocks.items() %}
                                <option value="{{ symbol }}">{{ name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                <div>
                    <label for="period_type" class="block text-sm font-medium text-gray-200">Prediction Period</label>
                    <div class="flex space-x-4 mt-2">
                        <select id="period_type" name="period_type" onchange="togglePeriodInput()"
                                class="glow-select flex-1">
                            <option value="days">Days</option>
                            <option value="months">Months</option>
                            <option value="years">Years</option>
                        </select>
                        <input type="number" id="period_days" name="period_days" min="1" max="90" value="30"
                               class="glow-input flex-1">
                        <select id="period_months" name="period_months" style="display: none;"
                                class="glow-select flex-1">
                            {% for i in range(1, 13) %}
                                <option value="{{ i }}">{{ i }}</option>
                            {% endfor %}
                        </select>
                        <select id="period_years" name="period_years" style="display: none;"
                                class="glow-select flex-1">
                            {% for i in range(1, 5) %}
                                <option value="{{ i }}">{{ i }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                <button type="submit" id="submitBtn" class="glow-button w-full sm:w-auto">Generate Forecast</button>
            </form>
            <div id="spinner" class="spinner"></div>
        </div>
        {% if error %}
            <div class="mt-6 card text-center fade-in">
                <p class="text-red-400">{{ error }}</p>
                {% if suggestions %}
                    <p class="mt-2 text-gray-300">Did you mean: {{ suggestions | join(', ') }}?</p>
                {% endif %}
            </div>
        {% endif %}
        {% if stock_info %}
            <div class="mt-6 card fade-in">
                <h2 class="text-2xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-blue-800">{{ stock_info.name }}</h2>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-4">
                    <div>
                        <p class="text-sm text-gray-400">Current Price</p>
                        <p class="text-lg font-bold text-blue-400">{{ stock_info.price }}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-400">Market Cap</p>
                        <p class="text-lg font-bold text-blue-400">{{ stock_info.market_cap }}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-400">Sector</p>
                        <p class="text-lg font-bold text-blue-400">{{ stock_info.sector }}</p>
                    </div>
                </div>
            </div>
        {% endif %}
        {% if plot_div %}
            <div class="mt-8 card fade-in">
                <div id="plot" style="height: {{ '500px' if request.user_agent.platform in ['android', 'iphone'] else '600px' }}">{{ plot_div | safe }}</div>
                <div class="flex space-x-4 mt-4">
                    <a href="/download?ticker={{ stock_info.ticker }}&forecast_id={{ forecast_id }}"
                       class="glow-button">Download Forecast (CSV)</a>
                    <p class="text-gray-300">Graph saved as {{ image_path }}</p>
                </div>
            </div>
        {% endif %}
    </div>
    <script>
        // Theme toggle
        const themeToggle = document.getElementById('themeToggle');
        const body = document.body;
        if (localStorage.getItem('theme') === 'light') {
            body.classList.remove('dark');
            body.classList.add('light');
            themeToggle.checked = true;
        }
        themeToggle.addEventListener('change', () => {
            body.classList.toggle('dark');
            body.classList.toggle('light');
            localStorage.setItem('theme', body.classList.contains('light') ? 'light' : 'dark');
            document.getElementById('stockForm').elements['theme'].value = body.classList.contains('light') ? 'light' : 'dark';
        });

        // Form validation and loading spinner
        const form = document.getElementById('stockForm');
        const tickerInput = document.getElementById('ticker');
        const submitBtn = document.getElementById('submitBtn');
        const spinner = document.getElementById('spinner');
        const periodType = document.getElementById('period_type');
        const periodDays = document.getElementById('period_days');
        const periodMonths = document.getElementById('period_months');
        const periodYears = document.getElementById('period_years');

        function togglePeriodInput() {
            periodDays.style.display = periodType.value === 'days' ? 'block' : 'none';
            periodMonths.style.display = periodType.value === 'months' ? 'block' : 'none';
            periodYears.style.display = periodType.value === 'years' ? 'block' : 'none';
        }

        togglePeriodInput();

        tickerInput.addEventListener('input', () => {
            tickerInput.classList.toggle('invalid', !tickerInput.value.trim());
        });

        form.addEventListener('submit', (e) => {
            if (!tickerInput.value.trim()) {
                e.preventDefault();
                tickerInput.classList.add('invalid');
                tickerInput.focus();
            } else {
                submitBtn.disabled = true;
                spinner.style.display = 'block';
            }
        });
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    global FORECAST_STORAGE
    plot_div = None
    error = None
    stock_info = None
    forecast_data = None
    suggestions = None
    forecast_id = None
    image_path = None
    theme = request.form.get('theme', 'dark')

    if request.method == "POST":
        ticker = request.form.get("ticker", "").strip().upper()
        period_type = request.form.get("period_type", "days")
        try:
            if period_type == "days":
                period_value = int(request.form.get("period_days", 30))
                if not 1 <= period_value <= 90:
                    raise ValueError("Days must be between 1 and 90.")
                period = period_value
            elif period_type == "months":
                period_value = int(request.form.get("period_months", 1))
                period = period_value * 30
            else:  # years
                period_value = int(request.form.get("period_years", 1))
                period = period_value * 365
        except ValueError as e:
            error = f"Invalid period value: {str(e)}"
            return render_template_string(HTML_TEMPLATE, error=error, popular_stocks=POPULAR_STOCKS, theme=theme)

        if '.' not in ticker:
            ticker = f"{ticker}.NS"
        
        stock_info = {'ticker': ticker}

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
            error = f"Error loading data for symbol {ticker}: {str(e)}"
            suggestions = [symbol for name, symbol in POPULAR_STOCKS.items() if ticker.replace('.NS', '').lower() in symbol.lower() or ticker.replace('.NS', '').lower() in name.lower()]
            suggestions = [f"{s}.NS" for s in suggestions]
            return render_template_string(HTML_TEMPLATE, error=error, suggestions=suggestions, popular_stocks=POPULAR_STOCKS, theme=theme)

        df_train = data[['Close']].reset_index()
        df_train.columns = ["ds", "y"]
        df_train['y'] = pd.to_numeric(df_train['y'], errors='coerce')
        df_train = df_train.dropna(subset=['y'])

        if df_train.shape[0] < 2:
            error = "Not enough data to generate a forecast."
        else:
            try:
                m = Prophet()
                m.fit(df_train)
                future = m.make_future_dataframe(periods=period)
                forecast = m.predict(future)

                forecast_data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
                forecast_data.columns = ['Date', 'Forecast', 'Lower Bound', 'Upper Bound']

                forecast_id = str(uuid.uuid4())
                FORECAST_STORAGE[forecast_id] = forecast_data

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
                    template='plotly_dark' if theme == 'dark' else 'plotly_white',
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

                plot_div = fig.to_html(full_html=False, include_plotlyjs='cdn')

                # Save plot as image
                try:
                    folder = "pridiction of the stock"
                    os.makedirs(folder, exist_ok=True)
                    image_name = f"{date.today().strftime('%Y-%m-%d')}_{ticker.replace('.NS', '')}.png"
                    image_path = os.path.join(folder, image_name)
                    pio.write_image(fig, file=image_path, format='png', width=1200, height=600)
                    image_path = image_name
                except Exception as e:
                    print(f"Error saving image: {str(e)}")
                    image_path = "Failed to save image"

            except Exception as e:
                error = f"Error generating forecast: {str(e)}"

    return render_template_string(HTML_TEMPLATE, plot_div=plot_div, error=error, stock_info=stock_info, popular_stocks=POPULAR_STOCKS, suggestions=suggestions, forecast_id=forecast_id, image_path=image_path, theme=theme)

@app.route("/download")
def download_forecast():
    global FORECAST_STORAGE
    ticker = request.args.get('ticker', 'STOCK')
    forecast_id = request.args.get('forecast_id', '')
    
    forecast_data = FORECAST_STORAGE.get(forecast_id)
    if forecast_data is None or forecast_data.empty:
        return "No forecast data available", 400

    del FORECAST_STORAGE[forecast_id]

    buffer = io.StringIO()
    forecast_data.to_csv(buffer, index=False)
    buffer.seek(0)

    return send_file(
        io.BytesIO(buffer.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"{ticker}_forecast.csv"
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)