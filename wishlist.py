#!/usr/bin/env python3

from pprint import pprint
import bonobo
import bonobo_sqlalchemy
from bonobo.config import use, use_context, use_raw_input, use_context_processor
from bonobo.constants import NOT_MODIFIED
from os import listdir
from os.path import isfile, join

from sqlalchemy import create_engine

import logging
import mondrian

from copy import copy

import util

# One line setup (excepthook=True tells mondrian to handle uncaught exceptions)
mondrian.setup(excepthook=True)

# Use logging, as usual.
logger = logging.getLogger("mtg")
logger.setLevel(logging.DEBUG)

import random

CACHE_TIME = 14 + (random.randint(0, 14))
logger.warning("Caching for %d days" % CACHE_TIME)

import requests as req
from cachecontrol import CacheControl, CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.heuristics import ExpiresAfter
from cachecontrol.heuristics import LastModified

CACHE = FileCache(".web_cache")
requests = CacheControl(req.Session(),
                        cache=CACHE,
                        heuristic=ExpiresAfter(days=CACHE_TIME))

EXCLUDED_SETS = (
    "XLN",
    "RIX",
    "M19",
    "DOM",
    #    "RNA",
    #    "GRN",
    #    "WAR",
)

EXTRA_SETS = (
    #    "GK1",
    #    "GK2",
    #"UMA",
    #    "BFZ",
    #    "OGW",
    #    "SOI",
    # "AKH",
    # "AER",
    # "UST",
    # "HOU",
    # "JOU",
    # "BNG",
    # "GTC",
    # "RTR",
    "MH1",
    "M20",
)

INVENTORY = {'': {}}


def _inventory(foo, bar):
    yield INVENTORY


# Count,Tradelist Count,Name,Edition,Card Number,Condition,Language,Foil,Signed,Artist Proof,Altered Art,Misprint,Promo,Textless,My Price
@use_context_processor(_inventory)
def inventory(_inventory, count, tradelist, name, edition, number, condition,
              language, foil, *card):

    # edition = card.get('Edition')
    # name = card.get('Name')
    # foil = card.get('Foil')

    # Skip Foils
    if foil:
        return

    if edition not in _inventory:
        _inventory[edition] = {}

    if name not in _inventory[edition]:
        _inventory[edition][name] = 0

    _inventory[edition][name] += int(count)
    _inventory[''][name] = _inventory[''].get(name, 0) + int(count)

    yield NOT_MODIFIED


@use("http")
def get_cards(http):
    # sets = http.get("https://mtgjson.com/json/AllSets.json").json()

    sets = {}

    sets.update(http.get("https://mtgjson.com/json/Standard.json").json())

    for excluded_set in EXCLUDED_SETS:
        sets.pop(excluded_set, None)

    for extra_set in EXTRA_SETS:
        set_url = "https://mtgjson.com/json/%s.json" % extra_set
        info = http.get(set_url).json()
        sets.update({extra_set: info})

    set_map = {}
    for set_info in http.get("https://mtgjson.com/json/SetList.json").json():
        set_map[set_info["code"]] = [set_info["name"], set_info["type"]]

    for wanted_set in WANTS:
        for wanted_card in WANTS[wanted_set]:
            wanted_count = WANTS[wanted_set][wanted_card]["count"]
            wanted_number = WANTS[wanted_set][wanted_card]["number"]

            yield {
                "edition_name":
                WANTS[wanted_set][wanted_card]["wanted_edition"],
                "edition": WANTS[wanted_set][wanted_card]["wanted_edition"],
                "name": wanted_card,
                "wanted_count": wanted_count,
                "set_type": "wanted",
                "rarity": "wanted",
                "number": "",
            }

    for set_code, set_data in sets.items():
        print("Finding cards out of %s [%s]" %
              (set_code, set_map[set_code][0]))
        set_info = set_map.get(set_code)
        if not set_info:
            print("XXX: Can't find setinfo for %s %s" %
                  (set_code, card["name"]))
            continue

        # for token in set_data.get("tokens"):
        for card in set_data.get("cards"):
            card["edition"] = set_code
            card["edition_name"] = set_map.get(set_code)[0]
            card["set_type"] = set_map.get(set_code)[1]

            yield card


WANTS = {}


def load_wants():
    import csv

    with open("wants.csv") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # pprint(row)
            edition = row["Edition"]
            name = row["Name"]
            count = row["Count"]
            if edition not in WANTS:
                WANTS[edition] = {}

            if name not in WANTS[edition]:
                WANTS[edition][name] = {
                    "count": 0,
                    "number": row["Card Number"],
                    "wanted_edition": edition,
                }

            WANTS[edition][name]["count"] += int(count)


@use_context_processor(_inventory)
def wishlist_map(_inventory, card):
    # Count,Name,Edition,Card Number,Condition,Language,Foil,Signed,Artist Proof,Altered Art,Misprint,Promo,Textless
    name = card["name"]
    edition = util.edition_to_deckbox(card["edition_name"])
    set_type = card["set_type"]

    trace = False
    if card['name'] == 'XXX':
        print("Found %s" % name)
        trace = True

    want = 4

    # Skip Basic Lands
    if "supertypes" in card and "Basic" in card["supertypes"]:
        return

    # Skip Starter Decks
    isStarter = False
    if "isStarter" in card and card["isStarter"]:
        return

    isStandard = False
    if "legalities" in card and card["legalities"].get("standard") == "Legal":
        isStandard = True

    if card["number"].endswith("★"):
        return

    set_exclusions = [
        "FBB",
        "ME1",
        "ME2",
        "ME3",
        "ME4",
        "SUM",
        "VMA",
        "TPR",
        # Not released yet, wish we could tell
        "MH1",
        # Too Expsnsive!
        "LEA",
        "LEB",
        "2ED",
        "3ED",
        "LEG",
        "ARN",
        "ATQ",
    ]

    if card["edition"] in set_exclusions:
        return

    if trace:
        print("Edition OK")

    type_exclusions = [
        "memorabilia",
        "promo",
        "starter",
        "vanguard",
        "duel_deck",
        #"box",
        "funny",
        "archenemy",
        "planechase",
        "masterpiece",
        "treasure_chest",
        "token",
    ]

    if trace:
        print("Set type %s" % set_type)

    if set_type in type_exclusions:
        return

    if trace:
        print("Set Type OK")
    # XXX Refactor plz

    if "names" in card and len(card["names"]) > 0:
        if name != card["names"][0]:
            return
        if card["layout"] == "split" or card["layout"] == "aftermath":
            name = " // ".join(card["names"])

    have_count = 0
    if edition in _inventory:
        if name in _inventory[edition]:
            have_count = _inventory[edition][name]

    # handle things we want more than 4 of, mostly stuff in our decks
    # XXX

    if card.get("wanted_count", 0) > 0:
        want = card["wanted_count"]

    if have_count < want:
        want -= have_count

        yield {
            "Count": want,
            "Name": name,
            "Edition": edition,
            "Card Number": card["number"],
            "Condition": None,
            "Language": "English",
            "Foil": None,
            "Signed": None,
            "Artist Proof": None,
            "Altered Art": None,
            "Misprint": None,
            "Promo": None,
            "Textless": None,
        }


def get_inventory_graph(**options):
    """
    This function builds the graph that needs to be executed.

    :return: bonobo.Graph

    """
    graph = bonobo.Graph()

    graph.add_chain(
        bonobo.CsvReader("Deckbox-inventory.csv"),
        bonobo.Filter(lambda *args: args[-1] != 'English'),
        inventory,
        bonobo.Rename(Card_Number="Card Number",
                      Tradelist_Count="Tradelist Count"),
        #        bonobo_sqlalchemy.InsertOrUpdate(
        #            'cards',
        #            discriminant=(
        #                'Name',
        #               'Edition',
        ##               'Card_Number',
        ##              'Foil',
        #          ),
        #          engine='cards'),
        _name="main",
    )

    return graph


def get_graph(**options):
    """
    This function builds the graph that needs to be executed.

    :return: bonobo.Graph

    """
    graph = bonobo.Graph()

    graph.add_chain(
        get_cards,
        wishlist_map,
        bonobo.UnpackItems(0),
        bonobo.CsvWriter("Deckbox-wishlist.csv"),
        _name="main",
    )

    return graph


# Deckbox-inventory.csv


def get_services(**options):
    """
    This function builds the services dictionary, which is a simple dict of names-to-implementation used by bonobo
    for runtime injection.

    It will be used on top of the defaults provided by bonobo (fs, http, ...). You can override those defaults, or just
    let the framework define them. You can also define your own services and naming is up to you.

    :return: dict
    """

    return {
        "http":
        requests,
        # 'cards': create_engine("sqlite:///inventory.sqlite3", echo=False),
        "cards":
        create_engine("mysql+pymysql://mtg:mtg@localhost/mtg", echo=False),
    }


# The __main__ block actually execute the graph.
if __name__ == "__main__":
    parser = bonobo.get_argument_parser()
    with bonobo.parse_args(parser) as options:
        svc = get_services(**options)
        inventory = get_inventory_graph(**options)
        graph = get_graph(**options)

        bonobo.run(inventory, services=svc)

        load_wants()

        bonobo.run(graph, services=svc)
