import json
import requests


class By:
    ID = 0
    NAME = 1
    ROUTE = 2
    STOP = 3

class TNBus:
    def __init__(self, _api):
        self.api = _api
        stops = self.api.stops()
        self.areas = []
        self.news = []

        areas_ids = []
        self.routes = []
        self.stops = []
        for s in stops:
            self.stops.append(TNBus.Stop(s))
            for r in s["routes"]:
                print(r)
                g_r = self.get_route(r["routeId"])
                g_a = self.get_area(r["areaId"])
                if g_r is None:
                    if g_a is None:
                        self.areas.append(self.Area(r["areaId"]))
                        _a = self.areas[-1]
                    else:
                        _a = g_a
                    self.routes.append(self.Route(r, _a))
                    _r = self.routes[-1]
                else:
                    _r = g_r

                if isinstance(self.routes[-1].news, dict):
                    self.news += self.routes[-1].news
                self.stops[-1].routes.append(_r)

        print(json.dumps(_api.trip_news(self.stops[50]), indent=4))

    def get(self, _type, value, by=By.ID):
        if _type is self.Stop:
            store = self.stops
        elif _type is self.Area:
            store = self.areas
        elif _type is self.Route:
            store = self.routes
        else:
            raise TypeError(f"Unrecognised type: {_type}")
        if by == By.ID:
            for _i in store:
                if _i.id == value:
                    return _i

    def get_stop(self, value, by=By.ID):
        return self.get(self.Stop, value, by)

    def get_route(self, value, by=By.ID):
        return self.get(self.Route, value, by)

    def get_area(self, value, by=By.ID):
        return self.get(self.Area, value, by)

    class Area:
        def __init__(self, _id):
            self.id = _id
            self.routes = []

        class New:
            def __init__(self, data, route, area):
                self.route = route
                self.area = area
                self.id_feed = data["idFeed"]
                self.agency_id = data["agencyId"]
                self.service_type = data["serviceType"]
                self.start_date = data["startDate"]
                self.end_date = data["endDate"]
                self.header = data["header"]
                self.details = data["details"]
                self.stop_id = data["stopId"]
                self.url = data["url"]
                self.routes = None
                self.raw = data

    class Route:
        def __init__(self, data, area):
            self.area = area
            self.area.routes.append(self)
            self.id = data["routeId"]
            self.news = [TNBus.Area.New(i, self, area) for i in data["news"]] if data["news"] is not None else None
            self.color = data["routeColor"]
            self.long_name = data["routeLongName"]
            self.short_name = data["routeShortName"]
            self.type = data["routeType"]
            # unknown usage of data at index "type"
            # self.type = data["type"]
            self.raw = data

    class Stop:
        def __init__(self, data):
            self.routes = []
            self.code = data["stopCode"]
            self.desc = data["stopDesc"]
            self.id = data["stopId"]
            self.lat = data["stopLat"]
            self.level = data["stopLevel"]
            self.lon = data["stopLon"]
            self.name = data["stopName"]
            self.street = data["street"]
            self.town = data["town"]
            self.type = data["type"]
            self.wheelchair_boarding = data["wheelchairBoarding"]

    class Trip:
        def __init__(self, data):
            self.id = data["tripId"]
            self.cableway = data["cableway"]
            self.best = data["corsaPiuVicinaADataRiferimento"]
            self.delay = data["delay"]
            self.direction = data["directionId"]
            self.signal = data["indiceCorsaInLista"]
            self.last_sync = data["lastEventRecivedAt"]
            self.last_sequence_detection = data["lastSequenceDetection"]
            self.bus = TNBus.Bus(data["matricolaBus"])
            self.ora_arrivo_effettiva_a_fermata_selezionata = data["oraArrivoEffettivaAFermataSelezionata"]
            self.ora_arrivo_programmata_a_fermata_selezionata = data["oraArrivoProgrammataAFermataSelezionata"]
            self.id = data["routeId"]
            self.last = data["stopLast"]
            self.next = data["stopNext"]
            self.times = data["stopTimes"]
            self.totale_corse_in_lista = data["totaleCorseInLista"]
            self.trip_flag = data["tripFlag"]
            self.trip_headsign = data["tripHeadsign"]
            self.type = data["type"]
            self.wheelchair_accessible = data["wheelchairAccessible"]

    class Bus:
        def __init__(self, _id):
            self.id = _id


class API:
    HEAD = {"Authorization": "Basic bWl0dG1vYmlsZTplY0dzcC5SSEIz"}
    URL = "https://app-tpl.tndigit.it/gtlservice"

    def __init__(self):
        pass

    def query(self, call, para=None):
        if para is None:
            para = {}
        return requests.get(f"{self.URL}/{call}",
                            params=para,
                            headers=self.HEAD
                            ).text

    def routes(self, areas=()):
        if not isinstance(areas, (tuple, list)):
            raise TypeError("argument areas must be tuple or list")
        return json.loads(self.query("routes", {"areas": ",".join(areas)} if areas else {}))

    def stops(self):
        return json.loads(self.query("stops"))

    def trip(self, trip: TNBus.Trip):
        return json.loads(self.query(f"trips/{trip.id}"))

    def trip_news(self, stop: TNBus.Stop, limit=30):
        return json.loads(self.query("trips_new", {"limit": limit, "stopId": stop.id, "type": stop.type}))


if __name__ == "__main__":
    t = TNBus(API())

    for i in t.routes:
        if i.short_name == "13":
            r = i
    for i in t.stops:
        if r.id in map(lambda l: l.id, i.routes):
            if "Fogazzaro" in i.name:
                print(t.api.trip_news(i)[0])
