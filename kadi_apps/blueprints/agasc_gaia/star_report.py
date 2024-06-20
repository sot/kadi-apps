import os
# import tables
import warnings
import functools
import jinja2
import tqdm
import tables
import flask

# import seaborn as sns
import numpy as np

import plotly.express as px
import plotly.graph_objects as go

from pathlib import Path

# from ipywidgets.widgets import Button
from IPython.display import display, HTML

# from astropy.table import Table, join
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.table import vstack, Table


from agasc import get_agasc_cone, get_stars, get_agasc_filename


from jinja2 import Environment, PackageLoader, select_autoescape

SKA = Path(os.environ["SKA"])
AGASC_FILE = SKA / "data" / "agasc" / "agasc1p7.h5"
MATCHES_FILE = SKA / "data" / "agasc-gaia" / "agasc-gaia-matches.h5"
SUMMARY_FILE = SKA / "data" / "agasc-gaia" / "agasc-summary.h5"


def symsize(mag):
    # map mags to figsizes
    return np.interp(mag, [6.0, 12.0], [20.0, 4.0])


def norm(val, fmt):
    if hasattr(val, "mask") and val.mask:
        return "--"
    else:
        return fmt.format(val)


def get_agasc_gaia_x_match_all(agasc_ids):
    print("get_agasc_gaia_x_match_all")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=tables.NaturalNameWarning)
        with tables.open_file(MATCHES_FILE) as h5:
            idx = np.sort(np.concatenate(
                [h5.root.data.get_where_list(f"agasc_id == {aid}") for aid in agasc_ids]
            ))
            x_match_direct_table = Table(   
                np.ma.MaskedArray(data=h5.root.data[idx], mask=h5.root.mask[idx])
            )

    agasc_summary = get_agasc_summary(agasc_ids)
    cols = [
        "mag_aca",
        "mag_aca_err",
        "mag_aca_obs",
        "mag_aca_err_obs",
        "guide",
        "acq",
        "tycho_id",
        "tycho_tdsc_id",
        "mag_catid",
        "mag_band",
    ]

    i = np.searchsorted(agasc_summary["agasc_id"], x_match_direct_table["agasc_id"])
    for col in cols:
        x_match_direct_table[col] = agasc_summary[col][i]
    x_match_direct_table["mag_1p7"] = agasc_summary["mag"][i]

    print("done in get_agasc_gaia_x_match_all")
    return x_match_direct_table


def get_agasc_summary(agasc_id):
    print(f"get_agasc_summary agasc_id={agasc_id}")
    with warnings.catch_warnings(), tables.open_file(SUMMARY_FILE) as h5:
        warnings.filterwarnings("ignore", category=tables.NaturalNameWarning)
        agasc_summary_idx = np.sort(np.concatenate(
            [h5.root.data.get_where_list(f"agasc_id == {aid}") for aid in agasc_id]
        ))
        print(f"done with get_agasc_summary {agasc_id}")
        return h5.root.data[agasc_summary_idx]


def get_data(agasc_id):
    return get_data_(','.join(np.sort(np.atleast_1d(agasc_id)).astype(str)))


@functools.cache
def get_data_(agasc_id):
    print(f"get_data {agasc_id}")
    agasc_id = np.atleast_1d(agasc_id.split(",")).astype(int)

    star = Table(get_agasc_summary(agasc_id))

    target ={
        "ra": np.mean(star['ra']),
        "dec": np.mean(star['dec']),
        "epoch": np.mean(star['epoch']),
    }

    half_width = 500 / 3600
    agasc = get_agasc_cone(
        target["ra"],
        target["dec"],
        half_width,
        agasc_file=AGASC_FILE,
        use_supplement=False,
    )
    agasc.rename_columns(agasc.colnames, [col.lower() for col in agasc.colnames])
    agasc.sort("agasc_id")

    agasc_summary = Table(get_agasc_summary(np.concatenate([agasc_id, agasc["agasc_id"]])))

    agasc_idx = np.searchsorted(agasc_summary["agasc_id"], agasc["agasc_id"])
    agasc["mag_aca_obs"] = agasc_summary["mag_aca_obs"][agasc_idx]
    agasc["tycho_id"] = agasc_summary["tycho_id"][agasc_idx]
    agasc["gsc2.3"] = agasc_summary["gsc2.3"][agasc_idx]

    gaia = get_agasc_gaia_x_match_all(agasc_id)
    gaia.sort("p_match", reverse=True)
    gaia["baseline"] = gaia["best_match"]

    gaia_idx = np.searchsorted(agasc_summary["agasc_id"], gaia["agasc_id"])
    gaia["pos_catid"] = agasc_summary["pos_catid"][gaia_idx]
    gaia["epoch_agasc"] = agasc_summary["epoch"][gaia_idx]

    # position at epoch of the AGASC match candidate for comparison
    # NOTE that epoch comes from the summary and not the AGASC catalog
    gaia["ra_corr"] = gaia["ra"] + gaia["pm_ra"] * (
        gaia["epoch_agasc"] - gaia["epoch"]
    ) / 1000 / 3600 / np.cos(np.deg2rad(gaia["dec"]))
    gaia["dec_corr"] = (
        gaia["dec"] + gaia["pm_dec"] * (gaia["epoch_agasc"] - gaia["epoch"]) / 1000 / 3600
    )
    gaia["dec_corr"][gaia["dec_corr"].mask] = gaia["dec"][gaia["dec_corr"].mask]
    gaia["ra_corr"][gaia["ra_corr"].mask] = gaia["ra"][gaia["ra_corr"].mask]

    # Setting AGASC positions at target epoch
    # this is just for the purpose of filtering, these positions are not plotted.
    coord_target = SkyCoord(ra=target["ra"], dec=target["dec"], unit="deg")

    ra = np.array(agasc["ra"])
    dec = np.array(agasc["dec"])
    pm_ra = np.array(agasc["pm_ra"])
    pm_dec = np.array(agasc["pm_dec"])
    pm = (pm_ra != -9999) | (pm_dec != -9999)
    pm_ra[pm_ra == -9999] = 0
    pm_dec[pm_dec == -9999] = 0

    ra[pm] += (
        pm_ra[pm]
        * (target["epoch"] - agasc["epoch"][pm])
        / 1000
        / 3600
        / np.cos(np.deg2rad(agasc["dec"][pm]))
    )
    dec[pm] += pm_dec[pm] * (target["epoch"] - agasc["epoch"][pm]) / 1000 / 3600
    agasc_coord = SkyCoord(ra=ra, dec=dec, unit="deg")

    agasc["d2d"] = agasc_coord.separation(coord_target).to(u.arcsec)
    agasc.sort("d2d")

    # this is redundant, because `star` is a subset of `agasc_2`
    # the only difference is that `star`` contains the stars explicitly requested,
    # whereas `agasc_2` includes the entire neighborhood.
    # currently the only difference between `agasc` and `agasc_2` is that `agasc_2` uses
    # the original Tycho2 epoch, RA, and dec (instead of the position shifted to 2000. epoch)
    agasc_idx = np.searchsorted(agasc_summary["agasc_id"], agasc["agasc_id"])
    agasc_2 = agasc_summary[agasc_idx]
    agasc_2["d2d"] = agasc["d2d"]

    for col in ["mag_aca", "mag_aca_obs", "mag", "pos_catid", "pm_catid", "mag_catid"]:
        if col not in agasc.colnames:
            # these are used later, but they are not present in proseco agasc
            # so we add them here to avoid errors
            agasc[col] = agasc[col]

    print("get_data done")
    return star, agasc, gaia, target, agasc_2


class Report:
    def __init__(self, agasc_id, alternates=None):
        self.agasc_id = agasc_id

        assert np.isscalar(agasc_id) or alternates is None, "Alternates only for single stars"

        agasc_id = np.atleast_1d(agasc_id)
        self.target = []
        self.star, self.agasc, self.gaia, self.target, self.agasc_2 = get_data(agasc_id)

        self.comparison = None
        self.alternates = {}
        if alternates:
            self.alternates = alternates

            # COMPARISON
            for key, val in self.alternates.items():
                self.gaia[key] = self.gaia["gaia_id"] == val
            cols = [
                "gaia_id",
                "d2d",
                "d_mag",
                "p_value",
                "p_relative",
                "pm_ra",
                "pm_dec",
                "baseline",
            ]
            cols += list(self.alternates.keys())
            self.comparison = vstack(
                [
                    self.gaia[self.gaia[key]]
                    for key in ["baseline"] + list(self.alternates.keys())
                ]
            )

        self.agasc["mag_aca"].format = ".2f"
        self.agasc["mag_aca_obs"].format = ".2f"
        self.agasc["mag"].format = ".2f"
        self.agasc["d2d"].format = ".2f"

        self.gaia["p_match"].format = ".4f"
        self.gaia["p_value"].format = ".4f"
        self.gaia["p_relative"].format = ".3f"
        self.gaia["pm_ra"].format = ".3f"
        self.gaia["pm_dec"].format = ".3f"
        self.gaia["d2d"].format = ".2f"
        self.gaia["d_mag"].format = ".2f"
        self.gaia["mag_aca"].format = ".2f"
        self.gaia["mag_aca_pred"].format = ".2f"
        self.gaia["mag_pred"].format = ".2f"
        self.gaia["mag_1p7"].format = ".2f"

    @functools.lru_cache(maxsize=128)
    @staticmethod
    def get_report(agasc_id):
        return Report(agasc_id)

    def plotly_fig(self):
        colors = px.colors.qualitative.T10
        agasc_color = "black"
        gaia_color = colors[0]
        colors = colors[1:]
        agasc = self.agasc.copy()
        agasc_2 = self.agasc_2.copy()
        gaia = self.gaia.copy()

        cos = np.cos(np.deg2rad(np.mean(self.star["dec"])))
        # this is the position in 1p7, except that the original Tycho2 positions at 1991.5 are used
        x0 = np.mean(self.star["ra"])
        y0 = np.mean(self.star["dec"])
        # the actual position in AGASC 1p7 would be
        # star = agasc[agasc["agasc_id"] == self.agasc_id][0]
        # x0 = star['ra']
        # y0 = star['dec']

        gaia['x'] = (gaia["ra_corr"] - x0) * 3600
        gaia['y'] = (gaia["dec_corr"] - y0) * 3600

        gaia.sort(['agasc_id', 'gaia_id'])

        # these are the matches that will be marked with crosses
        if self.alternates:
            matches = Table([
                {"label": name, "agasc_id": self.star['agasc_id'][0], "gaia_id": gaia_id}
                for name, gaia_id in self.alternates.items()
            ])
        else:
            matches = gaia[['agasc_id', 'gaia_id']][gaia["best_match"]]
            matches["label"] = [
                "match" + (f" {idx}" if len(matches) else "") for idx in range(len(matches))
            ]

        # Gaia IDs can be repeated in `gaia` (`gaia` contains matches, so the star can be matched
        # to multiple AGASC stars) but we only want one entry per star. The one star row we want to
        # keep is the one with the best match (the highest p-value).
        # This is so ra_corr and dec_corr correspond to the best match
        unique_gaia = gaia[['gaia_id', 'ra', 'dec', "ra_corr", "dec_corr", 'pm_ra', 'pm_dec', 'epoch', 'x', 'y', 'p_value', 'mag_pred', 'mag_aca_pred', 'd2d']].copy()
        unique_gaia['epoch'] = unique_gaia['epoch'].astype(np.float64)  # the type matters
        unique_gaia.sort(['gaia_id', 'p_value'])
        unique_gaia = unique_gaia.group_by('gaia_id')
        unique_gaia = unique_gaia[unique_gaia.groups.indices[:-1]]

        # Gaia positions will be shifted according these epochs:
        # - "best match". The default. These are ra_corr and dec_corr in self.gaia.
        #   The epoch of its best AGASC match
        # - "Gaia" epoch. The Gaia positions at the Gaia epoch (2016.)
        # - epoch of a given AGASC star
        gaia_epochs = [
            {"label": "Gaia", "epoch": 2016.0}
        ]
        agasc_epochs = [(agasc_id, gaia["epoch_agasc"][gaia["agasc_id"] == agasc_id][0]) for agasc_id in np.unique(gaia["agasc_id"])]
        gaia_epochs += [
            {"label": f'{agasc_epoch:.2f} - AGASC {agasc_id}', "epoch": agasc_epoch}
            for agasc_id, agasc_epoch in agasc_epochs
        ]

        # There are several possible traces for the Gaia stars:
        # - best match. The Gaia stars are displayed at the epoch of its best match
        # - Gaia. The Gaia stars are displayed at the Gaia epoch
        # - AGASC <ID>. The Gaia stars are displayed at the epoch of the AGASC star with the given ID
        self.gaia_trace_data = {
            "best match": {
                "gaia_id": np.asarray(unique_gaia["gaia_id"]),
                "ra": np.asarray(unique_gaia["ra"]),
                "dec": np.asarray(unique_gaia["dec"]),
                "ra_corr": np.asarray(unique_gaia["ra_corr"]),
                "dec_corr": np.asarray(unique_gaia["dec_corr"]),
                "x": np.asarray(unique_gaia["x"]),
                "y": np.asarray(unique_gaia["y"]),
                "label": "best match",
            }
        }

        for ge in gaia_epochs:
            label = ge["label"]
            agasc_epoch = ge["epoch"]
            has_pm = ~unique_gaia['pm_dec'].mask & ~unique_gaia['pm_ra'].mask

            ra_corr = np.array(unique_gaia['ra'].astype(np.float64))
            dec_corr = np.array(unique_gaia['dec'].astype(np.float64))

            ra_corr[has_pm] = unique_gaia["ra"][has_pm] + unique_gaia["pm_ra"][has_pm] * (
                agasc_epoch - unique_gaia["epoch"][has_pm]
            ) / 1000 / 3600 / np.cos(np.deg2rad(unique_gaia["dec"][has_pm]))
            dec_corr[has_pm] = unique_gaia["dec"][has_pm] + unique_gaia["pm_dec"][has_pm] * (
                agasc_epoch - unique_gaia["epoch"][has_pm]
            ) / 1000 / 3600

            self.gaia_trace_data[label] = {
                "gaia_id": np.asarray(unique_gaia["gaia_id"]),
                "ra": np.asarray(unique_gaia["ra"]),
                "dec": np.asarray(unique_gaia["dec"]),
                "ra_corr": ra_corr,
                "dec_corr": dec_corr,
                "x": (ra_corr - x0) * 3600,
                "y": (dec_corr - y0) * 3600,
                "label": label,
            }

        # all Gaia traces are grouped so one can display one group at a time
        # at this point in the code, each group is trivial (only the one trace)
        # later on we will add markers to display match pairs
        gaia_button_traces = {
            k: [k] for k in self.gaia_trace_data
        }

        # There will be three possible AGASC traces:
        # - Summary (using 1991 epoch to avoid issues with proper motion)
        # - 1p7. The original AGASC 1p7 positions.
        # - Gaia (positions shifted to Gaia epoch).
        self.agasc_trace_data = {
            "AGASC_2": {
                "x": (agasc_2["ra"] - x0) * 3600,
                "y": (agasc_2["dec"] - y0) * 3600,
                "label": "Summary",
            },
            "AGASC": {
                "x": (agasc["ra"] - x0) * 3600,
                "y": (agasc["dec"] - y0) * 3600,
                "label": "1p7",
            },
        }

        # this is to move AGASC to 2016. epoch
        pm_ra = np.zeros(len(agasc))
        pm_dec = np.zeros(len(agasc))
        pm_ra[agasc["pm_ra"] != -9999] = agasc["pm_ra"][agasc["pm_ra"] != -9999]
        pm_dec[agasc["pm_dec"] != -9999] = agasc["pm_dec"][agasc["pm_dec"] != -9999]

        ra_corr = np.array(agasc['ra'].astype(np.float64))
        dec_corr = np.array(agasc['dec'].astype(np.float64))

        ra_corr = agasc["ra"] + pm_ra * (
            2016. - agasc["epoch"]
        ) / 1000 / 3600 / np.cos(np.deg2rad(agasc["dec"]))
        dec_corr = agasc["dec"] + pm_dec * (
            2016. - agasc["epoch"]
        ) / 1000 / 3600

        self.agasc_trace_data["Gaia epoch"] = {
            "x": (ra_corr - x0) * 3600,
            "y": (dec_corr - y0) * 3600,
            "label": "Gaia epoch",
        }

        # all AGASC traces are grouped so one can display one group at a time
        # at this point in the code, each group is trivial (only the one trace)
        # later on we will add markers to display match pairs
        agasc_button_traces = {
            k: [k] for k in self.agasc_trace_data
        }

        fig = go.FigureWidget()

        # all traces added will be collected here so we can point and them to enable/disable them
        traces = []

        half_width = 3
        x_range = [-half_width / cos, half_width / cos]
        y_range = [-half_width, half_width]

        # predicted mag and d2d of the Gaia markers depends on its best match
        # I am not going to change this for all combinations
        gaia_text = [
            f"ID: {row['gaia_id']}<br>"
            f"MAG: {row['mag_pred']:.2f}<br>"
            f"2d2: {row['d2d']:.2f}<br>"
            f"MAG_ACA pred.: {norm(row['mag_aca_pred'], '{:.2f}')}<br>"
            f"PM_RA: {norm(row['pm_ra'], '{:.2f}')}<br>"
            f"PM_DEC: {norm(row['pm_dec'], '{:.2f}')}<br>"
            for row in unique_gaia
        ]
        gaia_sizes = unique_gaia["mag_pred"].copy()
        gaia_sizes[np.isnan(gaia_sizes)] = 20

        active_gaia_data = 0
        for key, dat in self.gaia_trace_data.items():
            traces.append(key)
            fig.add_trace(
                go.Scattergl(
                    x=dat["x"],
                    y=dat["y"],
                    text=gaia_text,
                    hovertemplate="%{text}",
                    marker={
                        "size": 2 * symsize(gaia_sizes),
                        "color": gaia_color,
                        # "alpha": 0.5,
                        "line_width": 0,
                    },
                    mode="markers",
                    name="Gaia",
                    visible=(key == list(self.gaia_trace_data.keys())[active_gaia_data]),
                )
            )

        agasc_text = [
            f"ID: {row['agasc_id']}<br>"
            f"MAG: {row['mag']:.2f}<br>"
            f"MAG_ACA: {row['mag_aca']:.2f}<br>"
            f"MAG_ACA obs: {norm(row['mag_aca_obs'], '{:.2f}')}<br>"
            f"PM_RA: {row['pm_ra']:.2f}<br>"
            f"PM_DEC: {row['pm_dec']:.2f}<br>"
            for row in agasc
        ]
        active_agasc_data = 0
        for key, dat in self.agasc_trace_data.items():
            traces.append(key)
            fig.add_trace(
                go.Scattergl(
                    x=dat["x"],
                    y=dat["y"],
                    text=agasc_text,
                    hovertemplate="%{text}",
                    marker={
                        "size": 2 * symsize(agasc["mag"]),
                        "color": agasc_color,
                        "opacity": 0.7,
                        "line_width": 0,
                    },
                    mode="markers",
                    name="AGASC",
                    visible=(key == list(self.agasc_trace_data.keys())[active_agasc_data]),
                )
            )

        # Now we add match pairs
        for idx, match in enumerate(matches):
            # for each Gaia star in a match, we have multiple traces, one for each epoch
            # (corresponding to the possible AGASC stars)
            i = np.argwhere((unique_gaia["gaia_id"] == match["gaia_id"]))[0][0]
            for key in self.gaia_trace_data:
                uid = f"{key}-match-{idx}"
                traces.append(uid)
                gaia_button_traces[key] += [uid]
                fig.add_trace(
                    go.Scattergl(
                        x=[self.gaia_trace_data[key]["x"][i]],
                        y=[self.gaia_trace_data[key]["y"][i]],
                        marker={
                            "size": 15,
                            "color": colors[idx],
                            "opacity": 1.,
                            "symbol": "star-triangle-down-open",
                            "line_color": colors[idx],
                            "line_width": 1,
                            "angle": 30 * idx,
                        },
                        mode="markers",
                        name=match["label"],
                        visible=(key == list(self.gaia_trace_data.keys())[active_gaia_data]),
                    )
                )

            # for each AGASC star in a match, we have two possible traces, one with the 1p7 AGASC
            # position, and one with the summary position
            i = np.argwhere(agasc["agasc_id"] == match["agasc_id"])[0][0]
            for key in self.agasc_trace_data:
                uid = f"{key}-target-{idx}"
                traces.append(uid)
                agasc_button_traces[key] += [uid]
                fig.add_trace(
                    go.Scattergl(
                        x=[self.agasc_trace_data[key]["x"][i]],
                        y=[self.agasc_trace_data[key]["y"][i]],
                        marker={
                            "size": 15,
                            "color": "black",
                            "symbol": "y-down",
                            "line_color": colors[idx],
                            "line_width": 1,
                            "angle": 30 * idx,
                        },
                        mode="markers",
                        name="target" + (f" {idx}" if len(matches) else ""),
                        visible=(key == list(self.agasc_trace_data.keys())[active_agasc_data]),
                    )
                )

        # this maps trace ID string in the traces list to their index in the list
        trace_idx = {tr: i for i, (tr, d) in enumerate(zip(traces, fig.data, strict=True))}

        for key4 in self.agasc_trace_data:
            for but in agasc_button_traces[key4]:
                trace_idx[but]

        buttons_agasc = [
            {
                "method": 'update',
                "label": "None",
                "visible": True,
                "args": [
                    {"visible": [("legendonly" if j==0 else False) for j, key2 in enumerate(self.agasc_trace_data) for _ in agasc_button_traces[key2]]},
                    {},
                    [trace_idx[but] for key in self.agasc_trace_data for but in agasc_button_traces[key]]
                ],
                "args2": [
                    {"visible": [("legendonly" if j==0 else False) for j, key2 in enumerate(self.agasc_trace_data) for _ in agasc_button_traces[key2]]},
                    {},
                    [trace_idx[but] for key in self.agasc_trace_data for but in agasc_button_traces[key]]
                ]
            }
        ] + [
            {
                "method": 'update',
                "label": self.agasc_trace_data[key1]["label"],
                "visible": True,
                "args": [
                    {"visible": [j==i for j, key2 in enumerate(self.agasc_trace_data) for _ in agasc_button_traces[key2]],},
                    {},
                    [trace_idx[but] for key2 in self.agasc_trace_data for but in agasc_button_traces[key2]]
                ],
                "args2": [
                    {"visible": [j==i for j, key2 in enumerate(self.agasc_trace_data) for _ in agasc_button_traces[key2]],},
                    {},
                    [trace_idx[but] for key2 in self.agasc_trace_data for but in agasc_button_traces[key2]]
                ],
            }
            for i, key1 in enumerate(self.agasc_trace_data)
        ]
        buttons_gaia = [
            {
                "method": 'update',
                "label": self.gaia_trace_data[key1]["label"],
                "visible": True,
                "args": [
                    {"visible": [j==i for j, key2 in enumerate(self.gaia_trace_data) for _ in gaia_button_traces[key2]],},
                    {},
                    [trace_idx[but] for key2 in self.gaia_trace_data for but in gaia_button_traces[key2]]
                ],
                "args2": [
                    {"visible": [j==i for j, key2 in enumerate(self.gaia_trace_data) for _ in gaia_button_traces[key2]],},
                    {},
                    [trace_idx[but] for key2 in self.gaia_trace_data for but in gaia_button_traces[key2]]
                ],
            }
            for i, key1 in enumerate(self.gaia_trace_data)
        ]

        fig.update_layout(
            # title=f"AGASC {agasc_id}",
            # template=templates[0],
            template="seaborn",
            # xaxis_range=[star['ra'] - half_width / cos, star['ra'] + half_width / cos],
            # yaxis_range=[star['dec'] - half_width, star['dec'] + half_width],
            xaxis_range=x_range,
            yaxis_range=y_range,
            yaxis={"scaleanchor": "x"},
            autosize=False,
            width=500,
            height=400,
        )

        fig.update_layout(
            updatemenus=[
                dict(
                    type='dropdown',
                    # type='buttons',
                    direction='down',
                    x=0.4,
                    y=1.2,
                    showactive=True,
                    buttons=buttons_agasc,
                    active=active_agasc_data + 1,
                ),
                dict(
                    type='dropdown',
                    # type='buttons',
                    direction='down',
                    x=1.25,
                    y=1.2,
                    showactive=True,
                    buttons=buttons_gaia,
                    active=active_gaia_data,
                )
            ],
            # title=dict(text='Toggle Traces',x=0.),
        )
        fig.update_layout(
            annotations=[
                dict(
                    text="AGASC version:",
                    x=0.,
                    xref="paper",
                    y=1.3,
                    yref="paper",
                    align="left",
                    showarrow=False
                ),
                dict(
                    text="Epoch:",
                    x=0.55,
                    xref="paper",
                    y=1.3,
                    yref="paper",
                    align="right",
                    showarrow=False
                )
            ]
        )

        return fig

    # def plot(agasc_id):
    #     fig = plotly_fig(agasc_id)
    #     display(fig)

    def get_html(self):
        fig = self.plotly_fig()
        sky_plot_html = fig.to_html(
            full_html=False,
            include_plotlyjs="cdn",
            default_width=1000,
            default_height=600,
        )

        cols = ["agasc_id", "gaia_id", "baseline"]
        # COMPARISON
        cols += list(self.alternates.keys())
        cols += [
            "mag_1p7",
            "mag_pred",
            "d_mag",
            "d2d",
            "p_match",
            "p_value",
            "p_relative",
            "pm_ra",
            "pm_dec",
            "mag_aca",
            "mag_aca_pred",
        ]
        gaia_str = {col: list(self.gaia[col].iter_str_vals()) for col in cols}
        target_str = {
            col: list(
                self.agasc[np.in1d(self.agasc["agasc_id"], self.agasc_id)][col].iter_str_vals()
            )
            for col in [
                "agasc_id",
                "ra",
                "dec",
                "mag",
                "mag_aca",
                "mag_aca_obs",
                "pm_ra",
                "pm_dec",
                "tycho_id",
                "gsc2.3",
            ]
        }
        agasc_str = {
            col: list(self.agasc[self.agasc["d2d"] < 20][col].iter_str_vals())
            for col in [
                "agasc_id",
                "ra",
                "dec",
                "d2d",
                "mag",
                "mag_aca",
                "mag_aca_obs",
                "pm_ra",
                "pm_dec",
                "pos_catid",
                "pm_catid",
                "mag_catid",
            ]
        }

        comment = ""
        for star in self.star:
            star[0]
            agasc_star = self.agasc[self.agasc["agasc_id"] == star['agasc_id']][0]
            if star["epoch"] != agasc_star["epoch"]:
                comment += f"AGASC {star['agasc_id']} epoch in AGASC: {agasc_star['epoch']}, epoch in summary: {star['epoch']:.2f}<br/>"

        if self.alternates:
            cols = ["gaia_id", "d2d", "d_mag", "p_value", "p_relative", "pm_ra", "pm_dec"]
            names = ["baseline"] + list(self.alternates)
            values = list(
                zip(*[list(self.comparison[col].iter_str_vals()) for col in cols])
            )
        else:
            cols = ["agasc_id", "gaia_id", "d2d", "d_mag", "p_value", "p_relative", "pos_catid", "pm_ra", "pm_dec"]
            matches = self.gaia[self.gaia["best_match"]]
            names = ["" for _ in matches]
            values = list(zip(*[list(matches[col].iter_str_vals()) for col in cols]))
        comparison = {
            "names": names,
            "columns": cols,
            "cases": values,
        }

        agasc_id = '_'.join(np.atleast_1d(self.agasc_id).astype(str))
        html = flask.render_template(
            "agasc_gaia/star_report.html",
            agasc_id=agasc_id.replace('_', ', '),
            comment=comment,
            target=target_str,
            agasc=agasc_str,
            comparison=comparison,
            gaia=gaia_str,
            sky_plot_html=sky_plot_html,
        )

        return html

    def save_html(self, path=None, previous_agasc_id=None, next_agasc_id=None):
        path = Path(path) if path else Path()
        agasc_id = '_'.join(np.atleast_1d(self.agasc_id).astype(str))
        filename = path / f"report_{agasc_id}.html"
        path.mkdir(parents=True, exist_ok=True)
        with open(filename, "w") as f:
            f.write(
                self.get_html(
                    previous_agasc_id=previous_agasc_id, next_agasc_id=next_agasc_id
                )
            )


def make_report_list(data, title, description, path, alternates=None, overwrite=False):
    path = Path(path)
    agasc_ids = data['agasc_id']
    for i, agasc_id in tqdm.tqdm(enumerate(agasc_ids)):
        if (path / f"report_{agasc_id}.html").exists() and not overwrite:
            continue
        alt = {
            key: data[data['agasc_id'] == agasc_id][f"gaia_id_{key}"][0] for key in alternates
        } if alternates is not None else None
        prev_star = agasc_ids[i-1] if i > 0 else None
        next_star = agasc_ids[i+1] if i < len(agasc_ids)-1 else None
        report = Report(agasc_id, alternates=alt)
        report.save_html(path=path, previous_agasc_id=prev_star, next_agasc_id=next_star)

    index_file = Path(__file__).parent / "templates" / "star_report_collection.html"
    template = jinja2.Template(
        open(index_file).read()
    )
    data_ = {col: data[col].pformat(max_lines=-1, show_name=False) for col in data.colnames}
    data_ = {name: [val.strip() for val in values] for name, values in data_.items()}
    html = template.render(
        title=title,
        description=description,
        data=data_,
        columns=data.colnames,
        path=".",
    )

    with open(path / 'index.html', 'w') as index_file:
        index_file.write(html)


def make_report_list_by_group(data, title, description, path, overwrite=False):
    path = Path(path)
    for i, group in tqdm.tqdm(enumerate(data.groups)):
        agasc_ids = np.sort(np.unique(group['agasc_id']))
        agasc_id_str = '_'.join(agasc_ids.astype(str))
        if (path / f"report_{agasc_id_str}.html").exists() and not overwrite:
            continue
        prev_star = '_'.join(np.sort(np.unique(data.groups[i-1]['agasc_id'])).astype(str)) if i > 0 else None 
        next_star = '_'.join(np.sort(np.unique(data.groups[i+1]['agasc_id'])).astype(str)) if i < len(data.groups)-1 else None
        report = Report(agasc_ids)
        report.save_html(path=path, previous_agasc_id=prev_star, next_agasc_id=next_star)

    index_file = Path(__file__).parent / "templates" / "star_report_collection.html"
    columns = ["AGASC IDs", "group size", "N_matches"]
    data_ = {
        "agasc_id": ['_'.join(np.sort(np.unique(gr['agasc_id'])).astype(str)) for gr in data.groups],
        "AGASC IDs": [', '.join(np.sort(np.unique(gr['agasc_id'])).astype(str)) for gr in data.groups],
        "group size": data['group_size'].groups.aggregate(np.mean).pformat(max_lines=-1, show_name=False),
        "N_matches": data['best_match'].groups.aggregate(np.count_nonzero).pformat(max_lines=-1, show_name=False),
    }

    template = jinja2.Template(
        open(index_file).read()
    )
    html = template.render(
        title=title,
        description=description,
        data=data_,
        columns=columns,
        path=".",
    )

    with open(path / 'index.html', 'w') as index_file:
        index_file.write(html)
