import os
from coinbase.wallet.client import Client
from websocket import create_connection, WebSocketConnectionClosedException
import json
import ssl
import time
import hmac
import hashlib
from threading import Thread
import requests
from datetime import datetime
import ta
import numpy as np
import pandas as pd

# Get the keys from the environment variables
api_key = os.environ['CB_KEY']
api_secret = os.environ['CB_SECRET']

# Make a new client
client = Client(api_key, api_secret)

# Sign a message
def sign_message(request) -> requests.Request:
    """Signs the request"""

    timestamp = str(int(time.time()))
    body = (request.body or b"").decode()
    url = request.path_url.split("?")[0]
    message = f"{timestamp}{request.method}{url}{body}"
    signature = hmac.new(api_secret.encode("utf-8"), message.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()

    request.headers.update(
        {
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-KEY": api_key,
            "Content-Type": "application/json",
        }
    )

    return request

def websocket_receive():
    ws = None
    thread = None
    thread_running = False
    thread_keepalive = None

    def websocket_thread():
        global ws

        channel = "level2"
        timestamp = str(int(time.time()))
        product_ids = ["ETH-USD"]
        product_ids_str = ",".join(product_ids)
        message = f"{timestamp}{channel}{product_ids_str}"
        signature = hmac.new(api_secret.encode("utf-8"), message.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()

        ws = create_connection("wss://advanced-trade-ws.coinbase.com", sslopt={"cert_reqs": ssl.CERT_NONE})
        ws.send(
            json.dumps(
                {
                    "type": "subscribe",
                    "product_ids": [
                        "ETH-USD",
                    ],
                    "channel": channel,
                    "api_key": api_key,
                    "timestamp": timestamp,
                    "signature": signature,
                }
            )
        )

        thread_keepalive.start()
        while not thread_running:
            try:
                data = ws.recv()
                if data != "":
                    msg = json.loads(data)
                else:
                    msg = {}
            except ValueError as e:
                print(e)
                print("{} - data: {}".format(e, data))
            except Exception as e:
                print(e)
                print("{} - data: {}".format(e, data))
            else:
                if "result" not in msg:
                    print(msg)

        try:
            if ws:
                ws.close()
        except WebSocketConnectionClosedException:
            pass
        finally:
            thread_keepalive.join()

    def websocket_keepalive(interval=30):
        global ws
        while ws.connected:
            ws.ping("keepalive")
            time.sleep(interval)

    thread = Thread(target=websocket_thread)
    thread_keepalive = Thread(target=websocket_keepalive)
    thread.start()

eth_candles_api = 'https://api.coinbase.com/api/v3/brokerage/products/ETH-USD/candles'
order_api = 'https://api.coinbase.com/api/v3/brokerage/orders'

accounts = client.get_accounts()

eth_account = client.get_account('ETH')
print(eth_account)
usd_account = client.get_account('USD')
print(usd_account)

long_position = True

# Main function
if __name__ == "__main__":
    start_date_time = 0
    end_date_time = 0
    
    # Wait for 15 minute interval
    print("Waiting for 15 minute interval to start...")
    while datetime.now().minute not in {0, 15, 30, 45}:  # Wait 1 second until we are synced up with the 'every 15 minutes' clock
        time.sleep(1)

    periods = 14
    seconds_in_fifteen_minutes = 900

    rsi_oversold = 25
    rsi_overbought = 75

    def task():
        global long_position

        # Get the last 14 15 minute candles (3.5 hours)
        end_date_time = int(time.mktime(datetime.now().timetuple()))
        start_date_time = end_date_time - seconds_in_fifteen_minutes*periods*4    # 900 seconds in 15 minutes
        payload = {"start": start_date_time, "end": end_date_time, "granularity": "FIFTEEN_MINUTE"}
        candles = requests.get(eth_candles_api, params=payload, auth=sign_message)

        closing_prices = []
        for candle in candles.json()['candles']:
            closing_prices.append(float(candle['close']))

        # reverse the prices
        closing_prices.reverse()

        np_prices = np.array(closing_prices)
        price_series = pd.Series(np_prices)
        rsi = ta.momentum.rsi(price_series, periods, False)
        current_rsi = rsi.iloc[-1]
        print(datetime.now(), " RSI: ", current_rsi)

        if long_position and (current_rsi > rsi_overbought):
            max_eth_amount = float(client.get_account('ETH')['balance']['amount'])
            print ("PLACE SELL ORDER ", max_eth_amount, " ETH")
            payload = {
                "client_order_id": str(np.random.randint(2**63)),
                "product_id": "ETH-USD",
                "side": "SELL",
                "order_configuration": {
                    "market_market_ioc": {
                        "base_size": max_eth_amount,
                    }
                }
            }
            resp = requests.post(order_api, params=payload, auth=sign_message)
            long_position = False
        
        elif (not long_position) and  (current_rsi < rsi_oversold):
            max_usd_amount = float(client.get_account('USD')['balance']['amount'])
            print ("PLACE BUY ORDER ", max_usd_amount, " USD")
            payload = {
                "client_order_id": str(np.random.randint(2**63)),
                "product_id": "ETH-USD",
                "side": "BUY",
                "order_configuration": {
                    "market_market_ioc": {
                        "quote_size": max_usd_amount,
                    }
                }
            }
            resp = requests.post(order_api, params=payload, auth=sign_message)
            long_position = True

    task()

    while True:
        time.sleep(60*15)  # Wait for 15 minutes
        task()

    # websocket_receive()
    