# Licensed under a 3-clause BSD style license - see LICENSE.rst
from flask import Blueprint, request

from kadi_apps.rendering import render_template

from .pcad_table import get_acq_table, get_acq_date_for_obsid, get_closest_npnt_start_time


blueprint = Blueprint('pcad_acq_blueprint', __name__, template_folder='templates')


@blueprint.route("/", methods=["POST", "GET"])
def pcad_acq():
    obsid = ''
    load_name = ''
    pcad_data = ''

    if request.method == 'POST':
        obsid = request.form.get('obsid', '')
        date = request.form.get('date', '')
        load_name = request.form.get('load_name', '')

    if request.method == 'GET':
        obsid = request.args.get('obsid', '')
        load_name = request.args.get('load_name', '')
        date = request.args.get('date', '')

    if obsid.strip() is not '':
        acq_date = get_acq_date_for_obsid(int(obsid), load_name=load_name)
    elif date.strip() is not '':
        acq_date = get_closest_npnt_start_time(date)

    pcad_data = get_acq_table(acq_date)


    # If there is a GUIDE row, render that separately
    acq_rows = None
    for row in pcad_data:
        if row['AOACASEQ'] == "GUID":
            acq_rows = [row]
            break

    return render_template(
        'pcad_table/acq.html',
        pcad_data=pcad_data,
        acq_rows=acq_rows,
    )
