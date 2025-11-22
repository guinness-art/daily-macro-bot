import yfinance as yf
import requests
import os
from datetime import datetime

# Github Secrets에서 환경변수로 받아옵니다 (보안)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_financial_summary():
    tickers = {
        '원/달러': 'KRW=X', '원/엔': 'JPYKRW=X', '원/유로': 'EURKRW=X',
        '달러/위안': 'CNY=X', '금 선물': 'GC=F', 'WTI 원유': 'CL=F',
        'S&P 500': '^GSPC', '나스닥': '^IXIC', '닛케이': '^N225',
        '코스피': '^KS11', '코스닥': '^KQ11', '미 국채 10년': '^TNX'
    }
    
    try:
        df = yf.download(list(tickers.values()), period="5d", progress=False)['Close']
        inv_tickers = {v: k for k, v in tickers.items()}
        df.rename(columns=inv_tickers, inplace=True)
        df.fillna(method='ffill', inplace=True)

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        today_str = df.index[-1].strftime('%Y-%m-%d')
        message = f"📊 [경제 지표 요약] {today_str}\n"
        message += "-" * 25 + "\n"

        for name in tickers.keys():
            if name in latest:
                price = latest[name]
                change_pct = ((price - prev[name]) / prev[name]) * 100
                emoji = "🔺" if change_pct > 0 else "🔻"
                if change_pct == 0: emoji = "➖"
                message += f"{emoji} {name}\n"
                message += f"   {price:,.2f} ({change_pct:+.2f}%)\n"
        
        return message
    except Exception as e:
        return f"❌ 오류 발생: {e}"

def send_telegram_message():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("토큰이나 ID가 설정되지 않았습니다.")
        return

    summary_text = get_financial_summary()
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': CHAT_ID, 'text': summary_text}
    
    # 수정된 부분: 응답(response)을 받아서 확인합니다.
    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        print("✅ 텔레그램 서버 전송 성공!")
    else:
        # 실패했다면 왜 실패했는지 텔레그램이 알려주는 메시지를 출력합니다.
        print(f"❌ 전송 실패! 상태 코드: {response.status_code}")
        print(f"상세 에러 내용: {response.text}")

if __name__ == "__main__":
    send_telegram_message()
