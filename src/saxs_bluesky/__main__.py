"""Interface for ``python -m saxs_bluesky``."""

import os
from datetime import datetime
from pathlib import Path

import click
from bluesky import RunEngine

from saxs_bluesky.gui.panda_gui import PandAGUI
from saxs_bluesky.stubs.panda_stubs import return_connected_device, save_device_to_yaml
from saxs_bluesky.utils.utils import get_saxs_beamline, load_beamline_config

from . import __version__

__all__ = ["main"]

BL = get_saxs_beamline()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, message="%(version)s")
@click.pass_context
def main(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")


@main.command(name="start_gui")
def start_gui():
    CONFIG = load_beamline_config()
    PandAGUI(configuration=CONFIG.DEFAULT_EXPERIMENT)


@main.command(name="login")
def login():
    os.system(
        f"blueapi -c ./src/saxs_bluesky/blueapi_configs/{os.environ['BEAMLINE']}_blueapi_config.yaml login"  # noqa
    )


@main.command(name="save_panda")
def save_panda():
    RE = RunEngine()

    CONFIG = load_beamline_config()
    panda_name = CONFIG.DEFAULT_PANDA
    connected_panda = return_connected_device(os.environ["BEAMLINE"], panda_name)
    yaml_name = input("Input name suffix to save:  ")

    if (yaml_name is None) or (yaml_name == ""):
        yaml_name = datetime.now().strftime("%Y-%m-%d")

    yaml_dir = os.path.join(os.path.dirname(Path(__file__)), "ophyd_panda_yamls")
    yaml_filename = f"{BL}_{panda_name}_{yaml_name}"

    RE(
        save_device_to_yaml(
            yaml_directory=yaml_dir,
            yaml_file_name=yaml_filename,
            device=connected_panda,
        )
    )

    print(f"Saved PandA yaml to {yaml_dir}/{yaml_filename}.yaml")


if __name__ == "__main__":
    main()
