#!/usr/bin/env python3
from configparser import ConfigParser
from tornado.options import options
import tornado.httpserver
import tornado.ioloop
import tornado.web
import sqlite3
import json
import socket
import os
import sys

def config(section):
	direct='%s/config.ini'%os.path.realpath(os.path.dirname(sys.argv[0]))
	parser = ConfigParser()
	parser.read(direct)
	params = {}
	if parser.has_section(section):
		items = parser.items(section)
		for item in items:
			params[item[0]] = item[1]
	return params

class CallHandler(tornado.web.RequestHandler):
	@tornado.web.asynchronous
	def post(self):
		self.add_header('Access-Control-Allow-Origin','*')
		params = self.request.arguments['call'][0].decode()
		self.call(params)
		
	def call(self,params):
		params = json.loads(params)
		connect = sqlite3.connect("amocrm.db")
		connect.row_factory = lambda c, r: dict([(col[0], r[idx]) for idx, col in enumerate(c.description)])
		cursor = connect.cursor()
		cursor.execute('SELECT * FROM users WHERE id = "%s"'%params['id'])
		user = cursor.fetchone()

		variable = ''
		callerid = 'Amocrm'
		
		channel = user['channel']
		protList = ['SIP','PJSIP','IAX']
		for prot in protList:
			if user['channel'].find('%s'%prot) == -1:
				channel = 'SIP/%s'%user['channel']
				break
			
		ami = socket.socket()
		HOST = config('ami').get('host')
		PORT = int(config('ami').get('port'))
		ami.connect((HOST, PORT))
		ami.settimeout(1)
		ami.send(b'''Action: login
Username: %b
Secret: %b

'''%(config('ami').get('username').encode(),config('ami').get('password').encode()))
		ami.send(b'''Action: Originate
Channel: %b
Exten: %b
Context: %b
Priority: 1
Variable: %b
Callerid: %b
Async: Yes

'''%(channel.encode(),params['phone'].encode(),user['context'].encode(),variable.encode(),callerid.encode()))	
		self.finish()

class StatusHandler(tornado.web.RequestHandler):
	@tornado.web.asynchronous
	def get(self):
		self.add_header('Access-Control-Allow-Origin','*')
		status = self.status()
		self.write(status)
		self.finish()
		
	def status(self):
		ami = socket.socket()
		HOST = config('ami').get('host')
		PORT = int(config('ami').get('port'))
		ami.connect((HOST, PORT))
		ami.settimeout(1)
		ami.send(b'''Action: login
Username: %b
Secret: %b

'''%(config('ami').get('username').encode(),config('ami').get('password').encode()))
		ami.send(b'Action: Status\r\n\r\n')
		byteraw = b''
		while True:
			try:
				byteraw += ami.recv(1024)
			except socket.timeout:
				break
		data = []
		for items in byteraw.split(b'\r\n\r\n'):
			dict = {}
			if items:
				for item in items.split(b'\r\n'):
					item = item.decode()
					try:
						dict['%s'%item.split(':')[0].strip().lower()] = item.split(':')[1].strip()
					except IndexError:
						pass
				try:
					if dict['event'] == 'Status':
						data.append(dict)
				except KeyError:
					pass

		return {'status': data}
			
class SettingsHandler(tornado.web.RequestHandler):
	@tornado.web.asynchronous
	def post(self):
		self.add_header('Access-Control-Allow-Origin','*')
		params = self.request.arguments['amo'][0].decode()
		self.amoPhones(params)
		
	def amoPhones(self,params):
		params = json.loads(params)
		users = []
		
		context = 'office'
		
		for user in params['users']:
			users.append((user,params['users'][user],context,params['account']['login'],params['account']['api'],params['account']['subdomain']))
		
		connect = sqlite3.connect('amocrm.db')
		cursor = connect.cursor()
		try:
			cursor.execute('DELETE FROM users')
			cursor.executemany('INSERT INTO users VALUES (?,?,?,?,?,?)', users)
		except sqlite3.OperationalError:
			cursor.execute('CREATE TABLE users (id text, channel text, context text, login text, api text, subdomain text)')
			cursor.executemany('INSERT INTO users VALUES (?,?,?,?,?,?)', users)
		connect.commit()
		self.finish()
		
def main():
	tornado.options.parse_command_line()	
	application = tornado.web.Application([
		(r"/amocrm/call", CallHandler),
		(r"/amocrm/status", StatusHandler),
		(r"/amocrm/settings", SettingsHandler)
	])
	http_server = tornado.httpserver.HTTPServer(application)
	http_server.listen(config('server').get('port'),config('server').get('host'))
	tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
	main()