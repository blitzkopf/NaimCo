import logging
import asyncio

NAIM_SOCKET_API_PORT = 15555
_LOG = logging.getLogger(__name__)


class Connection:
    """Class that takes care of actual connection to device.

    Creates a asyncio socket connection to the Mu-so device.
    """

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    @classmethod
    async def create_connection(self, ip_address, socket_api_port=NAIM_SOCKET_API_PORT):
        """Make the connection

        Parameters
        ----------
        ip_address : str
            IP-address of the Mu-so speaker.
        socket_api_port : int
            TCP port for communicating with Mu-so.

        Returns
        -------
        Connection
            a connection object that has opened a TCP connection to device.
        """
        _LOG.debug("Connecting to  Naim Mu-So on ip: %s", ip_address)

        reader, writer = await asyncio.open_connection(ip_address, socket_api_port)
        conn = Connection(reader, writer)
        return conn

        # _LOG.debug("Created NaimCo instance for ip: %s", ip_address)

    async def receive(self):
        """Receive one packet of data from Mu-so device.

        Returns
        -------
        str
            Received data as a UTF-8 string.
        """
        if not self.reader.at_eof():
            data = await self.reader.read(2000)
            # FIXME: I guess it is possible that the incoming packets get split in
            # such a way that a multibyte char gets split.
            return data.decode()
        else:
            # What just happened? TODO:deal with connection failures and dropped connections
            # for now just throw exception
            raise ConnectionAbortedError("EOF on reader")

        # await self.reader.close()

    async def send(self, message):
        _LOG.debug(f"Send: {message!r}")
        self.writer.write(message.encode())
        await self.writer.drain()

    async def close(self):
        """Close the connection

        Closing the writer causes the whole connection to close
        """
        self.writer.close()
