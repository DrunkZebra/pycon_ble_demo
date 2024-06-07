import enum
import queue
from multiprocessing import Process
from signal import SIGINT, SIGTERM, signal

import dbus
import dbus.exceptions
import dbus.mainloop.glib
from dbus.mainloop.glib import DBusGMainLoop
import dbus.service
from gi.repository import GLib

from demo.core_ble.advertisement import Advertisement
from demo.core_ble.application import Application
from demo.core_ble.constants import BLUEZ_SERVICE_NAME, GATT_MANAGER_IFACE
from demo.core_ble.service import Service
from demo.exceptions import BluetoothNotFoundException
from demo.util import find_adapter

language = "spanish"

def register_app_cb(v=None):
    print("Bluetooth service registered")



def register_app_error_cb(error):
    print("Failed to register application: " + str(error))


class BLEProcess(Process):
    def __init__(self, output_queue: queue.Queue) -> None:
        super().__init__()
        self._system_bus = None
        self._mainloop = None
        self._advertisement = None
        self._output_queue = output_queue

    def _shutdown_handler(self, sig: enum, frame: enum) -> None:
        """
        Handler that stops the main loop and stop the advertisements.
        """
        self._mainloop.quit()
        self._advertisement.release()

    def run(self) -> None:
        """
        The main run function that set-ups the BLE service.
        """

        # The mainloop initialized here handles the asynchronous communication over dbus documentation can be found
        # here: https://docs.gtk.org/glib/main-loop.html
        DBusGMainLoop(set_as_default=True)
        self._mainloop = GLib.MainLoop()

        # register shutdown handler
        signal(SIGTERM, self._shutdown_handler)
        signal(SIGINT, self._shutdown_handler)

        # create the shared system bus object and find the main bluez adapter
        self._system_bus = dbus.SystemBus()
        adapter = find_adapter(self._system_bus)

        if not adapter:
            raise BluetoothNotFoundException()

        adapter_obj = self._system_bus.get_object(bus_name=BLUEZ_SERVICE_NAME, object_path=adapter)

        service_manager = dbus.Interface(adapter_obj, GATT_MANAGER_IFACE)

        # Create the advertisement
        self._advertisement = Advertisement(
            bus=self._system_bus,
            index=0,
            adapter_obj=adapter_obj,
            uuid="0000180d-aaaa-1000-8000-0081239b35fb",
            name="revdemoservice",
        )

        # Create the application and add the service to it
        app = Application(self._system_bus)

        example_service = Service(
            bus=self._system_bus,
            index=1,
            uuid="0000180d-aaaa-1000-8000-0081239b35fc",
            primary=True,
            output_queue=self._output_queue,
        )

        example_service.add_characteristic(
            "f76ce015-952b-c6a8-e17c-c2c19aac7b1b", ["read", "write"], "Language", "Spanish"
        )

        example_service.add_characteristic(
            "aec7fba8-24cf-11ef-a164-f7472c9c63ea", ["read", "write"], "SSID", "Rev Member"
        )

        example_service.add_characteristic(
            "c8c51d2e-24cf-11ef-9434-7b8d949480af", ["write"], "Password", "incubator"
        )

        example_service.add_characteristic(
            "f863217a-24cf-11ef-821e-7732ec12df3b", ["read"], "Status", "idk"
        )

        app.add_service(example_service)

        # Initialise the advertisement
        self._advertisement.init_advertisement()

        # Register the application
        service_manager.RegisterApplication(
            app.get_path(),
            {},
            reply_handler=register_app_cb,
            error_handler=register_app_error_cb,
        )

        # Blocking call to run the main event loop
        self._mainloop.run()
