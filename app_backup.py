#!flask/bin/python

# Websocket Packages 
import time, random
from threading import Lock
import threading
from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, disconnect
import requests

# REST packages
from flask import jsonify
from flask import make_response
from flask import abort
import json

from flask import Response

import serial

async_mode = None

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None
thread_lock = Lock()

usernames = {}
number_of_users = 0

arduino = serial.Serial('/dev/ttyACM0', 9600)

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


@app.route('/domotica/api/dispositivosItems/actuadores/<int:dispositivoItem_id>', methods=['PUT'])
def update_dispositivoItemActuador(dispositivoItem_id):
	
	nodCodigo = request.json.get('nodo').get('id')
	dispCodigo = request.json.get('codigo')
	vals = request.json.get('valores')

	#print(nodCodigo)
	print(dispCodigo)
	print(vals)
	
	data = {'codigo':dispCodigo, 'valores':vals}
	comando = json.dumps(data)
		

	##cambios_realizados = realizar_cambios_actuador(dispCodigo, vals)
	cambios_realizados = realizar_cambios_actuador(comando)

	if cambios_realizados == False:

		data = {
		'tipo'  : 'Mensaje',
		'mensaje' : 'No Actualizado',
		'body' : None
		}

		resp = make_response(json.dumps(data), 304)
		resp.headers['Content-Type'] = 'application/json'
		return resp


	data = {
		'tipo'  : 'Mensaje',
		'mensaje' : 'Actualizado',
		'body' : None
	}

	resp = Response(json.dumps(data), status=200, mimetype='application/json')
	return resp


##def realizar_cambios_actuador(dispCod, vals):
def realizar_cambios_actuador(comando):
	# *  ENVIAMOS POR SERIAL AL ARDUINO ESCOGIDO Y EL ARDUINO CON EL CODIGO
	#    CAMBIARA EL ESTADO DEL ACTUADOR.

	#comandoJson = "{\"codigo\" : \""+ dispCod+"\",  \"valores\" : \"" + vals + "\"}"
	#comandoJson = "{\"codigo\" : \"66666-D\",  \"valores\" : vals}"
	print(comando)

	arduino.write(comando)
	#respuesta = arduino.readline()
	#print(respuesta)
	
	#if respuesta != "Valor Actualizado":
	#	return False
	#
	return True



@app.route('/')
def index():	
	return render_template('index.html', async_mode=socketio.async_mode)

'''
def sensores_info():
	""" Let's do it a bit cleaner """
	while True:
		print('Enviando informacion sensores...')
		socketio.sleep(3)
		#time.sleep(3)
		t = str(time.clock())
		socketio.emit('sensores_info', {'bombillo1': 'encendido', 'bombillo2': 'apagado', 'time': t}, namespace='/vivienda')


# When the client emits 'connection', this listens and executes
@socketio.on('thread sensores', namespace='/vivienda')
def thread_devices():
	print('Creating Background Thread for sensors.')
	global thread
	with thread_lock:
		if thread is None:
			thread = socketio.start_background_task(target=sensores_info)
			#thread = Thread(target=devices_info)
			#thread.start()
	emit('thread sensores created', {'message': 'Thread Created', 'count': 0})
'''

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
	#print msg['data']
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

