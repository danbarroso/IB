from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import threading
import time

class IBapi(EWrapper, EClient):
	def __init__(self):
		EClient.__init__(self, self)

	def error(self, reqId, errorCode, errorString):
		print("Error: ", reqId, " ", errorCode, " ", errorString)

def run_loop():
	app.run()

print("Testing connection...")

app = IBapi()
app.connect('127.0.0.1', 7497, 123)

time.sleep(3)
thread = threading.Thread(target=run_loop)
thread.start()

time.sleep(10)
app.disconnect()
print("-------------------------------------")
print("Check the above messages to see if your connection is working")