# Licensed under a 3-clause BSD style license - see LICENSE.rst
import os

from flask import Blueprint, request

from kadi import __version__
from find_attitude.find_attitude import get_stars_from_text, find_attitude_solutions, logger
from logging import CRITICAL
from kadi_apps.rendering import render_template

# Only emit critical messages
logger.level = CRITICAL
for hdlr in logger.handlers:
    logger.setLevel(CRITICAL)


blueprint = Blueprint(
    'find_attitude',
    __name__,
    template_folder='templates',
)


@blueprint.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        context = find_solutions_and_get_context()
    else:
        context = {}

    context['kadi_version'] = __version__
    context['distance_tolerance'] = float(request.form.get('distance_tolerance', '2.5'))

    if context.get('solutions'):
        context['subtitle'] = ': Solution'
    elif context.get('error_message'):
        context['subtitle'] = ': Error'

    return render_template(
        'find_attitude/index.html',
        **context
    )


def find_solutions_and_get_context():
    stars_text = request.form.get('stars_text', '')
    context = {'stars_text': stars_text}

    # First parse the star text input
    try:
        stars = get_stars_from_text(stars_text)
    except Exception as err:
        context['error_message'] = ("{}\n"
                                    "Does it look like one of the examples?"
                                    .format(err))
        return context

    # Try to find solutions
    tolerance = float(request.form.get('distance_tolerance', '2.5'))
    try:
        solutions = find_attitude_solutions(stars, tolerance=tolerance)
    except Exception:
        import traceback
        context['error_message'] = traceback.format_exc()
        return context

    # No solutions, bummer.
    if not solutions:
        context['error_message'] = ('No matching solutions found.\n'
                                    'Try increasing distance and/or magnitude tolerance.')
        return context

    context['solutions'] = []
    for solution in solutions:
        summary_lines = solution['summary'].pformat(max_width=-1, max_lines=-1)
        sol = {'att_fit': solution['att_fit'],
               'summary': os.linesep.join(summary_lines)}
        context['solutions'].append(sol)

    return context
