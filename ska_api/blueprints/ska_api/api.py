from flask import Blueprint, render_template
from flask import request

import logging
import json
import os


APPS = {
    ('mica', 'starcheck'): ['get_*'],
    ('kadi', 'events'): ['*.filter'],
    ('kadi', 'commands'): ['get_cmds'],
    ('kadi', 'commands', 'states'): ['get_states']}


blueprint = Blueprint('astromon', __name__, template_folder='templates')


@blueprint.route("/")
def show_help():
    """Return help page for web-kadi API access"""
    return render_template('help.html')


@blueprint.route("/<path:path>")
def api(path):
    try:
        app_func = _get_function(path)
        app_kwargs = _get_args(exclude=['table_format'])
        logger = logging.getLogger()
        logger.info(f'{path.replace("/", ".")}(')
        logger.info(f'    **{app_kwargs}')
        logger.info(f')')

        dumper = APIEncoder(request.args.get('table_format', None))
        output = app_func(**app_kwargs)
        output = dumper.encode(output).encode('utf-8')
        return output, 200
    except Exception as e:
        logger.info(f'Exception: {e}')
        return {'ok': False, 'error': str(e)}


def _get_function(path):
    from fnmatch import fnmatch
    from importlib import import_module

    # Get the module with the app function and the function within that module
    module_parts = []
    module_func_parts = path.split('/')
    app_module = None
    for ii, module_part in enumerate(module_func_parts):
        module_parts = module_func_parts[:ii + 1]

        # Ensure that the module parts correspond to an allowed app
        if tuple(module_parts) in APPS:
            app_globs = APPS[tuple(module_parts)]
            app_module_parts = module_parts
            try:
                app_module = import_module('.'.join(module_parts))
            except Exception:
                import sys
                err_str = '{} {} {} {}'.format(sys.path, sys.prefix, module_parts,
                                               '.'.join(module_parts))
                raise ImportError(err_str)
            func_parts = module_func_parts[ii + 1:]

    if app_module is None:
        raise ValueError('no app module found for URL path {}'.format(url.path))

    if not func_parts:
        raise ValueError('no function parts found for URL path {}'.format(url.path))

    # Check that the function is allowed
    func_name = '.'.join(func_parts)
    if not any(fnmatch(func_name, app_glob) for app_glob in app_globs):
        raise ValueError('function {} is not allowed for {}'
                         .format(func_name, '.'.join(app_module_parts)))

    app_func = app_module
    for func_part in func_parts:
        app_func = getattr(app_func, func_part)
    return app_func


def _get_args(exclude):
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


class APIEncoder(json.JSONEncoder):
    def __init__(self, table_format=None):
        self.table_format = table_format or 'rows'
        super(APIEncoder, self).__init__()

    def encode_table(self, obj):
        if self.table_format not in ('rows', 'columns'):
            raise ValueError('table_format={} not allowed'.format(self.table_format))

        out = {name: obj[name].tolist() for name in obj.colnames}

        if self.table_format == 'rows':
            # Convert from dict of list to list of dict
            out = [{name: out[name][ii] for name in obj.colnames}
                   for ii in range(len(obj))]

        return out

    def default(self, obj):
        from astropy.table import Table

        # Potentially convert something with a `table` property to an astropy Table.
        if hasattr(obj, 'table') and isinstance(obj.__class__.table, property):
            obj_table = obj.table
            if isinstance(obj_table, Table):
                obj = obj_table

        if isinstance(obj, Table):
            out = self.encode_table(obj)

        elif isinstance(obj, bytes):
            out = obj.decode('utf-8')

        else:
            try:
                print('OOPS')
                out = super(APIEncoder, self).default(obj)
            except TypeError:
                # Last gasp to never fail the JSON encoding.  This is mostly helpful
                # for debugging instead of the inscrutable exception:
                # TypeError: default() missing 1 required positional argument: 'o'
                out = repr(obj)
        return out
