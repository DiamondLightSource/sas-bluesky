from collections.abc import Mapping
from typing import Literal

from ophyd_async.core import StandardDetector
from ophyd_async.fastcs.panda import HDFPanda
from pydantic import BaseModel, Field


class DeviceConfig(BaseModel):
    FAST_DETECTORS: set[StandardDetector]
    DEFAULT_PANDA: HDFPanda


class GUIElements(BaseModel):
    PULSEBLOCKS: int
    USE_MULTIPLIERS: bool
    PULSE_BLOCK_AS_ENTRY_BOX: bool
    PULSE_BLOCK_NAMES: list[str]
    THEME_NAME: Literal["clam", "alt", "default", "classic"]


PortMapping = Mapping[int, str | None]


class PandAWiring(BaseModel):
    TTL_IN: PortMapping
    TTL_OUT: PortMapping
    LVDS_IN: PortMapping
    LVDS_OUT: PortMapping
    PULSE_CONNECTIONS: Mapping[int, list[str | None]]


class NCDPlanParameters(BaseModel):
    DEADTIME_BUFFER: float = Field(
        default=20e-6,
        description="Buffer added to deadtime to handle "
        + "minor discrepencies between detector and panda "
        + "clocks",
    )
    DEFAULT_SEQ: Literal[1, 2] = Field(description="default sequencer")
    GENERAL_TIMEOUT: float = Field(default=30, json_schema_extra={"units": "s"})
    CONFIG_NAME: str
