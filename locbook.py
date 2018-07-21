# 3rd party javascripts
# https://github.com/Leaflet/Leaflet.heat
# https://github.com/perliedman/leaflet-realtime
# https://github.com/Leaflet/Leaflet

# 3rd party packages
# https://github.com/isagalaev/ijson
# https://github.com/frewsxcv/python-geojson

# 3rd party packages
import geojson as gj
import ijson.backends.yajl2_cffi as ijson 

# Standard packages
import time
import datetime
import pickle
import logging
import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler

parser = argparse.ArgumentParser()
parser.add_argument("--import_google", "-i", help='Import Google location history JSON file and quit')
parser.add_argument("--export_geojson", "-e", help='Export location history as GeoJSON file and quit')
parser.add_argument("--port", "-p", help='Port to listen on for Owntracks POST requests, default 9001', default=9001)
parser.add_argument("--logfile", "-l", help='If specified, log to file, otherwise log to terminal')
args = parser.parse_args()

history = dict()

# Defaults
js_filename = 'map.js'
history_filename = 'history.pickle'
geojson_filename = 'realtime.geojson'
precision = 4 # Only 4 or 5 make sense for phone data
blur = 5
port = args.port

# Only log to file if argument is present
logging.basicConfig(filename=args.logfile, level=logging.DEBUG, format='%(asctime)s %(message)s') 

class RequestHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        request_headers = self.headers
        content_length = int(request_headers['Content-Length'])
        parse_msg(self.rfile.read(content_length))
        self.send_response(200)
        self.end_headers() 

    def log_message(self, format, *args):
        # We don't need http.server to run its own log
        return 

def load_history():
    global history
    # Load history from pickle file
    logging.info('Loading history from ' + history_filename)
    try: 
        history = pickle.load(open(history_filename, 'rb'))
        logging.info('History size: ' + str(len(history)) + ' points')   
    except FileNotFoundError:
        logging.info('History not found, creating new file ' + history_filename)
        pass
     
def parse_msg(msg):
    data = json.loads(msg.decode("utf-8"))
    if (data['_type'] == 'location'):

        lon = round(data['lon'], precision)
        lat = round(data['lat'], precision)

        p = (lon, lat)
        d,t = tst_to_dt(data['tst'])
        make_history(p, d, t, True)

        logging.info('Location update from device ' + data['tid'] + ': ' + json.dumps(data))
        write_js()
        popup_content = 'Device: ' + data['tid'] + '<br>Date: ' + d + '<br>Time: ' + t
        write_geojson(p, popup_content, geojson_filename)

def make_history(p, d, t, sour):
    global history
    # Defaultdict of defaultdicts
    if p in history:
        if d in history[p]:
            history[p][d].append(t)
        else:
            history[p][d] = [t]
    else:
        history[p] = dict()
        history[p][d] = [t]

    if (sour):
        pickle.dump(history, open('history.pickle', 'wb'))

def export_geojson(filename):
    global history
    logging.info('Exporting to ' + filename)
    with open(filename, 'w') as f:
        features = list()
        for p,dt in history.items():
            properties = dict()
            for d,t in dt.items(): properties[d] = t
            features.append(gj.Feature(geometry=gj.Point(p), properties=properties))
        f.write(gj.dumps(gj.FeatureCollection(features)))
    f.close()

def write_geojson(p, popup_content, filename):
    with open(filename, 'w') as f:
        properties = {'popupContent': popup_content}
        features = [gj.Feature(geometry=gj.Point(p), properties=properties)]
        f.write(gj.dumps(gj.FeatureCollection(features)))
    f.close()

def import_google(filename):
    logging.info('Importing from ' + filename)
    # Needs to be rb!
    with open(filename, 'rb') as f:
        data = ijson.items(f, 'locations.item')
        c=0
        for o in data:
            c+=1
            p = (round(o['longitudeE7']/10000000, precision), round(o['latitudeE7']/10000000, precision))
            d, t = tst_to_dt(int(o['timestampMs'][:-3]))
            make_history(p, d, t, False)
    f.close()
    logging.info(str(c) + ' items imported from ' + filename)
    logging.info('History size: ' + str(len(history)) + ' points')
    pickle.dump(history, open('history.pickle', 'wb'))
    write_js()

def tst_to_dt(tst):
    d = datetime.datetime.fromtimestamp(tst).strftime('%Y-%m-%d')
    t = datetime.datetime.fromtimestamp(tst).strftime('%H-%M-%S')
    return d, t

def prec_to_m(prec):
    # https://en.wikipedia.org/wiki/Decimal_degrees
    return(111320) / (10**prec)

def write_js():
    global history
    logging.info('Updating .js file')
    with open(js_filename, 'w') as f:
        f.write('var points = [')
        first = True
        for p,dt in history.items():
            v = 0
            for d,t in dt.items():
                v += len(t)
            if (first):
                pv_string = '[' + str(p[1]) + ',' + str(p[0]) + ',' + str(v) + ']'
                first = False
            else:
                pv_string = ',[' + str(p[1]) + ',' + str(p[0]) + ',' + str(v) + ']'
            f.write(pv_string)
        f.write('];')
        f.write('config = {radius: ' + str(prec_to_m(precision)) + ',blur:' + str(blur) + '};')
    f.close()

def main():
    server = HTTPServer(('', port), RequestHandler)
    server.serve_forever() # Run the HTTP server

if __name__ == "__main__":
    load_history()
    if (args.import_google): import_google(args.import_google)
    if (args.export_geojson): export_geojson(args.export_geojson)
    # Running the import or export function quits the program afterwards
    if (not args.import_google and not args.export_geojson): main()