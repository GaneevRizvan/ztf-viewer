import math
import re

import numpy as np
from astropy import units


def dict_to_bullet(d):
    return '\n'.join(f'* **{k}**: {v}' for k, v in d.items())


def db_coord_to_degrees(coord):
    match = re.search(r'^\((\S+)\s*,\s*(\S+)\)$', coord)
    ra = math.degrees(float(match.group(1)))
    dec = math.degrees(float(match.group(2)))
    return ra, dec


def coord_str_to_pair(coord):
    return tuple(float(x) for x in coord.split(', '))


def hms_to_deg(hms: str):
    h, m, s = (float(x) for x in hms.split())
    angle = h * units.hourangle + m * units.arcmin + s * units.arcsec
    deg = angle.to_value(units.deg)
    return deg


def convert_to_json_friendly(values):
    x = values[0]
    if np.issubdtype(values.dtype, np.str_) or isinstance(x, str):
        return values
    if np.issubdtype(values.dtype, np.number) or isinstance(x, float):
        return [float(x) for x in values]
    if np.issubdtype(values.dtype, np.string_) or isinstance(x, bytes):
        return [b.decode() for b in values]
    return list(map(str, values))


def astropy_table_to_records(table, columns=None):
    if columns is None:
        columns = table.colnames
    length = len(table)
    d = {c: convert_to_json_friendly(table[c]) for c in columns}
    records = [{c: d[c][i] for c in columns} for i in range(length)]
    return records
