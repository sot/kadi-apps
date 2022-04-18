import re
import shlex
from flask import Blueprint, request, url_for
from collections import namedtuple
# from flask import request

# import logging
# import json
# import os


# kadi.events.query is imported before models so django is setup
from kadi.events import query  # noqa
from kadi.events import models
import kadi.events
from kadi_apps.rendering import render_template


blueprint = Blueprint(
    'kadi',
    __name__,
    template_folder='templates',
)


EVENT_MODELS = {
    em['name']: em for em in sorted([
        {
            'name': name,
            'description': model.__doc__.strip().splitlines()[0],
            'model': model,
        }
        for name, model in models.get_event_models().items()
    ], key=lambda x: x['description'])
}


def filter_events(
        queryset,
        filter_string,
        filter_string_field='start',
        filter_string_op='startswith'
):
    tokens = shlex.split(filter_string)
    for token in tokens:
        match = re.match(r'(\w+)(=|>|<|>=|<=)([^=><]+)$', token)
        if match:
            op = {
                '=': 'exact',
                '>=': 'gte',
                '<=': 'lte',
                '<': 'lt',
                '>': 'gt'
            }[match.group(2)]
            key = '{}__{}'.format(match.group(1), op)
            val = match.group(3)
            queryset = queryset.filter(**{key: val})
        elif re.match(r'[12]\d{3}', filter_string):
            key = 'start__startswith'
            queryset = queryset.filter(**{key: filter_string})
        else:
            key = '{}__{}'.format(filter_string_field, filter_string_op)
            queryset = queryset.filter(**{key: filter_string})
    return queryset


@blueprint.route("/")
def index():
    """Return help page for web-kadi API access"""
    return render_template(
        'index.html',
    )


@blueprint.route("/events/")
def events():
    """Return help page for web-kadi API access"""
    return render_template(
        'events/events.html',
    )


def _get_args(exclude=()):
    import ast
    app_kwargs = {}
    for key, val in request.args.items():
        if key in exclude:
            continue
        try:
            # See if it parses as some native Python literal like float or int
            app_kwargs[key] = ast.literal_eval(val)
        except Exception:
            # Use the string itself
            app_kwargs[key] = val
    return app_kwargs


@blueprint.route("/events/<string:model_name>/<string:primary_key>")
def event_detail(model_name, primary_key):
    """Return a list of kadi events"""

    assert model_name in EVENT_DETAIL, f'Unknown model {model_name}'
    event_detail_spec = EVENT_DETAIL[model_name]
    model_pk = event_detail_spec.model._meta.pk.name
    field_names = [
        field.name for field in event_detail_spec.model.get_model_fields()
        # if field.name not in event_detail_spec.ignore_fields
    ]

    kwargs = _get_args()
    event_filter = kwargs.get('filter', '')
    sort = kwargs.get('sort', '')
    index = kwargs.get('index', '')

    # this might be less than ideal, but it is what django kadi does
    # the whole set is assembled only to get the previous and next event
    kadi_events = getattr(kadi.events, model_name + 's').all()
    kadi_events = filter_events(
        kadi_events,
        event_filter,
        event_detail_spec.filter_string_field,
        event_detail_spec.filter_string_op
    )
    if sort:
        kadi_events = kadi_events.order_by(sort)

    next_event_url = ''
    previous_event_url = ''
    if index != '':
        index = int(index)
        if index + 1 < kadi_events.count():
            next_event_url = url_for(
                'kadi.event_detail', model_name=model_name, filter=event_filter, sort=sort,
                primary_key=kadi_events[index + 1].pk,
                index=index + 1
            )
        if index > 0:
            previous_event_url = url_for(
                'kadi.event_detail', model_name=model_name, filter=event_filter, sort=sort,
                primary_key=kadi_events[index - 1].pk,
                index=index - 1
            )
    else:
        next_events = kadi_events.filter(pk__gt=primary_key)
        next_event_url = url_for(
            'kadi.event_detail', model_name=model_name, filter=event_filter, sort=sort,
            primary_key=next_events[0].pk if next_events.count() else '',
        )
        prev_events = kadi_events.filter(pk__lt=primary_key)
        previous_event_url = url_for(
            'kadi.event_detail', model_name=model_name, filter=event_filter, sort=sort,
            primary_key=prev_events[-1].pk if prev_events.count() else '',
        )

    event = kadi_events.get(**{model_pk: primary_key})
    formats = {
        field.name: getattr(field, '_kadi_format', '{}')
        for field in event_detail_spec.model.get_model_fields()
    }
    name_vals = [
        [field_name, formats[field_name].format(getattr(event, field_name, ''))]
        for field_name in field_names
    ]

    try:
        obsid = event.get_obsid()
    except Exception:
        obsid = ''

    return render_template(
        'events/event_detail.html',
        model_name=model_name,
        filter=event_filter,
        sort=sort,
        index=index,
        model_description=EVENT_MODELS[model_name]['description'],
        primary_key=primary_key,
        names_vals=name_vals,
        next_event_url=next_event_url,
        obsid=obsid,
        previous_event_url=previous_event_url,
    )


@blueprint.route("/events/<string:model_name>/list")
def event_list(model_name):
    """Return a list of kadi events"""

    assert model_name in EVENT_LIST, f'Unknown model {model_name}'

    # model/view definitions
    event_list_spec = EVENT_LIST[model_name]
    model = event_list_spec.model
    model_pk = model._meta.pk.name
    ignore_fields = event_list_spec.ignore_fields
    field_names = [
        field.name for field in model.get_model_fields()
        if field.name not in ignore_fields
    ]
    formats = {
        field.name: getattr(field, '_kadi_format', '{}')
        for field in model.get_model_fields()
    }
    paginate_by = event_list_spec.paginate_by
    filter_string_field = event_list_spec.filter_string_field
    filter_string_op = event_list_spec.filter_string_op
    reverse_sort = event_list_spec.reverse_sort

    kwargs = _get_args()
    event_filter = kwargs.get('filter', '')
    page = kwargs.get('page', 1)
    sort = kwargs.get('sort', None)
    if not sort:  # No sort explicitly set in request
        sort = model._meta.ordering[0]
        if reverse_sort:
            sort = '-' + sort
    sort_field = sort.lstrip('-')
    descending = sort.startswith('-')

    kadi_events = getattr(kadi.events, model_name + 's').all()
    kadi_events = filter_events(kadi_events, event_filter, filter_string_field, filter_string_op)
    if sort:
        kadi_events = kadi_events.order_by(sort)

    # pagination stuff
    n_rows = len(kadi_events)
    n_pages = n_rows // paginate_by + (1 if n_rows % paginate_by else 0)
    page_obj = {
        'has_previous': page > 1,
        'has_next': page < n_pages,
        'previous_page_number': page - 1 if page > 1 else None,
        'next_page_number': page + 1 if page < n_pages else None,
        'number': page,
        'num_pages': n_pages,
        'start_index': page * paginate_by,
    }

    if n_pages > 1:
        subset = slice((page - 1) * paginate_by, page * paginate_by, 1)
        kadi_events = kadi_events[subset]

    # the table headers. Most of this mess is just for sorting (only the name is not)
    headers = [
        {
            'field_name': field.name,
            'sort_by': field.name == sort_field,
            'header_class': 'class="SortBy"' if field.name == sort_field else '',
            'sort_icon':
            'asc-desc' if field.name != sort_field else ('asc' if descending else 'desc')
        }
        for field in model.get_model_fields() if field.name not in ignore_fields
    ]
    for header in headers:
        args = kwargs.copy()
        if header['field_name'] != sort_field:
            args['sort'] = header['field_name']
            icon = 'asc-desc'
        elif descending:
            icon = 'asc'
            args['sort'] = header['field_name']
        else:
            icon = 'desc'
            args['sort'] = '-' + header['field_name']
        url = url_for('.event_list', model_name=model_name, **args)
        images = url_for('static', filename='images')
        header['header_class'] = 'class="SortBy"' if header['field_name'] == sort_field else ''
        header['sort_icon'] = f'<a href="{url}"> <img src="{images}/{icon}.gif"></a>'

    # the table content, the tuple's first entry is an absolute index
    j_start = (page - 1) * paginate_by  # pages start at 1
    event_rows = [
        (j_start + j, [formats[fn].format(getattr(ke, fn)) for fn in field_names])
        for j, ke in enumerate(kadi_events)
    ]

    return render_template(
        'events/event_list.html',
        model_name=model_name,
        model_pk_col_index=field_names.index(model_pk) + 1,  # jinja indices start at 1
        headers=headers,
        event_rows=event_rows,
        filter=event_filter,
        page_obj=page_obj,
        sort=sort,
        model_description=EVENT_MODELS[model_name]['description'],
        filter_help=FILTER_HELP,
    )


FILTER_HELP = """
<strong>Filtering help</strong>
<p><p>
Enter one or more filter criteria in the form <tt>column-name operator value</tt>,
with NO SPACE between the <tt>column-name</tt> and the <tt>value</tt>.

<p>
Examples:
<pre>
  start>2013
  start>2013:001 stop<2014:001
  start<2001 dur<=1800 n_dwell=2   [Maneuver]
</pre>

<p><p>
For some event types like <tt>MajorEvent</tt> which have one or more key
text fields, you can just enter a single word to search on.

<p>
Examples:
<pre>
  safe                            [MajorEvent]
  start>2013 eclipse              [MajorEvent]
  sequencer start>2010 stop<2011  [CAP from iFOT]
</pre>
"""


EVENT_LIST_DEFAULTS = {
    'ignore_fields': ['tstart', 'tstop'],
    'filter_string_field': 'start',
    'filter_string_op': 'startswith',
    'paginate_by': 30,
    'reverse_sort': True,
}

EVENT_LIST = [
    {
        'name': 'obsid',
        'model': models.Obsid,
    },
    {
        'name': 'tsc_move',
        'model': models.TscMove,
        'filter_string_field': 'start_det',
    },
    {
        'name': 'dark_cal_replica',
        'model': models.DarkCalReplica,
    },
    {
        'name': 'dark_cal',
        'model': models.DarkCal,
    },
    {
        'name': 'scs107',
        'model': models.Scs107,
    },
    {
        'name': 'grating_move',
        'model': models.GratingMove,
    },
    {
        'name': 'load_segment',
        'model': models.LoadSegment,
    },
    {
        'name': 'fa_move',
        'model': models.FaMove,
    },
    {
        'name': 'dump',
        'model': models.Dump,
    },
    {
        'name': 'eclipse',
        'model': models.Eclipse,
    },
    {
        'name': 'manvr',
        'model': models.Manvr,
    },
    {
        'name': 'dwell',
        'model': models.Dwell,
    },
    {
        'model': models.ManvrSeq
    },
    {
        'name': 'safe_sun',
        'model': models.SafeSun,
    },
    {
        'name': 'normal_sun',
        'model': models.NormalSun,
    },
    {
        'name': 'major_event',
        'model': models.MajorEvent,
        'filter_string_field': 'descr',
        'filter_string_op': 'icontains',
        'reverse_sort': True,
    },
    {
        'name': 'cap',
        'model': models.CAP,
        'filter_string_field': 'title',
        'filter_string_op': 'icontains',
        'ignore_fields': EVENT_LIST_DEFAULTS['ignore_fields'] + ['descr', 'notes', 'link'],
    },
    {
        'name': 'dsn_comm',
        'model': models.DsnComm,
        'filter_string_field': 'activity',
        'filter_string_op': 'icontains',
    },
    {
        'name': 'orbit',
        'model': models.Orbit,
        'ignore_fields': EVENT_LIST_DEFAULTS['ignore_fields'] + ['t_perigee'],
    },
    {
        'model': models.OrbitPoint,
    },
    {
        'name': 'pass_plan',
        'model': models.PassPlan,
        'reverse_sort': True
    },
    {
        'model': models.RadZone, 'name': 'rad_zone',
    },
    {
        'model': models.LttBad, 'name': 'ltt_bad',
    }
]
_cols = [
    'name', 'model', 'ignore_fields', 'filter_string_field', 'filter_string_op', 'reverse_sort',
    'paginate_by'
]
EventListSpec = namedtuple(
    'EventListSpec', _cols, defaults=[EVENT_LIST_DEFAULTS[k] for k in _cols[2:]]
)
EVENT_LIST = {ev['name']: EventListSpec(**ev) for ev in EVENT_LIST if 'name' in ev}


EVENT_DETAIL_DEFAULTS = {
    'filter_string_field': 'start',
    'filter_string_op': 'startswith',
}


EVENT_DETAIL = [
    {
        'name': 'obsid',
        'model': models.Obsid,
    },
    {
        'name': 'tsc_move',
        'model': models.TscMove,
        'filter_string_field': 'start_det',
    },
    {
        'name': 'dark_cal_replica',
        'model': models.DarkCalReplica,
    },
    {
        'name': 'dark_cal',
        'model': models.DarkCal,
    },
    {
        'name': 'scs107',
        'model': models.Scs107,
    },
    {
        'name': 'grating_move',
        'model': models.GratingMove,
    },
    {
        'name': 'load_segment',
        'model': models.LoadSegment,
    },
    {
        'name': 'fa_move',
        'model': models.FaMove,
    },
    {
        'name': 'dump',
        'model': models.Dump,
    },
    {
        'name': 'eclipse',
        'model': models.Eclipse,
    },
    {
        'name': 'manvr',
        'model': models.Manvr,
    },
    {
        'name': 'dwell',
        'model': models.Dwell,
    },
    {
        'model': models.ManvrSeq,
    },
    {
        'name': 'safe_sun',
        'model': models.SafeSun,
    },
    {
        'name': 'normal_sun',
        'model': models.NormalSun,
    },
    {
        'name': 'major_event',
        'model': models.MajorEvent,
        'filter_string_field': 'descr',
        'filter_string_op': 'icontains',
    },
    {
        'name': 'cap',
        'model': models.CAP,
        'filter_string_field': 'title',
        'filter_string_op': 'icontains',
    },
    {
        'name': 'dsn_comm',
        'model': models.DsnComm,
        'filter_string_field': 'activity',
        'filter_string_op': 'icontains',
    },
    {
        'name': 'orbit',
        'model': models.Orbit,
    },
    {
        'model': models.OrbitPoint,
    },
    {
        'name': 'rad_zone',
        'model': models.RadZone,
    },
    {
        'name': 'pass_plan',
        'model': models.PassPlan,
    },
    {
        'name': 'ltt_bad',
        'model': models.LttBad,
    }
]
_cols = [
    'name', 'model', 'filter_string_field', 'filter_string_op'
]
EventDetailSpec = namedtuple(
    'EventDetailSpec', _cols, defaults=[EVENT_DETAIL_DEFAULTS[k] for k in _cols[2:]]
)
EVENT_DETAIL = {ev['name']: EventDetailSpec(**ev) for ev in EVENT_DETAIL if 'name' in ev}
