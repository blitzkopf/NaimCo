import logging
import socket
import asyncio

from .controllers import Controller

_LOG = logging.getLogger(__name__)

class NaimCo:
    
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
        self.cmd_id = 0
        self.state = NaimState()
        self.controller = None
        self.product = None
        self.version = None
        _LOG.debug("Created NaimCo instance for ip: %s", ip_address)
  
    async def startup(self):
        self.controller=Controller(self)
        await self.controller.connect()

    async def run_connection(self,timeout=None):
        #await self.connect()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.controller.receiver())
            if timeout:
                tg.create_task(self.controller.keep_alive(timeout))

        _LOG.warn("Connection to naim closed")
        # what just happened, how did it happen?
             
    async def initialize(self,timeout):
        await self.controller.enable_v1_api()
        await self.controller.get_bridge_co_app_version()
        #await self.controller.set_heartbeat_timout(timeout)

    async def on(self):
        await self.controller.nvm.send_command('SETSTANDBY OFF')
        await asyncio.sleep(3)
        await self.controller.nvm.send_command('GETSTANDBYSTATUS')

    async def off(self):
        await self.controller.nvm.send_command('SETSTANDBY ON')

    async def set_volume(self,volume):
        await self.controller.nvm.send_command(f'SETRVOL {volume}')

    async def volume_up(self):
        await self.controller.nvm.send_command(f'VOL+')

    async def volume_down(self):
        await self.controller.nvm.send_command(f'VOL-')
    
    async def select_input(self,input):
        await self.controller.nvm.send_command(f'SETINPUT {input}')
    
    async def select_preset(self,preset):
        await self.controller.nvm.send_command(f'GOTOPRESET {preset}')

    def get_input(self):
        return self.state.input
    
    def get_volume(self):
        return self.state.volume

    def get_viewstate(self):
        return self.state.viewstate
    
    def get_standby_status(self):
        return self.state.standby_status

    def get_now_playing(self):
        resp={}
        try :    
            md = self.state.now_playing['metadata']
            resp['artist'] = md.get('artist')
            resp['album'] = md.get('album')
        except Exception:
            #_LOG.debug("No metadata for now playing")
            pass
        try :    
            resp['source'] = self.state.now_playing['source']
            resp['title'] = self.state.now_playing.get('title')
        except Exception:
            #_LOG.debug(f"No playback for now playing {self.state.now_playing}")
            pass
        try :    
            if resp['source'] == 'iradio':
                resp['string'] = f'{resp.get("artist")} {resp.get("title")}' 
            else:
                resp['string'] = f'{resp.get("artist")} / {resp.get("title")} / {resp.get("album")}' 

        except Exception as e:            
            #_LOG.debug(f"failed to make string {resp} {e}")
            resp['string'] = f'No information available' 
        return resp

class NaimState:
    def __init__(self):
        self.view_state = None
        self.now_playing = None
        self.now_playing_time = None
        self.active_list = None
        #NVM 
        self.volume = None
        self.bufferstate = None
        self.views_tate = None
        self.briefno = None
        self.standby_status = None
        self.input = None
        self.viewstate = None

    def set_volume(self,volume):
        self.volume=volume
    
    def set_input(self,input):
        self.input=input
    
    def set_view_state(self,state):
        self.view_state=state
    
    def set_viewstate(self,state):
        """ NVM view state"""
        self.viewstate=state

    def set_now_playing(self,state):
        self.now_playing=state
    
    def set_active_list(self,state):
        self.active_list=state
    
    def set_now_playing_time(self,state):
        self.now_playing_time=state
    
    def set_briefnp(self,brief):
        self.briefno=brief

    def set_bufferstate(self,bufferstate):
        self.bufferstate=bufferstate

    def set_standby_status(self,standby_status):
        self.standby_status=standby_status