import os
from pathlib import Path

from pydantic_core import from_json

from saxs_bluesky.utils.profile_groups import ExperimentLoader, Group, Profile

SAXS_bluesky_ROOT = Path(__file__)

yaml_dir = os.path.join(
    SAXS_bluesky_ROOT.parent.parent, "src", "saxs_bluesky", "profile_yamls"
)


def test_profile_loader():
    config_filepath = os.path.join(yaml_dir, "panda_config.yaml")
    config = ExperimentLoader.read_from_yaml(config_filepath)

    first_profile = config.profiles[0]

    assert isinstance(first_profile, Profile)
    assert isinstance(first_profile.groups[0], Group)


def test_profile_append():
    P = Profile()
    P.append_group(
        Group(
            frames=1,
            trigger="IMMEDIATE",
            wait_time=1,
            wait_units="S",
            run_time=1,
            run_units="S",
            wait_pulses=[0, 0, 0, 0],
            run_pulses=[1, 1, 1, 1],
        )
    )

    assert isinstance(P, Profile)
    assert len(P.groups) == 1


def test_profile_json():
    P = Profile()
    P.append_group(
        Group(
            frames=1,
            trigger="IMMEDIATE",
            wait_time=1,
            wait_units="S",
            run_time=1,
            run_units="S",
            wait_pulses=[0, 0, 0, 0],
            run_pulses=[1, 1, 1, 1],
        )
    )

    json_schema = P.model_dump_json()

    profile = Profile.model_validate(P)
    converted_profile = Profile.model_validate(
        from_json(json_schema, allow_partial=True)
    )

    assert profile.__dict__ == converted_profile.__dict__


def test_profile_delete():
    P = Profile()

    for _i in range(5):
        P.append_group(
            Group(
                frames=1,
                trigger="IMMEDIATE",
                wait_time=1,
                wait_units="S",
                run_time=1,
                run_units="S",
                wait_pulses=[0, 0, 0, 0],
                run_pulses=[1, 1, 1, 1],
            )
        )

    P.delete_group(len(P.groups) - 1)

    assert len(P.groups) == 4


def test_active_pulses():
    P = Profile()
    P.append_group(
        Group(
            frames=1,
            trigger="IMMEDIATE",
            wait_time=1,
            wait_units="S",
            run_time=1,
            run_units="S",
            wait_pulses=[0, 0, 0, 0],
            run_pulses=[1, 1, 1, 1],
        )
    )

    assert P.active_pulses == [1, 2, 3, 4]
