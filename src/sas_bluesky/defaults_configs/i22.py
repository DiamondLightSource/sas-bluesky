from functools import cache

from dodal.beamlines import i22

from sas_bluesky.defaults_configs.models import (
    DeviceConfig,
    GUIElements,
    NCDPlanParameters,
    PandAWiring,
    PortMapping,
)
from sas_bluesky.profile_groups import ExperimentProfiles, Group, Profile


@cache
def get_devices() -> DeviceConfig:
    return DeviceConfig(
        FAST_DETECTORS={
            i22.saxs(),
            i22.waxs(),
            # i22.i0(),
            # i22.it(),
        },
        DEFAULT_PANDA=i22.panda1(),
    )


@cache
def get_gui() -> GUIElements:
    return GUIElements(
        PULSEBLOCKS=4,
        USE_MULTIPLIERS=True,
        PULSE_BLOCK_AS_ENTRY_BOX=False,
        PULSE_BLOCK_NAMES=["FS", "DETS/TETS", "OAV", "Fluro"],
        THEME_NAME="clam",
    )


@cache
def get_wiring() -> PandAWiring:
    TTL_OUT: PortMapping = {
        1: "it",
        2: "FS",
        3: "oav",
        4: "User Tet",
        5: "waxs",
        6: "i0",
        7: "saxs",
        8: "Fluores",
        9: "User1",
        10: "User2",
    }

    return PandAWiring(
        TTL_IN={1: "TFG Det", 2: "TFG FS", 3: None, 4: None, 5: None, 6: None},
        TTL_OUT=TTL_OUT,
        LVDS_IN={1: None, 2: None},
        LVDS_OUT={1: None, 2: None},
        PULSE_CONNECTIONS={
            1: [TTL_OUT[2]],
            2: [TTL_OUT[1], TTL_OUT[4], TTL_OUT[5], TTL_OUT[6], TTL_OUT[7]],
            3: [TTL_OUT[3]],
            4: [TTL_OUT[8]],
        },
    )


@cache
def get_plan_params() -> NCDPlanParameters:
    return NCDPlanParameters(DEFAULT_SEQ=1, CONFIG_NAME="PandaTrigger")


@cache
def default_group() -> Group:
    return Group(
        frames=1,
        wait_time=1,
        wait_units="S",
        run_time=1,
        run_units="S",
        pause_trigger="IMMEDIATE",
        wait_pulses=[0, 0, 0, 0],
        run_pulses=[1, 1, 1, 1],
    )


@cache
def default_profile() -> Profile:
    return Profile(
        cycles=1,
        seq_trigger="IMMEDIATE",
        groups=[default_group()],
        multiplier=[1, 1, 1, 1],
    )


def experiment_profile(instrument_session: str) -> ExperimentProfiles:
    return ExperimentProfiles(
        profiles=[default_profile()],
        instrument=i22.BL,
        experiment=str(instrument_session),
        detectors=["saxs", "waxs"],
    )
