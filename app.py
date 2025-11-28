import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import twstock
import os
import matplotlib.pyplot as plt

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="TitanLens 泰坦透視鏡",
    page_icon="💎",
    layout="wide"
)

# --- 2. 字型設定 (針對 Streamlit Cloud 優化) ---
# 我們在 packages.txt 安裝了 fonts-wqy-zenhei，這裡直接設定使用它
# 這樣就不用每次跑程式都去下載，速度更快且穩定
font_name = 'WenQuanYi Zen Hei'

# 設定 Matplotlib 全域參數
plt.rcParams['font.sans-serif'] = [font_name]
plt.rcParams['axes.unicode_minus'] = False 

# 設定 mplfinance 的字型樣式
my_rc_params = {
    'font.family': font_name,
    'axes.unicode_minus': False
}

# --- 3. 核心邏輯函數 ---

def get_macro_data():
    """抓取總經數據"""
    try:
        tickers = ["DX-Y.NYB", "^VIX"]
        data = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
        
        if isinstance(data.columns, pd.MultiIndex):
            close_df = data.xs('Close', level=0, axis=1)
            
            dxy = close_df['DX-Y.NYB'].iloc[-1]
            dxy_prev = close_df['DX-Y.NYB'].iloc[-2]
            vix = close_df['^VIX'].iloc[-1]
            
            if dxy >= 105: dxy_msg = "🔴 強力吸金 (不利台股)"
            elif dxy <= 100: dxy_msg = "🟢 資金寬鬆 (有利台股)"
            else: dxy_msg = "🟡 中性觀察"
            
            if np.isnan(vix): vix_msg = "⚪ 暫無數據"
            elif vix > 30: vix_msg = "🔴 市場恐慌"
            elif vix > 20: vix_msg = "🟠 氣氛緊張"
            else: vix_msg = "🟢 市場安靜"

            return {
                "DXY": f"{dxy:.2f}", "DXY_MSG": dxy_msg, 
                "VIX": f"{vix:.2f}", "VIX_MSG": vix_msg
            }
        return None
    except:
        return None

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
    
    # OBV
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
        
        data = {
            "is_etf": is_etf,
            "verdict": "中性",
            "pe": "-", "eps": "-", "roe": "-", "yield": "-"
        }
        
        if is_etf:
            data['desc'] = info.get('longBusinessSummary', '無描述')
            try:
                funds = ticker_obj.funds_data
                if funds and funds.top_holdings is not None:
                    holdings = funds.top_holdings.reset_index()
                    holdings.columns = ['公司', '比例']
                    holdings['比例'] = holdings['比例'].apply(lambda x: f"{x*100:.2f}%")
                    data['holdings'] = holdings
            except:
                data['holdings'] = None
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
            
            if score >= 3: data['verdict'] = "💎 績優潛力"
            elif score == 0: data['verdict'] = "⚠️ 體質偏弱"
            
        return data
    except:
        return None

# --- 4. 介面呈現 ---

st.title("💎 TitanLens 泰坦透視鏡")
st.markdown("### 總經 x 技術 x 籌碼 x 基本面｜全方位診斷系統")

with st.sidebar:
    st.header("🔍 查詢設定")
    raw_code = st.text_input("輸入股票代號", value="2330")
    run_btn = st.button("開始分析", type="primary")
    st.markdown("---")
    st.markdown("**📊 指標說明**")
    st.caption("1. **波浪總經**：判斷大環境順風逆風")
    st.caption("2. **雙指標**：KD+MACD 判斷多空")
    st.caption("3. **籌碼 OBV**：監控主力進出")

if run_btn or raw_code:
    stock_code = raw_code.strip().upper()
    market = "美股"
    if stock_code.isdigit():
        stock_code = f"{stock_code}.TW"
        market = "台股"
        
    try:
        with st.spinner("🔄 正在連線全球資料庫，進行全方位分析..."):
            # 資料獲取與處理
            df = yf.download(stock_code, period="6mo", progress=False, auto_adjust=True)
            if df.empty and market == "台股":
                stock_code = stock_code.replace(".TW", ".TWO")
                df = yf.download(stock_code, period="6mo", progress=False, auto_adjust=True)
            
            if df.empty:
                st.error("❌ 找不到資料，請確認代號是否正確。")
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

        # --- Dashboard ---
        price_change = latest['Close'] - prev['Close']
        st.subheader(f"{name} ({stock_code})")
        st.metric("目前股價", f"{latest['Close']:.2f}", f"{price_change:.2f}")
        st.divider()

        # 區塊 1: 總經與波浪
        st.markdown("#### 🌍 指標 1：總經與波浪")
        col1, col2, col3 = st.columns(3)
        
        wave_status = "盤整浪"
        wave_icon = "⚖️"
        if latest['Close'] > latest['MA60']: 
            wave_status = "多頭浪 (股價>季線)"
            wave_icon = "🌊"
        elif latest['Close'] < latest['MA60']: 
            wave_status = "修正浪 (股價<季線)"
            wave_icon = "🔻"
        col1.info(f"**波浪判斷**\n\n{wave_icon} {wave_status}")
        
        if macro:
            col2.warning(f"**美元指數 (DXY)**\n\n{macro['DXY']}\n\n({macro['DXY_MSG']})")
            col3.success(f"**恐慌指數 (VIX)**\n\n{macro['VIX']}\n\n({macro['VIX_MSG']})")
        else:
            col2.write("總經數據連線失敗")

        st.divider()

        # 區塊 2 & 3: 技術與量能
        st.markdown("#### ⚔️ 指標 2 & 3：技術動能與籌碼")
        c1, c2, c3, c4 = st.columns(4)
        
        k, d = latest['K'], latest['D']
        kd_msg = "中性"
        if prev['K'] < prev['D'] and k > d: kd_msg = "✨ 黃金交叉"
        elif k < 20: kd_msg = "💎 低檔鈍化"
        elif k > 80: kd_msg = "⚠️ 高檔過熱"
        c1.metric("KD 指標", f"K={k:.1f}", kd_msg)
        
        hist = latest['Hist']
        macd_msg = "中性"
        if prev['Hist'] < 0 and hist > 0: macd_msg = "🌊 翻紅轉強"
        elif hist > 0: macd_msg = "📈 多方勢"
        elif hist < 0: macd_msg = "📉 空方勢"
        c2.metric("MACD", f"{hist:.2f}", macd_msg)
        
        vol_msg = "平穩"
        if latest['Volume'] > latest['Vol_MA5'] * 1.5: vol_msg = "🔥 爆量"
        elif latest['Volume'] < latest['Vol_MA5'] * 0.6: vol_msg = "💤 量縮"
        c3.metric("成交量", vol_msg)
        
        obv_msg = "中性"
        if latest['OBV'] > latest['OBV_MA']:
            if latest['OBV'] > prev['OBV']: obv_msg = "🔴 吸納強勁"
            else: obv_msg = "🟠 多方回檔"
        else:
            if latest['OBV'] > prev['OBV']: obv_msg = "🔵 低檔承接"
            else: obv_msg = "🟢 籌碼渙散"
        c4.metric("OBV 籌碼", obv_msg)

        st.divider()

        # 區塊 4: 基本面
        with st.expander("🏢 點擊查看：個股體質診斷 / ETF 持股", expanded=True):
            if fund_data['is_etf']:
                st.write(f"**ETF 描述：** {fund_data.get('desc', '無')}")
                if 'holdings' in fund_data and fund_data['holdings'] is not None:
                    st.dataframe(fund_data['holdings'], hide_index=True, use_container_width=True)
                else:
                    st.caption("⚠️ 無法取得即時持股明細")
            else:
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("基本面評級", fund_data['verdict'])
                f2.metric("EPS", fund_data['eps'])
                f3.metric("ROE", fund_data['roe'])
                f4.metric("殖利率", fund_data['yield'])
                if fund_data['eps'] != "-" and float(fund_data['eps']) < 0:
                    st.error("⚠️ 警告：EPS 為負值，屬無基之彈，投資風險較高！")

        # 區塊 5: 圖表
        st.markdown("### 📈 全方位趨勢圖 (含 OBV)")
        
        # 設定圖表樣式 (使用系統字型)
        mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
        if market == "美股": mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
        
        # 關鍵：直接指定 packages.txt 安裝的字型
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
        
        # 圖表標題使用 Unicode 確保不亂碼
        fig, ax = mpf.plot(plot_data, type='candle', style=s, volume=True, 
                           addplot=add_plots, returnfig=True, 
                           panel_ratios=(4,1,1,1,1),
                           title=f"\n{name} ({stock_code}) Trend",
                           figratio=(10, 14))
        
        st.pyplot(fig)

    except Exception as e:
        st.error(f"發生錯誤：{e}")
