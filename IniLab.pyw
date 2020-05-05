#Colores para el designer
#background-color: rgb(52, 52, 52);
#color: rgb(255, 255, 255);
#border-color: rgb(0, 0, 0);
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMainWindow
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QPixmap, QImage, QPalette, QColor
from PyQt5 import uic
from pyueye import ueye
from ctypes import *
import numpy as np
import cv2
import threading
import sys
import time
import statistics
import recursos
from datetime import datetime as dt
import os
import csv
from colormath.color_objects import XYZColor, sRGBColor,LabColor
from colormath.color_conversions import convert_color

#Funciones Auxiliares.
def valida_respuesta(answer, source):
	if answer == ueye.IS_SUCCESS:
		#print("SUCCESS")
		pass
	elif answer == ueye.IS_NOT_SUPPORTED:
		print(source + " - NOT SUPPORTED")
	elif answer == ueye.IS_NO_SUCCESS:
		print(source + " - NO SUCCESS")
	elif answer == ueye.IS_INVALID_PARAMETER:
		print(source + " - INVALID PARAMETER")
	elif answer == ueye.IS_INVALID_MODE:
		print(source + " - INVALID MODE")
	else:
		print(source + " - OTHER ERROR")

def guardar_configuracion():
	global dic_configuracion, variables
	f = open(pathConfig, "w")
	for variable in variables:
		string_array = dic_configuracion[variable]
		linea = variable
		for string in string_array:
			linea += ',' + string
		linea = linea + '\n'
		f.write(linea)
	f.close()

def agrega_variable(string):
	global dic_configuracion, variables
	data = string.split(",")
	variables.append(data[0])
	dic_configuracion[data[0]]=data[1:]

def leer_config_guardada():
	global dic_configuracion
	dic_configuracion = {}
	f = open(pathConfig, 'r')
	f1 = f.readlines()
	for x in f1:
		agrega_variable(x.rstrip('\n')) 
	f.close()

def guardar_medicion(R,G,B,L,a,b):
	directorio = 'Registro/Mediciones/' + dt.today().strftime('%Y/%B')
	if not os.path.exists(directorio):
		os.makedirs(directorio,0o755) #usar 0755 en rasb
	
	archivo = directorio +'/Registro_Mediciones_' + dt.today().strftime('%d-%m-%Y') + '.csv'
	if os.path.exists(archivo) == False:
		with open(archivo, "w") as f:
			writer = csv.writer(f,delimiter = ',')
			columnas = ['Hora','R','G','B','L','a','b']
			writer.writerow(columnas)
	
	with open(archivo,'a') as f:
		writer = csv.writer(f,delimiter = ',')
		renglon = [dt.today().strftime('%H:%M:%S'),str(R),str(G),str(B),str(L),str(a),str(b)]
		writer.writerow(renglon)

def guardar_imagen(img_data):
	directorio = 'Registro/Capturas/' + dt.today().strftime('%Y/%B/%d')
	if not os.path.exists(directorio):
		os.makedirs(directorio,0o755) #usar 0755 en rasb
	
	index = len(os.listdir(directorio))
	archivo = directorio + '/Img_'+ '{:04d}'.format(index) + '.jpg'
	cv2.imwrite(archivo, img_data)
	print(img_data)
	print (img_data.shape)
	
#Clase de QMainWindow
class VentanaManager(QMainWindow):

	#answ = pyqtSignal(str)
	#img = pyqtSignal(QImage)
	#Constructor de la clase
	def __init__(self):
		#Inicializamos el objeto QMainWindow
		QMainWindow.__init__(self)
		
		#Cargamos archivo de configuracion
		uic.loadUi("MainWindow.ui",self)
		
		#Ventana sin bordes
		self.setWindowFlags(Qt.FramelessWindowHint)
		
        #Hacemos la aplicacion modo pantalla completa
        self.showFullScreen()
        
		#Ocultamos el frame de control manual de la camara
		self.Manual.hide()
		
		#Ocultamos el frame de configuracion del software
		self.Configuracion.hide()
		
		#Cargamos iconos
		self.btn_config.setIcon(QIcon('recursos/logoConfig.png'))
		self.btn_cerrar.setIcon(QIcon('recursos/BotonCerrar.png'))
		self.barra_titulo_1.setPixmap(QPixmap('recursos/BarraTitulo.png'))
		self.barra_titulo_2.setPixmap(QPixmap('recursos/BarraTitulo2.png'))
		self.barra_titulo_3.setPixmap(QPixmap('recursos/BarraTitulo2.png'))
		
		#Se une a los botones con su funcion
		self.iniciar_captura.clicked.connect(self.capturar_imagen)
		self.parar_captura.clicked.connect(self.detener_captura)
		self.buscar.clicked.connect(self.buscar_camara)
		self.manual.clicked.connect(self.calibracion_manual)
		self.aceptar_man.clicked.connect(self.calibracion_aceptar)
		self.calibracion_default.clicked.connect(self.calibracion_poner_default)
		self.btn_config.clicked.connect(self.configuracion)
		self.aceptar_config.clicked.connect(self.configuracion_aceptar)
		self.guardar_datos.clicked.connect(self.guarda_medicion)
		self.guardar_img.clicked.connect(self.guarda_imagen)
		self.btn_cerrar.clicked.connect(self.funcion_cerrar)
		
		#Unimos Sliders con sus funciones
		self.slider_reloj.valueChanged.connect(self.cambiar_pixelclock)
		self.slider_exposicion.valueChanged.connect(self.cambiar_exposicion)
		self.slider_frecuencia.valueChanged.connect(self.cambiar_frecuencia)
		
		#Unimos los RadioButtons con sus funciones
		self.muestra_traslucida.toggled.connect(lambda:self.calibracion_auto(self.muestra_traslucida))
		self.muestra_opaca.toggled.connect(lambda:self.calibracion_auto(self.muestra_opaca))
		self.selec_manual.toggled.connect(lambda:self.calibracion_auto(self.selec_manual))
		self.promedio.toggled.connect(lambda:self.calculo_color(self.promedio))
		self.conglomerados.toggled.connect(lambda:self.calculo_color(self.conglomerados))
		
		#Control de color del area de muestra de medicion
		self.mostrar_color.setStyleSheet("background-color:#000000;")
			
		w = 320
		h = 256
		ch = 4
		#Creamos vector de imagen
		creando_bgra = np.empty((h, w, ch), np.uint8, 'C')
		#Capa B
		creando_bgra[...,0] = np.full((h, w), 0, np.uint8, 'C')
		#Capa G
		creando_bgra[...,1] = np.full((h, w), 0, np.uint8, 'C')
		#Capa R
		creando_bgra[...,2] = np.full((h, w), 0, np.uint8, 'C')
		#Capa A de transparencia
		creando_bgra[...,3] = np.full((h, w), 254, np.uint8, 'C')
		#Creamos frame
		myframe = QImage(creando_bgra, w, h, QImage.Format_ARGB32)
		#self.pixmap = QPixmap('test1.jpg')
		self.vista_imagen.setPixmap(QPixmap(myframe))
		self.vista_imagen.move(450,51)
		#self.modelo.setText('Testing...')
		#self.resize(pixmap.width(),pixmap.height())
		#self.vista_imagen.setBackgroundRole(QPalette.Base)
		#self.vista_imagen.setScaledContents(True)
	
		#Estado inicial de capturar imagen
		self.capturando_imagen = False
		
		#Estado inicial de capturar imagen
		self.calibracion_manual_visible = False
		
		#Variables para usar la camara
		self.Cam = ueye.HIDS(0)    #0: first available camera;  1-254: The camera with the specified camera ID
		self.sensor_info = ueye.SENSORINFO()
		self.cam_info = ueye.CAMINFO()
		self.mem_img = ueye.c_mem_p()
		self.MemID = ueye.int()
		self.rectAOI = ueye.IS_RECT()
		self.pitch = ueye.INT()
		self.nBitsPerPixel = ueye.INT(24)    #24: bits per pixel for color mode; take 8 bits per pixel for monochrome
		self.channels = 3                    #3: channels for color mode(RGB); take 1 channel for monochrome
		self.m_nColorMode = ueye.INT()		# Y8/RGB16/RGB24/REG32
		self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
		
		#Variables con valores iniciales para evitar errores
		self.fps_porcentaje_act = 0.5
		self.medicion_R = 0
		self.medicion_G = 0
		self.medicion_B = 0
		self.calculo_L = 0
		self.calculo_a = 0
		self.calculo_b = 0
		self.img_data = []
		#----------------------------------------------------
		print("Iniciando camara")
		self.buscar_camara()

	def detener_captura(self):
		print('Se llama a detener_captura')
		self.capturando_imagen = False
		self.iniciar_captura.setEnabled(True)
		self.parar_captura.setEnabled(False)
		self.guardar_datos.setEnabled(False)
		self.guardar_img.setEnabled(False)
		self.manual.setEnabled(False)
		self.automatica.setEnabled(False)

	def loop_captura(self):
		# Reservamos memoria para una imagen dadas las dimensiones definidas en width y height y por la profundidad de color definida por nBitsPerPixel
		answer = ueye.is_AllocImageMem(self.Cam, self.width, self.height, self.nBitsPerPixel, self.mem_img, self.MemID)
		if answer != ueye.IS_SUCCESS:
			print("is_AllocImageMem ERROR")
		else:
			#Hacemos la memoria especificada the memoria activa
			answer = ueye.is_SetImageMem(self.Cam, self.mem_img, self.MemID)
			if answer != ueye.IS_SUCCESS:
				print("is_SetImageMem ERROR")
			else:
				#Seleccionamos el modo de color selecionado
				answer = ueye.is_SetColorMode(self.Cam, self.m_nColorMode)

		# Activamos el modo de video de la camara (modo free run)
		answer = ueye.is_CaptureVideo(self.Cam, ueye.IS_DONT_WAIT)
		if answer != ueye.IS_SUCCESS:
			print("is_CaptureVideo ERROR")

		# Habilitamos el modo de cola para la secuencia de imagenes de memoria
		answer = ueye.is_InquireImageMem(self.Cam, self.mem_img, self.MemID, self.width, self.height, self.nBitsPerPixel, self.pitch)
		if answer != ueye.IS_SUCCESS:
			print("is_InquireImageMem ERROR")
		else:
			print("Inicia ciclo de captura")
			print()

		#---------------------------------------------------------------------------------------------------------------------------------------
		
		#Recuperamos la calibracion que estaba seleccionada la ultima vez que se encendio el dispositivo
		calibracion_seleccionada = int(dic_configuracion['calibselec'][0])
		if self.muestra_traslucida.isChecked() or self.muestra_opaca.isChecked() or self.selec_manual.isChecked():
			if self.muestra_traslucida.isChecked():
				#print()
				#print ('1 Checked')
				pixel = int(dic_configuracion['translucida'][0])
				frames = float(dic_configuracion['translucida'][1])
				exposure = float(dic_configuracion['translucida'][2])
			elif self.muestra_opaca.isChecked():
				#print()
				#print ('2 Checked')
				pixel = int(dic_configuracion['opaca'][0])
				frames = float(dic_configuracion['opaca'][1])
				exposure = float(dic_configuracion['opaca'][2])
			elif self.selec_manual.isChecked():
				#print()
				#print ('3 Checked')
				pixel = int(dic_configuracion['manual'][0])
				frames = float(dic_configuracion['manual'][1])
				exposure = float(dic_configuracion['manual'][2])	
			print()
			#print('Checked - Setting pixel: ' + str(pixel))
			self.slider_reloj.setValue(pixel)
			#print('Checked - Setting fps: ' + str(frames))
			self.slider_frecuencia.setValue(int(frames*100))
			#print('Checked - Setting exposure: ' + str(exposure))
			self.slider_exposicion.setValue(int(exposure*100))
		else:
			if calibracion_seleccionada == 1:
				self.muestra_traslucida.setChecked(True)
			elif calibracion_seleccionada == 2:
				self.muestra_opaca.setChecked(True)
			else:
				self.selec_manual.setChecked(True)
		
		counter = 0
		# Modo de despliegue de imagen continua
		while (answer == ueye.IS_SUCCESS and self.capturando_imagen):
			# In order to display the image in an OpenCV window we need to...
			# ...extract the data of our image memory
			array = ueye.get_data(self.mem_img, self.width, self.height, self.nBitsPerPixel, self.pitch, copy=False)
			self.bytes_per_pixel = int(self.nBitsPerPixel / 8)

			# ...reshape it in an numpy array...
			frame = np.reshape(array,(self.height.value, self.width.value, self.bytes_per_pixel))
			self.img_data = frame
			# ...resize the image by a half
			frame = cv2.resize(frame,(0,0),fx=0.25, fy=0.25)
			
			#calculamos promedio de RGB
			average = np.average(frame, axis = 0)
		
		#---------------------------------------------------------------------------------------------------------------------------------------
			#Include image data processing here
			h, w, ch = frame.shape
			#print(frame.shape)
			creando_bgra = np.empty((h, w, 3), np.uint8, 'C')
			#if counter == 0:
				#print(frame[...,2])
				#print(frame[...,1])
				#print(frame[...,0])
				#print(frame[...,3])
			#elif counter >500:
			#	counter = 0
			#counter += 1
			creando_bgra[...,0] = frame[...,2]
			creando_bgra[...,1] = frame[...,1]
			creando_bgra[...,2] = frame[...,0]
			#creando_bgra[...,3] = np.full((h, w), 254, np.uint8, 'C') - frame[...,3]
			bytesPerLine = 3 * w
			myframe = QImage(creando_bgra, w, h, bytesPerLine, QImage.Format_RGB888)#Format_RGB32)
			self.vista_imagen.setPixmap(QPixmap(myframe))
			#self.vista_imagen.move(330,70)
			
			calcular_color = int(dic_configuracion['calccolor'][0])
			
			if calcular_color == 1:
				#Calculamos promedio
				avg_color_per_row = np.average(creando_bgra, axis=0)
				avg_color = np.average(avg_color_per_row, axis=0)
				R =  int(avg_color[0])
				G =  int(avg_color[1])
				B =  int(avg_color[2])
				#print( "Average: "+ str(avg_color))
			else:
				#Calculamos valor con clusterizacion 
				pixels = np.float32(creando_bgra[:,:,0:3].reshape(-1, 3))

				n_colors = 1
				criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 200, .1)
				flags = cv2.KMEANS_RANDOM_CENTERS

				_, labels, palette = cv2.kmeans(pixels, n_colors, None, criteria, 10, flags)
				_, counts = np.unique(labels, return_counts=True)

				dominant = palette[np.argmax(counts)]
				R = int(dominant[0])
				G = int(dominant[1])
				B = int(dominant[2])	
			
			self.medicion_R = R
			self.medicion_G = G
			self.medicion_B = B
			color_medido = QColor(R,G,B)
			valores = "{r}, {g}, {b}".format(r = color_medido.red(), 
											g = color_medido.green(),
											b = color_medido.blue())
			self.mostrar_color.setStyleSheet("background-color: rgb(" + valores + ");")#str(R) + ", " + str(G) + ", " + str(B) + ");")
			#print("background-color: rgb(" + str(R) + ", " + str(G) + ", " + str(B) + ");")
			self.r.display(R)
			self.g.display(G)
			self.b.display(B)
			#print("Clustering: " + str(dominant)) 
			#time.sleep(0.25)
			
			#Calculo de color en LabColor
			rgb = sRGBColor(R/255, G/255, B/255)
			xyz = convert_color(rgb, XYZColor)
			lab = convert_color(xyz,LabColor)
			self.calculo_L = lab.lab_l
			self.calculo_a = lab.lab_a
			self.calculo_b = lab.lab_b
			
			self.l.display(int(lab.lab_l))
			self.a.display(int(lab.lab_a))
			self.b_2.display(int(lab.lab_b))
			
			#if self.calibracion_manual_visible == True:
			#	pixel_clock_actual = ueye.UINT()
			#	answer = ueye.is_PixelClock(self.Cam, ueye.IS_PIXELCLOCK_CMD_GET, pixel_clock_actual, sizeof(ueye.UINT()))
			#	self.reloj_valor.setText(str(pixel_clock_actual) + ' ms')
				
		#---------------------------------------------------------------------------------------------------------------------------------------
			
			#...and finally display it
			#cv2.imshow("Captura de Imagen", frame)

			# Press q if you want to end the loop
			#if cv2.waitKey(1) & 0xFF == ord('q'):
			#	self.capturando_imagen = False
			#	break
			time.sleep(0.25)
			answer = 0
			
			#f = open("img_data.txt", "w")
			#f.write(str(frame))
			#f.close()
		
		print('Salimos de ciclo infinito')
		# Liberamos la memoria que se reservo usando is_AllocImageMem() 
		ueye.is_FreeImageMem(self.Cam, self.mem_img, self.MemID)

		# Desactivamos el control de self.Cam y liberamos la memoria ocupada por la camara
		ueye.is_ExitCamera(self.Cam)

		# Cerramos las ventanas de OpenCV
		#cv2.destroyAllWindows()
		
		return 1
	
	def capturar_imagen(self):
		self.capturando_imagen = True
		self.buscar_camara()
		capturando_imagen = self.capturando_imagen
		self.threat_video = threading.Thread(target = self.loop_captura,args = ())
		self.threat_video.start()
		self.iniciar_captura.setEnabled(False)
		self.parar_captura.setEnabled(True)
		self.guardar_datos.setEnabled(True)
		self.automatica.setEnabled(True)
		self.manual.setEnabled(True)
		self.guardar_img.setEnabled(True)
	
	def buscar_camara(self):
		
		# Liberamos la memoria que se reservo usando is_AllocImageMem() si se uso la camara antes
		ueye.is_FreeImageMem(self.Cam, self.mem_img, self.MemID)

		# Desactivamos el control de self.Cam y liberamos la memoria ocupada por la camara
		ueye.is_ExitCamera(self.Cam)
	
		# Inicia el driver y establece conexion con la camara
		answer = ueye.is_InitCamera(self.Cam, None)
		if answer != ueye.IS_SUCCESS:
			print("is_InitCamera ERROR")
			return 0

		#Leemos la memoria no volatil de la camara y la asignamos a donde cam_info apunta
		answer = ueye.is_GetCameraInfo(self.Cam, self.cam_info)
		if answer != ueye.IS_SUCCESS:
			print("is_GetCameraInfo ERROR")
			return 0

		#Se puede buscar informacion extra del sensor en la camara
		answer = ueye.is_GetSensorInfo(self.Cam, self.sensor_info)
		if answer != ueye.IS_SUCCESS:
			print("is_GetSensorInfo ERROR")
			return 0

		#Reiniciamos la configuracion de la camara, solo para evitar algun bug
		answer = ueye.is_ResetToDefault(self.Cam)
		if answer != ueye.IS_SUCCESS: 
			print("is_ResetToDefault ERROR")
			return 0

		# Ponemos el modo de display a DIB
		answer = ueye.is_SetDisplayMode(self.Cam, ueye.IS_SET_DM_DIB)

		# Ponemos el modo de color correcto
		if int.from_bytes(self.sensor_info.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_BAYER:
			#Si esta seleccionado el modo a color
			ueye.is_GetColorDepth(self.Cam, self.nBitsPerPixel, self.m_nColorMode)
			self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
			print("IS_COLORMODE_BAYER: ", )
			print("\tm_nColorMode: \t\t", self.m_nColorMode)
			print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
			print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
			print()

		elif int.from_bytes(self.sensor_info.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_CBYCRY:
			# Para camaras que usan el modo de color RGB32 en CBYCRY
			self.m_nColorMode = ueye.IS_CM_BGRA8_PACKED
			self.nBitsPerPixel = ueye.INT(32)
			self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
			print("IS_COLORMODE_CBYCRY: ", )
			print("\tm_nColorMode: \t\t", self.m_nColorMode)
			print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
			print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
			print()

		elif int.from_bytes(self.sensor_info.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_MONOCHROME:
			# Para camaras que usan el modo de color RGB32 en monochromatico
			self.m_nColorMode = ueye.IS_CM_MONO8
			self.nBitsPerPixel = ueye.INT(8)
			self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
			print("IS_COLORMODE_MONOCHROME: ", )
			print("\tm_nColorMode: \t\t", self.m_nColorMode)
			print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
			print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
			print()

		else:
			# Para modelos camaras monochromaticas que usan el modo Y8
			self.m_nColorMode = ueye.IS_CM_MONO8
			self.nBitsPerPixel = ueye.INT(8)
			self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
			print("else")

		# Se puede usar para enfocar en un area en interes "AOI" (area of interest) dentro de una imagen
		answer = ueye.is_AOI(self.Cam, ueye.IS_AOI_IMAGE_GET_AOI, self.rectAOI, ueye.sizeof(self.rectAOI))
		if answer != ueye.IS_SUCCESS:
			print("is_AOI ERROR")
			return 0

		self.width = self.rectAOI.s32Width
		self.height = self.rectAOI.s32Height

		# Prints out some information about the camera and the sensor
		self.modelo.setText(self.sensor_info.strSensorName.decode('utf-8'))
		print("Camera model:\t\t", self.sensor_info.strSensorName.decode('utf-8'))
		self.serie.setText(self.cam_info.SerNo.decode('utf-8'))
		print("Camera serial no.:\t", self.cam_info.SerNo.decode('utf-8'))
		self.tam.setText(str(self.width) + " x " + str(self.height))
		print("Maximum image width:\t", self.width)
		print("Maximum image height:\t", self.height)
		print()
		
		self.iniciar_captura.setEnabled(True)
		self.parar_captura.setEnabled(False)
		self.guardar_datos.setEnabled(False)
		self.guardar_img.setEnabled(False)
		self.automatica.setEnabled(False)
		self.manual.setEnabled(False)#Esto cambiara a iniciar captura
		
		return 1
	
	def calculo_color(self, btn):
		if btn.text() == "Promedio":
			if btn.isChecked() == True:
				dic_configuracion['calccolor'][0] = '1'
				
		if btn.text() == "Conglomerados":
			if btn.isChecked() == True:
				dic_configuracion['calccolor'][0] = '2'
				
	def calibracion_auto(self, btn):
		select_true = False
		if btn.text() == "Traslucida":
			if btn.isChecked() == True:
				select_true = True
				dic_configuracion['calibselec'][0] = '1'
				pixel = int(dic_configuracion['translucida'][0])
				frames = float(dic_configuracion['translucida'][1])
				exposure = float(dic_configuracion['translucida'][2])
		
		if btn.text() == "Opaca":
			if btn.isChecked() == True:
				select_true = True
				dic_configuracion['calibselec'][0] = '2'
				pixel = int(dic_configuracion['opaca'][0])
				frames = float(dic_configuracion['opaca'][1])
				exposure = float(dic_configuracion['opaca'][2])
				
		if btn.text() == "Manual":
			if btn.isChecked() == True:
				select_true = True
				dic_configuracion['calibselec'][0] = '3'
				pixel = int(dic_configuracion['manual'][0])
				frames = float(dic_configuracion['manual'][1])
				exposure = float(dic_configuracion['manual'][2])
		if select_true == True:
			#print('Setting pixel: ' + str(pixel))
			self.slider_reloj.setValue(pixel)
			#print('Setting fps: ' + str(frames))
			self.slider_frecuencia.setValue(int(frames*100))
			#print('Setting exposure: ' + str(exposure))
			self.slider_exposicion.setValue(int(exposure*100))
		
	def calibracion_manual(self):
		#Mostramos el frame de control manual de la camara
		self.Manual.show()
		self.calibracion_manual_visible = True
		
		pixel_clock_rango = (ueye.UINT * 3)()
		answer = ueye.is_PixelClock(self.Cam, ueye.IS_PIXELCLOCK_CMD_GET_RANGE, pixel_clock_rango, 3*sizeof(ueye.UINT()))
		lim_inf = pixel_clock_rango[0]
		lim_sup = pixel_clock_rango[1]
		self.reloj_inf.setText(str(lim_inf) + ' MHz')
		self.slider_reloj.setMinimum(lim_inf)
		self.reloj_sup.setText(str(lim_sup) + ' MHz')
		self.slider_reloj.setMaximum(lim_sup)
		
		pixel_clock_actual = ueye.UINT()
		answer = ueye.is_PixelClock(self.Cam, ueye.IS_PIXELCLOCK_CMD_GET, pixel_clock_actual, sizeof(ueye.UINT()))
		self.slider_reloj.setValue(pixel_clock_actual)
		
		time_min = ueye.DOUBLE(0.1)
		time_max = ueye.DOUBLE(1)
		step_time = ueye.DOUBLE()
		answer = ueye.is_GetFrameTimeRange(self.Cam, time_min, time_max, step_time)
		fps_lim_inf = 1/time_max
		fps_lim_sup = 1/time_min
		self.frecuencia_inf.setText('{0:.2f}'.format(float(fps_lim_inf)) + ' fps')
		self.slider_frecuencia.setMinimum(int(fps_lim_inf * 100))
		self.frecuencia_sup.setText('{0:.2f}'.format(float(fps_lim_sup)) + ' fps')
		self.slider_frecuencia.setMaximum(int(fps_lim_sup * 100))
		
		fps_actual = ueye.DOUBLE()
		answer = ueye.is_GetFramesPerSecond(self.Cam, fps_actual)
		valida_respuesta(answer,'Obtener FPS Actual')
		self.frecuencia_valor.setText('{0:.2f}'.format(float(fps_actual)) + ' fps')
		self.slider_frecuencia.setValue(int(fps_actual * 100))
		self.fps_porcentaje_act = (fps_actual-fps_lim_inf)/(fps_lim_sup-fps_lim_inf)

		exposure_rango = (ueye.DOUBLE * 3)()
		answer = ueye.is_Exposure(self.Cam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE_RANGE , exposure_rango, 3*sizeof(ueye.DOUBLE()))
		lim_inf = float(exposure_rango[0])
		lim_sup = float(exposure_rango[1])
		self.exposicion_inf.setText('{0:.2f}'.format(lim_inf) + ' ms')
		self.slider_exposicion.setMinimum(int(lim_inf * 100))
		self.exposicion_sup.setText('{0:.2f}'.format(lim_sup) + ' ms')
		self.slider_exposicion.setMaximum(int(lim_sup * 100))
		
		exposure_time_actual = ueye.DOUBLE()
		answer = ueye.is_Exposure(self.Cam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE, exposure_time_actual, sizeof(ueye.DOUBLE()))
		self.slider_exposicion.setValue(int(exposure_time_actual * 100))
		
		if self.muestra_traslucida.isChecked():
			pixel = int(dic_configuracion['translucida'][0])
			frames = float(dic_configuracion['translucida'][1])
			exposure = float(dic_configuracion['translucida'][2])
		elif self.muestra_opaca.isChecked():
			pixel = int(dic_configuracion['opaca'][0])
			frames = float(dic_configuracion['opaca'][1])
			exposure = float(dic_configuracion['opaca'][2])
		elif self.selec_manual.isChecked():
			pixel = int(dic_configuracion['manual'][0])
			frames = float(dic_configuracion['manual'][1])
			exposure = float(dic_configuracion['manual'][2])	
		print()
		#print('Checked - Setting pixel: ' + str(pixel))
		self.slider_reloj.setValue(pixel)
		#print('Checked - Setting fps: ' + str(frames))
		self.slider_frecuencia.setValue(int(frames*100))
		#print('Checked - Setting exposure: ' + str(exposure))
		self.slider_exposicion.setValue(int(exposure*100))
		
	def calibracion_poner_default(self):
		pixel_clock_default = ueye.UINT()
		answer = ueye.is_PixelClock(self.Cam, ueye.IS_PIXELCLOCK_CMD_GET_DEFAULT, pixel_clock_default, sizeof(ueye.UINT()))
		valida_respuesta(answer,'Obtener PixelClock default')
		self.slider_reloj.setValue(pixel_clock_default)
		
		fps_default = ueye.DOUBLE()
		answer = ueye.is_SetFrameRate(self.Cam, ueye.IS_GET_DEFAULT_FRAMERATE,fps_default)
		valida_respuesta(answer,'Obtener FPS default')
		self.slider_frecuencia.setValue(int(fps_default*100))
		
		exposure_time_default = ueye.DOUBLE()
		answer = ueye.is_Exposure(self.Cam, ueye.IS_PIXELCLOCK_CMD_GET_DEFAULT, exposure_time_default, sizeof(ueye.DOUBLE()))
		valida_respuesta(answer,'Obtener Exposure default')
		self.slider_exposicion.setValue(int(exposure_time_default * 100))
		
	def cambiar_pixelclock(self):
		value = self.slider_reloj.value()
		#print('Setting pixel_clock: ' + str(value))
		pixel_clock = ueye.UINT(value)
		answer = ueye.is_PixelClock(self.Cam, ueye.IS_PIXELCLOCK_CMD_SET, pixel_clock, sizeof(ueye.UINT()))
		valida_respuesta(answer,'Cambiar PixelClock')
		
		pixel_clock_actual = ueye.UINT()
		answer = ueye.is_PixelClock(self.Cam, ueye.IS_PIXELCLOCK_CMD_GET, pixel_clock_actual, sizeof(ueye.UINT()))
		self.reloj_valor.setText(str(pixel_clock_actual) + ' MHz')
		
		time_min = ueye.DOUBLE(0.1)
		time_max = ueye.DOUBLE(1)
		step_time = ueye.DOUBLE()
		answer = ueye.is_GetFrameTimeRange(self.Cam, time_min, time_max, step_time)
		fps_lim_inf = 1/time_max
		fps_lim_sup = 1/time_min
		self.frecuencia_inf.setText('{0:.2f}'.format(float(fps_lim_inf)) + ' fps')
		self.slider_frecuencia.setMinimum(int(fps_lim_inf * 100))
		self.frecuencia_sup.setText('{0:.2f}'.format(float(fps_lim_sup)) + ' fps')
		self.slider_frecuencia.setMaximum(int(fps_lim_sup * 100))
		fps_new = self.fps_porcentaje_act*(fps_lim_sup - fps_lim_inf) + fps_lim_inf
		self.slider_frecuencia.setValue(int(fps_new * 100))
		
	def cambiar_frecuencia(self):
		value = self.slider_frecuencia.value()
		new_fps = ueye.DOUBLE(float(value/100))
		#print('Setting fps: ' + str(new_fps))
		valor_puesto = ueye.DOUBLE()
		answer = ueye.is_SetFrameRate(self.Cam,new_fps,valor_puesto)
		valida_respuesta(answer,'Cambiar los FPS')
		self.frecuencia_valor.setText('{0:.2f}'.format(float(valor_puesto)) + ' fps')
		
		time_min = ueye.DOUBLE(0.1)
		time_max = ueye.DOUBLE(1)
		step_time = ueye.DOUBLE()
		answer = ueye.is_GetFrameTimeRange(self.Cam, time_min, time_max, step_time)
		fps_lim_inf = 1/time_max
		fps_lim_sup = 1/time_min
		self.fps_porcentaje_act = (valor_puesto-fps_lim_inf)/(fps_lim_sup-fps_lim_inf)
		
		exposure_rango = (ueye.DOUBLE * 3)()
		answer = ueye.is_Exposure(self.Cam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE_RANGE , exposure_rango, 3*sizeof(ueye.DOUBLE()))
		lim_inf = float(exposure_rango[0])
		lim_sup = float(exposure_rango[1])
		self.exposicion_inf.setText('{0:.2f}'.format(lim_inf) + ' ms')
		self.slider_exposicion.setMinimum(int(lim_inf * 100))
		self.exposicion_sup.setText('{0:.2f}'.format(lim_sup) + ' ms')
		self.slider_exposicion.setMaximum(int(lim_sup * 100))
		
		exposure_time_actual = ueye.DOUBLE()
		answer = ueye.is_Exposure(self.Cam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE, exposure_time_actual, sizeof(ueye.DOUBLE()))
		self.slider_exposicion.setValue(int(exposure_time_actual * 100))
	
	def cambiar_exposicion(self):
		value = self.slider_exposicion.value()
		exposure_time = ueye.DOUBLE(float(value/100))
		#print('Setting exposure: ' + str(exposure_time))
		answer = ueye.is_Exposure(self.Cam, ueye.IS_EXPOSURE_CMD_SET_EXPOSURE, exposure_time, sizeof(ueye.DOUBLE()))
		valida_respuesta(answer,'Cambiar Expousure')
		
		exposure_time_actual = ueye.DOUBLE()
		answer = ueye.is_Exposure(self.Cam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE, exposure_time_actual, sizeof(ueye.DOUBLE()))
		self.exposicion_valor.setText('{0:.2f}'.format(float(exposure_time_actual)) + ' ms')
		
	def configuracion(self):
		#Mostramos el frame de control manual de la camara
		self.Configuracion.show()
	
	def configuracion_aceptar(self):
		guardar_configuracion()
		self.Configuracion.hide()
	
	def calibracion_aceptar(self):
		#Ocultamos el frame de control manual de la camara
		self.Manual.hide()
		#Nos saltamos la calibracion en el ciclo de captura
		self.calibracion_manual_visible = False
		
		pixel_clock_actual = ueye.UINT()
		answer = ueye.is_PixelClock(self.Cam, ueye.IS_PIXELCLOCK_CMD_GET, pixel_clock_actual, sizeof(ueye.UINT()))
		valida_respuesta(answer,'Obtener PixelClock Actual')
		
		fps_actual = ueye.DOUBLE()
		answer = ueye.is_GetFramesPerSecond(self.Cam, fps_actual)
		valida_respuesta(answer,'Obtener FPS actual')
		
		exposure_time_actual = ueye.DOUBLE()
		answer = ueye.is_Exposure(self.Cam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE, exposure_time_actual, sizeof(ueye.DOUBLE()))
		valida_respuesta(answer,'Obtener Expousure actual')
		
		dic_configuracion['manual'][0] = str(pixel_clock_actual)
		dic_configuracion['manual'][1] = str(fps_actual)
		dic_configuracion['manual'][2] = str(exposure_time_actual)
		dic_configuracion['calibselec'][0] = '3'
		guardar_configuracion()
		
		#Marcamos Seleccionada la calibracion manual
		self.selec_manual.setChecked(True)
	
	def guarda_medicion(self):
		guardar_medicion(self.medicion_R, self.medicion_G, self.medicion_B, self.calculo_L, self.calculo_a, self.calculo_b)
	
	def guarda_imagen(self):
		guardar_imagen(self.img_data)
	
	def funcion_cerrar(self):
		self.capturando_imagen = False
		self.close()
#-----------------------------------------------------------------------
				

pathConfig = 'Inilab.config'
variables = []
dic_configuracion = {}
leer_config_guardada()

#Funcion principal
#Instancionamos nuestra app a el sistema
app = QApplication(sys.argv)
#Creamos la ventana
ventana	= VentanaManager()
#Hacemos la ventana visible
ventana.show()
#Iniciamos nuestra app
app.exec_()
