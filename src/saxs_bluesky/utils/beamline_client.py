from pathlib import Path

from blueapi.client.client import BlueapiClient
from blueapi.config import (
    ApplicationConfig,
    ConfigLoader,
)
from blueapi.service.model import TaskRequest


class BlueAPIPythonClient(BlueapiClient):
    def __init__(
        self, BL: str, blueapi_config_path: str | Path, instrument_session: str
    ):
        self.BL = BL
        self.instrument_session = instrument_session

        blueapi_config_path = Path(blueapi_config_path)

        config_loader = ConfigLoader(ApplicationConfig)
        config_loader.use_values_from_yaml(blueapi_config_path)
        loaded_config = config_loader.load()
        blueapi_class = BlueapiClient.from_config(loaded_config)
        super().__init__(blueapi_class._rest, blueapi_class._events)  # noqa

    def run(self, plan_name: str, params: dict):
        task = TaskRequest(
            name=plan_name,
            params=params,
            instrument_session=self.instrument_session,
        )

        response = self.create_and_start_task(task)
        print(response)
