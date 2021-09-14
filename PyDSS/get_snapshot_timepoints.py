"""Logic to determine snapshot time point by mode"""

import logging
from pathlib import Path
import pandas as pd
import opendssdirect as dss
import numpy as np
from PyDSS.common import SnapshotTimePointSelectionMode
from PyDSS.utils.simulation_utils import create_loadshape_pmult_dataframe_for_simulation
from PyDSS.utils.utils import dump_data
from PyDSS.reports.reports import logger


logger = logging.getLogger(__name__)


def get_snapshot_timepoint(options, mode: SnapshotTimePointSelectionMode):
    pv_systems = dss.PVsystems.AllNames()
    if not pv_systems:
        logger.info("No PVSystems are present.")
        if mode != SnapshotTimePointSelectionMode.MAX_LOAD:
            mode = SnapshotTimePointSelectionMode.MAX_LOAD
            logger.info("Changed mode to %s", SnapshotTimePointSelectionMode.MAX_LOAD.value)
    if mode == SnapshotTimePointSelectionMode.MAX_LOAD:
        column = "Max Load"
    elif mode == SnapshotTimePointSelectionMode.MAX_PV_LOAD_RATIO:
        column = "Max PV to Load Ratio"
    elif mode == SnapshotTimePointSelectionMode.DAYTIME_MIN_LOAD:
        column = "Min Daytime Load"
    elif mode == SnapshotTimePointSelectionMode.MAX_PV_MINUS_LOAD:
        column = "Max PV minus Load"
    else:
        assert False, f"{mode} is not supported"

    filename = Path(options['Project']['Project Path']) / options["Project"]["Active Project"] / "Exports" / "snapshot_time_points.json"
    if filename.exists():
        timepoints = pd.read_json(filename)
        return pd.to_datetime(timepoints[column][0]).to_pydatetime()
    pv_generation_hours = {'start_time': '8:00', 'end_time': '17:00'}
    aggregate_profiles = pd.DataFrame(columns=['Load', 'PV'])
    pv_shapes = {}
    for pv_name in pv_systems:
        dss.PVsystems.Name(pv_name)
        pmpp = float(dss.Properties.Value('Pmpp'))
        profile_name = dss.Properties.Value('yearly')
        dss.LoadShape.Name(profile_name)
        if profile_name not in pv_shapes.keys():
            pv_shapes[profile_name] = create_loadshape_pmult_dataframe_for_simulation(options)
        aggregate_profiles['PV'] = aggregate_profiles['PV'].replace(np.nan, 0) + (pv_shapes[profile_name] * pmpp)[0]
    del pv_shapes

    loads = dss.Loads.AllNames()
    if not loads:
        logger.info("No Loads are present")
    load_shapes = {}
    for load_name in loads:
        dss.Loads.Name(load_name)
        kw = float(dss.Properties.Value('kW'))
        profile_name = dss.Properties.Value('yearly')
        dss.LoadShape.Name(profile_name)
        if profile_name not in load_shapes.keys():
            load_shapes[profile_name] = create_loadshape_pmult_dataframe_for_simulation(options)
        aggregate_profiles['Load'] = aggregate_profiles['Load'].replace(np.nan, 0) + (load_shapes[profile_name] * kw)[0]
    del load_shapes
    if pv_systems:
        aggregate_profiles['PV to Load Ratio'] = aggregate_profiles['PV'] / aggregate_profiles['Load']
        aggregate_profiles['PV minus Load'] = aggregate_profiles['PV'] - aggregate_profiles['Load']

    timepoints = pd.DataFrame(columns=['Timepoints'])
    timepoints.loc['Max Load'] = aggregate_profiles['Load'].idxmax()
    if pv_systems:
        timepoints.loc['Max PV to Load Ratio'] = aggregate_profiles.between_time(pv_generation_hours['start_time'],
                                                                                 pv_generation_hours['end_time'])['PV to Load Ratio'].idxmax()
        timepoints.loc['Max PV minus Load'] = aggregate_profiles.between_time(pv_generation_hours['start_time'],
                                                                              pv_generation_hours['end_time'])['PV minus Load'].idxmax()
        timepoints.loc['Max PV'] = aggregate_profiles.between_time(pv_generation_hours['start_time'],
                                                                   pv_generation_hours['end_time'])['PV'].idxmax()
    timepoints.loc['Min Load'] = aggregate_profiles['Load'].idxmin()
    timepoints.loc['Min Daytime Load'] = aggregate_profiles.between_time(pv_generation_hours['start_time'],
                                                                         pv_generation_hours['end_time'])['Load'].idxmin()
    logger.info("Time points: %s", {k: str(v) for k, v in timepoints.to_records()})
    dump_data(timepoints.astype(str).to_dict(orient='index'), filename, indent=2)
    return timepoints.loc[column][0].to_pydatetime()
