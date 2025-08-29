import os
from pathlib import Path
from typing import Annotated

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.log import LOGGER
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from ophyd_async.core import (
    DEFAULT_TIMEOUT,
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
from pydantic import validate_call

from saxs_bluesky.stubs.panda_stubs import (
    fly_and_collect_with_wait,
    load_settings_from_yaml,
    upload_yaml_to_panda,
)
from saxs_bluesky.utils.profile_groups import ExperimentLoader, Profile
from saxs_bluesky.utils.utils import (
    get_saxs_beamline,
    load_beamline_config,
)

BL = get_saxs_beamline()
CONFIG = load_beamline_config()
DEFAULT_PANDA = CONFIG.DEFAULT_PANDA
FAST_DETECTORS = CONFIG.FAST_DETECTORS


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


# def set_experiment_directory(beamline: str, visit_path: Path):
#     """Updates the root folder"""

#     print("should not require this to also be set in i22.py")

#     path_provider = StaticVisitPathProvider(
#         beamline,
#         Path(visit_path),
#         client=RemoteDirectoryServiceClient(f"http://{beamline}-control:8088/api"),
#     )
#     set_path_provider(path_provider)

#     suffix = datetime.now().strftime("_%Y%m%d%H%M%S")

#     async def set_panda_dir():
#         await path_provider.update(directory=visit_path, suffix=suffix)

#     yield from bps.wait_for([set_panda_dir])


def set_panda_pulses(
    panda: HDFPanda,
    pulses: list[int],
    setting: str = "arm",
    group="arm_panda",
):
    """

    Takes a HDFPanda and a list of integers corresponding

    to the number of the pulse blocks.

    Iterates through the numbered pulse blocks

    and arms them and then waits for all to be armed.

    """

    if setting.lower() == "arm":
        value = PandaBitMux.ONE.value
    else:
        value = PandaBitMux.ONE.value

    for n_pulse in pulses:
        yield from bps.abs_set(
            panda.pulse[int(n_pulse)].enable,  # type: ignore
            value,
            group=group,
        )

    yield from bps.wait(group=group, timeout=DEFAULT_TIMEOUT)


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

    yield from bps.wait(group=group, timeout=DEFAULT_TIMEOUT)


def return_deadtime(
    detectors: list[StandardDetector], exposure: float = 1.0
) -> np.ndarray:
    """
    Given a list of connected detector devices, and an exposure time,
    it returns an array of the deadtime for each detector
    """

    deadtime = (
        np.array([det._controller.get_deadtime(exposure) for det in detectors])  # noqa: SLF001
        + CONFIG.DEADTIME_BUFFER
    )
    return deadtime


def generate_repeated_trigger_info(
    profile: Profile,
    max_deadtime: float,
    livetime: float,
    trigger=DetectorTrigger.CONSTANT_GATE,
) -> list[TriggerInfo]:
    repeated_trigger_info = []

    # [3, 1, 1, 1, 1] or something
    n_triggers = [group.frames for group in profile.groups]
    n_cycles = profile.cycles

    if profile.multiplier is not None:
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

    return repeated_trigger_info


def check_and_apply_panda_settings(panda: HDFPanda, panda_name: str) -> MsgGenerator:
    """

    Checks the settings currently on the PandA

    - if different they will be overwritten with the ones

    specified in the CONFIG.CONFIG_NAME

    Settings may have changed due to Malcolm or

    someone chnaging things in EPICS which might prevent the plan from running

    This mitigates that

    """

    # this is the directory where the yaml files are stored
    yaml_directory = os.path.join(
        os.path.dirname(Path(__file__).parent), "ophyd_panda_yamls"
    )
    yaml_file_name = f"{BL}_{CONFIG.CONFIG_NAME}_{panda_name}"

    current_panda_settings = yield from get_current_settings(panda)
    yaml_settings = yield from load_settings_from_yaml(yaml_directory, yaml_file_name)

    if current_panda_settings != yaml_settings:
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


def multiple_pulse_blocks():
    pass
    # for pulse in CONFIG.PULSEBLOCKS
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
        LOGGER.info(f"deadtime for {dn} is {dt}")


def set_panda_output(
    panda: HDFPanda,
    output_type: str = "TTL",
    output: int = 1,
    state: str = "ON",
    group: str = "switch",
) -> MsgGenerator:
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
    yield from bps.wait(group=group, timeout=DEFAULT_TIMEOUT)


@attach_data_session_metadata_decorator()
@validate_call(config={"arbitrary_types_allowed": True})
def configure_panda_triggering(
    profile: Annotated[
        Profile,
        (
            "Profile or json of a Profile containing the infomation required to setup ",
            "the panda, triggers, times etc",
        ),
    ],
    detectors: Annotated[
        set[StandardDetector] | list[StandardDetector],
        "List of str of the detector names, eg. saxs, waxs, i0, it",
    ] = FAST_DETECTORS,
    panda: HDFPanda = DEFAULT_PANDA,
    force_load: bool = False,
) -> MsgGenerator:
    """

    This plans configures the panda and the detectors,

    setting them up for hardware triggering, loads all of the correct

    settings.

    Stage - sets the hdf writer
    Prepare - sets the trigger info

    Stage must come before prepare

    """

    try:
        yield from ensure_connected(panda)  # ensure the panda is connected
    except Exception as e:
        LOGGER.error(f"Failed to connect to PandA: {e}")
        raise

    LOGGER.info("Using the following detectors:")
    LOGGER.info("")
    for det in detectors:
        LOGGER.info(str(det))

    detector_deadtime = return_deadtime(
        detectors=list(detectors), exposure=profile.duration
    )

    max_deadtime = max(detector_deadtime)
    # show_deadtime(detector_deadtime, max_deadtime)

    # load Panda setting to panda
    if force_load:
        yield from check_and_apply_panda_settings(panda, panda.name)

    # n_cycles = profile.cycles
    # seq table should be grabbed from the panda and used instead,
    # in order to decouple run from setup panda
    # seq_table = profile.seq_table
    duration = profile.duration
    number_of_events = profile.number_of_events

    if profile.multiplier is not None:
        LOGGER.info(f"Multipliers used: {profile.active_pulses}")
        # arm the panda pulses if the profile has multipliers
        yield from set_panda_pulses(
            panda=panda, pulses=profile.active_pulses, setting="arm"
        )
        LOGGER.info(f"Multipliers values: {profile.multiplier}")

    ############################################################
    # setup triggering of detectors
    seq_table_info: SeqTableInfo = profile.seq_table_info

    # set up trigger info etc
    trigger_info = TriggerInfo(
        number_of_events=number_of_events,
        trigger=DetectorTrigger.EDGE_TRIGGER,  # or maybe EDGE_TRIGGER
        deadtime=max_deadtime,
        livetime=np.amax(profile.duration_per_cycle),
        exposures_per_event=1,
        exposure_timeout=duration,
    )

    panda._trigger_info = trigger_info  # noqa

    ############################################################
    # flyer and prepare fly, sets the sequencers table
    trigger_logic = StaticSeqTableTriggerLogic(panda.seq[CONFIG.DEFAULT_SEQ])
    flyer = StandardFlyer(trigger_logic)

    # setup triggering on panda - changes the sequence table
    # !! wait otherwise risking _context missing error
    # change the sequence table
    yield from bps.prepare(flyer, seq_table_info, wait=True)

    # yield from bps.wait(group="prepare", timeout=DEFAULT_TIMEOUT * len(detectors))


@attach_data_session_metadata_decorator()
@bpp.run_decorator()  #    # open/close run
@validate_call(config={"arbitrary_types_allowed": True})
def run_panda_triggering(
    detectors: Annotated[
        set[StandardDetector] | list[StandardDetector],
        "List of str of the detector names, eg. saxs, waxs, i0, it",
    ] = FAST_DETECTORS,
    panda: HDFPanda = DEFAULT_PANDA,
) -> MsgGenerator:
    """

    This will run whatever flyscanning settings
    are currenly loaded on the PandA and start it triggering

    """

    # get the loaded seq table
    panda_seq_table = panda.seq[CONFIG.DEFAULT_SEQ]
    # flyer and prepare fly, sets the sequencers table
    trigger_logic = StaticSeqTableTriggerLogic(panda_seq_table)
    flyer = StandardFlyer(trigger_logic)

    trigger_info = panda._trigger_info  # noqa

    # STAGE SETS HDF WRITER TO ON
    yield from bps.stage_all(*detectors, flyer, group="stage")
    yield from bps.wait(group="stage", timeout=DEFAULT_TIMEOUT * len(detectors))

    # yield from stage_and_prepare_detectors(list(detectors), flyer, trigger_info)
    for det in detectors:
        ###this tells the detector how may triggers to expect and sets the CAN aquire on
        yield from bps.prepare(det, trigger_info, wait=False, group="prepare")

    yield from fly_and_collect_with_wait(
        stream_name="primary",
        detectors=list(detectors),
        flyer=flyer,
    )
    ##########################
    ###########################
    yield from wait_until_complete(panda_seq_table.active, False)

    # turn off all pulses
    yield from set_panda_pulses(
        panda=panda, pulses=list(np.array(range(4)) + 1), setting="disarm"
    )

    # start diabling and unstaging everything
    yield from bps.unstage_all(*detectors, flyer)  # stops the hdf capture mode


@bpp.run_decorator()  #    # open/close run
@attach_data_session_metadata_decorator()
def configure_and_run_panda_triggering(
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
    ] = FAST_DETECTORS,
    panda: HDFPanda = DEFAULT_PANDA,
    force_load: bool = True,
) -> MsgGenerator:
    """

    This plans configures the panda and the detectors,

    setting them up for hardware triggering, loads all of the correct

    settings and then runs the flyscanning

    """

    yield from configure_panda_triggering(
        profile=profile,
        detectors=detectors,
        panda=panda,
        force_load=force_load,
    )

    yield from run_panda_triggering(profile, detectors=detectors, panda=panda)  # type: ignore


@validate_call(config={"arbitrary_types_allowed": True})
def set_detectors(bs_detectors: list[str]) -> MsgGenerator:
    global detectors
    detectors = [inject(f) for f in bs_detectors]
    yield from bps.sleep(0.1)


@validate_call(config={"arbitrary_types_allowed": True})
def log_detectors() -> MsgGenerator:
    LOGGER.info(detectors)
    yield from bps.sleep(0.1)


if __name__ == "__main__":
    from bluesky.run_engine import RunEngine

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

    ###if TETRAMMS ARE NOT WORKING TRY TfgAcquisition() in gda to reset all malcolm
    #### stuff to defaults

    default_config_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "profile_yamls",
        "panda_config.yaml",
    )
    configuration = ExperimentLoader.read_from_yaml(default_config_path)
    profile = configuration.profiles[1]

    detectors: list[StandardDetector] = [inject("saxs"), inject("waxs")]

    RE(
        configure_panda_triggering(
            profile,
            detectors=detectors,
            force_load=False,
        )
    )
