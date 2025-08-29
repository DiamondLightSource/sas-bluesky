import os
from pathlib import Path
from string import ascii_lowercase
from typing import Any

import numpy as np
import yaml
from ophyd_async.core import in_micros
from ophyd_async.fastcs.panda import SeqTable, SeqTableInfo, SeqTrigger
from pydantic import BaseModel
from pydantic.dataclasses import dataclass as pydanticdataclass

from saxs_bluesky.utils.ncdcore import ncdcore

"""

Group and Profile BaseModels

"""


class Group(BaseModel):
    """A Group represents the information of one line in the PandA sequence table.
    Additional information is stored and used for configuration in the GUI
    This can be used alonside the Profile class
    to build up complex experimental profiles"""

    frames: int
    trigger: str
    wait_time: int
    wait_units: str
    run_time: int
    run_units: str
    wait_pulses: list[int]
    run_pulses: list[int]
    # created by model_post_init
    # wait_time_s: float = 0.0
    # run_time_s: float = 0.0
    # group_duration: float = 0.0

    def model_post_init(self, __context: Any) -> None:
        assert len(self.wait_pulses) == len(self.run_pulses)
        self.run_units = self.run_units.upper()
        self.wait_units = self.wait_units.upper()
        self.trigger = self.trigger.upper()

    @property
    def wait_time_s(self) -> float:
        return self.wait_time * ncdcore.to_seconds(self.wait_units)

    @property
    def run_time_s(self) -> float:
        return self.run_time * ncdcore.to_seconds(self.run_units)

    @property
    def group_duration(self) -> float:
        return (self.wait_time_s + self.run_time_s) * self.frames

    def seq_row(self) -> SeqTable:
        if not self.trigger:
            trigger = SeqTrigger.IMMEDIATE
        elif self.trigger == "FALSE":
            trigger = SeqTrigger.IMMEDIATE
            self.trigger = "IMMEDIATE"
        else:
            trigger = eval(f"SeqTrigger.{self.trigger}")

        seq_table_kwargs = {
            "repeats": self.frames,
            "trigger": trigger,
            "position": 0,
            "time1": in_micros(self.wait_time_s),
        }

        alphabet = list(ascii_lowercase)

        out1 = {
            f"out{alphabet[f]}1": self.wait_pulses[f]
            for f in range(len(self.wait_pulses))
        }
        seq_table_kwargs.update(out1)

        seq_table_kwargs.update({"time2": in_micros(self.run_time_s)})

        out2 = {
            f"out{alphabet[f]}2": self.run_pulses[f]
            for f in range(len(self.run_pulses))
        }
        seq_table_kwargs.update(out2)

        seq_table = SeqTable.row(**seq_table_kwargs)

        return seq_table


class Profile(BaseModel):
    """A basemodel for all the information needed to configure the PandA triggering.
    Cycles are the number of times the who sequence table is run
    Seq trigger must be set to either immediate or one of the panda trigger types.
    A group is effectively a line in the sequencer table
    Multiplier is use when the PandA is set up for triggering different
    sets of detetcors at different rates
    The information stored in this BaseModel can be passed to ncd_panda and applied.
    The information can also be used to configure it in the gui"""

    cycles: int = 1
    seq_trigger: str = "Immediate"
    groups: list[Group] = []
    multiplier: list[int] | None = None

    @property
    def total_frames(self) -> int:
        total_frames = 0
        for n_group in self.groups:
            total_frames += n_group.frames
        return total_frames

    @property
    def duration_per_cycle(self) -> float:
        duration_per_cycle = 0

        for n_group in self.groups:
            duration_per_cycle += n_group.group_duration
        return duration_per_cycle

    @property
    def duration(self) -> float:
        duration = self.duration_per_cycle * self.cycles
        return duration

    @property
    def seq_table_info(self) -> SeqTableInfo:
        seq_table_info = SeqTableInfo(
            sequence_table=self.seq_table, repeats=self.cycles
        )

        return seq_table_info

    @property
    def active_pulses(self) -> list[int]:
        """
        Checks which outputs are active in the wait phase,
        checks which outputs are active in the run phase
        and returns a list of active outputs. Because python uses 0-based indexing
        while the Panda uses 1-based indexing,
        the output indices are adjusted accordingly.
        """
        wait_matrix = np.array([g.wait_pulses for g in self.groups])
        run_matrix = np.array([g.run_pulses for g in self.groups])
        active_matrix = wait_matrix + run_matrix
        active_pulses = np.where((np.sum(active_matrix, axis=0)) != 0)[0] + 1
        active_pulses = active_pulses.tolist()

        return active_pulses

    @property
    def triggers(self) -> list[int]:
        # [3, 1, 1, 1, 1] or something
        return [group.frames for group in self.groups]

    @property
    def number_of_events(self) -> list[int]:
        return self.triggers * self.cycles

    def append_group(self, Group: Group) -> None:
        self.groups.append(Group)

    def delete_group(self, n: int) -> None:
        self.groups.pop(n)

    def insert_group(self, n: int, Group: Group):
        self.groups.insert(n, Group)

    @property
    def seq_table(self) -> SeqTable:
        seq_tables = (group.seq_row() for group in self.groups)

        seq = seq_tables.__next__()
        for table in seq_tables:
            seq = seq + table

        return seq

    @staticmethod
    def inputs() -> list[str]:
        TTLINS = [f"TTLIN{f + 1}" for f in range(6)]
        LVDSINS = [f"LVDSIN{f + 1}" for f in range(2)]
        return TTLINS + LVDSINS

    @staticmethod
    def seq_triggers() -> list[str]:
        return list(SeqTrigger.__dict__["_member_names_"])

    @staticmethod
    def outputs() -> list[str]:
        TTLOUTS = [f"TTLOUT{f + 1}" for f in range(10)]
        LVDSOUTS = [f"LVDSOUT{f + 1}" for f in range(2)]
        return TTLOUTS + LVDSOUTS


@pydanticdataclass
class ExperimentLoader:
    """
    The stores multiple Profiles and can be used in the GUI.
    The is analoaghous to the information shown in the legacy
    ncd_detectors configuration GUI in GDA
    These can be stored as yaml files or as objects and used for experiments
    """

    profiles: list[Profile]
    instrument: str
    detectors: list[str]
    instrument_session: str = ""

    def __post_init__(self):
        self.n_profiles = len(self.profiles)

    @staticmethod
    def read_from_yaml(config_filepath: str | Path):
        """Reads an Experimental configuration, containing n profiles
        and generates a ExperimentalProfiles object"""
        with open(config_filepath, "rb") as file:
            print("Using config:", config_filepath)

            if not os.path.exists(config_filepath):
                raise FileNotFoundError(f"Cannot find file: {config_filepath}")

            config = yaml.full_load(file)

            instrument = config["instrument"]
            detectors = config["detectors"]

            profile_names = [f for f in config if f.startswith("profile")]
            profiles = []

            for profile_name in profile_names:
                profile_cycles = config[profile_name]["cycles"]
                profile_trigger = config[profile_name]["seq_trigger"]
                multiplier = config[profile_name]["multiplier"]
                groups = {
                    key: config[profile_name][key]
                    for key in config[profile_name].keys()
                    if key.startswith("group")
                }
                group_list = []

                for group_name in groups.keys():
                    group = config[profile_name][group_name]

                    n_Group = Group(
                        frames=group["frames"],
                        trigger=group["trigger"],
                        wait_time=group["wait_time"],
                        wait_units=group["wait_units"],
                        run_time=group["run_time"],
                        run_units=group["run_units"],
                        wait_pulses=group["wait_pulses"],
                        run_pulses=group["run_pulses"],
                    )

                    group_list.append(n_Group)

                n_profile = Profile(
                    cycles=profile_cycles,
                    seq_trigger=profile_trigger,
                    groups=group_list,
                    multiplier=multiplier,
                )

                profiles.append(n_profile)

            return ExperimentLoader(profiles, instrument, detectors)

    def to_dict(self) -> dict:
        exp_dict = {
            "title": "Panda Configure",
            "instrument": self.instrument,
            "detectors": self.detectors,
        }

        for p, profile in enumerate(self.profiles):
            profile_dict = profile.model_dump()
            del profile_dict["groups"]

            for g, group in enumerate(profile.groups):
                group_dict = group.model_dump()
                profile_dict["group-" + str(g)] = group_dict

            exp_dict["profile-" + str(p)] = profile_dict

        return exp_dict

    def save_to_yaml(self, filepath: str | Path):
        print("Saving configuration to:", filepath)

        config_dict = self.to_dict()

        with open(filepath, "w") as outfile:
            yaml.dump(
                config_dict,
                outfile,
                default_flow_style=None,
                sort_keys=False,
                indent=2,
                explicit_start=True,
            )

    def delete_profile(self, n: int):
        """Deletes the nth profile from the object"""
        self.profiles.pop(n)
        self.__post_init__()

    def append_profile(self, Profile: Profile):
        self.profiles.append(Profile)
        self.__post_init__()
