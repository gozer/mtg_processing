import bonobo


def get_graph(**options):
    """
    This function builds the graph that needs to be executed.

    :return: bonobo.Graph

    """
    graph = bonobo.Graph()

    split = bonobo.noop

    graph.add_chain(
        bonobo.CsvReader('main.csv'),
        bonobo.CsvWriter("DeckedBuilder.csv"),
        split,
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
        tradeable_decked,
        bonobo.UnpackItems(0),
        bonobo.CsvWriter("Deckbox-inventory.csv"),
        _input=split,
    )

    return graph


#?
#? Total Qty[0] = '1'
#? Reg Qty[1] = '1'
#? Foil Qty[2] = '0'
#? Card[3] = 'Aggressive Mammoth'
#? Set[4] = 'Core Set 2019'
#? Mana Cost[5] = '3GGG'
#? Card Type[6] = 'Creature  - Elephant'
#? Color[7] = 'Green'
#? Rarity[8] = 'Rare'
#? Mvid[9] = '450249'
#? Single Price[10] = '2.00'
#? Single Foil Price[11] = '0.00'
#? Total Price[12] = '2.00'
#? Price Source[13] = 'tcglo'
#? Notes[14] = ''

from bonobo.config import use, use_context, use_raw_input
from bonobo.constants import NOT_MODIFIED


@use_raw_input
def a_lot(row):
    qty = int(row.get('Total Qty'))

    if qty > 16:
        return NOT_MODIFIED


@use_raw_input
def more_than_set(row):

    qty = int(row.get('Reg Qty'))

    if qty > 8:
        yield {
            **row._asdict(),
            'Reg Qty': qty - 8,
        }


#Count,Tradelist Count,Name,Edition,Card Number,Condition,Language,Foil,Signed,Artist Proof,Altered Art,Misprint,Promo,Textless,My Price
@use_raw_input
def tradeable_decked(row):
    qty = int(row.get('Reg Qty'))
    foil_qty = int(row.get('Foil Qty'))
    trade_qty = 0
    trade_foil_qty = 0
    rarity = row.get('Rarity')

    price_str = row.get('Single Price') or "0"
    price = float(price_str)

    foil_price_str = row.get('Single Foil Price') or "0"
    foil_price = float(foil_price_str)

    foil_cutoff = 1

    if rarity == "Rare" or rarity == "Mythic Rare":
        qty_cutoff = 1
    else:
        qty_cutoff = 8

    if qty > qty_cutoff and price > 0.1:
        trade_qty = qty - qty_cutoff
        #qty = qty_cutoff

    if foil_qty > foil_cutoff:
        trade_foil_qty = foil_qty - foil_cutoff
        #foil_qty = foil_cutoff

    edition = row.get('Set')
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

    name = row.get('Card')

    if name == 'Dimir Guildgate (b)':
        name = 'Dimir Guildgate'

    if name == 'Sword of Dungeons &amp; Dragons':
        name = 'Sword of Dungeons & Dragons'

    if name == 'Unholy Fiend':
        name = 'Cloistered Youth'

    if foil_qty > 0:
        yield {
            'Count': foil_qty,
            'Tradelist Count': trade_foil_qty,
            'Name': name,
            'Edition': edition,
            'Card Number': row.get('Mvid'),
            'Condition': 'Mint',
            'Language': 'English',
            'Foil': 'foil',
            'Signed': '',
            'Artist Proof': '',
            'Altered Art': '',
            'Misprint': '',
            'Promo': '',
            'Textless': '',
            'My Price': foil_price * 0.9,
        }

    if qty > 0:
        yield {
            'Count': qty,
            'Tradelist Count': trade_qty,
            'Name': name,
            'Edition': edition,
            'Card Number': row.get('Mvid'),
            'Condition': 'Mint',
            'Language': 'English',
            'Foil': '',
            'Signed': '',
            'Artist Proof': '',
            'Altered Art': '',
            'Misprint': '',
            'Promo': '',
            'Textless': '',
            'My Price': price * 0.9,
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
        qty_cutoff = 8

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
    return {}


# The __main__ block actually execute the graph.
if __name__ == '__main__':
    parser = bonobo.get_argument_parser()
    with bonobo.parse_args(parser) as options:
        bonobo.run(get_graph(**options), services=get_services(**options))
