# Licensed under a 3-clause BSD style license - see LICENSE.rst
from flask import Blueprint, request

from kadi import events
from kadi_apps.rendering import render_template


blueprint = Blueprint('mica_blueprint', __name__, template_folder='templates')


@blueprint.route("/")
def mica():
    obsid = request.args.get('obsid_or_date', None)
    print('GOT OBSID OR DATE:', obsid)
    if obsid is not None:
        try:
            obsid = int(obsid)
        except Exception:
            try:
                obsids = events.obsids.filter(start=obsid)
                obsid = obsids[0].obsid
            except Exception:
                obsid = None

    mica_url = ''
    if obsid:
        obsid = f'{obsid:05d}'
        mica_url = f'https://icxc.harvard.edu/aspect/mica_reports/{obsid[:2]}/{obsid}/index.html'

    return render_template(
        'mica/index.html',
        mica_url=mica_url,
    )
