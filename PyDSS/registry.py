"""Manages PyDSS customized modules."""

from collections import defaultdict
import logging
import os
import pathlib

import PyDSS
from PyDSS.common import ControllerType, CONTROLLER_TYPES
from PyDSS.exceptions import InvalidParameter
from PyDSS.utils.utils import dump_data, load_data


DEFAULT_REGISTRY = {
    "Controllers": {
        ControllerType.PV_CONTROLLER.value: [
            {
                "name": "cpf",
                "filename": os.path.join(
                    os.path.dirname(getattr(PyDSS, "__path__")[0]),
                    "PyDSS/pyControllers/Controllers/Settings/PvControllers.toml"
                ),
            },
            {
                "name": "volt-var",
                "filename": os.path.join(
                    os.path.dirname(getattr(PyDSS, "__path__")[0]),
                    "PyDSS/pyControllers/Controllers/Settings/PvControllers.toml"
                ),
            },
        ],
        ControllerType.SOCKET_CONTROLLER.value: [],
        ControllerType.STORAGE_CONTROLLER.value: [],
        ControllerType.XMFR_CONTROLLER.value: [],
        ControllerType.MOTOR_STALL.value: [],
        ControllerType.PV_VOLTAGE_RIDETHROUGH.value: [],
        ControllerType.FAULT_CONTROLLER.value: [],
    },
}

REQUIRED_CONTROLLER_FIELDS = ("name", "filename")


logger = logging.getLogger(__name__)


class Registry:
    """Manages controllers registered with PyDSS."""
    _REGISTRY_FILENAME = ".pydss-registry.json"

    def __init__(self, registry_filename=None):
        if registry_filename is None:
            self._registry_filename = os.path.join(
                str(pathlib.Path.home()),
                self._REGISTRY_FILENAME,
            )
        else:
            self._registry_filename = registry_filename

        self._controllers = {x: {} for x in CONTROLLER_TYPES}
        if not os.path.exists(self._registry_filename):
            self.reset_defaults()
        else:
            data = load_data(self._registry_filename)
            for controller_type in data["Controllers"]:
                for controller in data["Controllers"][controller_type]:
                    self._add_controller(controller_type, controller)

    def _add_controller(self, controller_type, controller):
        name = controller["name"]
        filename = controller["filename"]
        if self.is_controller_registered(controller_type, name):
            raise InvalidParameter(f"{controller_type} / {name} is already registered")
        if not os.path.exists(filename):
            raise InvalidParameter(f"{filename} does not exist")
        # Make sure the file can be parsed.
        load_data(filename)

        self._controllers[controller_type][name] = controller

    def _serialize_registry(self):
        data = {"Controllers": defaultdict(list)}
        for controller_type in self._controllers:
            for controller in self._controllers[controller_type].values():
                data["Controllers"][controller_type].append(controller)

        filename = self.registry_filename
        dump_data(data, filename, indent=2)
        logger.debug("Serialized data to %s", filename)

    def is_controller_registered(self, controller_type, name):
        """Check if the controller is registered"""
        return name in self._controllers[controller_type]

    def list_controllers(self, controller_type):
        """Return a list of registered controllers.

        Returns
        -------
        list of dict

        """
        return list(self._controllers[controller_type].values())

    def read_controller_settings(self, controller_type, name):
        """Return the settings for the controller.

        Parameters
        ----------
        name : str

        Raises
        ------
        InvalidParameter
            Raised if name is not registered.

        """
        controller = self._controllers[controller_type].get(name)
        if controller is None:
            raise InvalidParameter(f"{controller_type} / {name} is not registered")

        return load_data(controller["filename"])[name]

    def register_controller(self, controller_type, controller):
        """Registers a controller in the registry.

        Parameters
        ----------
        controller_type : str
        controller : dict

        Raises
        ------
        InvalidParameter
            Raised if the controller is invalid.

        """

        self._add_controller(controller_type, controller)
        self._serialize_registry()
        logger.debug("Registered controller %s / %s", controller_type, controller["name"])

    @property
    def registry_filename(self):
        """Return the filename that stores the registry."""
        return self._registry_filename

    def reset_defaults(self, controllers_only=False):
        """Reset the registry to its default values."""
        for controllers in self._controllers.values():
            controllers.clear()
        for controller_type in DEFAULT_REGISTRY["Controllers"]:
            for controller in DEFAULT_REGISTRY["Controllers"][controller_type]:
                self.register_controller(controller_type, controller)
        self._serialize_registry()

        logger.debug("Initialized registry to its defaults.")

    def show_controllers(self):
        """Show the registered controllers."""
        print("PyDSS Controllers:")
        for controller_type in self._controllers:
            print(f"Controller Type:  {controller_type}")
            controllers = list(self._controllers[controller_type].values())
            if controllers:
                for controller in controllers:
                    name = controller["name"]
                    filename = controller["filename"]
                    print(f"  {name}:  {filename}")
            else:
                print("  None")

    def unregister_controller(self, controller_type, name):
        """Unregisters a controller.

        Parameters
        ----------
        controller_type : str
        name : str

        """
        if not self.is_controller_registered(controller_type, name):
            raise InvalidParameter(
                f"{controller_type} / {name} isn't registered"
            )

        self._controllers[controller_type].pop(name)
        self._serialize_registry()
