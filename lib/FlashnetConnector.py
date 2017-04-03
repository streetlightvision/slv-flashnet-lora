import http.client
import json
import datetime
import asyncio
import aiohttp

from lib.FlashnetDevice import FlashnetDevice
from lib.FlashnetController import FlashnetController

class FlashnetConnector:
	def __init__(self, config_file):
		self.config = config_file
		self.conn = None
		self.headers = {
			'Content-Type' : 'application/json',
			'x-api-key' : self.config["api_key"]
			}
		self.devices = {}
		self.remoteAddress = ""

	def connect(self):
		if self.config["http_encrypt"] == True:
			self.conn = http.client.HTTPSConnection(self.config["http_api_host"], self.config["http_api_port"])
		else:
			self.conn = http.client.HTTPConnection(self.config["http_api_host"], self.config["http_api_port"])
		return self.conn

	async def loadControllers(self):
		resp = await self.request('GET', '/controllers')
		if resp["ok"] == 1:
			self.remoteAddress = resp["remoteAddress"]
			for entry in resp["data"]:
				print('Controller: '+entry['deveui'].lower())
				self.devices[entry['deveui'].lower()] = FlashnetController(entry['deveui'].lower(), self)

	async def request(self, type, path, body = None):
		if self.config["http_encrypt"] == True:
			target = "https://{}:{}".format(self.config["http_api_host"], self.config["http_api_port"])
		else:
			target = "http://{}:{}".format(self.config["http_api_host"], self.config["http_api_port"])

		async with aiohttp.ClientSession() as session:
			if type == 'GET':
				async with session.get(target+self.config["http_api_path"]+path,
					headers=self.headers) as resp:
					data = await resp.text()
					print("r: "+data)
					if len(data) > 0:
						data = json.loads(data)
					return data
			if type == 'POST':
				async with session.post(target+self.config["http_api_path"]+path,
					data=body,
					headers=self.headers) as resp:
					data = await resp.text()
					print("r: "+data)
					if len(data) > 0:
						data = json.loads(data)
					return data


		# conn.request(type, , body, self.headers)
		# r1 = self.conn.getresponse()
		# resp = r1.read().decode()

		if len(resp) > 0:
			resp = json.loads(resp)
		return resp

	def handleWSMessage(self, message):
		msg = json.loads(message)
		if msg["op"] == "var_push":
			if msg["deveui"].lower() in self.devices:
				print(msg["deveui"]+' is known device')
				self.devices[msg["deveui"].lower()].wsUpdate(msg["var"],msg["value"])
			else:
				self.loadControllers()
				if msg["deveui"].lower() in self.devices:
					self.devices[msg["deveui"].lower()].wsUpdate(msg["var"],msg["value"])
				else:
					print("< Unknown device: "+msg["deveui"])

	async def handleMessage(self, message_root):
		response = '<responses>'
		now = datetime.datetime.now().strftime(
			'%Y-%m-%dT%H:%M:%S.%fZ')  # get timestamp for 'now'

		for child in message_root:
			if child.tag == 'set':
				if 'id' in child.attrib and 'meaning' in child.attrib:
					print('SET command for '+child.attrib['id']+' meaning: '+child.attrib['meaning'])

					target = None;

					if child.attrib['ctrlId'].lower() in self.devices:
						target = self.devices[child.attrib['ctrlId'].lower()]
					elif child.attrib['id'].lower() in self.devices:
						target = self.devices[child.attrib['id'].lower()]

					if target != None:
						await target.handleSetCommand(child.attrib['meaning'], child.text)
						response += """
	<response>
		<status>QUEUED</status>
		<date>{now}</date>
		<value></value>
		<error></error>
	</response>""".format(now=now)
					else:
						response += """
	<response>
		<status>ERROR</status>
		<date>{now}</date>
		<value></value>
		<error>Device not found</error>
	</response>""".format(now=now)

			elif child.tag == 'get':
				if 'id' in child.attrib and 'meaning' in child.attrib:
					print('GET command for '+child.attrib['ctrlId']+' '+child.attrib['id']+' meaning: '+child.attrib['meaning'])
					target = None;
					if child.attrib['ctrlId'].lower() in self.devices:
						target = self.devices[child.attrib['ctrlId'].lower()]
					elif child.attrib['id'].lower() in self.devices:
						target = self.devices[child.attrib['id'].lower()]

					if target != None:
						answer = await target.handleGetCommand(child.attrib['meaning'])
						time = datetime.datetime.now().fromtimestamp(
							target.lastRefresh()).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
						print(child.attrib['meaning']+" : "+str(answer))
						if answer != -1:
							response += """
	<response>
		<status>OK</status>
		<date>{now}</date>
		<value>{answer}</value>
		<error></error>
	</response>""".format(now=time, answer=answer)
						else:
							response += """<response>
		<status>ERROR</status>
		<date>{now}</date>
		<value></value>
		<error>Meaning not available</error>
	</response>""".format(now=time)
					else:
						response += """
	<response>
		<status>ERROR</status>
		<date>{now}</date>
		<value></value>
		<error>Device not found</error>
	</response>""".format(now=now)

		response += "</responses>"
		return response
