from functools import cache

from dodal.beamlines import b21

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
            b21.saxs(),
            b21.waxs(),
        },
        DEFAULT_PANDA=b21.panda2(),
    )


@cache
def get_gui() -> GUIElements:
    return GUIElements(
        PULSEBLOCKS=6,  # this is higher than the number of pulseblocks
        # so each connection cant have a pulseblock for mutpliers
        USE_MULTIPLIERS=False,
        PULSE_BLOCK_AS_ENTRY_BOX=False,
        PULSE_BLOCK_NAMES=["FS", "SAXS/WAXS", "LED1", "LED2", "LED3", "LED4"],
        THEME_NAME="clam",
    )


@cache
def get_wiring() -> PandAWiring:
    TTL_OUT: PortMapping = {
        1: "FS",
        2: "SAXS",
        3: "WAXS",
        4: "LED1",
        5: "LED2",
        6: "LED3",
        7: "LED4",
        8: None,
        9: None,
        10: "V2F Relay",
    }

    return PandAWiring(
        TTL_IN={
            1: "Beamstop V2F",
            2: None,
            3: None,
            4: "TFG WAXS",
            5: "TFG FS",
            6: "TFG SAXS",
        },
        TTL_OUT=TTL_OUT,
        LVDS_IN={1: None, 2: None},
        LVDS_OUT={1: "SAXS LVDS Out", 2: "WAXS LVDS Out"},
        PULSE_CONNECTIONS={
            1: [TTL_OUT[1]],
            2: [TTL_OUT[2], TTL_OUT[3]],
            3: [TTL_OUT[4]],
            4: [TTL_OUT[5]],
            5: [TTL_OUT[6]],
            6: [TTL_OUT[7]],
        },
    )


@cache
def get_plan_params() -> NCDPlanParameters:
    return NCDPlanParameters(
        # default sequencer is this one, b21 currently uses seq 1 for somthing else
        DEFAULT_SEQ=2,
        CONFIG_NAME="PandaTriggerWithCounterAndPCAP",
    )


@cache
def default_group() -> Group:
    return Group(
        frames=1,
        wait_time=1,
        wait_units="S",
        run_time=1,
        run_units="S",
        pause_trigger="IMMEDIATE",
        wait_pulses=[1, 0, 0, 0, 0, 0],
        run_pulses=[1, 1, 0, 0, 0, 0],
    )


@cache
def default_profile() -> Profile:
    return Profile(
        cycles=1,
        seq_trigger="IMMEDIATE",
        groups=[default_group()],
        multiplier=[1, 1, 1, 1, 1, 1],
    )


def experiment_profile(instrument_session: str) -> ExperimentProfiles:
    return ExperimentProfiles(
        profiles=[default_profile()],
        instrument=b21.BL,
        experiment=str(instrument_session),
        detectors=["saxs", "waxs"],
    )
