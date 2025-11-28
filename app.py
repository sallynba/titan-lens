import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import twstock
import os
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="TitanLens 泰坦透視鏡",
    page_icon="💎",
    layout="wide"
)

# --- 2. 核彈級字型強制掛載 (針對 Streamlit Cloud Linux 環境) ---
@st.cache_resource
def configure_font():
    # 這是 fonts-wqy-zenhei 在 Linux 系統中的標準安裝路徑
    font_path = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
    
    font_prop = None
    if os.path.exists(font_path):
        # 1. 強制加入字型管理器
        fm.fontManager.addfont(font_path)
        # 2. 取得字型物件
        font_prop = fm.FontProperties(fname=font_path)
        # 3. 設定全域參數
        plt.rcParams['font.family'] = font_prop.get_name()
        return font_prop.get_name(), True
    else:
        # 如果找不到系統字型，回退到英文
        return "Sans-serif", False

custom_font_name, has_font = configure_font()

# 顯示除錯訊息 (確認字型有沒有抓到)
if has_font:
    st.sidebar.success(f"✅ 系統字型掛載成功：{custom_font_name}")
else:
    st.sidebar.warning("⚠️ 未偵測到中文字型，請確認 packages.txt 是否設定正確。")

# 設定 mplfinance 的字型參數
my_rc_params = {
    'font.family': custom_font_name,
    'axes.unicode_minus': False
}

# --- 3. 核心邏輯函數 ---

def get_macro_data():
    try:
        tickers = ["DX-Y.NYB", "^VIX"]
        data = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
        if isinstance(data.columns, pd.MultiIndex):
            close_df = data.xs('Close', level=0, axis=1)
            dxy = close_df['DX-Y.NYB'].iloc[-1]
            dxy_prev = close_df['DX-Y.NYB'].iloc[-2]
            vix = close_df['^VIX'].iloc[-1]
            
            if dxy >= 105: dxy_msg = "🔴 強力吸金"
            elif dxy <= 100: dxy_msg = "🟢 資金寬鬆"
            else: dxy_msg = "🟡 中性觀察"
            
            if np.isnan(vix): vix_msg = "⚪ 無數據"
            elif vix > 30: vix_msg = "🔴 市場恐慌"
            elif vix > 20: vix_msg = "🟠 氣氛緊張"
            else: vix_msg = "🟢 市場安靜"

            return {"DXY": f"{dxy:.2f}", "DXY_MSG": dxy_msg, "VIX": f"{vix:.2f}", "VIX_MSG": vix_msg}
        return None
    except: return None

def calculate_indicators(df):
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
    
    low_list = df['Low'].rolling(window=9).min()
    high_list = df['High'].rolling(window=9).max()
    rsv = (df['Close'] - low_list) / (high_list - low_list) * 100
    df['K'] = rsv.ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    
    close_arr = df['Close'].to_numpy().flatten()
    vol_arr = df['Volume'].to_numpy().flatten()
    obv = [0]
    for i in range(1, len(close_arr)):
        if close_arr[i] > close_arr[i-1]: obv.append(obv[-1] + vol_arr[i])
        elif close_arr[i] < close_arr[i-1]: obv.append(obv[-1] - vol_arr[i])
        else: obv.append(obv[-1])
    df['OBV'] = obv
    df['OBV_MA'] = df['OBV'].rolling(window=20).mean()
    return df

def get_fundamental_info(ticker_obj):
    try:
        info = ticker_obj.info
        quote_type = info.get('quoteType', '')
        is_etf = quote_type == 'ETF' or 'trailingEps' not in info
        
        data = {"is_etf": is_etf, "verdict": "中性", "pe": "-", "eps": "-", "roe": "-", "yield": "-"}
        
        if is_etf:
            data['desc'] = info.get('longBusinessSummary', '無描述')
            try:
                funds = ticker_obj.funds_data
                if funds and funds.top_holdings is not None:
                    holdings = funds.top_holdings.reset_index()
                    holdings.columns = ['公司', '比例']
                    holdings['比例'] = holdings['比例'].apply(lambda x: f"{x*100:.2f}%")
                    data['holdings'] = holdings
            except: data['holdings'] = None
        else:
            eps = info.get('trailingEps')
            pe = info.get('trailingPE')
            roe = info.get('returnOnEquity')
            yld = info.get('dividendYield')
            data['pe'] = f"{pe:.1f}" if pe else "-"
            data['eps'] = f"{eps:.2f}" if eps else "-"
            data['roe'] = f"{roe*100:.1f}%" if roe else "-"
            data['yield'] = f"{yld*100:.2f}%" if yld else "-"
            score = 0
            if eps and eps > 0: score += 1
            if roe and roe > 0.15: score += 1
            if pe and pe < 15: score += 1
            if yld and yld > 0.04: score += 1
            if score >= 3: data['verdict'] = "💎 績優"
            elif score == 0: data['verdict'] = "⚠️ 偏弱"
        return data
    except: return None

# --- 4. 介面呈現 ---

st.title("💎 TitanLens 泰坦透視鏡")

with st.sidebar:
    st.header("🔍 設定")
    raw_code = st.text_input("輸入代號", value="2330")
    run_btn = st.button("分析", type="primary")

if run_btn or raw_code:
    stock_code = raw_code.strip().upper()
    market = "美股"
    if stock_code.isdigit():
        stock_code = f"{stock_code}.TW"
        market = "台股"
        
    try:
        with st.spinner("🔄 分析中..."):
            df = yf.download(stock_code, period="6mo", progress=False, auto_adjust=True)
            if df.empty and market == "台股":
                stock_code = stock_code.replace(".TW", ".TWO")
                df = yf.download(stock_code, period="6mo", progress=False, auto_adjust=True)
            
            if df.empty:
                st.error("❌ 查無資料")
                st.stop()
                
            macro = get_macro_data()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = calculate_indicators(df)
            ticker = yf.Ticker(stock_code)
            fund_data = get_fundamental_info(ticker)
            
            name = stock_code
            if raw_code.isdigit() and raw_code in twstock.codes:
                name = twstock.codes[raw_code].name
            elif 'longName' in ticker.info:
                name = ticker.info['longName']

            latest = df.iloc[-1]
            prev = df.iloc[-2]

        # Dashboard
        st.subheader(f"{name} ({stock_code})")
        st.metric("股價", f"{latest['Close']:.2f}", f"{(latest['Close']-prev['Close']):.2f}")
        st.divider()

        col1, col2, col3 = st.columns(3)
        wave = "多頭浪" if latest['Close'] > latest['MA60'] else "修正浪"
        col1.info(f"**波浪**: {wave}")
        if macro:
            col2.write(f"**DXY**: {macro['DXY']} ({macro['DXY_MSG']})")
            col3.write(f"**VIX**: {macro['VIX']} ({macro['VIX_MSG']})")
        
        st.divider()
        
        c1, c2, c3, c4 = st.columns(4)
        k, d = latest['K'], latest['D']
        kd_msg = "金叉" if prev['K'] < prev['D'] and k > d else "中性"
        c1.metric("KD", f"{k:.0f}", kd_msg)
        
        hist = latest['Hist']
        macd_msg = "翻紅" if prev['Hist'] < 0 and hist > 0 else "中性"
        c2.metric("MACD", f"{hist:.2f}", macd_msg)
        
        vol_msg = "爆量" if latest['Volume'] > latest['Vol_MA5'] * 1.5 else "平穩"
        c3.metric("量能", vol_msg)
        
        obv_msg = "吸籌" if latest['OBV'] > latest['OBV_MA'] and latest['OBV'] > prev['OBV'] else "中性"
        c4.metric("籌碼", obv_msg)

        st.divider()

        with st.expander("🏢 基本面 / ETF 持股", expanded=True):
            if fund_data['is_etf']:
                if 'holdings' in fund_data and fund_data['holdings'] is not None:
                    st.dataframe(fund_data['holdings'], hide_index=True)
            else:
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("評級", fund_data['verdict'])
                f2.metric("EPS", fund_data['eps'])
                f3.metric("ROE", fund_data['roe'])
                f4.metric("殖利率", fund_data['yield'])

        st.markdown("### 📈 技術圖表")
        
        # 繪圖 (使用強制掛載的字型)
        mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
        if market == "美股": mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
        
        # 關鍵：這裡把 rc 參數傳進去
        s = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc, rc=my_rc_params)
        
        plot_data = df.tail(100)
        colors = ['red' if v >= 0 else 'green' for v in plot_data['Hist']]
        
        add_plots = [
            mpf.make_addplot(plot_data['MA60'], color='orange', width=2.0),
            mpf.make_addplot(plot_data['K'], panel=2, color='red', ylabel='KD'),
            mpf.make_addplot(plot_data['D'], panel=2, color='blue'),
            mpf.make_addplot(plot_data['Hist'], panel=3, type='bar', color=colors, ylabel='MACD'),
            mpf.make_addplot(plot_data['Signal'], panel=3, color='blue'),
            mpf.make_addplot(plot_data['OBV'], panel=4, color='purple', ylabel='OBV', width=1.5),
            mpf.make_addplot(plot_data['OBV_MA'], panel=4, color='orange', width=1.0)
        ]
        
        # 標題強制使用中文
        fig, ax = mpf.plot(plot_data, type='candle', style=s, volume=True, 
                           addplot=add_plots, returnfig=True, 
                           panel_ratios=(4,1,1,1,1),
                           title=f"\n{name} ({stock_code}) Trend",
                           figratio=(10, 14))
        
        st.pyplot(fig)

    except Exception as e:
        st.error(f"發生錯誤：{e}")
