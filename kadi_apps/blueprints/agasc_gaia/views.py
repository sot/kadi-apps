#case
# Licensed under a 3-clause BSD style license - see LICENSE.rst
from flask import Blueprint, request

from . import star_report
from kadi_apps.rendering import render_template


blueprint = Blueprint('agasc_gaia', __name__, template_folder='templates')


@blueprint.route("/")
def index():
    agasc_id = request.args.get('agasc_id', '')
    if agasc_id:
        try:
            agasc_id = int(agasc_id)
        except Exception:
            agasc_id = ''

    agasc_gaia_data = ''
    if agasc_id:
        report = star_report.Report(agasc_id)
        agasc_gaia_data = report.get_html()

    return render_template(
        'agasc_gaia/index.html',
        agasc_gaia_data=agasc_gaia_data,
        agasc_id=agasc_id,
    )
