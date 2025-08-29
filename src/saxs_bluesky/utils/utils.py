import os
from importlib import import_module
from pathlib import Path

############################################################################################
import matplotlib.pyplot as plt
import numpy as np
from dodal.utils import get_beamline_name

from saxs_bluesky.utils.ncdcore import ncdcore
from saxs_bluesky.utils.profile_groups import ExperimentLoader, Profile


def get_saxs_beamline() -> str:
    BL = get_beamline_name(os.getenv("BEAMLINE"))  # type: ignore

    if BL is None:
        BL = "i22"
        os.environ["BEAMLINE"] = BL

    return BL


BL = get_saxs_beamline()


def load_beamline_config():
    BL_CONFIG = import_module(f"saxs_bluesky.beamline_configs.{BL}_config")
    return BL_CONFIG


class ProfilePlotter:
    @staticmethod
    def generate_pulse_signal(
        profile: Profile, pulse: int
    ) -> tuple[np.ndarray, np.ndarray]:
        current_time = 0.0
        trigger_time = [current_time]
        signal = [0]  # starts low and ends low

        for group in profile.groups:
            wait_active = group.wait_pulses[pulse]
            run_active = group.run_pulses[pulse]

            for _frame in range(group.frames):
                current_time += group.wait_time * ncdcore.to_seconds(group.wait_units)
                trigger_time.append(current_time)
                signal.append(wait_active)

                current_time += group.run_time * ncdcore.to_seconds(group.run_units)
                trigger_time.append(current_time)
                signal.append(run_active)

        trigger_time.append(current_time + (current_time) / 10)
        signal.append(0)  # starts low and ends low

        trigger_time = np.asarray(trigger_time)
        signal = np.asarray(signal)

        return trigger_time, signal

    def plot_pulses(self, profile, pulse_names=None):
        if pulse_names is None:
            pulse_names = [f"Seq Pulse {f}" for f in range(len(profile.active_pulses))]

        _, axes = plt.subplots(
            len(profile.active_pulses),
            1,
            sharex=True,
            figsize=(10, len(profile.active_pulses) * 4),
        )  # noqa

        if len(profile.active_pulses) > 0:
            for n, i in enumerate(profile.active_pulses):
                trigger_time, signal = ProfilePlotter.generate_pulse_signal(
                    profile, i - 1
                )

                axes[n].step(trigger_time, signal)
                axes[n].set_ylabel(f"{pulse_names[n]} Signal")

        plt.xlabel("Time (s)")
        plt.show()

    def __init__(self, profile, pulse_names=None):
        self.plot_pulses(profile, pulse_names)


if __name__ == "__main__":
    _REPO_ROOT = Path(__file__).parent.parent.parent.parent

    default_config_path = os.path.join(
        _REPO_ROOT, "src/saxs_bluesky/profile_yamls", "panda_config.yaml"
    )

    experimental_profiles = ExperimentLoader.read_from_yaml(default_config_path)
    profile = experimental_profiles.profiles[0]

    ProfilePlotter(profile)
