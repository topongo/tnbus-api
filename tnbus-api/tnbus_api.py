import json
import requests
from unicodedata import normalize as u_normalize, combining as u_combining
from datetime import datetime, time, timedelta
from pytz import timezone
from datetime import datetime, timedelta
from geopy.distance import geodesic


def remove_accents(inp):
    return u"".join((c for c in u_normalize("NFKD", inp) if not u_combining(c)))


def tz_dt_fromisoformat(string):
    tz = timezone("utc")
    return tz.localize(datetime.fromisoformat(string.replace("Z", "")))


def tz_t_fromisoformat(string):
    tz = timezone("utc")
    return tz.localize(datetime.combine(datetime.today(), time.fromisoformat(string.replace("Z", "")))).time()


class By:
    # must refer to an int
    class ID:
        pass

    class ID_NUM:
        # specific for Stop, since trips use numeric IDs
        pass

    class DIRECTION:
        pass

    # must refer to a str
    class NAME:
        pass

    class NAME_MATCH:
        pass

    class CODE:
        pass

    # must refer to a str or a int
    class TYPE:
        pass

    # must refer to a TNBus.*
    class ROUTE:
        pass

    class STOP:
        pass

    class AREA:
        pass

    class TRIP:
        pass

    # must refer to a datetime
    class MAX_DATE:
        pass

    class MIN_DATE:
        pass

    class STATE:
        pass

    def string(self, _int):
        for _d in self.__dir__():
            if self.__getattribute__(_d) == _int:
                return f"By.{_d}"


class Cond:
    class OR:
        pass

    class AND:
        pass


class TNBus:
    def __init__(self, _api, preload=None, tz=None, initial_location=(46.074149, 11.121589)):
        self.api = _api
        self.areas = []
        self.news = []
        self.routes = []
        self.stops = []
        self.trips = []
        self.location = initial_location

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
        all stop dicts returned by API.stops are set to area 0
        this is an EXTERNAL bug, not fixable by me.
        So a separate call to API.routes is needed, even if API.stops returns stop info as well
        """

        for r in self.raw["routes"]:
            self.routes.append(self.Route(r, self.get_area(r["areaId"])))
            if type(self.routes[-1].news) is list:
                self.news += self.routes[-1].news

        for s in self.raw["stops"]:
            self.stops.append(self.Stop(s, self.location))
            for r in s["routes"]:
                _r = self.get(self.Route, (By.ID, r["routeId"]), (By.TYPE, r["type"]))
                self.stops[-1].routes.append(_r)
                _r.stops.add(self.stops[-1])
                self.stops[-1].areas.add(_r.area)
                if self.stops[-1].routes[-1] is None:
                    raise

        # self._reload_distances()
        # self._sort_by_distance()

        if preload:
            self.age = datetime.fromtimestamp(self.raw["age"])
        else:
            self.age = datetime.now()

    def get(self, t_, *filters: tuple[int, any], store_override=None, cond_mode=None, override_unique=False):
        cond_mode = Cond.AND if cond_mode is None else cond_mode
        for b_, _ in filters:
            if b_ not in t_.SEARCH_ASSOC:
                raise TypeError(f"Type {t_} doesn't support searches by {By.string(By(), b_)}")

        if store_override:
            store = store_override
        else:
            store = self.__getattribute__(t_.SEARCH_STORE)

        out = []
        if store:
            _iter = []
            for b_, v_ in filters:
                try:
                    # supports for generators
                    for _s in store:
                        if v_ in _s.__getattribute__(t_.SEARCH_ASSOC[b_]):
                            pass
                        _iter.append(True)
                        break
                except TypeError:
                    _iter.append(False)

            for _s in store:
                if cond_mode == Cond.AND:
                    add_ = True
                elif cond_mode == Cond.OR:
                    add_ = False
                else:
                    raise TypeError(cond_mode)
                for (b_, v_), i_ in zip(filters, _iter):
                    s_target = _s.__getattribute__(t_.SEARCH_ASSOC[b_])
                    if i_:
                        if b_ == By.NAME_MATCH:
                            if remove_accents(v_.lower()) not in \
                                    remove_accents(s_target.lower()):
                                if cond_mode == Cond.AND:
                                    add_ = False
                            else:
                                if cond_mode == Cond.OR:
                                    add_ = True
                        else:
                            if isinstance(v_, str):
                                v_ = remove_accents(v_).lower()
                                s_target = remove_accents(s_target).lower()
                            if v_ not in s_target:
                                if cond_mode == Cond.AND:
                                    add_ = False
                            else:
                                if cond_mode == Cond.OR:
                                    add_ = True
                    else:
                        if v_ != s_target:
                            if cond_mode == Cond.AND:
                                add_ = False
                        else:
                            if cond_mode == Cond.OR:
                                add_ = True

                    if (cond_mode == Cond.OR and add_ is True) or (cond_mode == Cond.AND and add_ is False):
                        break

                if add_:
                    out.append(_s)
                    if not override_unique and By.ID in (_f[0] for _f in filters):
                        break

        if not override_unique and By.ID in (_f[0] for _f in filters):
            if len(out) == 1:
                return out[0]
            elif len(out) == 0:
                return
            else:
                raise Exception(out)

        return out

    def _reload_distances(self):
        # n = datetime.now()
        # print(f"start distances reloading {n}")
        for _i in self.stops:
            _i.reload_distance(self.location)
        # print(f"end distances reloading {datetime.now()} ({(datetime.now()-n).total_seconds()})")

    def _sort_by_distance(self):
        # n = datetime.now()
        # print(f"start distances sorting {n}")
        self.stops.sort(key=lambda l: l.distance)
        # print(f"end distances sorting {datetime.now()} ({(datetime.now()-n).total_seconds()})")

    def nearest_stops(self, num=10, location=None):
        if location:
            self.update_location(location)
        for _s, _ in zip(self.stops, range(num)):
            yield _s

    def nearest_stop(self):
        return self.stops[0]

    def update_location(self, location: tuple[float, float]):
        self.location = location
        self._reload_distances()
        self._sort_by_distance()

    def get_stop(self, value, by=By.ID):
        return self.get(self.Stop, (by, value))

    def get_route(self, value, by=By.ID):
        return self.get(self.Route, (by, value))

    def get_area(self, value, by=By.ID):
        return self.get(self.Area, (by, value))

    def load_trips(self, search, since, limit):
        if not isinstance(search, (TNBus.Stop, TNBus.Route)):
            raise TypeError(search)
        routes_ = {}
        out = []
        for i in self.api.trips_new(search, since, limit):
            if i["routeId"] in routes_:
                r = routes_[i["routeId"]]
            else:
                r = self.get(TNBus.Route, (By.ID, i["routeId"]))
                routes_[r.id] = r
            out.append(TNBus.Trip(i, r))
        return out

    def load_best_trip(self, search, since):
        res = self.load_trips(search=search, since=since, limit=1)
        best = None
        for i in res:
            if i.best:
                best = i
                break
        if not best:
            raise TypeError(res)
        return best

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

        def load_trips(self, since=datetime.now(), limit=1):
            return t.load_trips(self, since, limit)

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

        def __init__(self, data, location):
            self.routes = []
            self.areas = set()
            self.id = data["stopCode"]
            self.desc = data["stopDesc"]
            # id_numeric is UNRELIABLE!
            self.id_numeric = data["stopId"]
            self.level = data["stopLevel"]
            self.name = data["stopName"]
            self.street = data["street"]
            self.town = data["town"]
            self.type = data["type"]
            self.wheelchair_boarding = data["wheelchairBoarding"]

            self.location = (data["stopLat"], data["stopLon"])
            self.distance = geodesic(self.location, location).kilometers

            self.raw = data

        def reload_distance(self, location):
            self.distance = geodesic(self.location, location).kilometers

        def get_trip_stop(self, trip):
            if not isinstance(trip, TNBus.Trip):
                raise TypeError(trip)

            for i_ in trip.times:
                if i_.stop == self:
                    return i_

        def load_trips(self, since=datetime.now(), limit=1):
            return t.load_trips(self, since, limit)

        def __str__(self):
            return f"Stop(id={self.id},n_id={self.id_numeric},name=\"{self.name}\")"

        def __repr__(self):
            return self.__str__()

    class TripStopTime:
        def __init__(self, data, trip):
            self.arrival = tz_t_fromisoformat(data["arrivalTime"])
            self.departureTime = tz_t_fromisoformat(data["departureTime"])
            self.stop_id = data["stopId"]
            self.trip = trip
            self.type = data["type"]
            stop_res = t.get(TNBus.Stop, (By.ID_NUM, self.stop_id), (By.TYPE, self.type))
            if len(stop_res) > 1:
                raise TypeError(stop_res)
            self.stop = stop_res[0]

            self.raw = data

        def __str__(self):
            return f"TripStopTime(arrival={self.arrival}, stop={self.stop})"

        def __repr__(self):
            return str(self)

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
            if not isinstance(route, TNBus.Route):
                raise TypeError(f"\"route\" argument must be of type TNBus.Route, {type(route).__str__} given.")
            self.id = data["tripId"]
            self.cable_way = data["cableway"]
            self.best = data["corsaPiuVicinaADataRiferimento"]
            self.delay = data["delay"]
            self.direction = data["directionId"]
            self.signal = data["indiceCorsaInLista"]
            self.last_sync = tz_dt_fromisoformat(data["lastEventRecivedAt"][:-1]) if data["lastEventRecivedAt"] else None
            self.last_sequence_detection = data["lastSequenceDetection"]
            self.bus = TNBus.Bus(data["matricolaBus"])
            try:
                self.actual_arrive_time = tz_dt_fromisoformat(data["oraArrivoEffettivaAFermataSelezionata"])
            except TypeError:
                self.actual_arrive_time = None
            try:
                self.scheduled_arrive_time = tz_dt_fromisoformat(data["oraArrivoProgrammataAFermataSelezionata"])
            except TypeError:
                self.scheduled_arrive_time = None
            self.route = route
            self.times = [TNBus.TripStopTime(i, self) for i in data["stopTimes"]]
            self.last = None
            self.next = None
            for i in self.times:
                if i.stop_id == data["stopLast"]:
                    self.last = i.stop
                if i.stop_id == data["stopNext"]:
                    self.next = i.stop
            self.totale_corse_in_lista = data["totaleCorseInLista"]
            self.start = self.times[0].departureTime

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
            self.raw = data

        def __str__(self):
            return f"Trip(id={self.id}, route={self.route}, start={self.start})"

        def __repr__(self):
            return str(self)

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

    def trip(self, trip_id: str, ro=None):
        res = json.loads(self.query(f"trips/{trip_id}"))
        return TNBus.Trip(res, ro)

    def trips_new(self, search: (TNBus.Stop, TNBus.Route), time=None, limit=30):
        args = {
            "limit": limit,
            "type": search.type,
            "refDateTime": time.utcnow().isoformat() if isinstance(time, datetime) else None
        }
        if isinstance(search, TNBus.Stop):
            args["stopId"] = search.id_numeric
        elif isinstance(search, TNBus.Route):
            args["routeId"] = search.id
        else:
            raise TypeError(f"{search} is of type {type(search)}")
        return json.loads(self.query("trips_new", args))


if __name__ == "__main__":
    with open("auth") as f, open("data.json", "r") as d:
        t = TNBus(API(f.read().strip())) #preload=json.load(d))

    all_from_piazza_dante = t.get(
        TNBus.Route,
        (By.NAME_MATCH, "piazza dante"),
    )
    # all_from_piazza_dante = [
    #     Route(id=400, code="5", name="Piazza Dante P.Fiera Povo Oltrecastello"),
    #     Route(id=402, code="7", name="Canova Melta Piazza Dante Gocciadoro"),
    #     Route(id=404, code="8", name="Centochiavi Piazza Dante Mattarello"),
    #     Route(id=425, code="11", name="Piazza Dante Via Brennero Gardolo Spini"),
    #     Route(id=478, code="15", name="Piazza Dante Interporto Spini Di Gardolo"),
    #     Route(id=543, code="17", name="Piazza Dante Via Bolzano Lamar Lavis")]
    # ]

    all_from_piazza_dante_and_povo = t.get(
        TNBus.Route,
        (By.NAME_MATCH, "piazza dante"),
        (By.NAME_MATCH, "povo")
    )
    # all_from_piazza_dante_and_povo = [Route(id=400, code="5", name="Piazza Dante P.Fiera Povo Oltrecastello")]

    # update location (location of povo-2)
    t.update_location((46.067335, 11.150375))

    # 10 nearest stops to povo-2
    for s in t.nearest_stops():
        print(f"{s}\t({s.distance*1000} m)")

    # Stop(id=25055x,n_id=2833,name="Povo Polo Scientifico Ovest")	(1.6476881296745567 m)
    # Stop(id=25055z,n_id=2683,name="Povo Polo Scientifico Est")	(50.29170985610265 m)
    # Stop(id=25050-,n_id=2682,name="Povo Sommarive")	(194.37024374373823 m)
    # Stop(id=25045z,n_id=149,name="Povo Valoni")	(356.1446767245698 m)
    # Stop(id=25045x,n_id=150,name="Povo Valoni")	(359.6316843179319 m)
    # Stop(id=25030x,n_id=187,name="Povo Piazza Manci")	(360.8088787149164 m)
    # Stop(id=25030z,n_id=186,name="Povo Piazza Manci")	(369.59753214659287 m)
    # Stop(id=25025z,n_id=2490,name="Povo Pantè")	(371.8276192891713 m)
    # Stop(id=25010z,n_id=183,name="Povo Centro Civico")	(374.58365978618946 m)
    # Stop(id=25025x,n_id=2820,name="Povo Pantè")	(376.8569417384571 m)

    # getting the nearest stop to povo-2
    nearest_stop = t.nearest_stop()

    # print(t._fetch_trips(t.get_stop(nearest_stop.id), datetime.now().replace(month=11, day=19, hour=7).isoformat(), num=1))

