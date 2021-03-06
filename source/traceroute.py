from scapy.all import *
import os, sys, time, csv
import json, requests
import numpy as np

CANT_REP = 30
MAX_INTENTOS = 4
TIME_LIMIT = 3
NODES_LIMIT = 30
TYPE_TIMEEXCEDED = 11
TYPE_LASTNODE = 0
LISTA_TAU = [0, 0, 0, 1.1511, 1.4250, 1.5712, 1.6563, 1.7110, 1.7491, 1.7770, 1.7984, 1.8153, 1.8290, 1.8403, 1.8498, 1.8579, 1.8649, 1.8710, 1.8764, 1.8811, 1.8853, 1.8891, 1.8926, 1.8957, 1.8985, 1.9011, 1.9035, 1.9057, 1.9078, 1.9096, 1.9114]

class traceroute():
    # Recibe un string con la ip/url de destino y un archivo de salida
    def __init__(self, destino, namefile):
        if not namefile:
            namefile = str(time.time())
        self.namefile = namefile
        self.destino = destino
        self.route = []
        self.numRep = 0
        self.numIntento = 0

    def iniciar(self):
        self.loggerRoute = csv.writer(open(self.namefile + '.csv', "wb"))
        self.loggerRoute.writerow(["ttl","ip","rtt","pais","region","ciudad","latitud","longitud"])
        self.ttlActual = 1
        fin_camino = False
        while not fin_camino and self.ttlActual < NODES_LIMIT:
            host = {}
            host['tiempos'] = []
            host['ttl'] = self.ttlActual
            self.numRep = 0
            numIntento = 0
            # arma el paquete con el ttl incluido
            paquete = IP(dst=self.destino,ttl=self.ttlActual)/ICMP()
            while self.numRep < CANT_REP and numIntento < MAX_INTENTOS:
                self.actualizarVistaProceso()
                # hago un echo request o ping para los pibes
                start_time = time.time()
                response = sr1(paquete, timeout=TIME_LIMIT)
                end_time = time.time()
                numIntento += 1
                if response:
                    # analizo response
                    if response[ICMP].type == TYPE_TIMEEXCEDED or response[ICMP].type == TYPE_LASTNODE:
                        # guarda ip del host al que llego
                        host['ip'] = response.src
                        # guarda el tiempo obtenido en el host
                        host['tiempos'].append(end_time - start_time)
                        # aumenta contador
                        self.numRep += 1
                        # reseteamos el numero de intentos
                        numIntento = 0
                    # chequeamos si es el nodo de destino
                    if response[ICMP].type == TYPE_LASTNODE:
                        print "PASA POR SALIDA"
                        fin_camino = True
            if len(host['tiempos']) > 0:
                last_ip = host['ip']
                self.route.append(host)
            self.ttlActual += 1

    def buscarIps(self):
        for host in self.route:
            # si es de red interna le digo a la pagina que me rastree
            pais = ""
            region = ""
            ciudad = ""
            latitud = ""
            longitud = ""
            respok = 0
            intentos_geo = 0
            while not respok and intentos_geo < 10:
                response = requests.get("http://freegeoip.net/json/" + str(host['ip']))
                if response.status_code == 200:
                    # parsea el json de respuesta de la api
                    infoip = json.loads(response.content)
                    # se guarda los datos necesarios
                    pais = infoip['country_name'].encode('utf-8')
                    region = infoip['region_name'].encode('utf-8')
                    ciudad = infoip['city'].encode('utf-8')
                    latitud = infoip['latitude']
                    longitud = infoip['longitude']
                    # setea que recibe los datos ok
                    respok = 1
                intentos_geo += 1
            # guarda en csv la salida
            for rtt in host['tiempos']:
                self.loggerRoute.writerow([host['ttl'], host['ip'], rtt, pais, region, ciudad, latitud, longitud])

    def estadoDesdeCsv(self, namefile):
        self.route = []
        self.namefile = namefile
        with open(self.namefile, 'rb') as archivocsv:
            lector = csv.reader(archivocsv)
            self.ttlActual = -1
            ip_actual = -1
            primera_linea = 1
            host = {}
            for linea in lector:
                if primera_linea:
                    primera_linea = 0
                else:
                    if self.ttlActual != linea[0]:
                        if self.ttlActual > 0:
                            self.route.append(host)
                        self.ttlActual = linea[0]
                        host = {}
                        host['tiempos'] = []
                        host['ttl'] = self.ttlActual
                        host['ip'] = linea[1]
                        host['pais'] = linea[3]
                        host['region'] = linea[4]
                        host['ciudad'] = linea[5]
                        host['latitud'] = linea[6]
                        host['longitud'] = linea[7]
                    host['tiempos'].append(float(linea[2]))
            self.route.append(host)
            self.actualizarVistaProceso()

    def actualizarVistaProceso(self):
        os.system('clear')
        print "-------------TRACEROUTE-------------"
        print "Destino:       " + self.destino
        print "TTL actual:    " + str(self.ttlActual)
        print "Num captura:   " + str(self.numRep)
        print "------------------------------------"
        print ""
        for host in self.route:
            print str(host['ttl']) + " -> " + host['ip'] + " - " + str(promediarRtts(host['tiempos']))
        print ""

    def mostrarVistaResultado(self):
        os.system('clear')
        print "-------------CAMINO OBTENIDO-------------"
        print ""
        for host in self.route:
            if host['es_salto']:
                print "...Salto Intercontinental..."
            print str(host['ttl']) + " -> " + host['ip'] + " (" + host['pais'] + ")" + " - " + str(host['rtt_salto'])
        print ""

    def calcularOutliers(self):
        rtts = []
        rtt_ultimo_nodo = 0
        # calcula rtt por salto y los agrega a una lista para calcular promedio y std
        for host in self.route:
            host['es_salto'] = False
            rtt_promedio = promediarRtts(host['tiempos'])
            host['rtt_salto'] = rtt_promedio - rtt_ultimo_nodo
            rtt_ultimo_nodo = rtt_promedio
            rtts.append((host['ip'], host['rtt_salto']))

        # ordena por rtt de salto
        rtts = sorted(rtts, key=lambda x: x[1])

        hay_outlier = True
        while hay_outlier:
            hay_outlier = False
            # calcula promedio y std
            np_rtt = []
            for par in rtts:
                rtt = par[1]
                np_rtt.append(rtt)
            np_rtt = np.array(np_rtt)
            promedio = np.mean(np_rtt)
            std = np.std(np_rtt)
            # tomamos el rtt mas alto (candidato)
            candidato = rtts[-1]
            # recorre los nodos y verifica si son outliers
            i = 0
            while i < len(self.route) and self.route[i]['ip'] != candidato[0]:
                i += 1
            if i < len(self.route):
                value = abs(self.route[i]['rtt_salto'] - promedio) / std
                if value > LISTA_TAU[len(rtts)]:
                    if self.route[i]['ttl'] != '1':
                        self.route[i]['es_salto'] = True
                    rtts.pop()
                    hay_outlier = True

        # muestra resultados en pantalla
        self.mostrarVistaResultado()

def promediarRtts(lista):
    listaOrdenada = np.sort(np.array(lista))
    listaOrdenada = np.delete(listaOrdenada, [0, listaOrdenada.shape[0]-1])
    return np.mean(listaOrdenada)

if os.geteuid() != 0:
    print "Correlo con root chabon!"
    exit(1)

def main():
    if len(sys.argv) < 2:
        print "-----TRACEROUTE-----"
        print "Modos:"
        print "1 -> Capturar:"
        print "    Parametros:"
        print "        1. Host"
        print "        2. Nombre de salida"
        print "2 -> Usar archivo de entrada y calcular outliers"
        print "        1. Archivo de entrada"
        print ""
        print "Recordar correr con permisos root."
        print ""
        print "Ejemplos:"
        print "   Iniciar un traceroute:"
        print "     sudo python traceroute.py 1 cambridge.ac.uk cambridge"
        print "   Buscar saltos intercontinentales en una ruta previamente calculada:"
        print "     sudo python traceroute.py 2 cambridge.csv"
        return

    if sys.argv[1] == '1':
        if len(sys.argv) > 3:
            host = sys.argv[2]
            namefile = sys.argv[3]
        else:
            host = raw_input("Pone la ip/url: ")
            namefile = raw_input("Pone el nombre del archivo de salida de logs: ")
        tr = traceroute(host, namefile)
        tr.iniciar()
        tr.buscarIps()
    else:
        if len(sys.argv) > 2:
            namefile = sys.argv[2]
        else:
            namefile = raw_input("Pone el nombre del archivo de entrada: ")
        tr = traceroute('', '')
        tr.estadoDesdeCsv(namefile)
        tr.calcularOutliers()

main()
