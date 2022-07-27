
from flask import Blueprint

from kadi_apps.rendering import render_template


blueprint = Blueprint(
    'kalman_watch',
    __name__,
    template_folder='templates',
)


@blueprint.route("/", methods=['GET'])
def recent_perigees():

    context = {
        'title': 'Recent Perigee Passages',
    }

    return render_template(
        'perigee_list.html',
        **context
    )


@blueprint.route("/<year>", methods=['GET'])
def yearly_perigees(year):

    year = int(year)

    context = {
        'year': year,
        'title': f'Perigee Kalman index page {year}',
    }

    return render_template(
        'perigee_list.html',
        **context
    )


@blueprint.route("/<year>/<date>", methods=['GET'])
def perigee(year, date):

    context = {
        'year': year,
        'date': date,
        'title': f'{date} {year} Perigee Kalman Plot',
    }

    return render_template(
        'perigee_detail.html',
        **context
    )
