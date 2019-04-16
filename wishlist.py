#!/usr/bin/env python3

import bonobo
from bonobo.config import use, use_context, use_raw_input, use_context_processor
from bonobo.constants import NOT_MODIFIED
from os import listdir
from os.path import isfile, join

import logging
import mondrian

from copy import copy

import util

# One line setup (excepthook=True tells mondrian to handle uncaught exceptions)
mondrian.setup(excepthook=True)

# Use logging, as usual.
logger = logging.getLogger("mtg")
logger.setLevel(logging.INFO)

import random
CACHE_TIME = 14 + (random.randint(0, 14))
logger.warning("Caching for %d days" % CACHE_TIME)

import requests as req
from cachecontrol import CacheControl, CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.heuristics import ExpiresAfter

CACHE = FileCache('.web_cache')
requests = CacheControl(
    req.Session(), cache=CACHE, heuristic=ExpiresAfter(days=CACHE_TIME))

INVENTORY = {}


def _inventory(foo, bar):
    yield INVENTORY


@use_context_processor(_inventory)
def inventory(_inventory, *card):
    edition = card[3]
    name = card[2]
    foil = card[7]

    # Skip Foils
    if foil:
        return

    if edition not in _inventory:
        _inventory[edition] = {}

    if name not in _inventory[edition]:
        _inventory[edition][name] = 0

    _inventory[edition][name] += int(card[0])

    yield card


@use('http')
def get_cards(http):
    sets = http.get("https://mtgjson.com/json/AllSets.json").json()

    set_map = {}
    for set_info in http.get("https://mtgjson.com/json/SetList.json").json():
        set_map[set_info['code']] = [set_info['name'], set_info['type']]

    for set_code, set_data in sets.items():
        print("Finding cards out of %s" % set_code)
        set_info = set_map.get(set_code)
        if not set_info:
            print("XXX: Can't find setinfo for %s %s" % (card, set_code))
            continue

        for card in set_data.get("cards"):
            card['edition'] = set_code
            card['edition_name'] = set_map.get(set_code)[0]
            card['set_type'] = set_map.get(set_code)[1]

            yield card


@use_context_processor(_inventory)
def wishlist_map(_inventory, card):
    #Count,Name,Edition,Card Number,Condition,Language,Foil,Signed,Artist Proof,Altered Art,Misprint,Promo,Textless
    name = card['name']
    edition = util.edition_to_deckbox(card['edition_name'])
    set_type = card['set_type']

    # Skip Basic Lands
    if "Basic" in card['supertypes']:
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
        "WAR",

        # Too Expsnsive!
        "LEA",
        "LEB",
        "2ED",
        "3ED",
        "LEG",
        "ARN",
        "ATQ",
    ]

    if card['edition'] in set_exclusions:
        return

    type_exclusions = [
        "memorabilia",
        "promo",
        "starter",
        "vanguard",
        "duel_deck",
        "box",
        "funny",
        "archenemy",
        "planechase",
        "masterpiece",
        "treasure_chest",
        "token",
    ]

    if set_type in type_exclusions:
        return

    #XXX Refactor plz

    want = 4

    if 'names' in card and len(card['names']) > 0:
        if name != card['names'][0]:
            return
        if card['layout'] == "split":
            name = " // ".join(card['names'])

    have_count = 0
    if edition in _inventory:
        if name in _inventory[edition]:
            have_count = _inventory[edition][name]

    if have_count < want:
        want -= have_count

        yield {
            'Count': want,
            'Name': name,
            'Edition': edition,
            'Card Number': card['number'],
            'Condition': None,
            'Language': "English",
            'Foil': None,
            'Signed': None,
            'Artist Proof': None,
            'Altered Art': None,
            'Misprint': None,
            'Promo': None,
            'Textless': None,
        }


def get_inventory_graph(**options):
    """
    This function builds the graph that needs to be executed.

    :return: bonobo.Graph

    """
    graph = bonobo.Graph()

    graph.add_chain(
        bonobo.CsvReader("Deckbox-inventory.csv"),
        inventory,
        #_input=None,
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
        'http': requests,
    }


# The __main__ block actually execute the graph.
if __name__ == '__main__':
    parser = bonobo.get_argument_parser()
    with bonobo.parse_args(parser) as options:
        svc = get_services(**options)
        inventory = get_inventory_graph(**options)
        graph = get_graph(**options)

        bonobo.run(inventory, services=svc)
        bonobo.run(graph, services=svc)
