import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime

# =========================================================
# [설정] 텔레그램 토큰 및 감시 종목
# =========================================================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
DATA_FILE = "market_cap_history.csv"

# 1. 매크로 지표
MACRO_TICKERS = {
    '원/달러': 'KRW=X', '원/엔': 'JPYKRW=X', '원/유로': 'EURKRW=X',
    '달러/위안': 'CNY=X', '금 선물': 'GC=F', 'WTI 원유': 'CL=F',
    'S&P 500': '^GSPC', '나스닥': '^IXIC', '닛케이': '^N225',
    '코스피': '^KS11', '코스닥': '^KQ11', '미 국채 10년': '^TNX'
}

# 2. 시가총액 상위 감시 대상 (Top 50 후보군)
MCAP_WATCHLIST = [
    'AAPL', 'MSFT', 'NVDA', 'GOOG', 'AMZN', 'META', 'TSLA', 'BRK-A', 'LLY', 'AVGO',
    'JPM', 'V', 'ORCL', 'WMT', 'XOM', 'MA', 'NFLX', 'JNJ', 'COST', 'ABBV', 'PLTR', 'BAC',
    'PG', 'HD', 'AMD', 'KO', 'GE', 'CRM', 'CSCO', 'CVX', 'UNH', 'IBM', 'WFC',
    'CAT', 'MS', 'AXP', 'MRK', 'PM', 'TMUS', 'MU', 'GS', 'RTX', 'ABT', 'TMO',
    'MCD', 'CRM', 'PEP', 'ISRG', 'LIN', 'SHOP'
]

# =========================================================
# [함수] 텔레그램 전송
# =========================================================
def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ 텔레그램 설정 누락")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': CHAT_ID, 'text': message}
    try:
        requests.post(url, data=data)
        print("✅ 텔레그램 전송 완료")
    except Exception as e:
        print(f"❌ 전송 실패: {e}")

# =========================================================
# [로직 1] 매크로 지표 요약
# =========================================================
def get_macro_summary():
    print("\n[1단계] 매크로 지표 수집 중...")
    try:
        df = yf.download(list(MACRO_TICKERS.values()), period="5d", progress=False)['Close']
        inv_tickers = {v: k for k, v in MACRO_TICKERS.items()}
        df.rename(columns=inv_tickers, inplace=True)
        df.fillna(method='ffill', inplace=True)

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        today_str = df.index[-1].strftime('%Y-%m-%d')
        
        msg = f"🌍 [세계 증시 및 지표] {today_str}\n"
        msg += "-" * 30 + "\n"

        for name in MACRO_TICKERS.keys():
            if name in latest:
                price = latest[name]
                change_pct = ((price - prev[name]) / prev[name]) * 100
                emoji = "🟢" if change_pct > 0 else "🔻"
                if change_pct == 0: emoji = "➖"
                
                msg += f"{emoji} {name}\n"
                msg += f"   {price:,.2f} ({change_pct:+.2f}%)\n"
        return msg
    except Exception as e:
        return f"❌ 매크로 지표 오류: {e}"

# =========================================================
# [로직 2] 시가총액 데이터 관리 및 분석
# =========================================================
def get_shares_outstanding(tickers):
    shares_data = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            s = info.get('sharesOutstanding', 0)
            if s > 0: shares_data[t] = s
        except: continue
    return shares_data

def ensure_data_consistency():
    need_backfill = False
    if not os.path.exists(DATA_FILE): need_backfill = True
    else:
        if len(pd.read_csv(DATA_FILE, index_col=0)) < 20: need_backfill = True
            
    if need_backfill:
        print("⚠️ 과거 데이터 복원 중... (시간 소요)")
        shares = get_shares_outstanding(MCAP_WATCHLIST)
        hist = yf.download(list(shares.keys()), period="1mo", progress=False)['Close']
        mcap_data = {}
        for date in hist.index:
            d_str = date.strftime('%Y-%m-%d')
            daily = {}
            row = hist.loc[date]
            for t, s in shares.items():
                if t in row and pd.notna(row[t]):
                    daily[t] = (row[t] * s) / 1_000_000_000
            if daily: mcap_data[d_str] = daily
        
        new_df = pd.DataFrame.from_dict(mcap_data, orient='index')
        new_df.sort_index(inplace=True)
        new_df.to_csv(DATA_FILE)
        print("✅ 데이터 복원 완료")

def update_and_analyze_mcap():
    print("\n[2단계] 시가총액 분석 중...")
    ensure_data_consistency()
    
    if os.path.exists(DATA_FILE): df = pd.read_csv(DATA_FILE, index_col=0)
    else: df = pd.DataFrame()

    prices = yf.download(MCAP_WATCHLIST, period="1d", progress=False)['Close']
    latest_prices = prices.iloc[-1]
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    shares = get_shares_outstanding(MCAP_WATCHLIST)
    today_caps = {}
    for t, s in shares.items():
        if t in latest_prices and pd.notna(latest_prices[t]):
            today_caps[t] = (latest_prices[t] * s) / 1_000_000_000
            
    new_row = pd.DataFrame([today_caps], index=[today_str])
    if today_str in df.index: df = df.drop(today_str)
    df = pd.concat([df, new_row])
    df.sort_index(inplace=True)
    df.to_csv(DATA_FILE)
    
    # ---- 보고서 작성 시작 ----
    msg = []
    msg.append(f"🇺🇸 [미국 시총 순위 분석] {today_str}")
    msg.append("=" * 30)
    
    if len(df) >= 2:
        today_s = df.iloc[-1].sort_values(ascending=False)
        prev_s = df.iloc[-2].sort_values(ascending=False)
        today_rk = {t: i+1 for i, t in enumerate(today_s.index)}
        prev_rk = {t: i+1 for i, t in enumerate(prev_s.index)}
        
        # ------------------------------------------
        # (1) Top 10 변동 (가장 중요!)
        # ------------------------------------------
        msg.append("\n🏆 [Top 10 최상위 변동]")
        top10_changes = []
        for t in today_s.head(10).index:
            cur, prv = today_rk.get(t), prev_rk.get(t)
            if prv and cur != prv:
                # 10위권 내 변동은 불꽃(🔥) 아이콘 사용
                top10_changes.append(f"🔥 {t}: {prv}위 → {cur}위")
        
        if top10_changes: msg.extend(top10_changes)
        else: msg.append("   변동 없음 (고요함)")

        # ------------------------------------------
        # (2) Top 11 ~ 30 변동
        # ------------------------------------------
        msg.append("\n📅 [Top 11~30위권 변동]")
        mid_changes = []
        # 10위 밖 ~ 30위 안쪽 종목들만 체크
        for t in today_s.iloc[10:30].index:
            cur, prv = today_rk.get(t), prev_rk.get(t)
            if prv and cur != prv:
                icon = "🟢" if prv > cur else "🔻"
                mid_changes.append(f"{icon} {t}: {prv}위 → {cur}위")
        
        if mid_changes: msg.extend(mid_changes)
        else: msg.append("   변동 없음")

    else:
        msg.append("   (데이터 수집 중: 2일차부터 분석 가능)")
    
    # ------------------------------------------
    # (3) 20일 이평선 진입/이탈
    # ------------------------------------------
    msg.append("\n🌊 [20일 평균 Top 30 진입/이탈]")
    if len(df) >= 20:
        ma_today = df.iloc[-20:].mean().sort_values(ascending=False)
        ma_prev = df.iloc[-21:-1].mean().sort_values(ascending=False)
        
        new_in = set(ma_today.head(30).index) - set(ma_prev.head(30).index)
        out = set(ma_prev.head(30).index) - set(ma_today.head(30).index)
        
        if new_in:
            for t in new_in: msg.append(f"🚀 [진입] {t} (평균 {list(ma_today.index).index(t)+1}위)")
        if out:
            for t in out: msg.append(f"🍂 [이탈] {t}")
        if not new_in and not out: msg.append("   특이 사항 없음")
    else:
        msg.append(f"   (데이터 쌓는 중: {len(df)}/20일)")

    return "\n".join(msg)

# =========================================================
# [메인 실행]
# =========================================================
if __name__ == "__main__":
    # 1. 매크로 지표 전송
    macro_msg = get_macro_summary()
    send_telegram(macro_msg)
    
    # 2. 시가총액 분석 전송
    mcap_msg = update_and_analyze_mcap()
    send_telegram(mcap_msg)
