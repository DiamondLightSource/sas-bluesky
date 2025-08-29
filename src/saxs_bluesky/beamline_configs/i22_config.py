"""

Configuration for i22 PandA beamline

"""

from dodal.beamlines import i22
from dodal.common import inject
from ophyd_async.core import StandardDetector
from ophyd_async.fastcs.panda import HDFPanda

from saxs_bluesky.utils.profile_groups import ExperimentLoader, Group, Profile

FAST_DETECTORS: list[StandardDetector] = [
    inject("saxs"),
    inject("waxs"),
    # inject("i0"),
    # inject("it"),
]


DEFAULT_PANDA: HDFPanda = inject("panda1")

# GUI Elements

PULSEBLOCKS = 4
PULSEBLOCKASENTRYBOX = False
PULSE_BLOCK_NAMES = ["FS", "DETS/TETS", "OAV", "Fluro"]
THEME_NAME = "clam"  # --> ('clam', 'alt', 'default', 'classic')

# PandA Wiring connections

TTLIN = {1: "TFG Det", 2: "TFG FS", 3: None, 4: None, 5: None, 6: None}

TTLOUT = {
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


LVDSIN = {1: None, 2: None}


LVDSOUT = {1: None, 2: None}

PULSE_CONNECTIONS = {
    1: [TTLOUT[2]],
    2: [TTLOUT[1], TTLOUT[4], TTLOUT[5], TTLOUT[6], TTLOUT[7]],
    3: [TTLOUT[3]],
    4: [TTLOUT[8]],
}

"""
# ncd plan parameters
"""

DEADTIME_BUFFER = 20e-6  # Buffer added to deadtime to handle minor discrepencies between detector and panda clocks #noqa
DEFAULT_SEQ = 1  # default sequencer is this one, pandas can have 2
CONFIG_NAME = "PandaTrigger"


"""
# DEFAULT PROFILES
"""

DEFAULT_GROUP = Group(
    frames=1,
    trigger="IMMEDIATE",
    wait_time=1,
    wait_units="S",
    run_time=1,
    run_units="S",
    wait_pulses=[0, 0, 0, 0],
    run_pulses=[1, 1, 1, 1],
)


DEFAULT_PROFILE = Profile(
    cycles=1, seq_trigger="IMMEDIATE", groups=[DEFAULT_GROUP], multiplier=[1, 1, 1, 1]
)

DEFAULT_EXPERIMENT = ExperimentLoader(
    profiles=[DEFAULT_PROFILE],
    instrument=i22.BL,
    detectors=["saxs", "waxs"],
    instrument_session="cm40643-4",
)
