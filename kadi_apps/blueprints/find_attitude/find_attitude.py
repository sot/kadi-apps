# Licensed under a 3-clause BSD style license - see LICENSE.rst
import os
from io import StringIO
import datetime
import pytz
from logging import CRITICAL
import pprint

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
from ska_helpers.utils import convert_to_int_float_str

from kadi_apps.rendering import render_template

DEFAULT_CONSTRAINTS = {'distance_tolerance': 3.0,
                       'maude_channel': 'FLIGHT',
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


def get_telem_from_maude(date=None, channel="FLIGHT"):
    msids = []
    for msid_root in ["aoacfct", "aoacfid", "aoacyan", "aoaczan", "aoacmag"]:
        msids.extend([f"{msid_root}{ii}" for ii in range(8)])
    msids.extend(["aoattqt1", "aoattqt2", "aoattqt3", "aoattqt4"])

    start = None
    stop = None
    if date is not None:
        start = CxoTime(date) - 5 * u.s
        stop = start + 10 * u.s
        kwargs = {'start': start, 'stop': stop}
    else:
        kwargs = {}
    dat = get_msids(msids, **kwargs, channel=channel)
    results = dat["data"]
    out = {}
    for result in results:
        msid = result["msid"]
        values = np.array(result["values"])
        if len(values) == 0:
            raise ValueError(f"No data for {msid} in time range date={date} start={start} stop={stop}")
        if msid.lower().startswith(("aoacyan", "aoaczan", "aoacmag")):
            if len(values) < 6:
                value = np.median(values)
            else:
                values = np.sort(values)
                value = np.mean(values[2:-2])
        else:
            value = values[-1]
        out[msid] = value

    # Use the time of one of the ACA msids to determine the reference time.
    # result[0] should be AOACFCT0.
    # The quaternions are sampled more frequently so if the last time of
    # one of those is used, an attempt to refetch the data based on
    # one of those times can fail for the case where one is working with
    # the last of the realtime telemetry.
    date_ref = CxoTime(np.median(results[0]['times'])).date

    tbl = Table()
    tbl['slot'] = np.arange(8)
    tbl["AOACFCT"] = [out[f"AOACFCT{ii}"] for ii in range(8)]
    tbl["AOACFID"] = [out[f"AOACFID{ii}"] for ii in range(8)]
    tbl['YAG'] = [out[f"AOACYAN{ii}"] for ii in range(8)]
    tbl['ZAG'] = [out[f"AOACZAN{ii}"] for ii in range(8)]
    tbl['MAG_ACA'] = [out[f"AOACMAG{ii}"] for ii in range(8)]

    # Cut fid lights and non-tracking centroids
    tbl = tbl[(tbl["AOACFID"] != "FID") & (tbl["AOACFCT"] == "TRAK")]

    # Remove the fid light and track columns as not needed for display
    tbl.remove_columns(["AOACFID", "AOACFCT"])

    # Save the date with the table metadata
    tbl.meta['date_solution'] = date_ref

    quat = Quat(q=[out[f"AOATTQT{ii}"] for ii in [1, 2, 3, 4]])

    return date_ref, tbl, quat




@blueprint.route("/", methods=['GET', 'POST'])
def index():
    context = {}
    if request.method == 'POST':
        action = request.form.get('action')
        context = find_solutions_and_get_context(action)
    else:
        context = {}

    local_tz = pytz.timezone('America/New_York')
    local_time = datetime.datetime.now(local_tz)
    generation_time = local_time.strftime("%I:%M:%S%p %Z on %Y-%m-%d")

    context['generation_time'] = generation_time
    context['kadi_version'] = __version__

    # Update some constraints to their default values
    context.update(DEFAULT_CONSTRAINTS)

    # But override with any values from the form
    for key in DEFAULT_CONSTRAINTS:
        form_val = request.form.get(key)
        if form_val is not None:
            context[key] = convert_to_int_float_str(form_val)


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
    maude_channel = request.form.get('maude_channel', 'FLIGHT')
    context["maude_channel"] = maude_channel
    if stars_text.strip() == '' or action == 'gettelem':
        # Get date for solution, defaulting to NOW for any blank input
        date_solution = request.form.get('date_solution', '').strip() or None
        try:
            date, stars, att_est = get_telem_from_maude(date_solution, channel=maude_channel)
        except Exception as err:
            context['error_message'] = (f"{err}\n",
                                        f"Could not fetch telemetry at date={date_solution}.")
            return context

        # Get a formatted version of the stars table that is used for finding
        # the solutions. This gets put back into the web page output.
        if len(stars) == 0:
            context["stars_text"] = "No tracked stars."
        else:
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
            context['error_message'] = (f"{err}\n"
                                        "Does it look like the example?")
            return context


        att_est_text = request.form.get("att", "").strip() or None
        if att_est_text:
            try:
                att_est = Quat(q=[float(val) for val in att_est_text.split(",")])
            except Exception as err:
                context['error_message'] = (f"{err}\n",
                                            "Malformed estimated attitude quaternion.")
                return context

    if action == 'gettelem':
        # don't continue to get the solution, just return with the updated context
        return context

    # Try to find solutions
    tolerance = float(request.form.get('distance_tolerance', '3.0'))

    # Keep any constraints in the form for next submission
    for constraint in POSSIBLE_CONSTRAINTS:
        form_val = request.form.get(constraint)
        if form_val is not None:
            context[constraint] = form_val

    if action == 'calc_solution_constraints':
        # And get the constraints for Constraints class
        try:
            constraints = get_constraints_from_form(request.form)
        except Exception as err:
            context['error_message'] = (f"Error: {err}",
                                        "Malformed constraints.")
            return context
        fa_constraints = find_attitude.Constraints(**constraints)
        context["inputs"] = f"{stars} \n tolerance={tolerance} \n constraints={pprint.pformat(constraints)}"
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
        for col in ['YAG', 'ZAG', 'MAG_ACA']:
            if col in tbl.colnames:
                tbl[col].format = '.2f'
        summary_lines = tbl.pformat(max_width=-1, max_lines=-1)
        sol = {'att_fit': solution['att_fit'],
               'summary': os.linesep.join(summary_lines)}
        sol["date"] = date
        pitch, off_nominal_roll = get_sol_pitch_roll(solution['att_fit'], date)
        sol['pitch'] = pitch
        sol['roll'] = off_nominal_roll
        if att_est is not None:
            sol["att_est"] = att_est
            att_est_dq = att_est.dq(solution['att_fit'])
            sol["dyaw"] = att_est_dq.yaw
            sol["dyaw_arcsec"] = att_est_dq.yaw * 3600
            sol["dpitch"] = att_est_dq.pitch
            sol["dpitch_arcsec"] = att_est_dq.pitch * 3600
            sol["droll"] = att_est_dq.roll0
            sol["droll_arcsec"] = att_est_dq.roll0 * 3600

        context['solutions'].append(sol)

    return context
