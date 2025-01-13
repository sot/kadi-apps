# Licensed under a 3-clause BSD style license - see LICENSE.rst
import os
from io import StringIO
from logging import CRITICAL

import astropy.units as u
import find_attitude
import numpy as np
import ska_sun
from astropy.table import Table
from cxotime import CxoTime
from find_attitude.find_attitude import (find_attitude_solutions,
                                         get_stars_from_text, logger)
from flask import Blueprint, request
from kadi import __version__
from maude import get_msids
from Quaternion import Quat, normalize

from kadi_apps.rendering import render_template

DEFAULT_CONSTRAINTS = {'distance_tolerance': 2.5,
            'pitch_err': 1.5,
            'att_err': 4.0,
            'mag_err': 1.5,
            'off_nom_roll_max': 2.0}

POSSIBLE_CONSTRAINTS = ["pitch", "pitch_err",
                        "att", "att_err",
                        "off_nom_roll_max",
                        "min_stars",
                        "mag_err"]

# Only emit critical messages
logger.level = CRITICAL
for hdlr in logger.handlers:
    logger.setLevel(CRITICAL)


blueprint = Blueprint(
    'find_attitude',
    __name__,
    template_folder='templates',
)


def get_telem_from_maude(date=None):


    msids = ["aoattqt1", "aoattqt2", "aoattqt3", "aoattqt4"]
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

    quat = Quat(q=[out[f"AOATTQT{ii}"] for ii in [1, 2, 3, 4]])

    return CxoTime(results[0]['times'][-1]).date, tbl, quat




@blueprint.route("/", methods=['GET', 'POST'])
def index():
    context = {}
    if request.method == 'POST':
        action = request.form.get('action')
        context = find_solutions_and_get_context(action)
    else:
        context = {}

    context['kadi_version'] = __version__

    # Update some constraints to their default values if not set.
    for key, value in DEFAULT_CONSTRAINTS.items():
        form_val = request.form.get(key)
        if form_val is not None and form_val.strip() != "":
            value = float(form_val)
            context[key] = value
        if key not in context:
            context[key] = value

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
            if form_val == "":
                form_val = None
            else:
                if constraint == 'att':
                    form_val = normalize([float(val) for val in form_val.split(",")])
                else:
                    form_val = float(form_val)
        if form_val is not None:
            constraints[constraint] = form_val

    date = form.get('date_solution', '').strip() or None
    constraints['date'] = date

    return constraints


def get_sol_pitch_roll(att_fit, date):
    sun_pitch = ska_sun.pitch(ra=att_fit.ra, dec=att_fit.dec, time=date)
    off_nom_roll = ska_sun.off_nominal_roll(att=att_fit, time=date)
    return sun_pitch, off_nom_roll


def find_solutions_and_get_context(action):
    stars_text = request.form.get('stars_text', '')
    context = {}
    att_est = None
    if stars_text.strip() == '' or action == 'gettelem':
        # Get date for solution, defaulting to NOW for any blank input
        date_solution = request.form.get('date_solution', '').strip() or None
        date, stars, att_est = get_telem_from_maude(date_solution)

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
        context['date_solution'] = date
        context['att'] = f"{att_est.q[0]:.8f}, {att_est.q[1]:.8f}, {att_est.q[2]:.8f}, {att_est.q[3]:.8f}"

        # calculate the pitch
        sun_pitch = ska_sun.pitch(ra=att_est.ra, dec=att_est.dec, time=date)
        context['pitch'] = f"{sun_pitch:.2f}"

    else:
        context['stars_text'] = stars_text
        date_solution = request.form.get('date_solution', '').strip() or None

        # First parse the star text input
        try:
            stars = get_stars_from_text(stars_text)
            context['date_solution'] = date_solution
        except Exception as err:
            context['error_message'] = ("{}\n"
                                        "Does it look like one of the examples?"
                                        .format(err))
            return context

        att_est_text = request.form.get("att", "").strip() or None
        if att_est_text:
            try:
                att_est = Quat(q=[float(val) for val in att_est_text.split(",")])
            except Exception:
                pass

    if action == 'gettelem':
        # don't continue to get the solution, just return with the updated context
        return context

    # Try to find solutions
    tolerance = float(request.form.get('distance_tolerance', '2.5'))

    # Keep any constraints in the form for next submission
    for constraint in POSSIBLE_CONSTRAINTS:
        form_val = request.form.get(constraint)
        if form_val is not None:
            context[constraint] = form_val

    if action == 'calc_solution_constraints':
        # And get the constraints for Constraints class
        constraints = get_constraints_from_form(request.form)
        fa_constraints = find_attitude.Constraints(**constraints)
        context["inputs"] = f"{stars} \n tolerance={tolerance} \n constraints={constraints}"
    else:
        fa_constraints = None
        context["inputs"] = f"{stars} \n tolerance={tolerance}"

    context["find_attitude_version"] = find_attitude.__version__

    try:
        solutions = find_attitude_solutions(stars, tolerance=tolerance, constraints=fa_constraints)
    except Exception:
        import traceback
        context['error_message'] = traceback.format_exc()
        return context

    # No solutions, bummer.
    if not solutions:
        context['error_message'] = ('No matching solutions found.\n'
                                    'Try increasing distance tolerance or relaxing optional constraints (if applied).')
        return context

    # Reference date
    date = context.get("date_solution", None)
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
        sol["date"] = date
        pitch, off_nominal_roll = get_sol_pitch_roll(solution['att_fit'], date)
        sol['pitch'] = f"{pitch:.3f}"
        sol['roll'] = f"{off_nominal_roll:.3f}"
        if att_est is not None:
            sol["att_est"] = att_est
            att_est_dq = att_est.dq(solution['att_fit'])
            sol["dyaw"] = att_est_dq.yaw
            sol["dpitch"] = att_est_dq.pitch

        context['solutions'].append(sol)

    return context
