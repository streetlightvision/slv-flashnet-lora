from lib.FlashnetDevice import FlashnetDevice
import json
import time
import datetime
import asyncio

meaning_dict = {
	"Current" : "nvoCurrent",
	"MainVoltage" : "nvoVolt",
	"PowerFactor" : "nvoPf",
	"MeteredPower" : "MeteredPower",
	"LampLevel" : "nvoLampStatus"
}

flash_dict = dict ( (v,k) for k, v in meaning_dict.items() )

property_dict = {
	"LampLevel" : "lampLevel"
}

class FlashnetController(FlashnetDevice):
	def __init__(self, deveui, connector):
		self.deveui = deveui
		self.connector = connector
		self.values = {}
		self.loaded = False
		self.values["Power"] = -1
		self.values["LampCommandMode"] = -1
		self.values["MeteredPower"] = 0
		self.values["LampCommandLevel"] = 0
		self.last_read = 0

	def lastRefresh(self):
		return int(self.last_read)

	async def loadData(self):
		now = int(time.time())
		if now - self.last_read > 10:
			resp = await self.connector.request('GET','/controllers/'+self.deveui)
			self.loaded = True
			if 'error' not in resp:
				if 'message' not in resp:
					print('Parsing...')
					resp_vars = resp["vars"]
					resp_deveui = resp["deveui"]
					if self.deveui != resp_deveui:
						print("Answer for wrong device! API is not sane!")
					else:
						for entry in resp_vars:
							if "last_poll_ts" in entry:
								if entry["last_poll_ts"] > self.last_read:
									self.last_read = entry["last_poll_ts"]
							# if isinstance(entry["value"], dict): # if is a dict
							# 	for value in entry["value"]:
							# 		print(value+" = "+str(entry["value"][value]))
							# 		self.values[value] = entry["value"][value]
							# else: # just a value
							print(entry["name"]+" = "+str(entry["value"]))
							self.values[entry["name"]] = entry["value"]
						self.values["LampCommandLevel"] = self.values["nvoLampStatus"]["lampLevel"]
						self.values["MeteredPower"] = float(self.values["nvoVolt"])*float(self.values["nvoCurrent"])
				else:
					print(resp["message"])
					self.loaded = False
			else:
				print('Error!')
				print(resp["error"])

	async def handleGetCommand(self, meaning):
		# self.loadData()
		if meaning in self.values:
			return self.values[meaning]
		elif meaning in meaning_dict:
			print(meaning+' not in self.values!')
			print('/controllers/'+self.deveui+"/"+meaning_dict[meaning])
			resp = await self.connector.request('GET','/controllers/'+self.deveui+"/"+meaning_dict[meaning])
			print(resp)
			if "last_poll_ts" in resp:
				if resp["last_poll_ts"] > self.last_read:
					self.last_read = resp["last_poll_ts"]
			if 'value' in resp:
				if isinstance(resp["value"], dict):
					if meaning in property_dict:
						print('updating '+str(meaning)+' to '+str(resp["value"][property_dict[meaning]])+' on '+self.deveui)
						self.values[meaning] = resp["value"][property_dict[meaning]]
						return resp["value"][property_dict[meaning]]
					else:
						return -1
				else:
					print('updating '+str(meaning)+' to '+str(resp["value"])+' on '+self.deveui)
					self.values[meaning] = resp["value"]
					return resp["value"]
			else:
				return -1
		else:
			return -1

	def wsUpdate(self, var, value):
		print(var)
		if str(var) in flash_dict:
			if isinstance(value, dict):
				meaning = flash_dict[var]
				if meaning in property_dict:
					print('updating '+str(meaning)+' to '+str(value[property_dict[meaning]])+' on '+self.deveui)
					self.values[meaning] = value[property_dict[meaning]]
			else:
				print('updating '+str(flash_dict[var])+' to '+str(value)+' on '+self.deveui)
				self.values[flash_dict[var]] = value

	async def handleSetCommand(self, meaning, value):
		if meaning == "LampCommandLevel":
			print("Level to "+value)
			self.values["LampCommandLevel"] = value
			value = int(float(value))
			msg = { "value": str(value) }
			body = json.dumps(msg)
			print(msg)
			resp = await self.connector.request('POST','/controllers/'+self.deveui, body)
