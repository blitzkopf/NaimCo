import logging
import socket

from .connection import Connection
from .controllers import TCPController,NVMController

_LOG = logging.getLogger(__name__)

class NaimCo:
    connection = None
    product = None
    version = None
    def __init__(self, ip_address):
        # Note: Creation of a NaimCo instance should be as cheap and quick as
        # possible. Do not make any network calls here
        super().__init__()
        # Check if ip_address is a valid IPv4 representation.
        # Sonos does not (yet) support IPv6
        try:
            socket.inet_aton(ip_address)
        except OSError as error:
            raise ValueError("Not a valid IP address string") from error
        #: The speaker's ip address
        self.ip_address = ip_address
        self.system_info = {}  # Stores information about the current speaker
        self.cmd_id = 0

        _LOG.debug("Created NaimCo instance for ip: %s", ip_address)
  
    async def startup(self):
        self.tcp_controller=TCPController(self)
        await self.tcp_controller.connect()
        self.nvm_controller=NVMController(self.tcp_controller)

    async def run_connection(self):
        #await self.connect()
        await self.tcp_controller.receiver()
        # what just happened?
             
    async def initialize(self):
        await self.tcp_controller.enable_v1_api()
        await self.tcp_controller.get_bridge_co_app_version()
        await self.tcp_controller.set_heartbeat_timout(180)

    async def on(self):
        await self.nvm_controller.send_command('*NVM SETSTANDBY OFF')

   