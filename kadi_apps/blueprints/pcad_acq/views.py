# Licensed under a 3-clause BSD style license - see LICENSE.rst
from flask import Blueprint, request

from kadi_apps.rendering import render_template

from .pcad_table import get_acq_table

blueprint = Blueprint('pcad_acq_blueprint', __name__, template_folder='templates')


@blueprint.route("/")
def pcad_acq():
    obsid = request.args.get('obsid', '')
    if obsid:
        try:
            obsid = int(obsid)
        except Exception:
            obsid = ''

    pcad_data = ''
    if obsid:
        pcad_data = get_acq_table(f'{obsid:05d}')

    return render_template(
        'pcad_table/acq.html',
        pcad_data=pcad_data,
        obsid=obsid,
    )
