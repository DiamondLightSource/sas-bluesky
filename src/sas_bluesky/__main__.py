"""Interface for ``python -m sas_bluesky``."""

import click
from bluesky import RunEngine
from dodal.utils import get_beamline_name
from ophyd_async.plan_stubs import ensure_connected

from sas_bluesky.defaults_configs import experiment_profile, get_devices
from sas_bluesky.panda_gui import PandAGUI
from sas_bluesky.stubs.panda_stubs import save_device_to_yaml

from . import __version__

__all__ = ["main"]
BL = get_beamline_name("i22")


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, message="%(version)s")
@click.pass_context
def main(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")


@main.command(name="start_gui")
def start_gui(instrument_session: str):
    PandAGUI(configuration=experiment_profile(BL, instrument_session))


@main.command(name="save_panda")
def save_panda():
    RE = RunEngine()

    panda = get_devices(BL).DEFAULT_PANDA
    RE(ensure_connected(panda))
    yaml_dir = input("Input directory to save")
    RE(
        save_device_to_yaml(
            yaml_directory=yaml_dir,
            yaml_file_name=f"{panda.name}_SAVED",
            device=panda,
        )
    )  # noqa


if __name__ == "__main__":
    main()
