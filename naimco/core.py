import logging
import socket

from .controllers import Controller

_LOG = logging.getLogger(__name__)

class NaimCo:
    connection = None
    product = None
    version = None
    
    def __init__(self, ip_address):
        # Note: Creation of a NaimCo instance should be as cheap and quick as
        # possible. Do not make any network calls here
        super().__init__()
        try:
            socket.inet_aton(ip_address)
        except OSError as error:
            raise ValueError("Not a valid IP address string") from error
        #: The systems's ip address
        self.ip_address = ip_address
        self.system_info = {}  # Stores information about the current speaker
        self.cmd_id = 0
        self.state = NaimState()

        _LOG.debug("Created NaimCo instance for ip: %s", ip_address)
  
    async def startup(self):
        self.controller=Controller(self)
        await self.controller.connect()

    async def run_connection(self):
        #await self.connect()
        try :
            await self.controller.receiver()
        except ConnectionAbortedError as e :
            _LOG.warn("Connection to naim closed")

        # what just happened?
             
    async def initialize(self):
        await self.controller.enable_v1_api()
        await self.controller.get_bridge_co_app_version()
        await self.controller.set_heartbeat_timout(5*60)

    async def on(self):
        await self.controller.nvm.send_command('SETSTANDBY OFF')
    async def off(self):
        await self.controller.nvm.send_command('SETSTANDBY ON')


class NaimState:
    view_state = None
    now_playing = None
    now_playing_time = None
    #NVM 
    volume = None
    bufferstate = None
    viewstate = None
    briefno = None

    def set_volume(self,volume):
        self.volume=volume
    
    def set_view_state(self,state):
        self.view_state=state

    def set_now_playing(self,state):
        self.now_playing=state
    
    def set_now_playing_time(self,state):
        self.now_playing_time=state
    
    def set_briefnp(self,brief):
        self.briefno=brief

    def set_bufferstate(self,bufferstate):
        self.bufferstate=bufferstate