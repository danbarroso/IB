from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract, ContractDetails
from ibapi.scanner import ScannerSubscription, ScanData
from ibapi.tag_value import TagValue
from ibapi.ticktype import TickTypeEnum
from ibapi.order import *
from ibapi.order_state import OrderState
import time
import threading
import datetime
from input import LONG_TICKERS, SHORT_TICKERS, TRADE_RISK, ACCOUNT_PERCENT, RISK_TYPE, ACCOUNT_STRING
import sys
import json


print("Retrieving Local Stage Data...")
with open("data.json") as f:
	data = json.load(f)



class IBapi(EWrapper, EClient):
	def __init__(self):
		EClient.__init__(self, self)

		self.nextOrderId = -1
		self.positions = {}
		self.pnl_req_ids = {}
		self.pnl_recieved = set()
		self.pnl_expected = -1
		self.price_req_ids = {}
		self.price_recieved = set()
		self.price_expected = -1



	def check_stages(self):
		for symbol, info in self.positions.items():
			if symbol in data["stage0"]["short"]: 
				if info["size"] != 0 and len(info["orders"]) == 2:
					data["stage0"]["short"].remove(symbol)
					data["stage1"]["short"].append(symbol)
					print(symbol, "moved from Stage 0 to Stage 1 (short)")
				elif info["size"] == 0 and len(info["orders"]) ==0:
					data["stage0"]["short"].remove(symbol)
					print(symbol, "position closed during day (bracket order).")
			elif symbol in data["stage0"]["long"]:
				if info["size"] != 0 and len(info["orders"]) == 2:
					data["stage0"]["long"].remove(symbol)
					data["stage1"]["long"].append(symbol)
					print(symbol, "moved from Stage 0 to Stage 1 (long)")
				elif info["size"] == 0 and len(info["orders"]) ==0:
					data["stage0"]["long"].remove(symbol)
					print(symbol, "position closed during day (bracket order).")

			elif symbol in data["stage1"]["short"]:
				if info["size"] == 0 and len(info["orders"]) == 0:
					data["stage1"]["short"].remove(symbol)
					print(symbol, "position closed during day (bracket order).")
			elif symbol in data["stage1"]["long"]:
				if info["size"] == 0 and len(info["orders"]) == 0:
					data["stage1"]["long"].remove(symbol)
					print(symbol, "position closed during day (bracket order).")

			elif symbol in data["stage2"]["short"]:
				if info["size"] == 0 and len(info["orders"]) == 0:
					data["stage2"]["short"].remove(symbol)
					print(symbol, "position closed during day (stop order).")
			elif symbol in data["stage2"]["long"]:
				if info["size"] == 0 and len(info["orders"]) == 0:
					data["stage2"]["long"].remove(symbol)
					print(symbol, "position closed during day (stop order).")

		
		print("Retrieving position profits...")
		self.advance_stage1()
			


	def advance_stage1(self):

		self.pnl_expected = len(data["stage1"]["long"]) + len(data["stage1"]["short"])
		if self.pnl_expected == 0:
			print("No Stage 1 positions, updating Stage 2 stops...")
			self.advance_stage2()
		reqId = 0
		for symbol in data["stage1"]["long"]:
			conId = self.positions[symbol]["contract"].conId
			self.pnl_req_ids[reqId] = symbol
			self.reqPnlSingle(reqId, ACCOUNT_STRING, "", conId)
			reqId += 1

		for symbol in data["stage1"]["short"]:
			conId = self.positions[symbol]["contract"].conId
			self.pnl_req_ids[reqId] = symbol
			self.reqPnlSingle(reqId, ACCOUNT_STRING, "", conId)
			reqId += 1

	def advance_stage2(self):

		self.price_expected = len(data["stage2"]) + len(data["stage2"])
		if self.price_expected == 0:
			print("No Stage 2 positions...")
			self.disconnect()
		reqId = 0
		for symbol in data["stage2"]["long"]:
			info = self.positions[symbol]
			for orderId in info["orders"]:
				self.cancelOrder(orderId)
			self.reqHistoricalData(reqId, info["contract"], "", "1 D", "1 day", 1, 1, False, [])
			self.price_req_ids[reqId] = symbol
			reqId += 1

		for symbol in data["stage2"]["short"]:
			info = self.positions[symbol]
			for orderId in info["orders"]:
				self.cancelOrder(orderId)
			self.reqHistoricalData(reqId, info["contract"], "", "1 D", "1 day", 1, 1, False, [])
			self.price_req_ids[reqId] = symbol
			reqId += 1

	def update_stops(self):

		for symbol in data["stage2"]["long"]:
			info = self.positions[symbol]
			order = Order()
			order.action = "SELL"
			order.orderType = "STP"
			order.auxPrice = info["bar"].low
			#self.placeOrder(self.nextOrderId, info["contract"], order)
			self.nextOrderId += 1

		for symbol in data["stage2"]["short"]:
			info = self.positions[symbol]
			order = Order()
			order.action = "BUY"
			order.orderType = "STP"
			order.auxPrice = info["bar"].high
			#self.placeOrder(self.nextOrderId, info["contract"], order)
			self.nextOrderId += 1

		self.disconnect()

	def error(self, reqId, errorCode, errorString):

		print("Error: ", reqId, " ", errorCode, " ", errorString)

	def nextValidId(self, orderId: int):

		super().nextValidId(orderId)
		self.nextOrderId = orderId

	def historicalData(self, reqId:int, bar):
		
		self.price_recieved.add(reqId)
		symbol = self.price_req_ids[reqId]
		self.positions[symbol]["bar"] = bar
		if len(self.price_recieved) == self.price_expected:
			self.update_stops()
		
		
	def position(self, account: str, contract: Contract, position: float, avgCost: float):
		self.positions[contract.symbol] = {"contract":contract, "size":position, "orders":[], "avgCost":avgCost}

	def positionEnd(self):
		print("Retrieving IB order data...")
		self.reqAllOpenOrders()

	def pnlSingle(self, reqId: int, pos: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float, value: float):

		print(reqId)
		self.pnl_recieved.add(reqId)
		symbol = self.pnl_req_ids[reqId]
		info = self.positions[symbol]
		basis = info["size"] * info["avgCost"]
		perChange = (value - basis) / basis
		if perChange >= 0.02:
			if symbol in data["stage1"]["short"]:
				data["stage1"]["short"].remove(symbol)
				data["stage2"]["short"].append(symbol)
				print(symbol, "moved from Stage 1 to Stage 2 (short)")
			elif symbol in data["stage1"]["long"]:
				data["stage1"]["long"].remove(symbol)
				data["stage2"]["long"].append(symbol)
				print(symbol, "moved from Stage 1 to Stage 2 (long)")

		if len(self.pnl_recieved) == self.pnl_expected:
			print("Updating Stage 2 stops...")
			self.advance_stage2()

	def openOrder(self, orderId: int, contract: Contract, order: Order, orderState: OrderState):
		#super().openOrder(orderId, contract, order, orderState)
		#print("OpenOrder. PermId: ", order.permId, "ClientId:", order.clientId, " OrderId:", orderId, "Account:", order.account, "Symbol:", contract.symbol, "SecType:", contract.secType, "Exchange:", contract.exchange, "Action:", order.action, "OrderType:", order.orderType, "TotalQty:", order.totalQuantity, "CashQty:", order.cashQty, "LmtPrice:", order.lmtPrice, "AuxPrice:", order.auxPrice, "Status:", orderState.status)
		self.positions[contract.symbol]["orders"] += orderId

	def orderStatus(self, orderId: int, status: str, filled: float, remaining: float, avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float, clientId: int, whyHeld: str, mktCapPrice: float):
		#super().orderStatus(orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)
		#print("OrderStatus. Id:", orderId, "Status:", status, "Filled:", filled, "Remaining:", remaining, "AvgFillPrice:", avgFillPrice, "PermId:", permId, "ParentId:", parentId, "LastFillPrice:", lastFillPrice, "ClientId:", clientId, "WhyHeld:", whyHeld, "MktCapPrice:", mktCapPrice)
		pass

	def openOrderEnd(self):
		self.check_stages()



	

def run_loop():
	app.run()


app = IBapi()
app.connect('127.0.0.1', 7496, 0)
print("Connecting to IBAPI...")
time.sleep(8)
thread = threading.Thread(target=run_loop)
thread.start()

now = datetime.datetime.today()
'''
last_time = datetime.datetime.strptime(data["last_update_positions"], "%m/%d/%Y, %H:%M:%S")
if last_time.day == now.day and last_time.month == now.month:
	print("Positions already updated today")
	print("Exiting program...")
	app.disconnect()
	time.sleep(2)
	sys.exit(0)
'''

print("Retrieving IB position data...")
app.reqPositions()

#thread.join()
time.sleep(20)
app.disconnect()
sys.exit(0)

print("Saving Local Stage Data...")
data["last_update_positions"] = datetime.datetime.today().strftime("%m/%d/%Y, %H:%M:%S")

with open("data.json", "w") as f:
	json.dump(data, f)
print(data)
print("Exiting program...")
time.sleep(2)



