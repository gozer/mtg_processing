import bonobo
from bonobo.config import use, use_context, use_raw_input, use_context_processor
from bonobo.constants import NOT_MODIFIED
from os import listdir
from os.path import isfile, join
import requests

import logging
import mondrian

# One line setup (excepthook=True tells mondrian to handle uncaught exceptions)
mondrian.setup(excepthook=True)

# Use logging, as usual.
logger = logging.getLogger("mtg")
logger.setLevel(logging.INFO)

import requests_cache
requests_cache.install_cache(
    'scryfall', backend='sqlite', expire_after=60 * 60 * 24 * 7)

from mtgtools.MtgDB import MtgDB
from mtgsdk import Card, Set
#import scrython
#from scryfall_cache import ScryfallCache
#cache = ScryfallCache(application="scryfall_tests")

MTG_DB = MtgDB('mtgdb.fs')

NO_SALE = True
CUTOFF = 4
PRICE_MODIFIER = 0.95
MIN_PRICE = 0.25
IN_USE_CARDS = {}
DEBUG = False
QUALITY = 'Near Mint'
LANGUAGE = 'English'


def _used_cards(foo, bar):
    yield IN_USE_CARDS


@use_context_processor(_used_cards)
def in_use_cards(_used_cards, count, name, section, edition, *rest):
    # Scratchpad, we don't care about
    if section == 'scratchpad':
        return

    if edition not in _used_cards:
        _used_cards[edition] = {}

    if name not in _used_cards[edition]:
        _used_cards[edition][name] = 0

    _used_cards[edition][name] += int(count)

    # pprint.pprint(IN_USE_CARDS)

    return


def get_decks(**options):
    """
    This function builds the graph that needs to be executed.

    :return: bonobo.Graph

    """
    graph = bonobo.Graph()

    csv_in = bonobo.noop

    graph.add_chain(
        csv_in,
        in_use_cards,
        _input=None,
    )

    for deck in listdir("decks"):
        deck_path = join("decks", deck)
        if deck == ".gitignore":
            continue

        if isfile(deck_path):
            graph.add_chain(
                bonobo.CsvReader(deck_path),
                _output=csv_in,
            )

    return graph


def get_graph(**options):
    """
    This function builds the graph that needs to be executed.

    :return: bonobo.Graph

    """
    graph = bonobo.Graph()

    split = bonobo.noop
    csv_in = bonobo.noop

    graph.add_chain(
        csv_in,
        bonobo.CsvWriter("DeckedBuilder.csv"),
        split,
        _input=None,
    )

    graph.add_chain(
        bonobo.CsvReader('main-en.csv'),
        _output=csv_in,
    )

    graph.add_chain(
        bonobo.CsvReader('Deckbox-extras.csv'),
        _output=csv_in,
    )

    #Reg Qty,Foil Qty,Name,Set,Acquired,Language
    echomtg = {
        "Acquired For": "0.004",
        "Language": "en",
    }
    graph.add_chain(
        bonobo.Rename(Name='Card', ),
        bonobo.Format(**echomtg, ),
        bonobo.CsvWriter("EchoMTG.csv"),
        _input=split,
    )

    graph.add_chain(
        foils,
        bonobo.CsvWriter("DeckedBuilder-foils.csv"),
        _input=split,
    )

    graph.add_chain(
        not_foils,
        rares,
        bonobo.CsvWriter("DeckedBuilder-rares.csv"),
        _input=split,
    )

    graph.add_chain(
        not_foils,
        not_rares,
        bonobo.CsvWriter(path="DeckedBuilder-commons.csv"),
        _input=split,
    )

    # MTG Studio
    graph.add_chain(
        bonobo.Rename(
            Name='Card',
            Edition='Set',
            Qty='Reg Qty',
            Foil='Foil Qty',
        ),
        bonobo.CsvWriter("MTG-Studio.csv"),
        _input=split,
    )

    graph.add_chain(
        not_foils,
        not_rares,
        a_lot,
        bonobo.OrderFields([
            'Card',
            'Set',
            'Foil Qty',
            'Reg Qty',
        ]),
        bonobo.CsvWriter("bulk.csv"),
        _input=split,
    )

    graph.add_chain(
        tradeable,
        bonobo.UnpackItems(0),
        #bonobo.PrettyPrinter(),
        #bonobo.Limit(3000),
        bonobo.CsvWriter("DeckedBuilder-tradelist.csv"),
        bonobo.OrderFields([
            'Card',
            'Set',
            'Foil',
            'Quantity',
        ]),
        bonobo.CsvWriter("CardKingdom-buylist.csv"),
        bonobo.OrderFields([
            'Quantity',
            'Card',
            'Set',
        ]),
        bonobo.CsvWriter(
            "mtgprice-buylist.csv",
            delimiter="\t",
        ),
        _input=split,
    )

    graph.add_chain(
        metadata,
        bonobo.UnpackItems(0),
        tradeable_decked,
        bonobo.UnpackItems(0),
        bonobo.CsvWriter("Deckbox-inventory.csv"),
        _input=split,
    )

    return graph


@use('http')
@use_raw_input
def metadata(card, *, http):
    mvid = card.get('Mvid')

    scryfall = None

    if mvid:
        try:
            response = requests.get(
                "https://api.scryfall.com/cards/multiverse/%s" % mvid).json()
            if response.get("object") == "card":
                scryfall = response
            else:
                logger.warn("[mvid:%s] Invalid scyfall response %r" %
                            (mvid, response.get('details')))
        except Exception as e:
            logger.error("[scryfall] Looking up %r failed: Exception was %r" %
                         (card.get('Card'), e))
    if not scryfall:

        name = card.get('Card')
        set_name = card.get('Set')

        logger.error("[mvid:%s] lookup failed, falling back %s [%s]" %
                     (mvid, name, set_name))

        set = list(
            filter(lambda x: x.type != "promo",
                   Set.where(name=set_name).all()))

        cards = []
        if len(set) == 1:
            set_code = set[0].code
            logger.debug("Set code is %s" % set_code)
            cards = Card.where(name=name).where(set=set_code).all()

        logger.debug("Found %d cards" % len(cards))

        if len(cards) == 1:
            mvid = cards[0].multiverse_id
            logger.warning("[mvid:%s] Found on magicthegathering.io" % mvid)
            # XXX: Duplication!

            try:
                response = requests.get(
                    "https://api.scryfall.com/cards/multiverse/%s" %
                    mvid).json()
                if response.get("object") == "card":
                    scryfall = response
                else:
                    logger.warn("[mvid:%s] Invalid scyfall response %r" %
                                (mvid, response.get('details')))
            except Exception as e:
                logger.error(
                    "[scryfall] Looking up %r failed: Exception was %r" %
                    (card.get('Card'), e))

    #XXX: What to do with Scryfall-less cards...
    yield {
        **card._asdict(),
        'mvid': mvid,
        'scryfall': scryfall,
    }


@use_raw_input
def a_lot(row):
    qty = int(row.get('Total Qty'))

    if qty > 16:
        return NOT_MODIFIED


def is_standard(card):
    scryfall = card.get('scryfall')
    if scryfall:
        legality = scryfall.get('legalities', None)
        if legality:
            standard = legality.get('standard', None)
            if standard == 'legal':
                return True

    return False


@use_raw_input
def more_than_set(row):

    qty = int(row.get('Reg Qty'))

    if qty > CUTOFF:
        yield {
            **row._asdict(),
            'Reg Qty': qty - CUTOFF,
        }


#Count,Tradelist Count,Name,Edition,Card Number,Condition,Language,Foil,Signed,Artist Proof,Altered Art,Misprint,Promo,Textless,My Price
@use_context_processor(_used_cards)
@use_raw_input
def tradeable_decked(_used_cards, row):

    #pprint.pprint(_used_cards)
    edition = row.get('Set')
    name = row.get('Card')

    #XXX: Check here
    standard = is_standard(row)

    qty = int(row.get('Reg Qty'))
    foil_qty = int(row.get('Foil Qty'))
    trade_qty = 0
    trade_foil_qty = 0
    rarity = row.get('Rarity')

    price_str = row.get('Single Price') or "0"
    price = float(price_str)

    foil_price_str = row.get('Single Foil Price') or "0"
    foil_price = float(foil_price_str)

    scryfall = row.get('scryfall')
    mtgio = row.get('mtgio')

    if scryfall and 'prices' in scryfall:
        # XXX: Check for foil somehow...
        if scryfall['prices']['usd']:
            price = float(scryfall['prices']['usd'])
        if scryfall['prices']['usd_foil']:
            foil_price = float(scryfall['prices']['usd_foil'])

        logger.debug("Prices from Scryfall for %s are %s/%s" % (name, price,
                                                                foil_price))

    foil_cutoff = 1

    if rarity == "Rare" or rarity == "Mythic Rare":
        qty_cutoff = 1
    else:
        qty_cutoff = CUTOFF

    # Are we using this card in our built decks ?
    if edition in _used_cards:
        if name in _used_cards[edition]:
            deck_qty = _used_cards[edition][name]
            if deck_qty > qty_cutoff:
                qty_cutoff = deck_qty
            #qty_cutoff += deck_qty

    if standard:
        if qty_cutoff < 4:
            qty_cutoff = 4
        if foil_cutoff < 4:
            foil_cutoff = 4

    if qty > qty_cutoff:
        trade_qty = qty - qty_cutoff

    if foil_qty > foil_cutoff:
        trade_foil_qty = foil_qty - foil_cutoff

    if scryfall:
        if not 'set_name' in scryfall:
            logger.error("MIssing set_name from scryfall %r" % scryfall)
        scryfall_set_name = scryfall['set_name']
        scryfall_set = scryfall['set']

        if scryfall_set_name != None:
            if edition != scryfall_set_name:
                logger.debug("XXX Set %s vs %s" % (edition, scryfall_set_name))

    # edition = scryfall_set_name

    if edition == "Magic: The Gathering-Conspiracy":
        edition = "Conspiracy"

    if edition == 'Time Spiral ""Timeshifted""':
        edition = 'Time Spiral "Timeshifted"'

    if edition == 'Magic: The Gathering-Commander':
        edition = "Commander"

    if edition == 'Commander 2013 Edition':
        edition = "Commander 2013"

    if edition == 'Planechase 2012 Edition':
        edition = 'Planechase 2012'

    import re
    name = re.sub(" \([ab]\)$", "", name)

    if name == 'Sword of Dungeons &amp; Dragons':
        name = 'Sword of Dungeons & Dragons'

    if name == 'Unholy Fiend':
        name = 'Cloistered Youth'

    collector_number = 0
    if scryfall:
        collector_number = scryfall['collector_number']

    # Dont sell yet
    if NO_SALE:
        price = 0
        foil_price = 0

    if foil_qty > 0:
        yield {
            'Count': foil_qty,
            'Tradelist Count': trade_foil_qty,
            'Name': name,
            'Edition': edition,
            'Card Number': collector_number,
            'Condition': QUALITY,
            'Language': LANGUAGE,
            'Foil': 'foil',
            'Signed': '',
            'Artist Proof': '',
            'Altered Art': '',
            'Misprint': '',
            'Promo': '',
            'Textless': '',
            'My Price': format(foil_price * PRICE_MODIFIER, '.2f'),
        }

    if qty > 0:
        # Don't price below MIN_PRICE
        price = price * PRICE_MODIFIER

        if price < MIN_PRICE and not NO_SALE:
            price = MIN_PRICE

        yield {
            'Count': qty,
            'Tradelist Count': trade_qty,
            'Name': name,
            'Edition': edition,
            'Card Number': collector_number,
            'Condition': QUALITY,
            'Language': LANGUAGE,
            'Foil': '',
            'Signed': '',
            'Artist Proof': '',
            'Altered Art': '',
            'Misprint': '',
            'Promo': '',
            'Textless': '',
            'My Price': format(price, '.2f'),
        }


@use_raw_input
def tradeable(row):

    qty = int(row.get('Reg Qty'))
    foil_qty = int(row.get('Foil Qty'))

    rarity = row.get('Rarity')

    foil_cutoff = 1

    if rarity == "Rare" or rarity == "Mythic Rare":
        qty_cutoff = 1
    else:
        qty_cutoff = CUTOFF

    if qty > qty_cutoff:
        qty -= qty_cutoff
    else:
        qty = 0

    if foil_qty > foil_cutoff:
        foil_qty -= foil_cutoff
    else:
        foil_qty = 0

    price_str = row.get('Single Price') or "0"
    price = float(price_str)

    if (foil_qty > 0):
        yield {
            **row._asdict(),
            'Reg Qty': 0,
            'Foil Qty': foil_qty,
            'Quantity': foil_qty,
            'Foil': 1,
        }

    if (qty > 0 and price > 0):
        yield {
            **row._asdict(),
            'Reg Qty': qty,
            'Foil Qty': 0,
            'Quantity': qty,
            'Foil': 0,
        }


@use_raw_input
def foils(row):
    foil = int(row.get('Foil Qty'))

    if foil > 0:
        return NOT_MODIFIED


@use_raw_input
def not_foils(row):
    foil = int(row.get('Foil Qty'))

    if foil <= 0:
        return NOT_MODIFIED


@use_raw_input
def rares(row):
    rarity = row.get('Rarity')

    if rarity == "Rare" or rarity == "Mythic Rare":
        return NOT_MODIFIED


@use_raw_input
def not_rares(row):
    rarity = row.get('Rarity')

    if rarity != "Rare" and rarity != "Mythic Rare":
        return NOT_MODIFIED


def get_services(**options):
    """
    This function builds the services dictionary, which is a simple dict of names-to-implementation used by bonobo
    for runtime injection.

    It will be used on top of the defaults provided by bonobo (fs, http, ...). You can override those defaults, or just
    let the framework define them. You can also define your own services and naming is up to you.

    :return: dict
    """

    #mtg_db.mtgio_update()

    return {
        'http': requests.Session(),
        'mtgdb': MTG_DB,
    }


# The __main__ block actually execute the graph.
if __name__ == '__main__':
    parser = bonobo.get_argument_parser()

    parser.add_argument('--update', action='store_true', default=False)

    with bonobo.parse_args(parser) as options:
        if options['update']:
            MTG_DB.scryfall_update()
            MTG_DB.mtgio_update()

        bonobo.run(get_decks(**options), services=get_services(**options))
        bonobo.run(get_graph(**options), services=get_services(**options))
