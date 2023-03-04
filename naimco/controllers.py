import logging
import asyncio
import base64
from .connection import Connection
from .msg_processing import MessageStreamProcessor,gen_xml_command

_LOG = logging.getLogger(__name__)

class TCPController:
    def __init__(self,naimco):
        self.naimco=naimco
        self.cmd_id_seq=0

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
                    if( tag== 'reply'):
                        id=dict['id']
                        #id,name,payload = process_reply(elem)
                        _LOG.debug(f'reply {dict}')
                    if( tag== 'event'):
                        #print(name,payload)
                        self.unpack_event(dict)
            else:
                print('.',end="")


    def unpack_event(self,dict):
        if  resp :=  dict.get('TunnelFromHost'):
            _LOG.debug(resp['data'])
        else:
            _LOG.debug(f'fun event {dict}')

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
    def __init__(self,tcpcontroller):
        self.tcpcontroller=tcpcontroller
        # fake tag to allow parsing of a stream og xml elements.
        # TODO: Figure out if this leaks memory.

    async def send_command(self,command):
        cmd = f'*NVM {command}'
        await self.tcpcontroller.send_command('TunnelToHost',
                        [{'item': {'name':'data','base64':base64.b64encode( bytes(cmd+"\r","utf-8")).decode("utf-8")+'\n'}}]
        )   