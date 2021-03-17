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
from input import LONG_TICKERS, SHORT_TICKERS, TRADE_RISK, ACCOUNT_PERCENT, RISK_TYPE, ACCOUNT_STRING, IGNORE
import sys



class IBapi(EWrapper, EClient):
	def __init__(self):
		EClient.__init__(self, self)

		self.positions = {}
		self.currentDataReqId = 0
		self.dataReqIds = {}


	def position(self, account: str, contract: Contract, position: float, avgCost: float):

		if position != 0 and contract.symbol not in IGNORE:
			self.positions[contract.symbol] = {"position":position}

	def positionEnd(self):

		print("Current Positions Recieved...")
		self.reqAllOpenOrders()

	def openOrder(self, orderId: int, contract: Contract, order: Order, orderState: OrderState):

		this_symbol = contract.symbol
		if order.orderType == "STP" and this_symbol in self.positions.keys():
		
			self.positions[this_symbol]["contract"] = contract
			self.positions[this_symbol]["order"] = order
			self.positions[this_symbol]["orderId"] = orderId

	def openOrderEnd(self):

		to_remove = []
		for symbol, info in self.positions.items():
			try:
				test = info["order"]
			except:
				to_remove.append(symbol)

		for symbol in to_remove:
			self.positions.pop(symbol)

		print("Open Orders Recieved, Checking Price Data...")
		for symbol, info in self.positions.items():

			self.reqHistoricalData(self.currentDataReqId, info["contract"], "", "1 D", "1 day", "TRADES", 1, 1, False, [])
			self.dataReqIds[self.currentDataReqId] = symbol
			self.currentDataReqId += 1

	def historicalData(self, reqId, bar):

		this_symbol = self.dataReqIds[reqId]
		self.positions[this_symbol]["bar"] = bar

		if self.completeData():
			print("Price Data Recieved...")
			self.beginUpdate()

	def completeData(self):

		for symbol, info in self.positions.items():
			try:
				test = info["bar"]
			except:
				return False

		return True


	def beginUpdate(self):

		print("The program will now loop through your positions with stops and suggest new prices...")
		print("-To take no action/skip a certain position, just hit enter or type N and then hit enter...")
		print("-To adjust the stop to the suggested price type Y and hit enter...")
		print("-To adjust the stop to a custom price just type in that price and hit enter...")

		for symbol, info in self.positions.items():

			if info["position"] < 0:
				suggested = info["bar"].high
			elif info["position"] > 0:
				suggested = info["bar"].low

			print("\n\n{sybmol} - Position: {pos}".format(sybmol=symbol, pos=info["position"]))
			print("Current Stop: {current}, Suggested New Stop: {suggested}".format(current=info["order"].auxPrice, suggested=suggested))
			while True:
				res = input("Please type (Enter/Y/N/customprice): ")
				try:
					res_num = float(res.strip)
				except:
					res_num = None

				if res in ["", "N", "n"] or res.isspace():
					break

				elif res in ["Y", "y"]:
					new_order = info["order"]
					new_order.auxPrice = suggested
					self.placeOrder(info["orderId"], info["contract"], new_order)
					break

				elif res_num != None:
					new_order = info["order"]
					new_order.auxPrice = res_num
					self.placeOrder(info["orderId"], info["contract"], new_order)
					break

				else:
					print("Incorrectly formatted response...")

		print("Program finished, shutting down...")
		print("Any following errors are to be ignored...")
		time.sleep(5)
		self.disconnect()


def run_loop():
	app.run()

print("Configuring Connection...")

app = IBapi()
app.connect('127.0.0.1', 7496, 104)

time.sleep(5)

thread = threading.Thread(target=run_loop)
thread.start()

time.sleep(5)

app.reqPositions()









