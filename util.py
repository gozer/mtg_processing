__all__ = ['edition_to_deckbox']


def edition_to_deckbox(edition):
    if edition == 'Time Spiral Timeshifted':
        edition = 'Time Spiral "Timeshifted"'

    elif edition == 'Magic: The Gathering-Commander':
        edition = "Commander"

    elif edition == 'Magic 2014':
        edition = "Magic 2014 Core Set"

    elif edition == 'Magic 2015':
        edition = "Magic 2015 Core Set"

    elif edition == 'Modern Masters 2015':
        edition = "Modern Masters 2015 Edition"

    elif edition == 'Modern Masters 2017':
        edition = "Modern Masters 2017 Edition"

    elif edition == 'Commander 2013 Edition':
        edition = "Commander 2013"

    elif edition == 'Commander 2011':
        edition = "Commander"

    elif edition == 'Planechase 2012 Edition':
        edition = 'Planechase 2012'

    elif edition == 'Commander Anthology 2018':
        edition = 'Commander Anthology Volume II'

    elif edition == 'M19 Gift Pack':
        edition = 'M19 Gift Pack Promos'

    return edition
