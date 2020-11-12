from io import BytesIO, StringIO

import matplotlib
import matplotlib.backends.backend_pgf
import matplotlib.figure
import numpy as np
import pandas as pd
from datetime import datetime
from flask import Response, request, send_file
from matplotlib.ticker import AutoMinorLocator

from app import app
from cache import cache
from cross import find_ztf_oid
from util import mjd_to_datetime, NotFound, FILTER_COLORS, FILTERS_ORDER


MJD_OFFSET = 58000


@cache()
def get_plot_data(cur_oid, dr, other_oids=frozenset(), min_mjd=None, max_mjd=None):
    oids = [cur_oid]
    oids.extend(sorted(other_oids, key=int))
    lcs = {}
    for oid in oids:
        if oid == cur_oid:
            size = 3
        else:
            size = 1
        lc = find_ztf_oid.get_lc(oid, dr, min_mjd=min_mjd, max_mjd=max_mjd)
        meta = find_ztf_oid.get_meta(oid, dr)
        for obs in lc:
            obs[f'mjd_{MJD_OFFSET}'] = obs['mjd'] - MJD_OFFSET
            obs['Heliodate'] = mjd_to_datetime(obs['mjd']).strftime('%Y-%m-%d %H:%m:%S')
            obs['oid'] = oid
            obs['fieldid'] = meta['fieldid']
            obs['rcid'] = meta['rcid']
            obs['filter'] = meta['filter']
            obs['mark_size'] = size
            obs['cur_oid'] = cur_oid
        lcs[oid] = lc
    return lcs


@cache()
def get_folded_plot_data(cur_oid, dr, period, offset=None, other_oids=frozenset(), min_mjd=None, max_mjd=None):
    if offset is None:
        offset = MJD_OFFSET
    lcs = get_plot_data(cur_oid, dr, other_oids=other_oids, min_mjd=min_mjd, max_mjd=max_mjd)
    for lc in lcs.values():
        for obs in lc:
            obs['folded_time'] = (obs['mjd'] - offset) % period
            obs['phase'] = obs['folded_time'] / period
    return lcs


MIMES = {
    'pdf': 'application/pdf',
    'png': 'image/png',
}


def save_fig(fig, fmt):
    bytes_io = BytesIO()
    if fmt == 'pdf':
        canvas = matplotlib.backends.backend_pgf.FigureCanvasPgf(fig)
        canvas.print_pdf(bytes_io)
    else:
        fig.savefig(bytes_io, format=fmt)
    return bytes_io


def plot_data(oid, dr, data, fmt='png', copyright=True):
    usetex = fmt == 'pdf'

    lcs = {}
    seen_filters = set()
    for lc_oid, lc in data.items():
        if len(lc) == 0:
            continue
        first_obs = lc[0]
        fltr = first_obs['filter']
        lcs[lc_oid] = {
            'filter': fltr,
            't': [obs['mjd'] for obs in lc],
            'm': [obs['mag'] for obs in lc],
            'err': [obs['magerr'] for obs in lc],
            'color': FILTER_COLORS[fltr],
            'marker_size': 24 if lc_oid == oid else 12,
            'label': '' if fltr in seen_filters else fltr,
            'marker': 'o' if lc_oid == oid else 's',
            'zorder': 2 if lc_oid == oid else 1,
        }
        seen_filters.add(fltr)

    fig = matplotlib.figure.Figure(dpi=300)
    if copyright:
        fig.text(
            0.50,
            0.005,
            f'Generated with the SNAD ZTF viewer on {datetime.now().date()}',
            ha='center',
            fontdict=dict(size=8, color='grey', usetex=usetex),
        )
    ax = fig.subplots()
    ax.invert_yaxis()
    if usetex:
        ax.set_title(rf'\underline{{\href{{https://ztf.snad.space/{dr}/view/{oid}}}{{\texttt{{{oid}}}}}}}', usetex=True)
    else:
        ax.set_title(str(oid))
    ax.set_xlabel('MJD', usetex=usetex)
    ax.set_ylabel('magnitude', usetex=usetex)
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.tick_params(which='major', direction='in', length=6, width=1.5)
    ax.tick_params(which='minor', direction='in', length=4, width=1)
    for lc_oid, lc in sorted(lcs.items(), key=lambda item: FILTERS_ORDER[item[1]['filter']]):
        ax.errorbar(
            lc['t'],
            lc['m'],
            lc['err'],
            c=lc['color'],
            label=lc['label'],
            marker='',
            zorder=lc['zorder'],
            ls='',
            alpha=0.7,
        )
        ax.scatter(
            lc['t'],
            lc['m'],
            c=lc['color'],
            label='',
            marker=lc['marker'],
            s=lc['marker_size'],
            linewidths=0.5,
            edgecolors='black',
            zorder=lc['zorder'],
            alpha=0.7,
        )
    legend_anchor_y = -0.026 if usetex else -0.032
    ax.legend(
        bbox_to_anchor=(1, legend_anchor_y),
        ncol=min(3, len(seen_filters)),
        # edgecolor='white',
        # facecolor=(0.95, 0.95, 0.95),
        frameon=False,
        handletextpad=0.0,
    )
    bytes_io = save_fig(fig, fmt)
    return bytes_io.getvalue()


def plot_folded_data(oid, dr, data, period, offset=None, repeat=None, fmt='png', copyright=True):
    if repeat is None:
        repeat = 2

    usetex = fmt == 'pdf'

    lcs = {}
    seen_filters = set()
    for lc_oid, lc in data.items():
        if len(lc) == 0:
            continue
        first_obs = lc[0]
        fltr = first_obs['filter']
        lcs[lc_oid] = {
            'filter': fltr,
            'folded_time': np.array([obs['folded_time'] for obs in lc]),
            'phase': np.array([obs['phase'] for obs in lc]),
            'm': np.array([obs['mag'] for obs in lc]),
            'err': np.array([obs['magerr'] for obs in lc]),
            'color': FILTER_COLORS[fltr],
            'marker_size': 24 if lc_oid == oid else 12,
            'label': '' if fltr in seen_filters else fltr,
            'marker': 'o' if lc_oid == oid else 's',
            'zorder': 2 if lc_oid == oid else 1,
        }
        seen_filters.add(fltr)

    fig = matplotlib.figure.Figure(dpi=300)
    if copyright:
        fig.text(
            0.50,
            0.005,
            f'Generated with the SNAD ZTF viewer on {datetime.now().date()}',
            ha='center',
            fontdict=dict(size=8, color='grey', usetex=usetex),
        )
    ax = fig.subplots()
    fig.subplots_adjust(top=0.85)
    ax.invert_yaxis()
    if usetex:
        ax.set_title(
            rf'\underline{{\href{{https://ztf.snad.space/{dr}/view/{oid}}}{{\texttt{{{oid}}}}}}}, '
            rf'$P = {period:.4g}$\,days',
            usetex=True,
        )
    else:
        ax.set_title(f'{oid}, P = {period:.4g} days')
    ax.set_xlabel('phase', usetex=usetex)
    ax.set_ylabel('magnitude', usetex=usetex)
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.tick_params(which='major', direction='in', length=6, width=1.5)
    ax.tick_params(which='minor', direction='in', length=4, width=1)
    for lc_oid, lc in sorted(lcs.items(), key=lambda item: FILTERS_ORDER[item[1]['filter']]):
        for i in range(-1, repeat + 1):
            label = ''
            if i == 0:
                label = lc['label']
            ax.errorbar(
                lc['phase'] + i,
                lc['m'],
                lc['err'],
                c=lc['color'],
                label=label,
                marker='',
                zorder=lc['zorder'],
                ls='',
                alpha=0.7,
            )
            ax.scatter(
                lc['phase'] + i,
                lc['m'],
                c=lc['color'],
                label='',
                marker=lc['marker'],
                s=lc['marker_size'],
                linewidths=0.5,
                edgecolors='black',
                zorder=lc['zorder'],
                alpha=0.7,
            )
    ax.set_xlim([-0.1, repeat + 0.1])
    secax = ax.secondary_xaxis('top', functions=(lambda x: x * period, lambda x: x / period))
    secax.set_xlabel('Folded time, days')
    secax.minorticks_on()
    secax.tick_params(direction='in', which='both')
    legend_anchor_y = -0.026 if usetex else -0.032
    ax.legend(
        bbox_to_anchor=(1, legend_anchor_y),
        ncol=min(3, len(seen_filters)),
        # edgecolor='white',
        # facecolor=(0.95, 0.95, 0.95),
        frameon=False,
        handletextpad=0.0,
    )
    bytes_io = save_fig(fig, fmt)
    return bytes_io.getvalue()


def parse_figure_args_helper(args):
    fmt = args.get('format', 'png')
    other_oids = frozenset(args.getlist('other_oid'))
    min_mjd = args.get('min_mjd', None)
    if min_mjd is not None:
        min_mjd = float(min_mjd)
    max_mjd = args.get('max_mjd', None)
    if max_mjd is not None:
        max_mjd = float(max_mjd)
    copyright = args.get('copyright', 'no') != 'no'

    if fmt not in MIMES:
        return '', 404

    return dict(fmt=fmt, other_oids=other_oids, min_mjd=min_mjd, max_mjd=max_mjd, copyright=copyright)


@app.server.route('/<dr>/figure/<int:oid>')
def response_figure(dr, oid):
    kwargs = parse_figure_args_helper(request.args)
    fmt = kwargs.pop('fmt')
    copyright = kwargs.pop('copyright')

    data = get_plot_data(oid, dr, **kwargs)
    img = plot_data(oid, dr, data, fmt=fmt, copyright=copyright)

    return Response(
        img,
        mimetype=MIMES[fmt],
        headers={'Content-disposition': f'attachment; filename={oid}.{fmt}'},
    )


@app.server.route('/<dr>/figure/<int:oid>/folded/<float:period>')
def response_figure_folded(dr, oid, period):
    kwargs = parse_figure_args_helper(request.args)
    fmt = kwargs.pop('fmt')
    copyright = kwargs.pop('copyright')

    repeat = request.args.get('repeat', None)
    if repeat is not None:
        repeat = int(repeat)

    data = get_folded_plot_data(oid, dr, period=period, **kwargs)
    img = plot_folded_data(oid, dr, data, period=period, repeat=repeat, fmt=fmt, copyright=copyright)

    return Response(
        img,
        mimetype=MIMES[fmt],
        headers={'Content-disposition': f'attachment; filename={oid}.{fmt}'},
    )


def get_csv(dr, oid):
    lc = find_ztf_oid.get_lc(oid, dr)
    if lc is None:
        raise NotFound
    df = pd.DataFrame.from_records(lc)
    string_io = StringIO()
    df.to_csv(string_io, index=False)
    return string_io.getvalue()


@app.server.route('/<dr>/csv/<int:oid>')
def response_csv(dr, oid):
    try:
        csv = get_csv(dr, oid)
    except NotFound:
        return '', 404
    return Response(
        csv,
        mimetype='text/csv',
        headers={'Content-disposition': f'attachment; filename={oid}.csv'},
    )


@app.server.route('/favicon.ico')
def favicon():
    return send_file('static/img/logo.svg', mimetype='image/svg+xml')
