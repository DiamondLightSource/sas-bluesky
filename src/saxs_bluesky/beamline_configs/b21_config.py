from dodal.beamlines import b21
from dodal.common import inject
from ophyd_async.core import StandardDetector
from ophyd_async.fastcs.panda import HDFPanda

from saxs_bluesky.utils.profile_groups import ExperimentLoader, Group, Profile

"""

Configuration for b21 PandA beamline

"""

# GUI Elements

PULSEBLOCKS = 6  # this is higher than the number of pulseblocks
# so each connection cant have a pulseblock for mutpliers
PULSEBLOCKASENTRYBOX = False
PULSE_BLOCK_NAMES = ["FS", "SAXS/WAXS", "LED1", "LED2", "LED3", "LED4"]
THEME_NAME = "clam"  # --> ('clam', 'alt', 'default', 'classic')

# PandA Wiring connections

TTLIN = {1: "Beamstop V2F", 2: None, 3: None, 4: "TFG WAXS", 5: "TFG FS", 6: "TFG SAXS"}

TTLOUT = {
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


LVDSIN = {1: None, 2: None}


LVDSOUT = {1: "SAXS LVDS Out", 2: "WAXS LVDS Out"}

PULSE_CONNECTIONS = {
    1: [TTLOUT[1]],
    2: [TTLOUT[2], TTLOUT[3]],
    3: [TTLOUT[4]],
    4: [TTLOUT[5]],
    5: [TTLOUT[6]],
    6: [TTLOUT[7]],
}


"""

# Panda plan parameters

"""

# Buffer added to deadtime to handle minor discrepencies between detector
# and panda clocks
DEADTIME_BUFFER = 20e-6
# default sequencer is this one, b21 currently uses seq 1 for somthing else
DEFAULT_SEQ = 2

CONFIG_NAME = "PandaTriggerWithCounterAndPCAP"


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
    wait_pulses=[1, 0, 0, 0, 0, 0],
    run_pulses=[1, 1, 0, 0, 0, 0],
)


DEFAULT_PROFILE = Profile(
    cycles=1,
    seq_trigger="IMMEDIATE",
    groups=[DEFAULT_GROUP],
    multiplier=None,
)

DEFAULT_EXPERIMENT = ExperimentLoader(
    profiles=[DEFAULT_PROFILE],
    instrument=b21.BL,
    detectors=["saxs", "waxs"],
    instrument_session="cm40642-4",
)


FAST_DETECTORS: list[StandardDetector] = [inject("saxs"), inject("waxs")]
DEFAULT_PANDA: HDFPanda = inject("panda2")
