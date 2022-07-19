from flask import Blueprint
from flask import request

import logging
import json


APPS = {
    ('agasc',): ['get_star', 'get_stars', 'get_agasc_cone'],
    ('mica', 'starcheck'): ['get_*'],
    ('mica', 'archive', 'aca_dark', 'dark_cal'): [
        'get_dark_cal_id', 'get_dark_cal_ids', 'get_dark_cal_image', 'get_dark_cal_props'
    ],
    ('kadi', 'events'): ['*.filter'],
    ('kadi', 'commands'): ['get_cmds', 'get_observations', 'get_starcats'],
    ('kadi', 'commands', 'states'): ['get_states']
}


blueprint = Blueprint('ska_api', __name__, template_folder='templates')


class NotFound(Exception):
    pass


@blueprint.route("/<path:path>")
def api(path):
    logger = logging.getLogger('kadi_apps')
    try:
        app_func = _get_function(path)
        app_kwargs = _get_args(exclude=[])
        table_format = app_kwargs.pop('table_format', None)
        strict_encode = app_kwargs.pop('strict_encode', True)

        logger.info(f'{path.replace("/", ".")}(')
        logger.info(f'    **{app_kwargs}')
        logger.info(f')')

        dumper = APIEncoder(table_format=table_format, strict_encode=strict_encode)
        output = app_func(**app_kwargs)
        output = dumper.encode(output).encode('utf-8')
        return output, 200
    except NotFound as e:
        logger.info(f'NotFound: {e}')
        return {'ok': False, 'error': str(e)}, 404
    except Exception as e:
        logger.info(f'Exception: {e}')
        return {'ok': False, 'error': str(e)}, 500


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
        raise NotFound('no app module found for URL path {}'.format(path))

    if not func_parts:
        raise NotFound('no function parts found for URL path {}'.format(path))

    # Check that the function is allowed
    func_name = '.'.join(func_parts)
    if not any(fnmatch(func_name, app_glob) for app_glob in app_globs):
        raise NotFound(
            'function {} was not found or is not allowed for {}'
            .format(func_name, '.'.join(app_module_parts))
        )

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
    def __init__(self, table_format=None, strict_encode=True, **kwargs):
        self.table_format = table_format or 'rows'
        super(APIEncoder, self).__init__()
        self.strict_encode = strict_encode

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
        import numpy as np

        # Potentially convert something with a `table` property to an astropy Table.
        if hasattr(obj, 'table') and isinstance(obj.__class__.table, property):
            obj_table = obj.table
            if isinstance(obj_table, Table):
                obj = obj_table

        if type(obj) in [np.int32, np.int64]:
            return int(obj)

        elif type(obj) in [np.float32, np.float64]:
            return float(obj)

        elif isinstance(obj, np.ma.MaskedArray):
            return {
                'data': obj.tolist(),
                'mask': obj.mask.tolist()
            }

        elif isinstance(obj, np.ndarray):
            return obj.tolist()

        elif isinstance(obj, Table):
            return self.encode_table(obj)

        elif isinstance(obj, bytes):
            return obj.decode('utf-8')

        else:
            try:
                out = super(APIEncoder, self).default(obj)
            except TypeError:
                if not self.strict_encode:
                    # Last gasp to never fail the JSON encoding.  This is mostly helpful
                    # for debugging instead of an inscrutable exception
                    out = repr(obj)
                else:
                    # re-raise the same exception. This will cause a 500 error (as it should).
                    # The entrypoint can decide to include the exception message in the response.
                    raise
        return out
