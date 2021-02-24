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
from input import LONG_TICKERS, SHORT_TICKERS, TRADE_RISK, ACCOUNT_PERCENT, RISK_TYPE, ATR_UP, ATR_DOWN, STOP_LIMIT_SPREAD
import sys
import json

try:
	if sys.argv[1] == "test":
		test = True
	else:
		test = False
except:
	test = False

with open("data.json") as f:
	data = json.load(f)

if test:
	print("TEST RUN")

def create_positions():

	reqId = 0
	for sym in LONG_TICKERS:
		app.newTickers[reqId] = {"symbol":sym, "side":"long"}
		reqId += 1
	for sym in SHORT_TICKERS:
		app.newTickers[reqId] = {"symbol":sym, "side":"short"}
	print("Retrieving necessary data...")
	app.reqPositions()
	app.reqAllOpenOrders()
	app.reqAccountSummary(0, "All", "NetLiquidation")


class IBapi(EWrapper, EClient):
	def __init__(self):
		EClient.__init__(self, self)
		self.recievedPositions = False
		self.recievedOrders = False
		self.recievedContracts = 0
		self.recievedPriceSets = 0
		self.got_contracts = False

		self.accountValue = -1
		self.nextOrderId = -1

		self.newTickers = {}
		
		self.allCurrentTickers = set()

	def error(self, reqId, errorCode, errorString):

		print("Error: ", reqId, " ", errorCode, " ", errorString)

	def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
		if tag == "NetLiquidation" and currency == "USD":
			self.accountValue = float(value)
			if self.recievedOrders and self.nextOrderId != -1 and self.recievedPositions and not self.got_contracts:
				print("Positions and orders data recieved")
				self.getContracts()

	def nextValidId(self, orderId: int):

		super().nextValidId(orderId)
		self.nextOrderId = orderId

		if self.recievedPositions and self.recievedOrders and self.accountValue != -1:
			print("Positions and orders data recieved")
			self.getContracts()
		
		
	def position(self, account: str, contract: Contract, position: float, avgCost: float):
		self.allCurrentTickers.add(contract.symbol)

	def positionEnd(self):
		self.recievedPositions = True
		if self.recievedOrders and self.nextOrderId != -1 and self.accountValue != -1:
			print("Positions and orders data recieved")
			self.getContracts()


	def openOrder(self, orderId: int, contract: Contract, order: Order, orderState: OrderState):
		#super().openOrder(orderId, contract, order, orderState)
		#print("OpenOrder. PermId: ", order.permId, "ClientId:", order.clientId, " OrderId:", orderId, "Account:", order.account, "Symbol:", contract.symbol, "SecType:", contract.secType, "Exchange:", contract.exchange, "Action:", order.action, "OrderType:", order.orderType, "TotalQty:", order.totalQuantity, "CashQty:", order.cashQty, "LmtPrice:", order.lmtPrice, "AuxPrice:", order.auxPrice, "Status:", orderState.status)
		self.allCurrentTickers.add(contract.symbol)

	def orderStatus(self, orderId: int, status: str, filled: float, remaining: float, avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float, clientId: int, whyHeld: str, mktCapPrice: float):
		#super().orderStatus(orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)
		#print("OrderStatus. Id:", orderId, "Status:", status, "Filled:", filled, "Remaining:", remaining, "AvgFillPrice:", avgFillPrice, "PermId:", permId, "ParentId:", parentId, "LastFillPrice:", lastFillPrice, "ClientId:", clientId, "WhyHeld:", whyHeld, "MktCapPrice:", mktCapPrice)
		pass

	def openOrderEnd(self):
		self.recievedOrders = True
		if self.recievedPositions and self.nextOrderId != -1 and self.accountValue != -1:
			print("Positions and orders data recieved")
			self.getContracts()


	def contractDetails(self, reqId : int, contractDetails : ContractDetails):
		self.newTickers[reqId]["contract"] = contractDetails.contract
		self.recievedContracts += 1
		if self.recievedContracts == len(self.newTickers):
			self.getPriceData()

	def historicalData(self, reqId:int, bar):
		#print(bar)
		self.newTickers[reqId]["bars"].append(bar)

	def historicalDataEnd(self, reqId: int, start: str, end: str):
		self.recievedPriceSets += 1
		if self.recievedPriceSets == len(self.newTickers):
			self.placeNewOrders()

	def getContracts(self):

		self.got_contracts = True
		#remove already current tickers
		to_remove = []
		for reqId, info in self.newTickers.items():
			if info['symbol'] in self.allCurrentTickers:
				to_remove.append(reqId)
		
		for reqId in to_remove:
			self.newTickers.pop(reqId)
		if self.newTickers == {}:
			print("No new tickers")
			app.disconnect()
		for reqId, info in self.newTickers.items():
			contract = Contract()
			contract.symbol = info["symbol"]
			contract.currency = "USD"
			contract.secType = "STK"
			contract.exchange = "SMART"
			self.reqContractDetails(reqId, contract)

	def getPriceData(self):
		
		for reqId, info in self.newTickers.items():
			self.newTickers[reqId]["bars"] = []
			self.reqHistoricalData(reqId, info["contract"], "", "2 W","1 day", "TRADES", 1, 1, False, [])

	def placeNewOrders(self):
		
		for reqId, info in self.newTickers.items():
			total = 0
			for bar in info["bars"]:
				total += (bar.high - bar.low)
			atr = total / len(info["bars"])

			if info["side"] == "long":
				data["stage0"]["long"].append(info["symbol"])
				stop_limit_price = info["bars"][-1].high
				limit_price = stop_limit_price + STOP_LIMIT_SPREAD
				take_profit_price = round(limit_price + (ATR_UP * atr), 2)
				stop_loss_price = round(limit_price - (ATR_DOWN * atr), 2)
				entrySide = "BUY"
				exitSide = "SELL"


			elif info["side"] == "short":
				data["stage0"]["short"].append(info["symbol"])
				stop_limit_price = info["bars"][-1].low
				limit_price = stop_limit_price - STOP_LIMIT_SPREAD
				take_profit_price = round(limit_price - (ATR_UP * atr), 2)
				stop_loss_price = round(limit_price + (ATR_DOWN * atr), 2)
				entrySide = "SELL"
				exitSide = "BUY"

			if RISK_TYPE == "dollar":
				qty = abs(int(TRADE_RISK // (limit_price - stop_loss_price)))
			elif RISK_TYPE == "percent":
				qty = abs(int((self.accountValue * ACCOUNT_PERCENT) // (limit_price - stop_loss_price)))

			print(info["side"], info["symbol"], "Limit Price:", limit_price,"Stop Price", stop_limit_price, "Take Profit Price:", take_profit_price, "Stop Loss Price:", stop_loss_price, "Quantity:", qty)

			if not test:
				parentOrder = Order()
				parentOrder.tif = "GTC"
				parentOrder.action = entrySide
				parentOrder.orderType = "STP LMT"
				parentOrder.totalQuantity = qty
				parentOrder.lmtPrice = limit_price
				parentOrder.auxPrice = stop_limit_price
				parentOrder.transmit = False
				#parentOrder.outsideRth = True

		
				

				
				takeProfitOrder = Order()
				takeProfitOrder.tif = "GTC"
				takeProfitOrder.action = exitSide
				takeProfitOrder.orderType = "LMT"
				takeProfitOrder.totalQuantity = qty
				takeProfitOrder.lmtPrice = take_profit_price
				takeProfitOrder.parentId = self.nextOrderId
				takeProfitOrder.transmit = False
				#takeProfitOrder.outsideRth = True

				

				stopLossOrder = Order()
				stopLossOrder.tif= "GTC"
				stopLossOrder.action = exitSide
				stopLossOrder.orderType = "STP"
				stopLossOrder.auxPrice = stop_loss_price
				stopLossOrder.totalQuantity = qty
				stopLossOrder.parentId = self.nextOrderId
				stopLossOrder.transmit = True
				#stopLossOrder.outsideRth = True
				
				

				self.placeOrder(self.nextOrderId, info["contract"], parentOrder)
				self.nextOrderId += 1
				self.placeOrder(self.nextOrderId, info["contract"], takeProfitOrder)
				self.nextOrderId += 1
				self.placeOrder(self.nextOrderId, info["contract"], stopLossOrder)
				self.nextOrderId += 1
				#print(limit_price, take_profit_price, stop_loss_price)
				time.sleep(1)

		#data["last_create_order"] = datetime.datetime.today().strftime("%m/%d/%Y, %H:%M:%S")
		self.disconnect()




def run_loop():
	app.run()


app = IBapi()
app.connect('127.0.0.1', 7497, 0)

thread = threading.Thread(target=run_loop)


now = datetime.datetime.today()


last_time = datetime.datetime.strptime(data["last_create_order"], "%m/%d/%Y, %H:%M:%S")
if last_time.day == now.day and last_time.month == now.month:
	inputStr = "You already placed new orders today at " + str(last_time.time()) + ", would you like to continue? (Enter Yes/No)"
	res = input(inputStr)
	if res != "Yes":
		print("Exiting program...")
		app.disconnect()
		time.sleep(2)
		sys.exit(0)


thread.start()
time.sleep(5)
create_positions()


thread.join()

if not test: 
	data["last_create_order"] = datetime.datetime.today().strftime("%m/%d/%Y, %H:%M:%S")

	with open("data.json", "w") as f:
		json.dump(data, f)
	print("Local position data updated")






