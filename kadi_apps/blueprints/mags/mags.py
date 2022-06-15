# Licensed under a 3-clause BSD style license - see LICENSE.rst
from flask import Blueprint, render_template, request

from kadi_apps.blueprints.kadi import CONTEXT


blueprint = Blueprint('blueprint', __name__, template_folder='templates')


@blueprint.route("/")
def mags():
    agasc_id = request.args.get('agasc_id', None)
    print('GOT AGASC_ID:', agasc_id)
    if agasc_id is not None:
        try:
            agasc_id = int(agasc_id)
        except Exception:
            agasc_id = None

    url = ''
    if agasc_id:
        agasc_id_1 = f'{agasc_id:010d}'
        url = (
            'https://cxc.cfa.harvard.edu/mta/ASPECT/agasc'
            f'/supplement_reports/stars/{agasc_id_1[:3]}/{agasc_id}/index.html'
        )

    return render_template(
        'mags/index.html',
        url=url,
        **CONTEXT
    )
