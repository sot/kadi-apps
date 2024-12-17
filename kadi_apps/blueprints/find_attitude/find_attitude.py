# Licensed under a 3-clause BSD style license - see LICENSE.rst
import os
from io import StringIO
from logging import CRITICAL

import find_attitude
import ska_sun
from cxotime import CxoTime
from find_attitude.find_attitude import (find_attitude_solutions,
                                         get_stars_from_text, logger)
from flask import Blueprint, request
from kadi import __version__

from kadi_apps.rendering import render_template

POSSIBLE_CONSTRAINTS = ['pitch', 'pitch_err',
                        'off_nom_roll_max',
                        'min_stars',
                        'mag_err']

# Only emit critical messages
logger.level = CRITICAL
for hdlr in logger.handlers:
    logger.setLevel(CRITICAL)


blueprint = Blueprint(
    'find_attitude',
    __name__,
    template_folder='templates',
)


def get_stars_from_maude(date=None):
    import astropy.units as u
    import numpy as np
    from astropy.table import Table
    from cxotime import CxoTime
    from maude import get_msids

    msids = []
    msids.extend([f"aoacyan{ii}" for ii in range(8)])
    msids.extend([f"aoaczan{ii}" for ii in range(8)])
    msids.extend([f"aoacmag{ii}" for ii in range(8)])
    if date is not None:
        start = CxoTime(date)
        stop = start + 10 * u.s
        kwargs = {'start': start, 'stop': stop}
    else:
        kwargs = {}
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
    tbl.meta['date_solution'] = CxoTime(results[0]['times'][-1]).date

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


def get_constraints_from_form(form):

    constraints = {}
    for constraint in POSSIBLE_CONSTRAINTS:
        form_val = form.get(constraint)
        if form_val is not None:
            form_val = form_val.strip()
            if form_val == '':
                form_val = None
            else:
                form_val = float(form_val)
        if form_val is not None:
            constraints[constraint] = form_val

    return constraints


def get_sol_pitch_roll(att_fit, date):
    sun_pitch = ska_sun.pitch(ra=att_fit.ra, dec=att_fit.dec, time=date)
    off_nom_roll = ska_sun.off_nominal_roll(att=att_fit, time=date)
    return sun_pitch, off_nom_roll


def find_solutions_and_get_context():
    stars_text = request.form.get('stars_text', '')
    context = {}
    if stars_text.strip() == '':
        # Get date for solution, defaulting to NOW for any blank input
        date_solution = request.form.get('date_solution', '').strip() or None
        stars = get_stars_from_maude(date_solution)

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

    # Keep any constraints in the form for next submission
    for constraint in POSSIBLE_CONSTRAINTS:
        form_val = request.form.get(constraint)
        if form_val is not None:
            context[constraint] = form_val

    # And get the constraints for Constraints class
    constraints = get_constraints_from_form(request.form)

    # If there are supplied constraints, create a Constraints object - but don't create
    # this at all if there are no constraints.
    if constraints:
        fa_constraints = find_attitude.Constraints(**constraints)
    else:
        fa_constraints = None

    # Save the inputs for debugging
    context['inputs'] = f"{stars} \n tolerance={tolerance} \n constraints={constraints} \n version={find_attitude.__version__}"

    try:
        solutions = find_attitude_solutions(stars, tolerance=tolerance, constraints=fa_constraints)
    except Exception:
        import traceback
        context['error_message'] = traceback.format_exc()
        return context

    # No solutions, bummer.
    if not solutions:
        context['error_message'] = ('No matching solutions found.\n'
                                    'Try increasing distance tolerance.')
        return context

    # Reference date
    date = context.get('date_solution', None)
    date = CxoTime(date) if date else CxoTime.now()

    context['solutions'] = []
    for solution in solutions:
        tbl = solution['summary']
        tbl['YAG'].format = '.2f'
        tbl['ZAG'].format = '.2f'
        tbl['MAG_ACA'].format = '.2f'
        summary_lines = tbl.pformat(max_width=-1, max_lines=-1)
        sol = {'att_fit': solution['att_fit'],
               'summary': os.linesep.join(summary_lines)}
        sol['date'] = date
        sol['pitch'], sol['roll'] = get_sol_pitch_roll(solution['att_fit'], date)
        context['solutions'].append(sol)

    return context
