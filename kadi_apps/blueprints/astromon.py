import logging
import numpy as np
import json

from pathlib import Path
from astropy.wcs import WCS
from astropy.io import fits
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Row, Table, Column
from astromon import observation
from astromon import db

from cxotime import CxoTime

from flask import Blueprint, current_app, request
import werkzeug
from kadi_apps.authentication import Authentication

blueprint = Blueprint('astromon', __name__)

auth = Authentication()

logger = logging.getLogger('kadi_apps')


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if np.isscalar(obj):
            return int(obj)
        if np.isreal(obj):
            return float(obj)
        return json.JSONEncoder.default(self, obj)


def encode(data):
    return json.loads(json.dumps(dict(data), cls=ComplexEncoder))


@blueprint.route('/regions', methods=['DELETE'])
@auth.login_required
def remove_regions():
    try:
        logger.info('astromon.remove_regions')
        workdir = Path(current_app.config['ASTROMON_OBS_DATA'])
        json_data = request.get_json(force=True)
        regions = json_data['regions']
        logger.info(f'regions: {regions}')
        db.remove_regions(regions, dbfile=workdir / 'astromon.h5')
        return {'regions': regions}, 200
    except werkzeug.exceptions.BadRequest as e:
        logger.info(f'BadRequest in Catalog.add_regions: {e}')
        return {'regions': []}, 400


@blueprint.route('/regions', methods=['POST'])
@auth.login_required
def add_regions():
    try:
        logger.info('astromon.add_regions')
        workdir = Path(current_app.config['ASTROMON_OBS_DATA'])

        json_data = request.get_json(force=True)
        obsid = json_data['obsid']
        regions = json_data.get('regions', None)
        logger.info(f'OBSID: {obsid}')
        logger.info(f'regions: {regions}')

        subdir = (
            workdir / 'archive' / f'obs{int(obsid)//1000:02d}' / str(obsid) / 'images'
        )
        images = (
            list(subdir.glob('*broad_flux.img'))
            + list(subdir.glob('*wide_flux.img'))
        )
        filename = Path(images[0]) if images else Path('image does not exist')
        if filename.exists():
            hdus = fits.open(filename)
            wcs = WCS(hdus[0].header)
            if regions is None:
                obs = observation.Observation(
                    obsid,
                    workdir=workdir / 'archive',
                    source=None
                )
                obspar = obs.get_obspar()
                loc = SkyCoord(obspar['ra'] * u.deg, obspar['dec'] * u.deg)
                regions = _get_regions(loc, obsid, dbfile=workdir / 'astromon.h5')
                regions['x'], regions['y'] = wcs.world_to_pixel(regions['loc'])
                regions = json.loads(json.dumps(
                    regions[['region_id', 'x', 'y', 'radius', 'obsid', 'comments']],
                    cls=Encoder('rows')
                ))

                result = {
                    'obsid': obsid,
                    'regions': regions,
                }
                return result, 200
            else:
                t = Table(regions)
                pos = wcs.pixel_to_world(
                    t[['x']].as_array().astype(int),
                    t[['y']].as_array().astype(int),
                )
                t['ra'] = float(pos.ra / u.deg)
                t['dec'] = float(pos.dec / u.deg)
                t['user'] = auth.user
                new_regions = db.add_regions(t, dbfile=workdir / 'astromon.h5')
                new_regions['loc'] = SkyCoord(new_regions['ra'] * u.deg, new_regions['dec'] * u.deg)
                new_regions['x'], new_regions['y'] = wcs.world_to_pixel(new_regions['loc'])
                new_regions = json.loads(json.dumps(
                    new_regions[['x', 'y', 'radius', 'obsid', 'comments', 'region_id']],
                    cls=Encoder('rows')
                ))
                return {'regions': new_regions, 'ok': True}, 200
        logger.info(f'Image file for OBSID {obsid} does not exist')
        return {'regions': [], 'ok': False}, 404
    except werkzeug.exceptions.BadRequest as e:
        logger.info(f'BadRequest in Catalog.add_regions: {e}')
        return {'region_id': -1}, 400


@blueprint.route('/', methods=['GET'])
@auth.login_required
def astromon():
    try:
        logger.info('astromon.get')
        workdir = Path(current_app.config['ASTROMON_OBS_DATA'])
        obsid = request.args.get('obsid', type=int)
        if obsid is None:
            logger.info('astromon.get with no valid OBSID')
            return {'obsid': None}, 400
        logger.info(f'OBSID: {obsid}')
        subdir = (
            workdir / 'archive' / f'obs{int(obsid)//1000:02d}' / str(obsid) / 'images'
        )
        images = (
            list(subdir.glob('*broad_flux.img'))
            + list(subdir.glob('*wide_flux.img'))
        )
        filename = Path(images[0]) if images else Path('image does not exist')
        try:
            obs = observation.Observation(
                obsid,
                workdir=workdir / 'archive',
                source=None
            )
        except Exception as e:
            logger.info(f'Error getting data: {e}')
            logger.info(f'workdir: {workdir}')
            raise Exception(f'Failed to get observation data for obsid {obsid}') from None

        if filename.exists():
            hdus = fits.open(filename)
            d = np.zeros_like(hdus[0].data)
            n_min = np.min(hdus[0].data[hdus[0].data > 0])
            d[hdus[0].data > 0] = np.log10(hdus[0].data[hdus[0].data > 0])
            d[hdus[0].data <= 0] = np.log10(n_min) - 1

            wcs = WCS(hdus[0].header)

            cat_src, xray_src = _get_sources(obsid, dbfile=workdir / 'astromon.h5')
            x, y = wcs.world_to_pixel(xray_src['loc'])
            sources_new = {
                'x': x.tolist(),
                'y': y.tolist(),
                'x_id': xray_src['id'].tolist(),
            }

            matches = _get_matches(dbfile=workdir / 'astromon.h5')
            matches = matches[matches['obsid'] == obsid]

            matches['x'], matches['y'] = wcs.world_to_pixel(matches['c_loc'])
            matches['ra'] = matches['c_loc'].ra.to_string(unit='hour')
            matches['dec'] = matches['c_loc'].dec.to_string(unit='deg')
            matches = json.loads(json.dumps(
                matches[['name', 'catalog', 'x', 'y', 'ra', 'dec', 'c_id']],
                cls=Encoder('rows')
            ))
            for match in matches:
                ra = match['ra']
                dec = match['dec']
                simbad_url = (
                    'https://simbad.u-strasbg.fr/simbad/sim-coo?'
                    f'Coord={ra}%2B{dec}&CooFrame=ICRS&CooEpoch=2000&Radius=2&Radius.unit=arcsec'
                )
                match['simbad_url'] = simbad_url

            rough_matches = cat_src
            rough_matches['x'], rough_matches['y'] = wcs.world_to_pixel(rough_matches['loc'])
            rough_matches['ra'] = rough_matches['loc'].ra.to_string(unit='hour')
            rough_matches['dec'] = rough_matches['loc'].dec.to_string(unit='deg')
            rough_matches = json.loads(json.dumps(
                rough_matches[['name', 'catalog', 'x', 'y', 'ra', 'dec', 'id']],
                cls=Encoder('rows')
            ))
            for match in rough_matches:
                ra = match['ra']
                dec = match['dec']
                simbad_url = (
                    'https://simbad.u-strasbg.fr/simbad/sim-coo?'
                    f'Coord={ra}%2B{dec}&CooFrame=ICRS&CooEpoch=2000&Radius=2&Radius.unit=arcsec'
                )
                match['simbad_url'] = simbad_url

            obspar = obs.get_obspar()
            del obspar['pre_id']  # it is a masked number, it seems

            loc = SkyCoord(obspar['ra'] * u.deg, obspar['dec'] * u.deg)
            regions = _get_regions(loc, obsid, dbfile=workdir / 'astromon.h5')
            regions['x'], regions['y'] = wcs.world_to_pixel(regions['loc'])
            regions = json.loads(json.dumps(
                regions[['region_id', 'x', 'y', 'radius', 'obsid', 'comments']],
                cls=Encoder('rows')
            ))

            # in our case, the transform is trivial
            # (ra, dec) = ((x, y) - crpix) * cdelt + crval
            # transform = {
            #     'crpix': wcs.wcs.crpix - 1,
            #     'cdelt': wcs.wcs.cdelt,
            #     'crval': wcs.wcs.crval,
            # }

            result = {
                'obsid': obsid,
                'image': d.tolist(),
                'sources': {'x': [], 'y': []},
                'sources_new': sources_new,
                'matches': matches,
                'rough_matches': rough_matches,
                'obspar': obspar,
                'simbad_url': simbad_url,
                'regions': regions,
                # 'transform': transform,
            }
            return result, 200
        else:
            return {'obsid': obsid}, 404
    except werkzeug.exceptions.BadRequest as e:
        logger.info(f'BadRequest in Catalog.get: {e}')
        return {'obsid': 0}, 400
    except Exception as e:
        msg = f'Exception in Catalog.get: {e}'
        logger.error(msg)
        return {'obsid': 0, 'error': msg}, 500


class EncoderImpl(json.JSONEncoder):
    def __init__(self, fmt, *args, **kwargs):
        super(EncoderImpl, self).__init__(*args, **kwargs)
        self.fmt = fmt

    def default(self, obj):
        if type(obj) in [np.int32, np.int64]:
            return int(obj)
        elif type(obj) in [np.float32, np.float64]:
            return float(obj)
        elif type(obj) in [Row]:
            return dict(obj)
        elif type(obj) in [Column]:
            return list(obj)
        elif type(obj) in [Table]:
            if self.fmt == 'rows':
                return list(obj)
            else:
                return dict(obj)
        return json.JSONEncoder.default(self, obj)


class Encoder:
    def __init__(self, fmt):
        self.fmt = fmt
        assert fmt in ['cols', 'rows']

    def __call__(self, *args, **kwargs):
        return EncoderImpl(self.fmt, *args, **kwargs)


@blueprint.route('/matches', methods=['GET'])
# @auth.login_required
def matches():
    try:
        workdir = Path(current_app.config['ASTROMON_OBS_DATA'])
        matches = _get_matches(dbfile=workdir / 'astromon.h5')
        keys = [
            'idx', 'obsid', 'time', 'date_iso', 'c_id', 'x_id', 'dr', 'dy', 'dz',
            'detector', 'grating',
            'target', 'name', 'category', 'snr',
            'catalog']
        result = {
            'matches': json.loads(json.dumps(matches[keys], cls=Encoder('rows'))),
            'time_range': [
                CxoTime(matches['time'].min(), format='unix').isot,
                CxoTime(matches['time'].max(), format='unix').isot],
        }
        return result, 200
    except werkzeug.exceptions.BadRequest as e:
        logger.info(f'BadRequest in matches.get: {e}')
        return {'matches': [], 'time_range': []}, 400


def _get_regions(loc, obsid, dbfile=None):
    regions = db.get_table('astromon_regions', dbfile=dbfile)
    regions['loc'] = SkyCoord(regions['ra'] * u.deg, regions['dec'] * u.deg)
    regions = regions[
        (regions['loc'].separation(loc) < 3 * u.arcmin) | (regions['obsid'] == obsid)
    ]
    return regions


def _get_matches(dbfile=None):
    matches = db.get_cross_matches(dbfile=dbfile)
    matches['time'] = matches['time'].unix
    matches['idx'] = np.arange(len(matches))
    matches['date_iso'] = CxoTime(matches['date_obs']).isot
    matches['dr'] = np.round(matches['dr'], 2)
    matches['snr'] = np.round(matches['snr'], 2)
    return matches


def _get_sources(obsid, dbfile=None):
    cat = db.get_table('astromon_cat_src', dbfile=dbfile)
    xray = db.get_table('astromon_xray_src', dbfile=dbfile)
    cat = cat[cat['obsid'] == obsid]
    xray = xray[xray['obsid'] == obsid]
    cat['loc'] = SkyCoord(cat['ra'] * u.deg, cat['dec'] * u.deg)
    xray['loc'] = SkyCoord(xray['ra'] * u.deg, xray['dec'] * u.deg)

    return cat, xray
