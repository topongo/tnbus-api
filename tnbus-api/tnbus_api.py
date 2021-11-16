import json
import requests
from unicodedata import normalize as u_normalize, combining as u_combining
from datetime import datetime


def remove_accents(inp):
    return u"".join((c for c in u_normalize("NFKD", inp) if not u_combining(c)))


class By:
    # must refer to an int
    ID = 0
    DIRECTION = 7

    # must refer to a str
    NAME = 1
    NAME_MATCH = 2

    # must refer to a str or a int
    TYPE = 6

    # must refer to a TNBus.*
    ROUTE = 3
    STOP = 4
    AREA = 5
    TRIP = 8

    # must refer to a datetime
    MAX_DATE = 9
    MIN_DATE = 10
    STATE = 11

    def string(self, _int):
        for _d in self.__dir__():
            if self.__getattribute__(_d) == _int:
                return f"By.{_d}"


class TNBus:
    def __init__(self, _api, preload=None):
        self.api = _api
        self.areas = []
        self.news = []
        self.routes = []
        self.stops = []

        if not preload:
            self.raw = {
                "areas": self.api.areas(),
                "routes": self.api.routes(),
                "stops": self.api.stops(),
                "trips": []
            }
        else:
            self.raw = preload

        for a in self.raw["areas"]:
            if self.get_area(a["areaId"]) is None:
                self.areas.append(self.Area(a))

        # API.areas() doesn't return area n. 8, area of cable ways (only one actually)
        self.areas.append(self.Area({"areaId": 8, "areaDesc": "Funivie", "type": "E"}))

        """
        # all stop dicts returned by API.stops are set to area 0
        # this is an EXTERNAL bug, not fixable by me.
        # So a separate call to API.routes is needed, even if API.stops returns stop info as well
        """

        for r in self.raw["routes"]:
            self.routes.append(self.Route(r, self.get_area(r["areaId"])))
            if type(self.routes[-1].news) is list:
                self.news += self.routes[-1].news

        for s in self.raw["stops"]:
            self.stops.append(self.Stop(s))
            for r in s["routes"]:
                _r = self.get(self.Route, {By.ID: r["routeId"], By.TYPE: r["type"]})
                self.stops[-1].routes.append(_r)
                _r.stops.add(self.stops[-1])
                self.stops[-1].areas.add(_r.area)
                if self.stops[-1].routes[-1] is None:
                    raise

        if preload:
            self.age = datetime.fromtimestamp(self.raw["age"])
        else:
            self.age = datetime.now()

    def get(self, t_, filters: dict[int, any]):
        for _b in filters:
            if _b not in t_.SEARCH_ASSOC:
                raise TypeError(f"Type {t_} doesn't support searches by {By.string(By(), _b)}")

        store = self.__getattribute__(t_.SEARCH_STORE)

        out = []
        if store:
            _iter = []
            for _b, _v in filters.items():
                try:
                    if _v in store[0].__getattribute__(t_.SEARCH_ASSOC[_b]):
                        pass
                    _iter.append(True)
                except TypeError:
                    _iter.append(False)

            for _s in store:
                _add = True
                for (_b, _v), _i in zip(filters.items(), _iter):
                    s_target = _s.__getattribute__(t_.SEARCH_ASSOC[_b])
                    if _i:
                        if _b == By.NAME_MATCH:
                            if remove_accents(_v.lower()) not in \
                                    remove_accents(s_target.lower()):
                                _add = False
                        else:
                            if _v not in s_target:
                                _add = False
                    else:
                        if _v != s_target:
                            _add = False
                if _add:
                    out.append(_s)

        if By.ID in filters:
            if len(out) == 1:
                return out[0]
            elif len(out) == 0:
                return
            else:
                raise Exception(out)

        return out

    def get_stop(self, value, by=By.ID):
        return self.get(self.Stop, {by: value})

    def get_route(self, value, by=By.ID):
        return self.get(self.Route, {by: value})

    def get_area(self, value, by=By.ID):
        return self.get(self.Area, {by: value})

    def _load_trip(self, trip_id: str):
        pass

    def dump(self, f_hand):
        self.raw["age"] = self.age.timestamp()
        json.dump(self.raw, f_hand)

    class Area:
        SEARCH_ASSOC = {
            By.ID: "id",
            By.NAME: "desc",
            By.NAME_MATCH: "desc",
            By.ROUTE: "routes",
            By.AREA: "",
            By.TYPE: "type"
        }
        SEARCH_STORE = "areas"

        def __init__(self, data):
            self.id = data["areaId"]
            self.desc = data["areaDesc"]
            self.type = data["type"]
            self.routes = []
            self.stops = []
            self.raw = data

        def __str__(self):
            return f"Area(id={self.id},desc=\"{self.desc}\",type={self.type})"

        def __repr__(self):
            return self.__str__()

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
        SEARCH_ASSOC = {
            By.ID: "id",
            By.NAME: "short_name",
            By.NAME_MATCH: "short_name",
            By.ROUTE: "",
            By.AREA: "area",
            By.STOP: "stops",
            By.TYPE: "type",
            By.TRIP: "trips"
        }
        SEARCH_STORE = "routes"
        SEARCH_TRIPS_UPDATED = "trips_load"

        TRAIN = 2
        BUS = 3
        CABLEWAY = 5

        def __init__(self, data, area):
            self.area = area
            self.area.routes.append(self)
            self.stops = set()
            self.id = data["routeId"]
            self.news = [TNBus.Area.New(i, self, area) for i in data["news"]] if data["news"] is not None else None
            self.color = data["routeColor"]
            self.long_name = data["routeLongName"]
            self.short_name = data["routeShortName"]
            self.type = data["type"]
            self.urban = True if data["routeType"] == "U" else False

            self.trips = []
            self.trips_load = datetime.fromtimestamp(0)

            self.raw = data

        def __str__(self):
            return f"Route(id={self.id},code=\"{self.short_name}\",name=\"{self.long_name}\")"

        def __repr__(self):
            return self.__str__()

    class Stop:
        SEARCH_ASSOC = {
            By.ID: "id",
            By.NAME: "name",
            By.NAME_MATCH: "name",
            By.ROUTE: "routes",
            By.AREA: "areas",
            By.TYPE: "type",
            By.TRIP: "trips"
        }
        SEARCH_STORE = "stops"
        SEARCH_TRIPS_UPDATED = "trips_load"

        def __init__(self, data):
            self.routes = []
            self.areas = set()
            self.id = data["stopCode"]
            self.desc = data["stopDesc"]
            # id_numeric is UNRELAIABLE!
            self.id_numeric = data["stopId"]
            self.lat = data["stopLat"]
            self.level = data["stopLevel"]
            self.lon = data["stopLon"]
            self.name = data["stopName"]
            self.street = data["street"]
            self.town = data["town"]
            self.type = data["type"]
            self.wheelchair_boarding = data["wheelchairBoarding"]

            self.trips = []
            self.trips_load = datetime.fromtimestamp(0)

            self.raw = data

        def __str__(self):
            return f"Stop(id={self.id},n_id={self.id_numeric},name=\"{self.name}\")"

        def __repr__(self):
            return self.__str__()

    class TripStopTime:
        def __init__(self, data):
            pass

    class Trip:
        SEARCH_ASSOC = {
            By.ROUTE: "routes",
            By.STOP: "stops",
            # search trip by id is very limiting!
            By.ID: "id",
            By.TRIP: "",
            By.DIRECTION: "direction",
            By.MAX_DATE: "actual_arrive_time",
            By.MIN_DATE: "",
            By.STATE: ""
        }

        NOT_DEPARTED = 0
        DEPARTED = 1
        ARRIVED = 2

        def __init__(self, data, route):
            # if not isinstance(route, TNBus.Route):
            #    raise TypeError(f"\"route\" argument must be of type TNBus.Route, {type(route).__str__} given.")
            self.id = data["tripId"]
            self.cable_way = data["cableway"]
            self.best = data["corsaPiuVicinaADataRiferimento"]
            self.delay = data["delay"]
            self.direction = data["directionId"]
            self.signal = data["indiceCorsaInLista"]
            self.last_sync = data["lastEventRecivedAt"]
            self.last_sequence_detection = data["lastSequenceDetection"]
            self.bus = TNBus.Bus(data["matricolaBus"])
            self.actual_arrive_time = datetime.fromtimestamp(data["oraArrivoEffettivaAFermataSelezionata"])
            self.scheduled_arrive_time = datetime.fromtimestamp(data["oraArrivoProgrammataAFermataSelezionata"])
            self.route = route
            self.last = None if data["stopLast"] == 0 else route.get(data["stopLast"])
            self.next = data["stopNext"]
            self.times = data["stopTimes"]
            self.totale_corse_in_lista = data["totaleCorseInLista"]

            # TODO: finish compiling this case
            if data["tripFlag"] == "TRIP_FLAG__MID":
                self.state = self.DEPARTED
            elif data["tripFlag"] == "":
                self.state = self.ARRIVED
            else:
                self.state = self.NOT_DEPARTED
            self.trip_headsign = data["tripHeadsign"]
            self.type = data["type"]
            self.wheelchair_accessible = data["wheelchairAccessible"]

        # def __str__(self):
        #    return f"Route \"{self.short_name}\" - {self.long_name}"

    class Bus:
        def __init__(self, _id):
            self.id = _id


class API:
    URL = "https://app-tpl.tndigit.it/gtlservice"

    def __init__(self, key, preload=None):
        self.auth = {"Authorization": f"Basic {key}"}

    def query(self, call, para=None):
        if para is None:
            para = {}
        return requests.get(f"{self.URL}/{call}",
                            params=para,
                            headers=self.auth
                            ).text

    def routes(self, areas=None):
        if areas is not None:
            areas = ",".join(areas)
        return json.loads(self.query("routes", {"areas": areas}))

    def stops(self, areas=None):
        if areas is not None:
            areas = ",".join(areas)
        return json.loads(self.query("stops", {"areas": areas}))

    def areas(self):
        return json.loads(self.query("areas"))

    def trip(self, trip: str):
        return json.loads(self.query(f"trips/{trip}"))

    def trips_new(self, search: (TNBus.Stop, TNBus.Route), time=None, limit=30):
        args = {
            "limit": limit,
            "type": search.type,
            "refDateTime": time.isoformat() if isinstance(time, datetime) else None
        }
        if isinstance(search, TNBus.Stop):
            args["stopId"] = search.id_numeric
        elif isinstance(search, TNBus.Route):
            args["routeId"] = search.id
        else:
            raise TypeError(f"{search} is of type {type(search)}")
        return json.loads(self.query("trips_new", args))


if __name__ == "__main__":
    with open("auth") as f, open("data.json") as d:
        t = TNBus(API(f.read().strip()), preload=json.load(d))

    print(t.api.trip_news(t.get(
        TNBus.Route,
        {
            By.STOP: t.get(TNBus.Stop, {By.NAME_MATCH: "povo sale"})[0],
            By.NAME_MATCH: "5"
        }
    )[0]))
