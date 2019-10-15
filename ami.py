#!/usr/bin/env python3
from multiprocessing import Process, Lock
from configparser import ConfigParser
from urllib.parse import urlencode, quote_plus
import pymysql
import sqlite3
import socket
import requests
import time
import json
import os
import sys

def unsorted(call, headers, user):
	params = {'login':user['login'],'api_key':user['api']}
	data = {'add[0][source_name]':'widget',
			'add[0][incoming_entities][contacts][0][name]':'The contact was created automatically',
			'add[0][incoming_entities][contacts][0][custom_fields][0][id]':call['custom_fields_id'],
			'add[0][incoming_entities][contacts][0][custom_fields][0][values][0][value]':call['amo_phone_number'],
			'add[0][incoming_entities][contacts][0][custom_fields][0][values][0][enum]':call['custom_fields_enum'],
			'add[0][incoming_entities][contacts][0][responsible_user_id]':call['user_id'],
			'add[0][incoming_entities][contacts][0][date_create]':call['uniqueid'].split('.')[0],
			'add[0][incoming_lead_info][to]':call['dst'],
			'add[0][incoming_lead_info][from]':call['src'],
			'add[0][incoming_lead_info][date_call]':call['uniqueid'].split('.')[0],
			'add[0][incoming_lead_info][duration]':call['duration'],
			'add[0][incoming_lead_info][link]': config('record').get('path')+call['mixmonitor_filename'],
			'add[0][incoming_lead_info][service_code]':'widget',
			'add[0][incoming_lead_info][uniq]':call['uniqueid'],
			'add[0][incoming_lead_info][add_note]':'incoming call'}
	result = urlencode(data, quote_via=quote_plus)
	time.sleep(1)
	requests.post('https://%s.amocrm.ru/api/v2/incoming_leads/sip'%from_config('amocrm').get('subdomain'),data = result, headers = headers, params = params)

def note(call, headers):
	time.sleep(1)
	notes = requests.get('https://%s.amocrm.ru/api/v2/notes?type=contact&note_type=10&element_id=%s'%(from_config('amocrm').get('subdomain'),call['contact_id']),headers = headers)
	if notes.text.find(call['uid']) == -1:
		data = {'add[0][created_by]':call['amo_user_id'],
				'add[0][created_at]':call['date'],
				'add[0][element_id]':call['amo_contact_id'],
				'add[0][element_type]':call['amo_element_type'],
				'add[0][note_type]':call['amo_note_type'],
				'add[0][params][UNIQ]':call['uniqueid'],
				'add[0][params][LINK]': config('record').get('path')+call['mixmonitor_filename'],
				'add[0][params][call]':call['amo_phone_number'],
				'add[0][params][DURATION]':call['duration'],
				'add[0][params][SRC]':'asterisk'}
		result = urlencode(data, quote_via=quote_plus)
		time.sleep(1)
		requests.post('https://%s.amocrm.ru/api/v2/notes'%from_config('amocrm').get('subdomain'),data = result, headers = headers)

def amocrm(call):

	connect = sqlite3.connect("amocrm.db")
	connect.row_factory = lambda c, r: dict([(col[0], r[idx]) for idx, col in enumerate(c.description)])
	cursor = connect.cursor()
	cursor.execute('SELECT * FROM users')
	users = cursor.fetchall()

	for user in users:
		if call['channel'].find('%s-'%user['channel']) != -1 or call['dstchannel'].find('%s-'%user['channel']) != -1:
			if len(call['src']) > 5 or len(call['dst']) > 5:
				call['amo_user_id'] = user['id']
				if len(call['src']) > 5:
					call['amo_note_type'] = '10'
					call['amo_phone_number'] = call['src']
				else:
					call['amo_note_type'] = '11'
					call['amo_phone_number'] = call['dst']	
					
					
				for i in call:
					print('%s : %s'%(i,call[i]))
				
				auth_params = {'USER_LOGIN':user['login'],'USER_HASH':user['api']}
				auth = requests.post('https://%s.amocrm.ru/private/api/auth.php'%user['subdomain'], params = auth_params)
				if auth.text.find('<auth>true') == -1:
					exit(0)
				headers = {'content-type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Cookie':auth.headers['Set-Cookie']}
							
				time.sleep(1)
				amo_account = requests.get('https://%s.amocrm.ru/api/v2/account?with=custom_fields'%from_config('amocrm').get('subdomain'),headers = headers)
				account = json.loads(amo_account.text)['_embedded']['custom_fields']['contacts']
				for contacts in account:
					if account[contacts]['name'] == 'Телефон':
						call['custom_fields_id'] = contacts
						for enum in account[contacts]['enums']:
							if account[contacts]['enums'][enum] == 'WORK':
								call['custom_fields_enum'] = enum
				
				time.sleep(1)
				contact = requests.get('https://%s.amocrm.ru/private/api/contact_search.php?SEARCH=%s'%(user['subdomain'],call['amo_phone_number']),headers = headers)
				if contact.text.find(call['amo_phone_number']) != -1:
					call['amo_contact_id'] = contact.text.expandtabs(0).split('</id>\n<name>')[0].split('<id>')[1]
					time.sleep(1)
					notes = requests.get('https://%s.amocrm.ru/api/v2/notes?type=contact&element_id=%s'%(user['subdomain'],call['amo_contact_id']),headers = headers)
					if notes.text.find(call['uniqueid']) == -1:
						if contact.text.split('</is_company>')[0].split('<is_company>')[1].find('1') != -1:
							call['amo_element_type'] = '3'			
						if contact.text.split('</is_company>')[0].split('<is_company>')[1].find('1') == -1:
							call['amo_element_type'] = '1'
						
						note(call, headers)
						
				if contact.text.find(call['amo_phone_number']) == -1:
					unsorted(call, headers, user)
			
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

def cdrConnect(uid):  
	code = 'Select * from cdr where uniqueid = "%s";'%uid
	connect = config('cdr')
	conn = pymysql.connect(**connect)
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute(code)
	item = cursor.fetchone()
	cursor.close()
	conn.close()
	return item

def newProcess(lock,uid):
	lock.acquire()
	try:
		call = cdrConnect(uid)
		amocrm(call)
	finally:
		lock.release()
		
if __name__ == '__main__':
	ami = socket.socket()
	HOST = config('ami').get('host')
	PORT = int(config('ami').get('port'))
	ami.connect((HOST, PORT))

	ami.send(b'''Action: login
Username: %b
Secret: %b

'''%(config('ami').get('username').encode(),config('ami').get('password').encode()))

	while True:
		raw = ami.recv(1024).decode()
		dict = {}
		for item in raw.split('\n'):
			try:
				action = item.split(':')[0].strip()
				value = item.split(':')[1].strip()
				dict['%s'%action] = value
			except IndexError:
				pass
		try:
			if dict['Event'] == 'Cdr':
				lock = Lock()
				uid = dict['UniqueID']
				Process(target = newProcess, args = (lock, uid)).start()
		except KeyError:
			pass
