# Licensed under a 3-clause BSD style license - see LICENSE.rst
from flask import Blueprint, request

from kadi_apps.rendering import render_template

from .pcad_table import get_acq_table

blueprint = Blueprint('pcad_acq_blueprint', __name__, template_folder='templates')


@blueprint.route("/")
def pcad_acq():
    obsid_or_date = request.args.get('obsid_or_date', '')
    pcad_data = ''
    if obsid_or_date != '':
        pcad_data = get_acq_table(obsid_or_date)

    return render_template(
        'pcad_table/acq.html',
        pcad_data=pcad_data,
        obsid_or_date=obsid_or_date,
    )
