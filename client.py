# other libs
import websockets
import socketserver
import threading
import http.client
import http.server
import json
import time
import xml.etree.ElementTree as ET
from queue import Queue

# async libs
import asyncio
import aiohttp.server
from aiohttp import MultiDict
from urllib.parse import urlparse, parse_qsl

# flashnet libs
from lib.FlashnetConnector import FlashnetConnector
from lib.FlashnetDevice import FlashnetDevice
from lib.FlashnetController import FlashnetController

config = {
	"ws_encrypt" : True,
	"ws_api_host" : "flashnet_websocket_api",
	"ws_api_port" : "8084",
	"http_encrypt" : True,
	"http_api_host" : "flashnet_http_api",
	"http_api_port" : "443",
	"http_api_path" : "/http_path",

	"cms_encrypt" : False,
	"cms_host" : "localhost",
	"cms_port" : 8080,
	"cms_path" : "/reports",

	"api_key" : "your_api_key",
	"httpd_port" : 8080
}

async def wsmain():
	global connector

	# get list of devices
	await connector.loadControllers()

	if config["ws_encrypt"] == True:
		ws_target = "wss://{}:{}".format(config["ws_api_host"], config["ws_api_port"])
	else:
		ws_target = "ws://{}:{}".format(config["ws_api_host"], config["ws_api_port"])

	while 1:
		print('Connecting to WS...')
		try:
			async with websockets.connect(ws_target) as websocket:

				auth = '{"op":"auth", "key":"'+config["api_key"]+'"}'
				print("> {}".format(auth))
				await websocket.send(auth)

				resp = await websocket.recv()
				print("< {}".format(resp))

				while 1:
					resp = await websocket.recv()
					print("< {}".format(resp))
					connector.handleWSMessage(resp)
		except websockets.exceptions.ConnectionClosed:
			print('Socket closed!')
			pass
		except ConnectionRefusedError:
			print('Connection refused! WS Server down? Retrying in 5s...')
			time.sleep(5)

def ws_start():
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	asyncio.get_event_loop().run_until_complete(wsmain())

class HttpHandler(aiohttp.server.ServerHttpProtocol):
	async def handle_request(self, message, payload):
		if message.method == 'POST' and message.path == '/slv/realtime':
			print(message.method+' request to '+message.path)
			http_status = 200
			answer_body = ''

			data = await payload.read() # get post body
			post_body = data.decode("utf-8") # decode

			try:
				message_xml = ET.fromstring(post_body) # parse XML
				answer_body = await connector.handleMessage(message_xml) # handle it
			except ET.ParseError:
				http_status = 400 # bad request
				answer_body = 'Bad Request'

			response = aiohttp.Response(
				self.writer, http_status, http_version=message.version
			)

			print(answer_body)
			# send response
			response.add_header('Content-Type', 'text/html')
			response.add_header('Content-Length', str(len(answer_body)))
			response.send_headers()
			response.write(answer_body.encode())
			await response.write_eof()
		else:
			print(message.method+' request to '+message.path+' - rejected')
			response = aiohttp.Response(
				self.writer, 404, http_version=message.version
			)
			response.add_header('Content-Type', 'text/html')
			response.add_header('Content-Length', '0')
			response.send_headers()
			await response.write_eof()

if __name__ == '__main__':
	# setup connector
	connector = FlashnetConnector(config)

	# start websocket
	ws_thread = threading.Thread(target=ws_start)
	ws_thread.start()

	# set up http server
	loop = asyncio.get_event_loop()
	f = loop.create_server(
		lambda: HttpHandler(debug=True, keep_alive=75),
		'0.0.0.0', config["httpd_port"])
	srv = loop.run_until_complete(f)
	print('serving on', srv.sockets[0].getsockname())
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		print('Stopped main thread! Ctrl+C again to quit!')
		pass