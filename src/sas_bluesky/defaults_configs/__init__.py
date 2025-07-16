from functools import cache

from sas_bluesky.defaults_configs.models import (
    DeviceConfig,
    GUIElements,
    NCDPlanParameters,
    PandAWiring,
)
from sas_bluesky.profile_groups import ExperimentProfiles, Group, Profile

from . import b21, i22


@cache
def get_devices(instrument: str) -> DeviceConfig:
    if instrument == "b21":
        return b21.get_devices()
    return i22.get_devices()


@cache
def get_gui(instrument: str) -> GUIElements:
    if instrument == "b21":
        return b21.get_gui()
    return i22.get_gui()


@cache
def get_wiring(instrument: str) -> PandAWiring:
    if instrument == "b21":
        return b21.get_wiring()
    return i22.get_wiring()


@cache
def get_plan_params(instrument: str) -> NCDPlanParameters:
    if instrument == "b21":
        return b21.get_plan_params()
    return i22.get_plan_params()


@cache
def default_group(instrument: str) -> Group:
    if instrument == "b21":
        return b21.default_group()
    return i22.default_group()


@cache
def default_profile(instrument: str) -> Profile:
    if instrument == "b21":
        return b21.default_profile()
    return i22.default_profile()


def experiment_profile(instrument: str, instrument_session: str) -> ExperimentProfiles:
    if instrument == "b21":
        return b21.experiment_profile(instrument_session)
    return i22.experiment_profile(instrument_session)
