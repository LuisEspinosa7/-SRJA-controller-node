#!flask/bin/python

#
# Node Controller - Domotic System
#


from flask import copy_current_request_context
# Websocket Packages 
import time, random
from threading import Lock, Thread
import threading
from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, disconnect
import requests

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
from lib_nrf24 import NRF24
import time
import spidev
import binascii
import numpy
from struct import *

# REST packages
from flask import jsonify
from flask import make_response
from flask import abort
import json

from flask import Response


# Variables del nodo jardin 1
humedad = 0
temperatura = 0
lluvia = 0
litrosPorMinuto = 0
humedadTierra1 = 0
humedadTierra2 = 0
temperaturaTierra = 0


STRUCT_TYPE_GETDATA=0
STRUCT_TYPE_INIT=1
STRUCT_TYPE_GARDEN=2
STRUCT_TYPE_SENDCOMMAND=3

async_mode = None


app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None
thread_lock = Lock()

usernames = {}
number_of_users = 0

#def emmitGardenInfo(self, command, deviceAddress):



class GARDENData:
	time = None
	humidity = 0
	temperature =0
	rain = 0
	litersPerMinute= 0
	SoilMoisture1 = 0
	SoilMoisture2 = 0
	SoilTemperature = 0
	voltage=0
	valid=False

class RF_Device:
	def __init__(self, deviceAddress, nextTime=60):
		self.deviceAddress=deviceAddress
		self.nextTime=nextTime;
		self.lastConnectionTime= time.time()
		self.nextConnectionTime= self.lastConnectionTime
		self.xdata = [0,0,0]
		self.rdata = ''

	def isTimeOut(self):
		return (time.time() > self.nextConnectionTime)


	def readNodeAddress(self):
		buffer = '{:02X}'.format(self.deviceAddress[0])
		for i in range(1,5,1):
			buffer += ':{:02X}'.format(self.deviceAddress[i])   
		return buffer

	def unpackGARDENData(self , buffer):
		garden =  GARDENData

		if len(buffer) != 25:
			return None
		try:
			self.rdata = unpack('<sBBBLBHHHHHHHH',''.join(map(chr,buffer)))
			garden.time = self.rdata[4]
			garden.valid = self.rdata[5]!=0
			garden.voltage = self.rdata[6]/1000.0
			garden.temperature = self.rdata[7]/10.0
			garden.humidity = self.rdata[8]
			garden.rain = self.rdata[9]
			garden.litersPerMinute = self.rdata[10]
			garden.SoilMoisture1 = self.rdata[11]
			garden.SoilMoisture2 = self.rdata[12]
			garden.SoilTemperature = self.rdata[13]
			return garden
		except:
			return None

	def getData(self):
		if( not self.isTimeOut()):
			return None
		
		print("timeout={}".format(self.nextTime))
		self.nextConnectionTime += self.nextTime
		#buildpacket
		packet = '*'
		packet += chr(10)  #get packet size
		packet += chr(STRUCT_TYPE_GETDATA)
		packet += chr(0)   #0 mean master
		packet += pack('<L', numpy.uint32(time.time()))  #get current time
		packet += pack('<H', numpy.uint16(self.nextTime *10))  #get next time reading
		
		# print("send : {}".format(list(packet)))

		radio.openWritingPipe(self.deviceAddress)

		radio.write(packet)
		if True:
			if radio.isAckPayloadAvailable():
				in_buffer=[]
				radio.read(in_buffer,radio.getDynamicPayloadSize())
				validFlag= False
				if len(in_buffer)>4:
					# check first four bytes
					if in_buffer[0] == ord('*'):
						if in_buffer[2] == STRUCT_TYPE_INIT:
							#sensor is valid but just boot
							print("Sensor {} - {} - Just boot".format(self.readNodeAddress(),time.ctime()))
							validFlag=True
						if in_buffer[2] == STRUCT_TYPE_GARDEN:
							garden = self.unpackGARDENData(in_buffer)
							if garden != None:
								if garden.valid:									
									# Configurar variables 
									if self.deviceAddress == [0xc2,0xc2,0xc2,0xc2,0xc3]:
										# Nodo jardin
										print("Sensor {} - {}   VCC:{}V T:{}C H:{} Lluvia:{} LPM:{} SM1:{} SM2:{} ST:{}".format(self.readNodeAddress(),time.ctime(garden.time),garden.voltage,garden.temperature,garden.humidity,garden.rain,garden.litersPerMinute,garden.SoilMoisture1,garden.SoilMoisture2,garden.SoilTemperature))
										print("Configurando las variables del jardin")
										global humedad, temperatura, lluvia, litrosPorMinuto, humedadTierra1, humedadTierra2, temperaturaTierra
										humedad = garden.humidity
										temperatura = garden.temperature
										lluvia = garden.rain
										litrosPorMinuto = garden.litersPerMinute
										humedadTierra1 = garden.SoilMoisture1
										humedadTierra2 = garden.SoilMoisture2
										temperaturaTierra = garden.SoilTemperature
										print("Ya configuramos las variables del jardin")
										#print("Valor variables")									
								else:
									print("Sensor {} - {}  VCC:{}V Unable to read garden sensor".format(self.readNodeAddress(),time.ctime(garden.time),garden.voltage))
								validFlag=True

				# except:
				# print("Unable to unpack!Bad packet")
				if not validFlag:
					print("Sensor {} - {}  Invalid packet!".format(self.readNodeAddress(),time.ctime()))
				else:
					print("Sensor {} - {}  time out!".format(self.readNodeAddress(),time.ctime()))


# Enviar comando
def sendCommand(command, deviceAddress):
	nextTime = 10
	print("timeout={}".format(nextTime))
	#buildpacket
	packet = '*'
	packet += chr(10)  #get packet size
	packet += chr(STRUCT_TYPE_SENDCOMMAND)
	packet += chr(0)   #0 mean master
	packet += pack('<L', numpy.uint32(time.time()))  #get current time
	packet += pack('<H', numpy.uint16(nextTime *10))  #get next time reading
	packet += command # command

	# print("send : {}".format(list(packet)))
	radio.openWritingPipe(deviceAddress)
	radio.write(packet)


masterAddress = [0xe7, 0xe7, 0xe7, 0xe7, 0xe7]
device = [RF_Device([0xc2,0xc2,0xc2,0xc2,0xc3],10)]
radio = NRF24(GPIO, spidev.SpiDev())
radio.begin(0, 17)
time.sleep(1)
radio.setRetries(15,15)
radio.setPayloadSize(32)
radio.setChannel(78)
radio.setDataRate(NRF24.BR_1MBPS)
radio.setPALevel(NRF24.PA_MAX)
radio.setAutoAck(True)
radio.enableDynamicPayloads()
radio.enableAckPayload()
radio.openWritingPipe(device[0].deviceAddress)
radio.openReadingPipe(1, masterAddress)
radio.printDetails()
time.sleep(1)

@app.errorhandler(404)
def not_found(error):
	return make_response(jsonify({'error': 'Not found'}), 404)

@app.errorhandler(400)
def not_found(error):
	return make_response(jsonify({'error': 'Not JSON'}), 404)

@app.errorhandler(500)
def error_found(error):
	data = {
		'tipo'  : 'Mensaje',
		'mensaje' : 'Error en Servidor',
		'body' : None
	}

	resp = make_response(json.dumps(data), 500)
	resp.headers['Content-Type'] = 'application/json'
	return resp


@app.route('/domotica/api/nodos', methods=['GET'])
def get_nodo():

	# ---- NODO RIEGO 1
	riegoData = [
		{'dispositivoItemId' : 1, 'dispositivoItemCodigo' : '000001-D', 'tipoValor' : 1, 'tipoMedicion' : 1, 'nombreMedicion' : 'humedad', 'valor'  : humedad},
		{'dispositivoItemId' : 1, 'dispositivoItemCodigo' : '000001-D', 'tipoValor' : 3, 'tipoMedicion' : 1, 'nombreMedicion' : 'temperatura', 'valor' : temperatura},
		{'dispositivoItemId' : 8, 'dispositivoItemCodigo' : '000008-D', 'tipoValor' : 8, 'tipoMedicion' : 1, 'nombreMedicion' : 'lluvia', 'valor' : lluvia},
		{'dispositivoItemId' : 9, 'dispositivoItemCodigo' : '000009-D', 'tipoValor' : 9, 'tipoMedicion' : 1, 'nombreMedicion' : 'litrosPorMinuto', 'valor' : litrosPorMinuto},
		{'dispositivoItemId' : 6, 'dispositivoItemCodigo' : '000006-D', 'tipoValor' : 10, 'tipoMedicion' : 1, 'nombreMedicion' : 'humedadTierra1', 'valor' : humedadTierra1},
		{'dispositivoItemId' : 7, 'dispositivoItemCodigo' : '000007-D', 'tipoValor' : 10, 'tipoMedicion' : 1, 'nombreMedicion' : 'humedadTierra2', 'valor' : humedadTierra2},
		{'dispositivoItemId' : 5, 'dispositivoItemCodigo' : '000005-D', 'tipoValor' : 11, 'tipoMedicion' : 1, 'nombreMedicion' : 'temperaturaTierra', 'valor' : temperaturaTierra}
	]

	# ------ CONFIGURACION DEL JSON
	nodos = [
		{
			'id': 4,
			'codigo': u'414141-N',
			'nombre': u'NODO RIEGO 1',
			'data' : riegoData
		}
	]
	
	
	#jNodos = json.dumps(nodos)
	
	jsonO = {
		'nodos'  : nodos
	}
	

	#resp = Response(jsonify(jsonO), status=200, mimetype='application/json')
	#resp = Response(jsonify(jsonO), status=200, mimetype='application/json')
	resp = jsonify(jsonO)
	return resp    


@app.route('/domotica/api/dispositivosItems/actuadores/<int:dispositivoItem_id>', methods=['PUT'])
def update_dispositivoItemActuador(dispositivoItem_id):
	
	nodId = request.json.get('nodo').get('id')
	dispItemCodigo = request.json.get('codigo')
	#dispItemId = request.json.get('id')
	dispId = request.json.get('dispositivo').get('id')
	values = request.json.get('valores')

	#canal = [nodo['canal'] for nodo in nodos if nodo['id'] == nodId]
	#canal = []	
	
	comando = ""

	# Definimos el comando depende de tipo de dispositivo	
	if dispId == 3:
		# ILUMINACION RGB
		print("Configuracion RGB")	
	else:
		# DISPOSITIVOS ACTUADORES CON ESTADO ENCENDIDO Y APAGADO
		if dispositivoItem_id == 10:
			# Electrovalvula nodo riego 1
			valor = values[0]['valor']
			canal = [0xc2,0xc2,0xc2,0xc2,0xc3]

			if valor == 1:
				comando = "ELVON"
			else:
				comando = "ELVOF"

	print("Canal {}- Nodo".format(canal))
	print("Comando= {}".format(comando))
	sendCommand(comando, canal)
		
	data = {
		'tipo'  : 'Mensaje',
		'mensaje' : 'Actualizado',
		'body' : None
	}

	resp = Response(json.dumps(data), status=200, mimetype='application/json')
	return resp


@app.route('/')
def index():	
	return render_template('index.html', async_mode=socketio.async_mode)


def nodes_info():
	""" Let's do it a bit cleaner """
	
	print('Enviando informacion sensores...')
	while True:
		for i in device:
			if(i.isTimeOut()):
				i.getData();
 
		#time.sleep(3)
		time.sleep(0.01)
		#emit('pong_event', {'data': {'tipo':'pong' , 'message': 'Connection Alive', 'count': 0}}, namespace='/vivienda')

# When the client emits 'connection', this listens and executes
#@socketio.on('thread nodes', namespace='/vivienda')
def thread_nodes():
	
	print('Verifying if the node Thread already exist')
	global thread
	with thread_lock:
		if thread is None:
			print('Creating Background Thread for nodes.')
			#thread = socketio.start_background_task(target=sensores_info)
			thread = Thread(target=nodes_info)
			thread.start()
	emit('thread nodes created', {'message': 'Thread Created', 'count': 0})


@socketio.on('ping_event', namespace='/vivienda')
def on_ping():
	print('Ping Recibido...')
	emit('pong_event', {'data': {'tipo':'pong' , 'message': 'Connection Alive', 'count': 0}}, namespace='/vivienda')


# When client emits 'add user' this listens and executes
@socketio.on('add user', namespace='/vivienda')
def add_user(data):
	print 'Adding User'
	global usernames
	global number_of_users
	session['username'] = data
	usernames[data] = session['username']
	number_of_users += 1;
	emit('user joined', { 'message': 'user joined', 'username' : session['username'], 'numUsers': number_of_users }, broadcast=True)


# When the client emits 'connection', this listens and executes
@socketio.on('connect', namespace='/vivienda')
def user_connected():
	print('User connected')
	thread_nodes()
	emit('conexion established', {'data': {'message': 'Connected', 'count': 0}})


@socketio.on('disconnect', namespace='/vivienda')
def disconnect():
	global usernames
	global number_of_users

	try:
		del usernames[session['username']]
		number_of_users -= 1
		emit('user left', { 'username' : session['username'], 'numUsers' : number_of_users}, broadcast=True)

	except:
		pass


if __name__ == '__main__':
	socketio.run(app, port=5000, host='0.0.0.0')
	


