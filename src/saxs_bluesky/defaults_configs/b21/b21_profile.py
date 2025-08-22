from dodal.beamlines import b21

from saxs_bluesky.utils.profile_groups import ExperimentProfiles, Group, Profile

DEFAULT_GROUP = Group(
    frames=1,
    wait_time=1,
    wait_units="S",
    run_time=1,
    run_units="S",
    pause_trigger="IMMEDIATE",
    wait_pulses=[1, 0, 0, 0, 0, 0],
    run_pulses=[1, 1, 0, 0, 0, 0],
)


DEFAULT_PROFILE = Profile(
    cycles=1,
    seq_trigger="IMMEDIATE",
    groups=[DEFAULT_GROUP],
    multiplier=[1, 1, 1, 1, 1, 1],
)

DEFAULT_EXPERIMENT = ExperimentProfiles(
    profiles=[DEFAULT_PROFILE],
    instrument=b21.BL,
    detectors=["saxs", "waxs"],
)
