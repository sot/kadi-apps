# Licensed under a 3-clause BSD style license - see LICENSE.rst
from flask import Blueprint, render_template, request

from kadi_apps.blueprints.kadi import CONTEXT

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
        obsid = f'{obsid:05d}'
        pcad_data = get_acq_table(obsid)

    return render_template(
        'pcad_table/acq.html',
        pcad_data=pcad_data,
        **CONTEXT
    )
