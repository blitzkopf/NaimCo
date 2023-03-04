import logging
import asyncio
import base64
import xml.etree.ElementTree as ET

NAIM_SOCKET_API_PORT=15555
_LOG = logging.getLogger(__name__)

class Connection:
    reader = None
    writer = None
    
    def __init__(self,reader,writer):
        self.reader=reader
        self.writer=writer

    @classmethod
    async def create_connection(self, ip_address,socket_api_port=NAIM_SOCKET_API_PORT):
    
        # Note: Creation of a SoCo instance should be as cheap and quick as
        # possible. Do not make any network calls here
        reader, writer =  await asyncio.open_connection(ip_address,socket_api_port)
        conn = Connection(reader,writer)
        return conn

        #_LOG.debug("Created NaimCo instance for ip: %s", ip_address)
    
    async def receive(self):
        if not self.reader.at_eof():
            data = await self.reader.read(2000)
            return data.decode()
        else:
            # What just happened? TODO:deal with connection failures and dropped connections
            # for now just throw exception
            raise ConnectionAbortedError("EOF on reader")

        #await self.reader.close()        


    async def close(self):
        self.writer.close()

    async def send(self,message):
        print(f'Send: {message!r}')
        self.writer.write(message.encode())
        await self.writer.drain()



