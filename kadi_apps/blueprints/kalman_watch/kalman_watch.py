
from pathlib import Path
from flask import Blueprint, abort
import numpy as np
import json

from cxotime import CxoTime
from astropy.table import Table

from kalman_watch.kalman_perigee_mon import EventPerigee
from kadi_apps.rendering import render_template


KALMAN_DATA = Path('/Users/javierg/SAO/git/kalman_watch/perigees')

blueprint = Blueprint(
    'kalman_watch',
    __name__,
    template_folder='templates',
)


@blueprint.route("/", methods=['GET'])
def recent_perigees():

    context = {
        'title': 'Recent Perigee Passages',
    }

    return render_template(
        'perigee_list.html',
        **context
    )


@blueprint.route("/<year>", methods=['GET'])
def yearly_perigees(year):

    year = int(year)

    stats = Table.read(KALMAN_DATA / "kalman_perigees.ecsv")

    years_all = CxoTime(stats["perigee"]).ymdhms.year
    years_unique = sorted(np.unique(years_all))
    stats_year = stats[years_all == year]

    stats_year['year'] = [dirname[:4] for dirname in stats_year['dirname']]
    stats_year['date'] = [dirname[5:] for dirname in stats_year['dirname']]

    prev_year = year - 1 if (year - 1) in years_unique else None
    next_year = year + 1 if (year + 1) in years_unique else None
    description = f"{year}"

    # Replace all zeros with "" for the HTML table
    kalman_stats = []
    for row in stats_year:
        context_row = {
            key: (val if val != 0 else "") for key, val in zip(row.keys(), row.values())
        }
        kalman_stats.append(context_row)

    context = {
        'year': year,
        'title': f'Perigee Kalman index page {year}',
    }

    return render_template(
        'perigee_list.html',
        kalman_stats=kalman_stats,
        description=description,
        prev=prev_year,
        next=next_year,
        **context
    )


@blueprint.route("/<year>/<date>", methods=['GET'])
def perigee(year, date):

    stats = Table.read(KALMAN_DATA / "kalman_perigees.ecsv")

    data_file = KALMAN_DATA / year / date / "data.npz"
    if not data_file.exists():
        abort(404, description="Resource not found")

    with open(KALMAN_DATA / year / date / "info.json") as fh:
        info = json.load(fh)
    perigee = info['perigee']

    index = np.arange(len(stats))[np.in1d(stats['perigee'], perigee)][0]
    evt = EventPerigee.from_npz(data_file)
    fig = evt.get_plot_fig()
    kalman_plot_html = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        default_width=1000,
        default_height=600,
    )

    has_low_kalmans = len(evt.low_kalmans) > 0
    low_kalmans_html = "\n".join(
        evt.low_kalmans.pformat(html=True, max_width=-1, max_lines=-1)
    )

    context = {
        'year': year,
        'date': date,
        'title': f'{date} {year} Perigee Kalman Plot',
    }

    return render_template(
        'perigee_detail.html',
        kalman_plot_html=kalman_plot_html,
        has_low_kalmans=has_low_kalmans,
        low_kalmans_html=low_kalmans_html,
        obsids=[obs["obsid"] for obs in evt.obss],
        prev_year=stats['dirname'][index + 1][:4] if index < len(stats) - 1 else None,
        prev_date=stats['dirname'][index + 1][5:] if index < len(stats) - 1 else None,
        next_year=stats['dirname'][index - 1][:4] if index > 0 else None,
        next_date=stats['dirname'][index - 1][5:] if index > 0 else None,
        **context
    )
