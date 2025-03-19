# Licensed under a 3-clause BSD style license - see LICENSE.rst

import kadi.events.query as events

# This import style (instead of "from kadi import events") is required due to a
# conflict with how the django app is initialized and standalone usage since
# django 2+. Basically `events/__init__.py` in a django app does not get the
# auto-generated query references because DJANGO_SETTINGS_MODULE is set.

import os
import numpy as np
from cxotime import CxoTime
from cheta import fetch
from astropy.table import Table, Column
import astropy.units as u
from Quaternion import Quat
import kadi.commands.states
from kadi.commands import observations
import ska_quatutil
import mica.starcheck
from pathlib import Path
import agasc
from ska_helpers import retry
import maude

# This app uses only the CXC data source with fetch
fetch.data_source.set('cxc')

msids = [
    "CVCDUCTR",
    "COBSRQID",
    "AOACASEQ",
    "AOACQSUC",
    "AOFREACQ",
    "AOFWAIT",
    "AOREPEAT",
    "AOACSTAT",
    "AOACHIBK",
    "AOFSTAR",
    "AOFATTMD",
    "AOACPRGS",
    "AOATUPST",
    "AONSTARS",
    "AOPCADMD",
    "AORFSTR1",
    "AORFSTR2",
    "AOATTQT1",
    "AOATTQT2",
    "AOATTQT3",
    "AOATTQT4",
]
per_slot = [
    "AOACQID",
    "AOACFCT",
    "AOIMAGE",
    "AOACMAG",
    "AOACYAN",
    "AOACZAN",
    "AOACICC",
    "AOACIDP",
    "AOACIIR",
    "AOACIMS",
    "AOACIQB",
    "AOACISP",
]

slot_msids = [field + "%s" % slot for field in per_slot for slot in range(0, 8)]


def deltas_vs_obc_quat(vals, times, catalog):
    """
    Calculate the deltas between the expected star positions (based on OBC attitude)
    and the observed star positions.
    """

    # Ignore misalign
    aca_misalign = np.array([[1.0, 0, 0], [0, 1, 0], [0, 0, 1]])
    q_ok = np.logical_and.reduce([~vals["AOATTQT1"].mask, ~vals["AOATTQT2"].mask,
                                  ~vals["AOATTQT3"].mask, ~vals["AOATTQT4"].mask])
    q_att = Quat(
        q=np.array(
            [vals["AOATTQT1"][q_ok], vals["AOATTQT2"][q_ok],
             vals["AOATTQT3"][q_ok], vals["AOATTQT4"][q_ok]]
        ).transpose()
    )

    Ts = q_att.transform
    acqs = catalog[(catalog["type"] == "BOT") | (catalog["type"] == "ACQ")]

    # Radians to arcsecs
    R2A = 206264.81

    dy = {}
    dz = {}
    for slot in range(0, 8):
        if len(acqs[acqs["slot"] == slot]) == 0:
            continue
        agasc_id = acqs[acqs["slot"] == slot][0]["id"]
        star = agasc.get_star(agasc_id, date=times[0])
        star_pos_eci = ska_quatutil.radec2eci(star['RA_PMCORR'], star['DEC_PMCORR'])
        d_aca = np.dot(
            np.dot(aca_misalign, Ts.transpose(0, 2, 1)), star_pos_eci
        ).transpose()
        dy[slot] = np.ma.masked_all(len(times))
        dz[slot] = np.ma.masked_all(len(times))
        yag = np.arctan2(d_aca[:, 1], d_aca[:, 0]) * R2A
        zag = np.arctan2(d_aca[:, 2], d_aca[:, 0]) * R2A
        dy[slot][q_ok] = vals["AOACYAN{}".format(slot)][q_ok] - yag
        dz[slot][q_ok] = vals["AOACZAN{}".format(slot)][q_ok] - zag

    return dy, dz


def get_acq_date_for_obsid(obsid, load_name=None):
    """
    Get the NPNT start time for an obsid (or the NPNT start time for a catalog associated with a date)

    Parameters
    ----------
    obsid : int
        The obsid.
    load_name : str
        The load name (optional)

    Returns
    -------
    start_time : str
        The NPNT start time for the given obsid.

    Raises
    ------
    ValueError
        If the obsid is not valid.

    """
    if load_name.strip() == "":
        return get_time_for_obsid_from_cmds(obsid)
    else:
        return get_time_for_obsid_from_starcheck(obsid, load_name)


def get_time_for_obsid_from_cmds(obsid):
    """
    Get the NPNT start time for an obsid from kadi.
    """
    obss = observations.get_observations(obsid=obsid)
    # Skip observations with src CMD_EVT for now and skip observations with npnt_enab=False
    for obs in obss:
        if obs["source"] == "CMD_EVT" or obs["npnt_enab"] == False:
            continue
        break
    return get_closest_npnt_start_time(obs["obs_start"])


def get_closest_npnt_start_time(date):
    """
    Get the closest NPNT start time for a given date.
    """
    # Get the closest NPNT mode to the date
    states = kadi.commands.states.get_states(
        start=CxoTime(date) - 3.5 * u.day,
        stop=CxoTime(date) + 3.5 * u.day,
        merge_identical=True, state_keys=['pcad_mode'])
    ok = states['pcad_mode'] == 'NPNT'
    if not np.any(ok):
        raise ValueError(f"No NPNT mode found for date {date}")
    # Return the start time of the closest NPNT mode
    dtime = states["tstart"][ok] - CxoTime(date).secs
    return states["tstart"][ok][np.argmin(np.abs(dtime))]


def get_time_for_obsid_from_starcheck(obsid, load_name):
    starcat = mica.starcheck.get_starcheck_catalog(obsid, mp_dir=load_name)
    if starcat is None or "obs" not in starcat:
        raise ValueError(f"No starcheck catalog found for obsid {obsid}")
    date = starcat["manvr"][-1]["end_date"]
    return get_closest_npnt_start_time(date)


def get_maude_telem(msids, start_time, stop_time):
    # Get the data directly from maude instead of cheta

    telem = retry.retry_call(
        maude.get_msids,
        args=[msids],
        kwargs={'start': start_time, 'stop': stop_time, 'allow_subset': False},
        tries=4, delay=1)
    # convert this to a dict of just times and vals by msid
    telem_dict = {}
    # telem data is a list of dicts, one per msid
    for entry in telem["data"]:
        msid = entry['msid']
        telem_dict[msid] = {
            'times': entry["times"],
            'vals': entry["values"],
        }
    return telem_dict


def get_cxc_telem(msids, start_time, stop_time):
    telem = fetch.MSIDset(msids, start_time, stop_time)
    # convert this to a dict of just times and vals
    telem_dict = {}
    for msid in telem:
        telem_dict[msid] = {
            'times': telem[msid].times,
            'vals': telem[msid].vals,
            'bads': telem[msid].bads
        }
    return telem_dict


def get_acq_table(start_time):
    """
    Retrieve the acquisition data for an obsid or date.
    """

    if CxoTime(start_time).date < '2002:007':
        raise ValueError("Tool not available for obsids before 2002:007")

    stop_time = start_time + (60 * 5)
    print(f"Getting acquisition data from {CxoTime(start_time).date} to {CxoTime(stop_time).date}")

    # Just use a reference MSID to figure out if CXC telem covers this enough
    _, vcdu_msid_stop = fetch.get_time_range("CVCDUCTR")
    if vcdu_msid_stop < (stop_time + 60 * 5):
        acq_data = get_maude_telem(msids + slot_msids, start_time, stop_time)
    else:
        acq_data = get_cxc_telem(msids + slot_msids, start_time, stop_time)


    # Find a mod 4 = 0 time to start the data set at beginning of ACA readout
    four_0 = acq_data['CVCDUCTR']["vals"] % 4 == 0
    all_four_0 = acq_data['CVCDUCTR']["times"][four_0]
    if len(all_four_0) == 0:
        raise ValueError("No mod 4 = 0 times found in the data set")

    # Makes a time grid to key off of the mod 4 times, but calculate the times in
    # the grid using 4 times the median time between samples so that if there is a
    # missing mod 4 time, we can still get the other pieces of data.
    t0 = all_four_0[0]
    max_time = acq_data['CVCDUCTR']["times"][-1]
    dtime = np.median(acq_data['CVCDUCTR']["times"][1:] - acq_data['CVCDUCTR']["times"][:-1])
    times = np.arange(t0, max_time + dtime, dtime * 4)[:-1]
    # I explicitly used times (always increasing) and not the VCDU counters,
    # so that I would not need to explicitly handle VCDU rollovers.

    # Loop over the columns and make masked versions of the data
    acq_data_masked = {}
    for col in msids + slot_msids:
        # initialize the column with masked values length of the grid_times
        acq_data_masked[col] = np.ma.masked_all(
            len(times),
            dtype=acq_data[col]["vals"].dtype)

        # COBSRQID isn't ACA data, so just do a straight searchsorted to line up
        # reasonable values with the grid of ACA data.
        if col == 'COBSRQID':
            for idx, time in enumerate(times):
                data_idx = np.searchsorted(acq_data[col]["times"], time)
                if data_idx < len(acq_data[col]["times"]):
                    acq_data_masked[col][idx] = acq_data[col]["vals"][data_idx]
            continue

        # For the other MSIDs, paste them into a grid of ACA times
        ok = (acq_data[col]["times"] >= times[0]) & (acq_data[col]["times"] <= times[-1])
        for idx, time in enumerate(acq_data[col]["times"][ok]):
            # Find the ACA grid index for the time
            gidx = np.searchsorted(times, time + (dtime * .9)) - 1
            if gidx < len(times):
                acq_data_masked[col][gidx] = acq_data[col]["vals"][idx]

    vals = Table([acq_data_masked[col] for col in msids + slot_msids], names=msids + slot_msids)
    vals['time'] = times
    vals["AOREPEAT"].fill_value = '0'
    vals["AOREPEAT"] = vals["AOREPEAT"].filled()

    # Deal with odd issue that COBSRQID can be missing or masked in anomaly data
    vals['COBSRQID'].fill_value = -1
    vals['COBSRQID'] = vals['COBSRQID'].filled()

    def compress_data(data, dtime):
        repeat = np.array([int(val) for val in data["AOREPEAT"]])
        return data[repeat == 0], dtime[repeat == 0]

    vals, times = compress_data(vals, times)

    # Find the time of the first AQXN row and filter the data to be after that
    acq = np.where(vals["AOACASEQ"] == "AQXN")[0]
    if len(acq) == 0:
        raise ValueError("No AQXN found in the data set")
    vals = vals[acq[0]:]
    times = times[acq[0]:]

    # Get the catalog for the stars
    # This is used both to map ACQID to the right slot and
    # to get the star positions to estimate deltas later
    starcheck = mica.starcheck.get_starcheck_catalog_at_date(start_time)
    #if "cat" not in starcheck:
    #    raise ValueError("No starcheck catalog found for {}".format(obsid))
    catalog = Table(starcheck["cat"])
    catalog.sort("idx")
    # Filter the catalog to be just acquisition stars
    catalog = catalog[(catalog["type"] == "ACQ") | (catalog["type"] == "BOT")]
    slot_for_pos = [cat_row["slot"] for cat_row in catalog]
    pos_for_slot = dict([(slot, idx) for idx, slot in enumerate(slot_for_pos)])
    # Also, save out the starcheck index for each slot for later
    index_for_slot = dict([(cat_row["slot"], cat_row["idx"]) for cat_row in catalog])

    # Estimate the offsets from the expected catalog positions
    dy, dz = deltas_vs_obc_quat(vals, times, catalog)
    for slot in range(0, 8):
        if slot not in dy or slot not in dz:
            continue
        vals.add_column(Column(name="dy{}".format(slot), data=dy[slot].data))
        vals.add_column(Column(name="dz{}".format(slot), data=dz[slot].data))
        cat_entry = catalog[catalog["slot"] == slot][0]
        dmag = vals["AOACMAG{}".format(slot)] - cat_entry["mag"]
        vals.add_column(Column(name="dmag{}".format(slot), data=dmag.data))

    # make a list of dicts of the table
    simple_data = []
    kalm_start = None
    for drow, time in zip(vals, times):
        if (kalm_start is None) and (drow["AOACASEQ"] == "KALM"):
            kalm_start = time
        if (kalm_start is not None) and (time > kalm_start + 5):
            continue
        slot_data = {
            "slots": [],
            "time": time,
            "date": CxoTime(time).date,
            "aorfstr1_slot": slot_for_pos[int(drow["AORFSTR1"])],
            "aorfstr2_slot": slot_for_pos[int(drow["AORFSTR2"])],
        }
        for m in msids:
            slot_data[m] = drow[m]
        for slot in range(0, 8):
            if slot not in slot_for_pos:
                continue
            row_dict = {
                "slot": slot,
                "catpos": pos_for_slot[slot],
                "index": index_for_slot[slot],
            }
            for col in per_slot:
                if col not in ["AOACQID"]:
                    row_dict[col] = drow["{}{}".format(col, slot)]
            for col in ["dy", "dz", "dmag"]:
                row_dict[col] = drow["{}{}".format(col, slot)]
            row_dict["POS_ACQID"] = drow["AOACQID{}".format(pos_for_slot[slot])]
            # Remove trailing spaces in the ACQID
            row_dict["POS_ACQID"] = row_dict["POS_ACQID"].strip()
            slot_data["slots"].append(row_dict)
        simple_data.append(slot_data)

    return simple_data
