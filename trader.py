import os
from coinbase.wallet.client import Client
from websocket import create_connection, WebSocketConnectionClosedException
import json
import ssl
import time
import hmac
import hashlib
from threading import Thread

# Get the keys from the environment variables
api_key = os.environ['CB_KEY']
api_secret = os.environ['CB_SECRET']

# Make a new client
client = Client(api_key, api_secret)

# Get the ethereum account
eth_account = client.get_account('ETH')
print(eth_account)

def main():
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


if __name__ == "__main__":
    main()