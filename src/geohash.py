#! /usr/bin/env python

from __future__ import print_function

from sys import version_info, exit
import os
import hashlib
import re
from numbers import Number

import time
import datetime
import argparse
import json
import webbrowser
    

if version_info[0] == 3:
    from urllib.request import urlopen
    from urllib.parse import quote
    basestring = str
    raw_input = input
else:
    from urllib import urlopen, quote

pyinput = lambda x: eval(raw_input(x), {}, {})

GEO_ROOT = os.path.join(os.getenv("RED_SPIDER_ROOT"), "work", "geohash")
DEFAULTS_FILE = os.path.join(GEO_ROOT, "defaults")
CACHE_FILE = os.path.join(GEO_ROOT, "cache")
URL_DOW = r"http://geo.crox.net/djia/{year:d}/{month:02d}/{day:02d}"
MAPS = "https://maps.google.com/maps?q={:f},{:f}"
MAPS_LOOKUP = "https://maps.google.com/maps?q={}"

def geohash(latitude, longitude, datedow):
    '''Compute geohash() using the Munroe algorithm.

    >>> geohash(37.421542, -122.085589, b'2005-05-26-10458.68')
    37.857713 -122.544543

    '''
    # http://xkcd.com/426/
    # adapted from antigravity.py
    datedow = datedow.encode("utf-8")
    h = hashlib.md5(datedow).hexdigest()
    p, q = [('%f' % float.fromhex('0.' + x)) for x in (h[:16], h[16:32])]
    return [float("{}{}".format(int(x), y[1:])) for x, y in ((latitude, p), (longitude, q))]

def memoize_to_disk(filename, invalid=set()):
    def decorator(func):
        try:
            with open(filename, "r") as fp:
                cache = json.load(fp)
        except (IOError, ValueError):
            cache = {}
            
        def memoize(*args):
            chk = str(args)
            if chk not in cache:
                ret = func(*args)
                if not ret in invalid:
                    cache[chk] = ret
                    with open(filename, "w") as fp:
                        json.dump(cache, fp)
                return ret
            else:
                return cache[chk]
        return memoize
    return decorator
    
def parse_date(date):
    datefract = re.findall("\d+|\w+", date)
    fid = len(datefract) - 1
    formats =  (
                ("%d",),
                ("%d-{m}","%b-%d", "%B-%d"),
                ("%x", "%Y-{m}-%d","%d-{m}-%Y", "{m}-%d-%Y")
    )
    # deal with date delimiters
    check_date = "-".join(datefract)
    months = {"%m", "%b", "%B"}
    for check_format in formats[fid]:
        for month in months if fid else {None}:
            try:
                date = list(time.strptime(check_date, check_format.format(m=month)))[:3]
                if fid < 2:
                    cur = time.localtime()
                    date[0] = cur.tm_year
                    if not month:
                        date[1] = cur.tm_mon
                return date[:3]
            except:
                pass
    else:
        raise ValueError("Invalid date format.")

def store_defaults(args, filepath):
    if not os.path.exists(os.path.split(filepath)[0]):
        os.makedirs(os.path.split(filepath)[0])
    with open(filepath, "w") as fp:
        json.dump(args.__dict__, fp)

def set_defaults(args, filepath):
    if os.path.exists(filepath) and os.path.isfile(filepath):
        with open(filepath, "r") as fp:
            defaults = json.load(fp)
        for key, value in defaults.items():
            if key in args.__dict__:
                chk = getattr(args, key)
                if not chk and chk != value:
                    puts("Default {} = {}".format( key, value ))
                    setattr(args, key, value)

def make_datedow(date, dow):
    date = time.strftime("%Y-%m-%d", date)
    if isinstance(dow, basestring):
        dow = float(dow)
    return "{}-{:.2f}".format(date, dow)

def get_date_of_dow(date, coords):
    date = datetime.date(*date[:3])
    if 0 > coords[1] > -30:
        date -= datetime.timedelta(days=1)
    wkday = date.weekday()
    if wkday > 4:
        date -= datetime.timedelta(wkday - 4)
    date = tuple(date.timetuple())
    return date

@memoize_to_disk(CACHE_FILE, invalid={None,})
def get_dow(date):
    request = URL_DOW.format(year=date[0], month=date[1], day=date[2])
    req = urlopen(request)
    page = req.read().decode("utf-8")
    req.close()
    if page == u"error\ndata not available yet":
        puts("DJIA for this date is not available (yet?)")
        return
    dow = float(page)
    return dow

def get_location_coords(gen_location):
    webbrowser.open(MAPS_LOOKUP.format( quote(gen_location) ))
    puts("`exit()` to abort.")
    prompt = "{: <9} >>> "
    coords = []
    for req in ("LATITUDE", "LONGITUDE"):
        while True:
            try:
                x = pyinput( prompt.format(req) )
                if isinstance(x, Number):
                    break
            except Exception as exc:
                pass
        coords += [x]
    return coords

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a geohash based on the Munroe Algorithm.")
    parser.add_argument("-ll", dest="location", 
                        metavar=("LATITUDE", "LONGITUDE"),nargs=2,
                        default=None, type=float, help="Coordinates to complement the geohashing algorithm")
    parser.add_argument("-l", dest="gen_location", metavar=("LOCATION"),
                        default="", nargs="*", help="Look up a locations coordinates in google.maps")
    parser.add_argument("-t", dest="date", metavar=("DATE"), 
                        default=None, help="Date for which the geohash is valid")
    parser.add_argument("-d", dest="dow", metavar=("DJIA"), 
                        default=None, help="Dow Jones Industrial Average required for hashing")
    parser.add_argument("-s", "--store-defaults", action="store_true",
                        help="Save the supplied command line arguments as defaults")
    parser.add_argument("-n", "--no-defaults", action="store_true",
                        help="Ignore default command line arguments")
    parser.add_argument("-cc", "--clear-cache", action="store_true",
                        help="Empty the DJIA cache")
    parser.add_argument("-m", "--maps", action="store_true",
                        help="Show the geohash coordinates in google.maps")
    parser.add_argument("-j", "--json", action="store_true",
                        help="Write geohash coordinates to stdout as json array")

    args = parser.parse_args()
    flag_location = True if type(args.gen_location) is list else False
    args.gen_location = " ".join(args.gen_location)
    puts = (lambda *x:None) if args.json else print

    if not os.path.exists(GEO_ROOT):
        os.makedirs(GEO_ROOT)
    
    if args.clear_cache:
        try:
            os.remove(CACHE_FILE)
        except OSError:
            pass
        exit()

    if args.no_defaults:
        del args.no_defaults
    else:
        set_defaults(args, DEFAULTS_FILE)
        
    if args.store_defaults:
        del args.store_defaults
        store_defaults(args, DEFAULTS_FILE)

    if not (args.location or args.json) and flag_location:
        args.location = get_location_coords(args.gen_location)
    
    if args.location:
        assert len(args.location) == 2
        date = parse_date(args.date) if args.date else time.localtime()
        date_of_dow = get_date_of_dow(date, args.location)
        datedow = None
    
        if not args.dow:
            puts("\nRetrieving DJIA..")
            args.dow = get_dow(date_of_dow)

        if args.dow:
            datedow = make_datedow(date_of_dow, args.dow)
            
            puts()
            puts("Input: {}".format(datedow))
            unpack = args.location + [datedow]
            geo_location = geohash(*unpack)
            puts("Output: {}, {}".format(*geo_location))
            if args.json:
                print(json.dumps(geo_location))
            if args.maps:
                webbrowser.open(MAPS.format(*geo_location))
