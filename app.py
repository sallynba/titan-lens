# --- 5. 頁面邏輯：策略雷達 (Strategy Radar) ---
def show_radar_page():
    st.header("📡 策略雷達掃描")
    
    # === 🌟 這裡擴充了更完整的清單 ===
    STOCK_POOLS = {
        "台股-權值50 (0050成份)": [
            "2330", "2317", "2454", "2308", "2303", "2881", "2882", "2603", "1301", "2002",
            "2382", "2357", "3231", "6669", "2891", "1216", "2886", "2884", "2002", "1303",
            "2412", "3008", "3045", "2892", "5880", "2327", "2880", "2345", "2885", "2207",
            "1101", "2395", "4938", "2883", "2887", "2609", "2615", "5871", "2379", "3034"
        ],
        "台股-AI 伺服器/散熱": [
            "2330", "2317", "2382", "3231", "2356", "2376", "6669", "3443", "3661", "3035", 
            "2454", "2308", "3017", "3324", "2421", "2059", "3013", "3533", "5269", "8210"
        ],
        "台股-航運/重電/綠能": [
            "2603", "2609", "2615", "2618", "2610", "2637", "5608", "2606", "2605", # 航運
            "1513", "1519", "1503", "1504", "1609", "6806", "3708" # 重電綠能
        ],
        "台股-熱門 ETF": [
            "0050", "0056", "00878", "00929", "00919", "00940", "00713", "00939", "006208", 
            "00881", "00830", "00679B", "00687B"
        ],
        "美股-科技巨頭 & 半導體": [
            "AAPL", "NVDA", "MSFT", "GOOG", "AMZN", "META", "TSLA", # 七雄
            "TSM", "AMD", "AVGO", "QCOM", "TXN", "INTC", "MU", "AMAT", "LRCX", "SMCI", "ARM"
        ]
    }

    with st.expander("📖 查看操作策略指南"):
        st.markdown("""
        * **🟢 存股/波段 (強度 1)：** 尋找 KD 金叉且基本面良好 (ROE>10%) 的股票。
        * **🟡 短線轉強 (強度 3)：** 出現爆量或 MACD 翻紅，資金開始進駐。
        * **🔴 強力攻擊 (強度 4-7)：** 多項指標同時轉強，通常為主升段。
        """)

    # --- 介面選擇區 ---
    mode = st.radio("選擇掃描模式：", ["使用內建清單", "自行輸入代號"], horizontal=True)
    
    selected_codes = []
    
    if mode == "使用內建清單":
        pool_name = st.selectbox("選擇掃描族群", list(STOCK_POOLS.keys()))
        selected_codes = STOCK_POOLS[pool_name]
        st.caption(f"共選取 {len(selected_codes)} 檔標的")
        
    else:
        user_input = st.text_area("輸入代號 (用逗號或空白分隔)", "2330, 2603, NVDA, TSLA")
        if user_input:
            # 自動處理分隔符號 (逗號、空白、換行)
            import re
            selected_codes = re.split(r'[,\s\n]+', user_input.strip())
            # 過濾空字串並轉大寫
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
                
                # 下載數據 (只抓最近3個月加快速度)
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
                
                # 1. 爆量
                vol_val = float(latest['Volume'])
                vol_ma = float(latest['Vol_MA5'])
                if vol_val > vol_ma * 1.5 and latest['Close'] > prev['Close']:
                    score += 3; reasons.append("🔥爆量")
                
                # 2. MACD (綠翻紅)
                hist_now = float(latest['Hist'])
                hist_prev = float(prev['Hist'])
                if hist_prev < 0 and hist_now > 0:
                     score += 3; reasons.append("🌊MACD翻紅")
                
                # 3. KD (金叉)
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
