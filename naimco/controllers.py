import logging
import base64
import shlex
from .connection import Connection
from .msg_processing import MessageStreamProcessor,gen_xml_command

_LOG = logging.getLogger(__name__)

class Controller:
    def __init__(self,naimco):
        self.naimco=naimco
        self.cmd_id_seq=0
        self.nvm=NVMController(self)

    async def connect(self):
        # TODO: deal with connection failures and dropped connections
        self.connection=await Connection.create_connection(self.naimco.ip_address)
    
    async def receiver(self):
        parser = MessageStreamProcessor()
        # what happens if msgs are split on non char boundaries?
        while True:
            data = await self.connection.receive()
            if len(data)>0:
                _LOG.debug(f'Received: {data!r}')
                parser.feed(data)
                for tag, dict in parser.read_messages():
                    self.process(tag,dict)
            else:
                print('.',end="")

    def process(self,tag,data):
        id = None
        if tag == 'reply':
            id=data['id']
            # is anyone waiting for an answer?
        for key,val in data.items():
            if key == 'id':
                continue
            method = getattr(self.__class__,'_'+key,None)
            if method:
                method(self,val,id)
            else: 
                _LOG.warn(f'Unhandled XML message {key} data:{data}')
                

    def _TunnelFromHost(self,val,id):
        # got some data from NVW
        # how should we deal with that?
        _LOG.debug(val['data'])
        self.nvm.assemble_msgs(val['data'])

    def _GetViewState(self,val,id):
        self.naimco.state.set_view_state(val['state'])
    
    def _GetNowPlaying(self,val,id):
        self.naimco.state.set_now_playing(val)
    
    def _GetNowPlayingTime(self,val,id):
        self.naimco.state.set_now_playing_time(val['play_time'])

    async def send_command(self,command,payload=None):
        self.cmd_id_seq += 1
        cmd = gen_xml_command(command,f"{self.cmd_id_seq}",payload)
        await self.connection.send(cmd)
    
    async def enable_v1_api(self):
        await self.send_command('RequestAPIVersion',
                        [{'item': {'name':'module','string':'NAIM'}},
                         {'item': {'name':'version','string':'1'}}]
        )

    async def get_bridge_co_app_version(self):
        await self.send_command('GetBridgeCoAppVersions')
    
    async def get_now_playing(self):
        await self.send_command('GetNowPlaying')
        
    async def set_heartbeat_timout(self,timeout):
        await self.send_command('SetHeartbeatTimeout',
            [{'item': {'name':'timeout','int':f'{timeout}'}}]
        )        

class NVMController:
    def __init__(self,controller):
        self.controller=controller
        self.buffer = ''
        self.state=controller.naimco.state

    async def send_command(self,command):
        cmd = f'*NVM {command}'
        await self.controller.send_command('TunnelToHost',
                        [{'item': {'name':'data','base64':base64.b64encode( bytes(cmd+"\r","utf-8")).decode("utf-8")+'\n'}}]
        )

    def assemble_msgs(self,string):
        ## incoming XML messages can both contain many NVM events and partial so we have to assamble them
        ## messages seem to start with # and be terminted with Carriege Return (\r)
        unpr_msg=self.buffer+string
        parts= unpr_msg.split("\r\n")
        for part in parts[0:-1]:
            _LOG.debug(f"NVM event:{part}")
            self.process_msg(part)
        self.buffer=parts[-1]
        _LOG.debug(f"NVM buffer {self.buffer}")
        
    def process_msg(self,msg):
        tokens=shlex.split(msg)
        nvm = tokens.pop(0)
        event = tokens.pop(0)
        event = event.replace(':','_')
        method = getattr(self.__class__,'_'+event)
        if method:
            method(self,tokens)
        else: 
            _LOG.warn(f'Unhandled message from NVM {msg}')
    
    def _GOTOPRESET(self,tokens):
        _LOG.debug(f"Playing iRadio preset number {tokens[0]} {tokens[1]}")
    
    def _PREAMP(self,tokens):
        # #NVM PREAMP 2 0 0 IRADIO OFF OFF OFF ON "iRadio" OFF
        volume = tokens[0]
        input = tokens[3]
        input_label = tokens[8]
        self.state.set_volume(volume)
        _LOG.debug(f"Volume set  {tokens[0]} {tokens[1]}")
    
    def _SETSTANDBY(self,tokens):
        #NVM SETSTANDBY OK
        if tokens[0] != 'OK':
            _LOG.warn(f"SETSTANDBY reports {tokens[0]}")


    def _SETRVOL(self,tokens):
        if tokens[0] != 'OK':
            _LOG.warn(f"SETRVOL reports {tokens[0]}")

    def _GETVIEWSTATE(self,tokens):
        # #NVM GETVIEWSTATE INITPLEASEWAIT NA NA N N NA IRADIO NA NA NA NA
        # #NVM GETVIEWSTATE PLAYERRESTORINGHISTORY 0 2 N N NA IRADIO "Rás2RÚV901" "Rás 2 RÚV 90.1 FM" NA NA
        # #NVM GETVIEWSTATE PLAYING CONNECTING 2 N N NA IRADIO "Rás2RÚV901" "Rás 2 RÚV 90.1 FM" NA NA
        # #NVM GETVIEWSTATE PLAYING ANALYSING NA N N NA SPOTIFY NA NA NA NA
        # There is also GetViewState XML Event
        state = tokens[0]
        phase = tokens[1] 
        input = tokens[6]
        compact_name = tokens[7]
        fullname = tokens[9]
        # self.state.set_viewstate(state,phase)

    def _ERROR_(self,tokens):
        # #NVM ERROR: [11] Command not allowed in current system configuration
        match tokens[0]:
            case '[11]':
                _LOG.debug(f'Error 11 received, usually something trivial')
            case _:
                _LOG.warn(f'Error from NVM:'+' '.join(tokens))
    
    def _GETBRIEFNP(self,tokens):
        # #NVM GETBRIEFNP PLAY "Rás 2 RÚV 90.1 FM" "http://http.cdnlayer.com/vt/logo/logo-1318.jpg" NA NA NA
        state = tokens[0]
        description = tokens[1]
        logo_url = tokens[2]
        self.state.set_briefnp({'state':state,'description':description,'logo_url':logo_url})
    
    def _GETBUFFERSTATE(self,tokens):
        # #NVM GETBUFFERSTATE 0
        self.state.set_bufferstate(tokens[0])
    def _ALARMSTATE(self,tokens):
        # #NVM ALARMSTATE TIME_ADJUST
        # Don't know what this is maybe something to do with heartbeat 
        pass

