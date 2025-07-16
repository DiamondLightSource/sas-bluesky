import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from bluesky.run_engine import RunEngine
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.common.beamlines.beamline_utils import set_path_provider
from dodal.common.visit import RemoteDirectoryServiceClient, StaticVisitPathProvider
from dodal.log import LOGGER
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from dodal.utils import get_beamline_name
from ophyd_async.core import (
    DetectorTrigger,
    StandardDetector,
    StandardFlyer,
    TriggerInfo,
    wait_for_value,
)
from ophyd_async.fastcs.panda import (
    HDFPanda,
    PandaBitMux,
    SeqTableInfo,
    StaticSeqTableTriggerLogic,
)
from ophyd_async.plan_stubs import ensure_connected, get_current_settings
from pydantic import validate_call  # ,NonNegativeFloat,

from sas_bluesky.defaults_configs import get_devices, get_gui, get_plan_params
from sas_bluesky.profile_groups import ExperimentProfiles, Profile  # Group
from sas_bluesky.stubs.panda_stubs import (
    fly_and_collect_with_wait,
    load_settings_from_yaml,
    upload_yaml_to_panda,
)

BL = get_beamline_name("i22")
gui_config = get_gui(BL)
default_devices = get_devices(BL)
plan_params = get_plan_params(BL)


def wait_until_complete(pv_obj, waiting_value=0, timeout=None):
    """
    An async wrapper for the ophyd async wait_for_value function,
    to allow it to run inside the bluesky run engine
    Typical use case is waiting for an active pv to change to 0,
    indicating that the run has finished, which then allows the
    run plan to disarm all the devices.
    """

    async def _wait():
        await wait_for_value(pv_obj, waiting_value, timeout=timeout)

    yield from bps.wait_for([_wait])


def set_experiment_directory(beamline: str, visit_path: Path):
    """Updates the root folder"""

    print("should not require this to also be set in i22.py")

    path_provider = StaticVisitPathProvider(
        beamline,
        Path(visit_path),
        client=RemoteDirectoryServiceClient(f"http://{beamline}-control:8088/api"),
    )
    set_path_provider(path_provider)

    suffix = datetime.now().strftime("_%Y%m%d%H%M%S")

    async def set_panda_dir():
        await path_provider.update(directory=visit_path, suffix=suffix)

    yield from bps.wait_for([set_panda_dir])


def modify_panda_seq_table(panda: HDFPanda, profile: Profile, n_seq=1):
    """

    Modifies the panda sequencer table,

    the default sequencer table to modify is the first one.

    Takes the panda and a Profile and then uses this to apply the sequencer table

    """

    seq_table = profile.seq_table()
    n_cycles = profile.cycles
    # time_unit = profile.best_time_unit

    group = "modify-seq"
    # yield from bps.stage(panda, group=group) ###maybe need this
    yield from bps.abs_set(panda.seq[int(n_seq)].table, seq_table, group=group)
    yield from bps.abs_set(panda.seq[int(n_seq)].repeats, n_cycles, group=group)
    yield from bps.abs_set(panda.seq[int(n_seq)].prescale, 1, group=group)
    yield from bps.abs_set(panda.seq[int(n_seq)].prescale_units, "s", group=group)
    yield from bps.wait(group=group, timeout=plan_params.GENERAL_TIMEOUT)


def arm_panda_pulses(panda: HDFPanda, pulses: list[int], n_seq=1, group="arm_panda"):
    """

    Takes a HDFPanda and a list of integers corresponding

    to the number of the pulse blocks.

    Iterates through the numbered pulse blocks

    and arms them and then waits for all to be armed.

    """

    for n_pulse in pulses:
        yield from bps.abs_set(
            panda.pulse[int(n_pulse)].enable,  # type: ignore
            PandaBitMux.ONE.value,
            group=group,
        )

    yield from bps.wait(group=group, timeout=plan_params.GENERAL_TIMEOUT)


def disarm_panda_pulses(
    panda: HDFPanda, pulses: list[int], n_seq=1, group="disarm_panda"
):
    """

    Takes a HDFPanda and a list of integers

    corresponding to the number of the pulse blocks.

    Iterates through the numbered pulse blocks

    and disarms them and then waits for all to be disarmed.

    """

    for n_pulse in pulses:
        yield from bps.abs_set(
            panda.pulse[n_pulse].enable,  # type: ignore
            PandaBitMux.ZERO.value,
            group=group,
        )

    yield from bps.wait(group=group, timeout=plan_params.GENERAL_TIMEOUT)


def stage_and_prepare_detectors(
    detectors: list[StandardDetector],
    flyer: StandardFlyer,
    trigger_info: TriggerInfo,
    group="det_atm",
):
    """

    Iterates through all of the detectors specified and prepares them.

    """

    yield from bps.stage_all(*detectors, flyer, group=group)

    for det in detectors:
        ###this tells the detector how may triggers to expect and sets the CAN aquire on
        yield from bps.prepare(det, trigger_info, wait=False, group=group)

    yield from bps.wait(group=group, timeout=plan_params.GENERAL_TIMEOUT)


def return_deadtime(
    detectors: list[StandardDetector], exposure: float = 1.0
) -> np.ndarray:
    """
    Given a list of connected detector devices, and an exposure time,
    it returns an array of the deadtime for each detector
    """

    deadtime = (
        np.array([det._controller.get_deadtime(exposure) for det in detectors])  # noqa: SLF001
        + plan_params.DEADTIME_BUFFER
    )
    return deadtime


def set_panda_output(
    panda: HDFPanda, output_type: str, output: int, state: str, group="switch"
):
    """
    Set a Panda output (TTL or LVDS) to a specified state (ON or OFF).

    Args:
        panda (HDFPanda): The Panda device.
        output_type (str): Type of output ("TTL" or "LVDS").
        output (int): Output number.
        state (str): Desired state ("ON" or "OFF").
        group (str): Bluesky group name.
    """
    state_value = (
        PandaBitMux.ONE.value if state.upper() == "ON" else PandaBitMux.ZERO.value
    )
    output_attr = getattr(panda, f"{output_type.lower()}out")[int(output)]
    yield from bps.abs_set(output_attr.val, state_value, group=group)
    yield from bps.wait(group=group, timeout=plan_params.GENERAL_TIMEOUT)


def generate_repeated_trigger_info(
    profile: Profile,
    max_deadtime: float,
    livetime: float,
    trigger=DetectorTrigger.CONSTANT_GATE,
):
    repeated_trigger_info = []

    # [3, 1, 1, 1, 1] or something
    n_triggers = [group.frames for group in profile.groups]
    n_cycles = profile.cycles

    for multiplier in profile.multiplier:
        trigger_info = TriggerInfo(
            number_of_events=n_triggers * n_cycles,
            trigger=trigger,
            deadtime=max_deadtime,
            livetime=profile.duration,
            exposures_per_event=multiplier,
            exposure_timeout=None,
        )

        repeated_trigger_info.append(trigger_info)


def check_and_apply_panda_settings(panda: HDFPanda, panda_name: str) -> MsgGenerator:
    """

    Checks the settings currently on the PandA

    - if different they will be overwritten with the ones

    specified in the plan_params.CONFIG_NAME

    Settings may have changed due to Malcolm or

    someone chnaging things in EPICS which might prevent the plan from running

    This mitigates that

    """

    # this is the directory where the yaml files are stored
    yaml_directory = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "ophyd_panda_yamls"
    )
    yaml_file_name = f"{BL}_{plan_params.CONFIG_NAME}_{panda_name}"

    current_panda_settings = yield from get_current_settings(panda)
    yaml_settings = yield from load_settings_from_yaml(yaml_directory, yaml_file_name)

    if current_panda_settings.__dict__ != yaml_settings.__dict__:
        print(
            (
                "Current Panda settings do not match the yaml settings, ",
                "loading yaml settings to panda",
            )
        )
        LOGGER.info(
            (
                "Current Panda settings do not match the yaml settings, ",
                "loading yaml settings to panda",
            )
        )

        print(f"{yaml_file_name}.yaml has been uploaded to PandA")
        LOGGER.info(f"{yaml_file_name}.yaml has been uploaded to PandA")
        ######### make sure correct yaml is loaded
        yield from upload_yaml_to_panda(
            yaml_directory=yaml_directory, yaml_file_name=yaml_file_name, panda=panda
        )


def inject_all(active_detector_names: list[str]) -> list[StandardDetector]:
    """

    Injects all of the devices into the dodal common beamline devices,
    so that they can be used in the plans

    """

    active_detectors = [inject(dev) for dev in active_detector_names]

    return active_detectors


def multiple_pulse_blocks():
    pass
    # for pulse in gui.PULSEBLOCKS
    #   get the pulse block, find out what is attached to it
    #   set the multiplier and possibly duration accordingly
    #   for det in detectors_on_pulse_block:
    #       trigger_info = TriggerInfo(number_of_triggers=n_triggers*n_cycles,
    #                                   trigger=DetectorTrigger.CONSTANT_GATE,
    #                                  deadtime=max_deadtime,
    #                                  multiplier=1,
    #                                 frame_timeout=None)


def show_deadtime(detector_deadtime, active_detector_names):
    """

    Takes two iterables, detetors deadtimes and detector names,
    and prints the deadtimes in the log

    """

    for dt, dn in zip(detector_deadtime, active_detector_names, strict=True):
        print(f"deadtime for {dn} is {dt}")
        LOGGER.info(f"deadtime for {dn} is {dt}")


@validate_call(config={"arbitrary_types_allowed": True})
def configure_panda_triggering(
    beamline: Annotated[str, "Name of the beamline to run the scan on eg. i22 or b21."],
    experiment: Annotated[
        str,
        "Experiment name eg. cm12345. This will go into /dls/data/beamline/experiment",
    ],
    profile: Annotated[
        Profile,
        (
            "Profile or json of a Profile containing the infomation required to setup ",
            "the panda, triggers, times etc",
        ),
    ],
    detectors: Annotated[
        set[StandardDetector],
        "List of str of the detector names, eg. saxs, waxs, i0, it",
    ] = default_devices.FAST_DETECTORS,
    panda: HDFPanda = default_devices.DEFAULT_PANDA,
    force_load=True,
) -> MsgGenerator[None]:
    """

    This plans configures the panda and the detectors,

    setting them up for hardware triggering, loads all of the correct

    settings.

    """
    visit_path = os.path.join(
        f"/dls/{beamline}/data", str(datetime.now().year), experiment
    )

    LOGGER.info(f"Data will be saved in {visit_path}")
    print(f"Data will be saved in {visit_path}")

    yield from set_experiment_directory(beamline, Path(visit_path))

    try:
        yield from ensure_connected(panda)  # ensure the panda is connected
    except Exception as e:
        LOGGER.error(f"Failed to connect to PandA: {e}")
        raise

    print("\n", detectors, "\n")
    LOGGER.info("\n", detectors, "\n")

    for device in detectors:
        try:
            yield from ensure_connected(device)
            print(f"{device.name} is connected")
        except Exception as e:
            LOGGER.error(f"{device} not connected: {e}")
            raise

    detector_deadtime = return_deadtime(
        detectors=list(detectors), exposure=profile.duration
    )

    max_deadtime = max(detector_deadtime)
    # show_deadtime(detector_deadtime, max_deadtime)

    # load Panda setting to panda
    if force_load is True:
        yield from check_and_apply_panda_settings(panda, panda.name)

    n_cycles = profile.cycles
    # seq table should be grabbed from the panda and used instead,
    # in order to decouple run from setup panda
    seq_table = profile.seq_table()
    n_triggers = [
        group.frames for group in profile.groups
    ]  # [3, 1, 1, 1, 1] or something
    duration = profile.duration

    ############################################################
    # ###setup triggering of detectors
    table_info = SeqTableInfo(sequence_table=seq_table, repeats=n_cycles)

    # set up trigger info etc
    trigger_info = TriggerInfo(
        number_of_events=n_triggers * n_cycles,
        trigger=DetectorTrigger.CONSTANT_GATE,  # or maybe EDGE_TRIGGER
        deadtime=max_deadtime,
        livetime=np.amax(profile.duration_per_cycle),
        exposures_per_event=1,
        exposure_timeout=duration,
    )

    ############################################################
    # flyer and prepare fly, sets the sequencers table
    trigger_logic = StaticSeqTableTriggerLogic(panda.seq[plan_params.DEFAULT_SEQ])
    flyer = StandardFlyer(trigger_logic)

    # ####stage the detectors, the flyer, the panda
    # setup triggering on panda - changes the sequence table
    # - wait otherwise risking _context missing error
    yield from bps.prepare(flyer, table_info, wait=True)

    ###change the sequence table
    # this is the last thing setting up the panda
    yield from stage_and_prepare_detectors(list(detectors), flyer, trigger_info)


@attach_data_session_metadata_decorator
@bpp.run_decorator()  #    # open/close run
@validate_call(config={"arbitrary_types_allowed": True})
def run_panda_triggering(
    panda: HDFPanda, active_detectors, active_pulses: list[int], group="run"
) -> MsgGenerator[None]:
    """

    This will run whatever flyscanning settings
    are currenly loaded on the PandA and start it triggering

    """
    # flyer and prepare fly, sets the sequencers table
    trigger_logic = StaticSeqTableTriggerLogic(panda.seq[plan_params.DEFAULT_SEQ])
    flyer = StandardFlyer(trigger_logic)

    ##########################
    # arm the panda pulses
    yield from arm_panda_pulses(panda=panda, pulses=active_pulses)

    ###########################
    yield from fly_and_collect_with_wait(
        stream_name="primary",
        detectors=active_detectors,
        flyer=flyer,
    )
    ##########################
    ###########################
    ####start diabling and unstaging everything
    yield from wait_until_complete(panda.seq[plan_params.DEFAULT_SEQ].active, False)
    # start set to false because currently don't actually want to collect data
    yield from disarm_panda_pulses(panda=panda, pulses=active_pulses)
    yield from bps.unstage_all(*active_detectors, flyer)  # stops the hdf capture mode


@attach_data_session_metadata_decorator
@bpp.run_decorator()  #    # open/close run
def configure_and_run_panda_triggering(
    beamline: Annotated[str, "Name of the beamline to run the scan on eg. i22 or b21."],
    experiment: Annotated[
        str,
        "Experiment name eg. cm12345. This will go into /dls/data/beamline/experiment",
    ],
    profile: Annotated[
        Profile,
        (
            "Profile or json of a Profile containing the infomation required to setup ",
            "the panda, triggers, times etc",
        ),
    ],
    detectors: Annotated[
        set[StandardDetector],
        "List of str of the detector names, eg. saxs, waxs, i0, it",
    ] = default_devices.FAST_DETECTORS,
    panda: HDFPanda = default_devices.DEFAULT_PANDA,
    force_load=True,
) -> MsgGenerator[None]:
    """

    This plans configures the panda and the detectors,

    setting them up for hardware triggering, loads all of the correct

    settings and then runs the flyscanning

    """

    active_pulses: list[int] = profile.active_pulses

    yield from configure_panda_triggering(
        beamline=beamline,
        experiment=experiment,
        profile=profile,
        detectors=detectors,
        panda=panda,
        force_load=force_load,
    )

    yield from run_panda_triggering(panda, detectors, active_pulses)


if __name__ == "__main__":
    RE = RunEngine(call_returns_result=True)

    #################################

    # notes to self
    # tetramm only works with mulitple triggers,
    # something to do with arm_status being set to none possible.
    # when tetramm has multiple triggers eg, 2 the data shape is not 2.
    # only every 1. It's duration is twice as long, but still 1000 samples

    # tetramm.py
    # async def prepare(self, trigger_info: TriggerInfo):
    #     self.maximum_readings_per_frame = self.maximum_readings_per_frame * sum(
    #         trigger_info.number_of_events
    #     )

    # still getting the experiment number jumping by two
    # neeed to sort out pulses on panda
    # split setup and run

    ###if TETRAMMS ARE NOT WORKING TRY TfgAcquisition() in gda to reset all malcolm
    #### stuff to defaults

    ###################################
    # Profile(
    #     id=0,
    #     cycles=1,
    #     in_trigger="IMMEDIATE",
    #     out_trigger="TTLOUT1",
    #     groups=[
    #         Group(
    #             id=0,
    #             frames=1,
    #             wait_time=100,
    #             wait_units="ms",
    #             run_time=100,
    #             run_units="ms",
    #             wait_pause=False,
    #             run_pause=False,
    #             wait_pulses=[1, 0, 0, 0, 0, 0, 0, 0],
    #             run_pulses=[0, 0, 0, 0, 0, 0, 0, 0],
    #         )
    #     ],
    #     multiplier=[1, 2, 4, 8, 16],
    # )

    default_config_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "profile_yamls",
        "panda_config.yaml",
    )
    configuration = ExperimentProfiles.read_from_yaml(default_config_path)
    profile = configuration.profiles[1]
    # RE(
    #     setup_panda(
    #         "i22",
    #         "cm40643-3/bluesky",
    #         profile,
    #         active_detector_names=["saxs", "waxs", "i0", "it"],
    #         force_load=False,
    #     )
    # )

    # for i in range(20):

    RE(
        configure_panda_triggering(
            "i22",
            "cm40643-3/bluesky",
            profile,
            force_load=False,
        )
    )

    # profile = configuration.profiles[2]
    # RE(
    #     setup_panda(
    #         "i22",
    #         None,
    #         "cm40643-3/bluesky",
    #         profile,
    #         active_detector_names=["saxs", "i0"],
    #         force_load=False,
    #     )
    # )

    # RE(panda_triggers_detectors("i22", active_detector_names=["saxs", "i0"]))

    # dev_name = "panda1"
    # connected_dev = return_connected_device('i22',dev_name)
    # print(f"{connected_dev=}")
    # RE(
    #     save_device_to_yaml(
    #         yaml_directory=os.path.join(
    #             os.path.dirname(os.path.realpath(__file__)), "ophyd_panda_yamls"
    #         ),
    #         yaml_file_name=f"{dev_name}_pv_without_pulse",
    #         device=connected_dev,
    #     )
    # )
