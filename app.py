import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import twstock
import os
import requests
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import re  # 用於處理自訂輸入

# --- 1. 頁面設定 (必須在第一行) ---
st.set_page_config(
    page_title="TitanLens Pro 泰坦透視鏡",
    page_icon="💎",
    layout="wide"
)

# =========== 🔒 密碼保護區 ===========
def check_password():
    SECRET_PASSWORD = "8888"  # 設定您的密碼
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        password = st.sidebar.text_input("🔒 請輸入啟用密碼", type="password")
        if password == SECRET_PASSWORD:
            st.session_state.password_correct = True
            st.rerun()
        elif password:
            st.sidebar.error("密碼錯誤")
        return False
    return True

if not check_password():
    st.stop()
# ====================================

# --- 2. 字型設定 ---
@st.cache_resource
def configure_font():
    # 嘗試使用系統字型
    font_path = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        font_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
        return font_prop.get_name(), True
    return "Sans-serif", False

custom_font_name, has_font = configure_font()
my_rc_params = {'font.family': custom_font_name, 'axes.unicode_minus': False}

# --- 3. 共用函數庫 ---

def get_stock_name(code, ticker):
    """取得股票名稱"""
    if code.isdigit() and code in twstock.codes:
        return twstock.codes[code].name
    return ticker.info.get('longName', code)

def calculate_indicators(df):
    """計算技術指標"""
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
    
    # KD
    low_list = df['Low'].rolling(window=9).min()
    high_list = df['High'].rolling(window=9).max()
    rsv = (df['Close'] - low_list) / (high_list - low_list) * 100
    df['K'] = rsv.ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    
    # MACD
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
    """取得基本面資料"""
    try:
        info = ticker_obj.info
        is_etf = info.get('quoteType') == 'ETF' or 'trailingEps' not in info
        
        data = {"is_etf": is_etf, "verdict": "中性", "pe": "-", "eps": "-", "roe": "-", "yield": "-"}
        
        if is_etf:
            data['desc'] = info.get('longBusinessSummary', '無描述')
            try:
                funds = ticker_obj.funds_data
                if funds and funds.top_holdings is not None:
                    h = funds.top_holdings.reset_index()
                    h.columns = ['公司', '比例']
                    h['比例'] = h['比例'].apply(lambda x: f"{x*100:.2f}%")
                    data['holdings'] = h
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

# --- 4. 頁面邏輯：單一診斷 (TitanLens) ---
def show_analysis_page():
    st.header("🔍 個股全方位診斷")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        raw_code = st.text_input("輸入代號 (例如 2330, 0050, NVDA)", value="2330")
    with col2:
        st.write("") 
        st.write("") 
        run_btn = st.button("開始診斷", type="primary", use_container_width=True)

    if run_btn or raw_code:
        stock_code = raw_code.strip().upper()
        market = "美股"
        if stock_code.isdigit():
            stock_code = f"{stock_code}.TW"
            market = "台股"
            
        try:
            with st.spinner("🔄 正在進行深度分析..."):
                df = yf.download(stock_code, period="6mo", progress=False, auto_adjust=True)
                if df.empty and market == "台股":
                    stock_code = stock_code.replace(".TW", ".TWO")
                    df = yf.download(stock_code, period="6mo", progress=False, auto_adjust=True)
                
                if df.empty:
                    st.error("❌ 找不到資料，請確認代號。")
                    return

                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                df = calculate_indicators(df)
                ticker = yf.Ticker(stock_code)
                fund_data = get_fundamental_info(ticker)
                name = get_stock_name(raw_code, ticker)
                latest = df.iloc[-1]
                prev = df.iloc[-2]

            # 顯示結果
            st.subheader(f"{name} ({stock_code})")
            st.metric("股價", f"{latest['Close']:.2f}", f"{(latest['Close']-prev['Close']):.2f}")
            
            # 指標卡片
            c1, c2, c3, c4 = st.columns(4)
            
            # KD
            k, d = latest['K'], latest['D']
            kd_msg = "金叉" if prev['K'] < prev['D'] and k > d else "中性"
            c1.metric("KD 指標", f"K={k:.0f}", kd_msg)
            
            # MACD
            hist = latest['Hist']
            macd_msg = "翻紅" if prev['Hist'] < 0 and hist > 0 else "中性"
            c2.metric("MACD", f"{hist:.2f}", macd_msg)
            
            # OBV
            obv_msg = "吸籌" if latest['OBV'] > latest['OBV_MA'] and latest['OBV'] > prev['OBV'] else "中性"
            c3.metric("籌碼 OBV", obv_msg)
            
            # 基本面
            if fund_data['is_etf']:
                c4.metric("類型", "ETF")
            else:
                c4.metric("體質", fund_data['verdict'], f"EPS: {fund_data['eps']}")

            # 圖表
            st.markdown("### 📈 技術走勢圖")
            mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
            if market == "美股": mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
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
            
            fig, ax = mpf.plot(plot_data, type='candle', style=s, volume=True, 
                               addplot=add_plots, returnfig=True, 
                               panel_ratios=(4,1,1,1,1), figratio=(10, 14),
                               title=f"\n{name} Trend")
            st.pyplot(fig)

        except Exception as e:
            st.error(f"發生錯誤：{e}")

# --- 5. 頁面邏輯：策略雷達 (Strategy Radar) ---
def show_radar_page():
    st.header("📡 策略雷達掃描")
    
    # 完整清單
    STOCK_POOLS = {
        "台股-權值50": [
            "2330", "2317", "2454", "2308", "2303", "2881", "2882", "2603", "1301", "2002",
            "2382", "2357", "3231", "6669", "2891", "1216", "2886", "2884", "1303", "2412",
            "3008", "3045", "2892", "5880", "2327", "2880", "2345", "2885", "2207", "1101",
            "2395", "4938", "2883", "2887", "2609", "2615", "5871", "2379", "3034"
        ],
        "台股-AI 伺服器/散熱": [
            "2330", "2317", "2382", "3231", "2356", "2376", "6669", "3443", "3661", "3035", 
            "2454", "2308", "3017", "3324", "2421", "2059", "3013", "3533", "5269", "8210"
        ],
        "台股-航運/重電": [
            "2603", "2609", "2615", "2618", "2610", "2637", "5608", "2606", "2605",
            "1513", "1519", "1503", "1504", "1609", "6806", "3708"
        ],
        "台股-熱門 ETF": [
            "0050", "0056", "00878", "00929", "00919", "00940", "00713", "00939", "006208", 
            "00881", "00830"
        ],
        "美股-科技巨頭": [
            "AAPL", "NVDA", "MSFT", "GOOG", "AMZN", "META", "TSLA",
            "TSM", "AMD", "AVGO", "QCOM", "TXN", "INTC", "MU", "AMAT", "LRCX", "SMCI", "ARM"
        ]
    }

    with st.expander("📖 查看操作策略指南"):
        st.markdown("""
        * **🟢 存股/波段 (強度 1)：** 尋找 KD 金叉且基本面良好 (ROE>10%) 的股票。
        * **🟡 短線轉強 (強度 3)：** 出現爆量或 MACD 翻紅，資金開始進駐。
        * **🔴 強力攻擊 (強度 4-7)：** 多項指標同時轉強，通常為主升段。
        """)

    # 選擇模式
    mode = st.radio("選擇掃描模式：", ["使用內建清單", "自行輸入代號"], horizontal=True)
    selected_codes = []
    
    if mode == "使用內建清單":
        pool_name = st.selectbox("選擇掃描族群", list(STOCK_POOLS.keys()))
        selected_codes = STOCK_POOLS[pool_name]
        st.caption(f"共選取 {len(selected_codes)} 檔標的")
    else:
        user_input = st.text_area("輸入代號 (用逗號或空白分隔)", "2330, 2603, NVDA, TSLA")
        if user_input:
            selected_codes = re.split(r'[,\s\n]+', user_input.strip())
            selected_codes = [c.upper() for c in selected_codes if c]
            st.caption(f"已辨識 {len(selected_codes)} 檔標的")

    min_score = st.slider("最低強度過濾", 1, 7, 3)
    
    if st.button("🚀 啟動雷達掃描", type="primary"):
        if not selected_codes:
            st.warning("請先選擇或輸入股票代號")
            return

        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        scan_count = 0
        
        for i, code in enumerate(selected_codes):
            status_text.text(f"正在掃描: {code} ...")
            progress_bar.progress((i + 1) / len(selected_codes))
            
            try:
                market = "美股"
                q_code = code
                if code.isdigit():
                    q_code = f"{code}.TW"
                    market = "台股"
                
                df = yf.download(q_code, period="3mo", progress=False, auto_adjust=True)
                if df.empty and market == "台股":
                    q_code = f"{code}.TWO"
                    df = yf.download(q_code, period="3mo", progress=False, auto_adjust=True)
                
                if df.empty or len(df) < 30: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                scan_count += 1
                
                # 計算指標
                df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
                
                ema12 = df['Close'].ewm(span=12, adjust=False).mean()
                ema26 = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = ema12 - ema26
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                df['Hist'] = df['MACD'] - df['Signal']
                
                low_9 = df['Low'].rolling(9).min()
                high_9 = df['High'].rolling(9).max()
                rsv = (df['Close'] - low_9) / (high_9 - low_9) * 100
                k = rsv.ewm(com=2).mean()
                d = k.ewm(com=2).mean()
                
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                
                # 評分
                score = 0
                reasons = []
                
                # 爆量
                vol_val = float(latest['Volume'])
                vol_ma = float(latest['Vol_MA5'])
                if vol_val > vol_ma * 1.5 and latest['Close'] > prev['Close']:
                    score += 3; reasons.append("🔥爆量")
                
                # MACD (綠翻紅)
                hist_now = float(latest['Hist'])
                hist_prev = float(prev['Hist'])
                if hist_prev < 0 and hist_now > 0:
                     score += 3; reasons.append("🌊MACD翻紅")
                
                # KD (金叉)
                k_now = float(k.iloc[-1])
                d_now = float(d.iloc[-1])
                k_prev = float(k.iloc[-2])
                d_prev = float(d.iloc[-2])
                if k_prev < d_prev and k_now > d_now and k_now < 50:
                    score += 1; reasons.append("✨KD金叉")
                
                if score >= min_score:
                    ticker = yf.Ticker(q_code)
                    info = ticker.info
                    name = get_stock_name(code, ticker)
                    
                    eps = info.get('trailingEps', '-')
                    if eps != '-' and isinstance(eps, (int, float)): eps = f"{eps:.2f}"
                    
                    results.append({
                        "代號": code,
                        "名稱": name,
                        "現價": f"{latest['Close']:.2f}",
                        "強度": score,
                        "訊號": " ".join(reasons),
                        "EPS": eps
                    })
            except Exception:
                continue
            
        progress_bar.empty()
        status_text.empty()
        
        st.info(f"掃描完畢！共分析 {scan_count} 檔有效股票。")
        
        if results:
            df_res = pd.DataFrame(results)
            df_res = df_res.sort_values(by="強度", ascending=False)
            st.success(f"🎉 找到 {len(df_res)} 檔符合條件標的！")
            st.dataframe(df_res, hide_index=True, use_container_width=True)
        else:
            st.warning(f"⚠️ 掃描結束，沒有發現強度 >= {min_score} 的股票。")

# --- 6. 主程式架構 ---

st.sidebar.title("💎 功能選單")
page = st.sidebar.radio("請選擇模式：", ["📊 個股全方位診斷", "📡 策略雷達掃描"])

if page == "📊 個股全方位診斷":
    show_analysis_page()
else:
    show_radar_page()
