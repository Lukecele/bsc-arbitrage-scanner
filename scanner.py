import requests
import time
import sys

BNB_INPUT_AMOUNT = 0.005  # Size in BNB
MIN_PROFIT_PCT = 1.2      # Soglia profitto per alert (%)

WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
KYBER_ROUTES_API = "https://aggregator-api.kyberswap.com/bsc/api/v1/routes"
KYBER_BUILD_API = "https://aggregator-api.kyberswap.com/bsc/api/v1/route/build"

TOKEN_LIST_URLS = [
    "https://tokens.pancakeswap.finance/pancakeswap-extended.json",
    "https://raw.githubusercontent.com/viaprotocol/tokenlists/main/tokenlists/bsc.json"
]

session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"
})

def verify_kyber_executable(route_summary, sender="0xaff5163102a945952d75ea6a32d185e4afd604e7"):
    """Verifica che KyberSwap riesca a compilare il calldata di routing senza errori di pool fantasma"""
    try:
        payload = {
            "routeSummary": route_summary,
            "sender": sender,
            "recipient": sender,
            "slippageTolerance": 150  # 1.5% slippage
        }
        r = session.post(KYBER_BUILD_API, json=payload, timeout=3)
        if r.status_code == 200:
            res = r.json()
            # Se data contiene il bytecode del router, la transazione è costruibile
            if res.get("data", {}).get("data"):
                return True
    except Exception:
        pass
    return False

def load_bsc_tokens():
    tokens = {}
    for url in TOKEN_LIST_URLS:
        try:
            r = session.get(url, timeout=6)
            if r.status_code == 200:
                raw = r.json()
                items = raw.get("tokens", []) if isinstance(raw, dict) else raw
                for t in items:
                    if isinstance(t, dict) and t.get("chainId") == 56:
                        addr = (t.get("address") or "").lower()
                        if addr and addr != WBNB.lower():
                            tokens[addr] = {
                                "address": t.get("address"),
                                "symbol": t.get("symbol", "TOKEN"),
                                "name": t.get("name", "")
                            }
        except Exception:
            continue
    return list(tokens.values())

def get_quote(token_in, token_out, amount_wei):
    params = {
        "tokenIn": token_in,
        "tokenOut": token_out,
        "amountIn": str(amount_wei),
        "saveGas": "0",
        "gasInclude": "1"
    }
    try:
        r = session.get(KYBER_ROUTES_API, params=params, timeout=3.5)
        if r.status_code == 200:
            return r.json().get("data", {}).get("routeSummary")
    except Exception:
        pass
    return None

last_alert_time = {}

def evaluate_token(token_data, current_idx, total_tokens):
    addr = token_data["address"]
    addr_lower = addr.lower()
    symbol = token_data["symbol"]
    
    # Aggiorna progress bar a video
    sys.stdout.write(f"\r[{time.strftime('%X')}] Analisi [{current_idx}/{total_tokens}] {symbol:<10}")
    sys.stdout.flush()

    amount_in_wei = int(BNB_INPUT_AMOUNT * 1e18)
    
    # 1. Quota Buy: BNB -> TOKEN
    quote_buy = get_quote(WBNB, addr, amount_in_wei)
    if not quote_buy:
        return
        
    token_out_wei = int(quote_buy.get("amountOut", 0))
    if token_out_wei == 0:
        return
        
    time.sleep(0.06)
    
    # 2. Quota Sell: TOKEN -> BNB
    quote_sell = get_quote(addr, WBNB, token_out_wei)
    if not quote_sell:
        return
        
    final_bnb_wei = int(quote_sell.get("amountOut", 0))
    if final_bnb_wei == 0:
        return
        
    final_bnb = final_bnb_wei / 1e18
    profit_bnb = final_bnb - BNB_INPUT_AMOUNT
    profit_pct = (profit_bnb / BNB_INPUT_AMOUNT) * 100
    
    # Se il profitto raggiunge la soglia minima richiesta
    if profit_pct >= MIN_PROFIT_PCT:
        # Verifica che il router sia in grado di generare la transazione (anti-pool fantasma)
        if not verify_kyber_executable(quote_buy) or not verify_kyber_executable(quote_sell):
            return
            
        if addr_lower in last_alert_time and (time.time() - last_alert_time[addr_lower]) < 120:
            return
            
        last_alert_time[addr_lower] = time.time()
        
        route_in = [s[0].get("exchange") for s in quote_buy.get("route", []) if s]
        route_out = [s[0].get("exchange") for s in quote_sell.get("route", []) if s]
        
        print("\n\n" + "🚀" * 32)
        print(f"🚨 OPPORTUNITÀ ATTIVA: {symbol} ({token_data['name']})")
        print(f"📍 Indirizzo Target: {addr}")
        print(f"📈 Profitto Stimato: +{profit_pct:.2f}% (+{profit_bnb:.6f} BNB)")
        print(f"🛒 Routing Compra  : {' -> '.join(route_in)}")
        print(f"💰 Routing Vendita : {' -> '.join(route_out)}")
        print(f"🔗 Swap Diretto    : https://kyberswap.com/swap/bsc/bnb-to-{addr}")
        print("🚀" * 32 + "\n")

if __name__ == "__main__":
    print("=" * 64)
    print("🚀 BSC KyberSwap Real-Time Arbitrage & Route Scanner")
    print("ℹ️  MODE: READ-ONLY TELEMETRY & SIMULATION")
    print("⚠️  Notice: On-chain auto-execution is disabled by design.")
    print("   This bot identifies live arbitrage opportunities and verifies")
    print("   routing calldata executability without holding private keys.")
    print("=" * 64 + "\n")

    token_list = load_bsc_tokens()
    print(f"✅ Monitoraggio avviato su {len(token_list)} token BSC.")
    print(f"Configurazione: Size {BNB_INPUT_AMOUNT} BNB | Soglia >= +{MIN_PROFIT_PCT}%\n")
    
    while True:
        for idx, t in enumerate(token_list, 1):
            evaluate_token(t, idx, len(token_list))
            time.sleep(0.08)
        print(f"\n[{time.strftime('%X')}] Ciclo completato. Riavvio...")
        time.sleep(2)
