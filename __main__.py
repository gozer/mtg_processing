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
        bonobo.CsvWriter("DeckedBuilder-commons.csv"),
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
