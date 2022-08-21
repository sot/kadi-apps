# Licensed under a 3-clause BSD style license - see LICENSE.rst
from io import StringIO
import os

from flask import Blueprint, request

from kadi import __version__
from find_attitude.find_attitude import get_stars_from_text, find_attitude_solutions, logger
from logging import CRITICAL
from kadi_apps.rendering import render_template

# Only emit critical messages
logger.level = CRITICAL
for hdlr in logger.handlers:
    logger.setLevel(CRITICAL)


blueprint = Blueprint(
    'find_attitude',
    __name__,
    template_folder='templates',
)


def get_stars_from_maude(date=None, username=None, password=None):
    from maude import get_msids
    import astropy.units as u
    from cxotime import CxoTime
    from astropy.table import Table
    import numpy as np

    msids = []
    msids.extend([f"aoacyan{ii}" for ii in range(8)])
    msids.extend([f"aoaczan{ii}" for ii in range(8)])
    msids.extend([f"aoacmag{ii}" for ii in range(8)])
    kwargs = {}
    if username:
        kwargs['user'] = username
    if password:
        kwargs['password'] = password
    if date is not None:
        start = CxoTime(date)
        stop = start + 10 * u.s
        kwargs['start'] = start
        kwargs['stop'] = stop

    dat = get_msids(msids, **kwargs)
    results = dat["data"]
    out = {}
    for result in results:
        msid = result["msid"]
        value = result["values"][-1]
        out[msid] = value
    tbl = Table()

    tbl['slot'] = np.arange(8)
    tbl['YAG'] = [out[f"AOACYAN{ii}"] for ii in range(8)]
    tbl['ZAG'] = [out[f"AOACZAN{ii}"] for ii in range(8)]
    tbl['MAG_ACA'] = [out[f"AOACMAG{ii}"] for ii in range(8)]
    tbl.meta['date_solution'] = CxoTime(date).date

    return tbl


@blueprint.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        context = find_solutions_and_get_context()
    else:
        context = {}

    context['kadi_version'] = __version__
    context['distance_tolerance'] = float(request.form.get('distance_tolerance', '2.5'))

    if context.get('solutions'):
        context['subtitle'] = ': Solution'
    elif context.get('error_message'):
        context['subtitle'] = ': Error'

    return render_template(
        'find_attitude/index.html',
        **context
    )


def find_solutions_and_get_context():
    stars_text = request.form.get('stars_text', '')
    context = {}
    if stars_text.strip() == '':
        username = request.form.get('username', 'fail')
        password = request.form.get('password', 'fail')
        # Get date for solution, defaulting to NOW for any blank input
        date_solution = request.form.get('date_solution', '').strip() or None
        stars = get_stars_from_maude(date_solution, username, password)

        # Get a formatted version of the stars table that is used for finding
        # the solutions. This gets put back into the web page output.
        out = StringIO()
        stars_context = stars.copy()
        cols_new = ['yag', 'zag', 'mag']
        stars_context.rename_columns(['YAG', 'ZAG', 'MAG_ACA'], cols_new)
        for name in cols_new:
            stars_context[name].format = '.2f'
        stars_context.write(out, format='ascii.fixed_width', delimiter=' ')
        context['stars_text'] = out.getvalue()
        context['date_solution'] = stars.meta['date_solution']
        context['username'] = username
        context['password'] = password
    else:
        context['stars_text'] = stars_text

        # First parse the star text input
        try:
            stars = get_stars_from_text(stars_text)
        except Exception as err:
            context['error_message'] = ("{}\n"
                                        "Does it look like one of the examples?"
                                        .format(err))
            return context

    # Try to find solutions
    tolerance = float(request.form.get('distance_tolerance', '2.5'))
    try:
        solutions = find_attitude_solutions(stars, tolerance=tolerance)
    except Exception:
        import traceback
        context['error_message'] = traceback.format_exc()
        return context

    # No solutions, bummer.
    if not solutions:
        context['error_message'] = ('No matching solutions found.\n'
                                    'Try increasing distance tolerance.')
        return context

    context['solutions'] = []
    for solution in solutions:
        tbl = solution['summary']
        tbl['YAG'].format = '.2f'
        tbl['ZAG'].format = '.2f'
        tbl['MAG_ACA'].format = '.2f'
        summary_lines = tbl.pformat(max_width=-1, max_lines=-1)
        sol = {'att_fit': solution['att_fit'],
               'summary': os.linesep.join(summary_lines)}
        context['solutions'].append(sol)

    return context
