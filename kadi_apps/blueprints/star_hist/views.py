# Licensed under a 3-clause BSD style license - see LICENSE.rst
from flask import Blueprint, request
from kadi_apps.rendering import render_template

blueprint = Blueprint('star_hist_blueprint', __name__, template_folder='templates')


@blueprint.route("/")
def star_hist():
    agasc_id = request.args.get('agasc_id', None)
    if agasc_id is not None:
        try:
            agasc_id = int(agasc_id)
        except Exception:
            agasc_id = None
    start = request.args.get('start', None)
    stop = request.args.get('stop', None)
    if start == '':
        start = None
    if stop == '':
        stop = None

    context = {}
    context['agasc_id'] = agasc_id or ''
    context['start'] = start or ''
    context['stop'] = stop or ''

    if agasc_id:
        import mica.web.star_hist
        import agasc
        from agasc.agasc import IdNotFound
        try:
            agasc_info = agasc.get_star(agasc_id)
            context['star_info'] = [(key, agasc_info[key]) for key in agasc_info.dtype.names]
        except IdNotFound:
            context['star_info'] = []
            pass
        acq_table, gui_table = mica.web.star_hist.get_star_stats(agasc_id, start, stop)
        if len(acq_table):
            context['acq_table'] = acq_table
        if len(gui_table):
            context['gui_table'] = gui_table
            reports_url = (
                "https://cxc.cfa.harvard.edu/mta/ASPECT/agasc/supplement_reports/stars/"
                + f'{int(agasc_id//1e7):03d}/{agasc_id}/index.html')
            context['reports_url'] = reports_url
    return render_template(
        'star_hist/star_hist.html',
        **context
    )
