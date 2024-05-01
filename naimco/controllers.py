import logging
import base64
import shlex
import time
import asyncio

from .connection import Connection
from .msg_processing import MessageStreamProcessor, gen_xml_command

_LOG = logging.getLogger(__name__)


class Controller:
    """Controller communicates with the Mu-so device through the Connection class.


    It encodes commands for the controller as XML.

    It reads incoming replies from from the Connections and parses them and
    decides what to do with them.

    For each expected reply/event name there is a class method that gets
    called when we get a xml using that name

    """

    def __init__(self, naimco):
        """Creates a Controller with NVMController"""
        self.naimco = naimco
        self.cmd_id_seq = 0
        self.nvm = NVMController(self)
        self.timeout_interval = None
        self.last_send_time = None
        self.keep_connection_alive: bool = None

    async def connect(self):
        """Opens the Connection to device"""
        # TODO: deal with connection failures and dropped connections
        self.connection = await Connection.create_connection(self.naimco.ip_address)

    async def initialize(self):
        """Initializes the controller

        Sends the initial commands to the Mu-so device to get the initial state.
        """
        await self.enable_v1_api()
        await self.get_bridge_co_app_version()

    async def startup(self, timeout=None):
        """Starts up the controller

        Connects to the Mu-so device and initializes the controller.
        """
        _LOG.info("Starting up controller")
        self.keep_connection_alive = True
        self.connection_task = asyncio.create_task(self.connection_runner())
        # FIXME : this sleep is a hack to get the connection up and running before we start sending commands
        await asyncio.sleep(0.1)
        if timeout:
            self.keep_alive_task = asyncio.create_task(self.keep_alive(timeout))

    async def shutdown(self):
        """Shuts down the controller

        Stops the connection runner and closes the connection.
        """
        self.keep_connection_alive = False
        await self.connection.close()
        if self.connection_task:
            await self.connection_task

    async def connection_runner(self):
        """Coroutine that reads incoming stream from Connection

        Reads the stream of strings from Connections and assembles them
        together and splits them into seperate XML snippets.

        The incoming stream of data is not split on event/reply boundaries
        so we can both have multiple xml element in one message and one xml
        element split between more than one message.

        Calls process for each XML extracted.

        """
        await self.connect()
        await self.initialize()
        parser = MessageStreamProcessor()
        # what happens if msgs are split on non char boundaries?
        while self.keep_connection_alive:
            try:
                data = await self.connection.receive()
                if len(data) > 0:
                    _LOG.debug(f"Received: {data!r}")
                    parser.feed(data)
                    for tag, dict in parser.read_messages():
                        self.process(tag, dict)
                else:
                    print(".", end="")
            except ConnectionAbortedError as e:
                # TODO:deal with connection failures and dropped connections
                if self.keep_connection_alive:
                    _LOG.error(f"Connection aborted, reconnecting: {e}")
                    await self.connect()
                    await self.initialize()
                    parser = MessageStreamProcessor()
                else:
                    _LOG.error(f"Connection aborted, not reconnecting: {e}")
                    return

    async def keep_alive(self, timeout):
        """Set timeout and keep the connection alive

        The Mu-so device will terminate the TCP socket if it does not receive
        anything for a specific time.
        This coroutine sets the timout value in the Mu-so device and then
        sets a timer to send a ping if we are within a second of reaching
        the time limit.
        Should be started as a seperate asyncio task.

        Parameters
        ----------
        timeout : int
            Timeout in seconds.
        """

        await self.set_heartbeat_timout(timeout)
        while True:
            now = time.monotonic()
            if now >= self.last_send_time + timeout - 1:
                # await self.nvm.ping()
                await self.send_command("Ping")
            now = time.monotonic()
            await asyncio.sleep(self.last_send_time + timeout - 1 - now)

    def process(self, tag, data):
        """Process each incoming XML message

        Calls a method with the name of the XML reply, prefixed with '_'.

        Parameters
        ----------
        tag : str
            XML tag of the message, expected values are 'reply' and 'event'
        data: dict
            dictionary with the 'payload' of the message.

        """
        id = None
        if tag == "reply":
            id = data["id"]
            # is anyone waiting for an answer?
        for key, val in data.items():
            if key == "id":
                continue
            method = getattr(self.__class__, "_" + key, None)
            if method:
                method(self, val, id)
            else:
                _LOG.warn(f"Unhandled XML message {key} data:{data}")

    def _TunnelFromHost(self, val, id):
        """Process data from NVM

        It looks there is a second controller module taking care of some
        basic functions of the player. It uses commands and replies encoded
        in base64.
        This will collect messages from that unit and have a subcrontroller
        called  NVMController take care of processing them.

        Parameters
        ----------
        val : dict
            Contains the data from NVM in val['data']
        """
        _LOG.debug(val["data"])
        self.nvm.assemble_msgs(val["data"])

    def _TunnelToHost(self, val, id):
        """As a reply this is just an empty reply, do nothing"""
        pass

    def _GetViewState(self, val, id):
        """Respond to GetViewState replies/events

        Register the current ViewState in a NaimCo device object
        """
        self.naimco.state.set_view_state(val["state"])

    def _RequestAPIVersion(self, val, id):
        """Respond to RequestAPIVersion requests

        Don't do anything just hope it works
        """
        None

    def _GetBridgeCoAppVersions(self, val, id):
        """Respond to GetBridgeCoAppVersions replies


        Register the bridge co app versions in the NaimCo device object.
        """
        self.naimco.state.set_bridge_co_app_versions(val)

    def _GetNowPlaying(self, val, id):
        """Respond to GetNowPlaying events/replies

        Register the now playing data in the NaimCo device object.
        Mu-so will both send these as replies when commanded and as events when
        changing tracks.
        """
        _LOG.debug(f"GetNowPlaying: {val}")
        self.naimco.state.set_now_playing(val)

    def _GetActiveList(self, val, id):
        """Respond to GetActiveList events/replies


        I have yet to figure out how this work, keeping track of it in the
        device state for now.
        """
        self.naimco.state.set_active_list(val)

    def _Ping(self, val, id):
        """Respond to Ping replies


        Just do nothing keep the connection open
        """
        pass

    def _GetNowPlayingTime(self, val, id):
        """Respond to GetNowPlaying time


        Store the time which is in seconds in the device state.


        Parameters
        ----------
        val : dict
            Contains the current play time in seconds in val['play_time']
        """
        self.naimco.state.set_now_playing_time(val["play_time"])

    async def send_command(self, command, payload=None):
        """Encodes a command as XML and send to Mu-so

        Parameter
        ---------
        command : str
            The Naim Mu-so command to send
        payload : dict
            Parameters to send with the command

        """
        self.cmd_id_seq += 1
        cmd = gen_xml_command(command, f"{self.cmd_id_seq}", payload)
        self.last_send_time = time.monotonic()
        await self.connection.send(cmd)

    async def enable_v1_api(self):
        """Enable version 1 of naim API


        This has to happen to enable the NVM commands
        """
        await self.send_command(
            "RequestAPIVersion",
            [
                {"item": {"name": "module", "string": "NAIM"}},
                {"item": {"name": "version", "string": "1"}},
            ],
        )

    async def get_bridge_co_app_version(self):
        await self.send_command("GetBridgeCoAppVersions")

    async def get_now_playing(self):
        await self.send_command("GetNowPlaying")

    async def set_heartbeat_timout(self, timeout):
        self.timeout_interval = timeout
        await self.send_command(
            "SetHeartbeatTimeout", [{"item": {"name": "timeout", "int": f"{timeout}"}}]
        )


def nanone(value: str) -> str | None:
    """Handle NA string in value

    Returns None if value is NA, value otherwise"""
    return None if value is None else value


class NVMController:
    def __init__(self, controller):
        self.controller = controller
        self.buffer = ""
        self.state = controller.naimco.state

    async def send_command(self, command):
        cmd = f"*NVM {command}"
        _LOG.debug(f"Sending {cmd}")
        await self.controller.send_command(
            "TunnelToHost",
            [
                {
                    "item": {
                        "name": "data",
                        "base64": base64.b64encode(bytes(cmd + "\r", "utf-8")).decode(
                            "utf-8"
                        )
                        + "\n",
                    }
                }
            ],
        )

    async def ping(self):
        await self.send_command("PING")

    def assemble_msgs(self, string):
        ## incoming XML messages can both contain many NVM events and partial so we have to assamble them
        ## messages seem to start with # and be terminted with Carriege Return (\r)
        unpr_msg = self.buffer + string
        parts = unpr_msg.split("\r\n")
        for part in parts[0:-1]:
            _LOG.debug(f"NVM event:{part}")
            self.process_msg(part)
        self.buffer = parts[-1]
        _LOG.debug(f"NVM buffer {self.buffer}")

    def process_msg(self, msg):
        tokens = shlex.split(msg)
        tokens.pop(0)  # #NVM token
        event = tokens.pop(0)
        event = event.replace(":", "_")
        event = event.replace("-", "minus")
        event = event.replace("+", "plus")
        method = getattr(self.__class__, "_" + event, None)
        if method:
            method(self, tokens)
        else:
            _LOG.warn(f"Unhandled message from NVM {msg}")

    def _GOTOPRESET(self, tokens):
        _LOG.debug(f"Playing iRadio preset number {tokens[0]} {tokens[1]}")

    def _PREAMP(self, tokens):
        # #NVM PREAMP 2 0 0 IRADIO OFF OFF OFF ON "iRadio" OFF
        volume = tokens[0]
        input = tokens[3]
        # Maybe do something with the rest of the tokens?
        # mute = tokens[4]
        # input_label = tokens[8]
        self.state.volume = volume
        self.state.input = input

        _LOG.debug(f"Volume set  {tokens[0]} {tokens[1]}")

    def _VOLminus(self, tokens):
        # #NVM VOL- 10 OK
        volume = tokens[0]
        self.state.volume = volume

    def _VOLplus(self, tokens):
        # #NVM VOL+ 10 OK
        volume = tokens[0]
        self.state.volume = volume

    def _SETSTANDBY(self, tokens):
        # NVM SETSTANDBY OK
        # standby status not reported, we need to query
        if tokens[0] != "OK":
            _LOG.warn(f"SETSTANDBY reports {tokens[0]}")

    def _SETRVOL(self, tokens):
        if tokens[0] != "OK":
            _LOG.warn(f"SETRVOL reports {tokens[0]}")

    def _GETVIEWSTATE(self, tokens):
        # #NVM GETVIEWSTATE INITPLEASEWAIT NA NA N N NA IRADIO NA NA NA NA
        # #NVM GETVIEWSTATE PLAYERRESTORINGHISTORY 0 2 N N NA IRADIO "Rás2RÚV901" "Rás 2 RÚV 90.1 FM" NA NA
        # #NVM GETVIEWSTATE PLAYING CONNECTING 2 N N NA IRADIO "Rás2RÚV901" "Rás 2 RÚV 90.1 FM" NA NA
        # #NVM GETVIEWSTATE PLAYING ANALYSING NA N N NA SPOTIFY NA NA NA NA
        # There is also GetViewState XML Event
        state = nanone(tokens[0])
        phase = nanone(tokens[1])
        preset = nanone(tokens[2])
        input = nanone(tokens[6])
        compact_name = nanone(tokens[7])
        fullname = nanone(tokens[9])
        self.state.viewstate = {
            "state": state,
            "phase": phase,
            "preset": preset,
            "input": input,
            "compact_name": compact_name,
            "fullname": fullname,
        }

    def _ERROR_(self, tokens):
        # #NVM ERROR: [11] Command not allowed in current system configuration
        match tokens[0]:
            case "[11]":
                _LOG.debug("Error 11 received, usually something trivial")
            case _:
                _LOG.warn("Error from NVM:" + " ".join(tokens))

    def _GETBRIEFNP(self, tokens):
        # #NVM GETBRIEFNP PLAY "Rás 2 RÚV 90.1 FM" "http://http.cdnlayer.com/vt/logo/logo-1318.jpg" NA NA NA
        state = nanone(tokens[0])
        description = nanone(tokens[1])
        logo_url = nanone(tokens[2])
        self.state.briefnp = {
            "state": state,
            "description": description,
            "logo_url": logo_url,
        }

    def _GETBUFFERSTATE(self, tokens):
        # #NVM GETBUFFERSTATE 0
        self.state.bufferstate = tokens[0]

    def _ALARMSTATE(self, tokens):
        # #NVM ALARMSTATE TIME_ADJUST
        # Don't know what this is seems to happen every minute on the minute
        pass

    def _SETINPUT(self, tokens):
        # NVM SETINPUT OK
        if tokens[0] != "OK":
            _LOG.warn(f"SETINPUT reports {tokens[0]}")

    def _GETINPUTBLK(self, tokens: list[str]):
        # NVM GETINPUTBLK 1 10 1 IRADIO "iRadio"
        # NVM GETINPUTBLK 2 10 1 MULTIROOM "Multiroom"
        index: int = int(tokens[0])
        id: str = tokens[3]
        name: str = tokens[4]
        self.state.set_inputblk_entry(index, {"id": id, "name": name})

    def _GETSTANDBYSTATUS(self, tokens):
        # NVM GETSTANDBYSTATUS ON NETWORK
        state = tokens[0]
        type = tokens[1]
        self.state.standbystatus = {"state": state, "type": type}

    def _PONG(self, tokens):
        pass

    def _GETVIEWMESSAGE(self, tokens):
        # NVM GETVIEWMESSAGE SKIPFILE
        pass

    def _PLAY(self, tokens):
        # NVM PLAY OK
        if tokens[0] != "OK":
            _LOG.warn(f"PLAY reports {tokens[0]}")

    def _PRODUCT(self, tokens):
        # NVM PRODUCT MUSO
        self.state.product = tokens[0]

    def _GETSERIALNUM(self, tokens):
        # NVM GETSERIALNUM 1107010284
        self.state.serialnum = tokens[0]

    def _GETROOMNAME(self, tokens):
        # NVM GETROOMNAME "Livingroom"
        self.state.roomname = tokens[0]

    def _GETTOTALPRESETS(self, tokens):
        # NVM GETTOTALPRESETS 40
        self.state.totalpresets = tokens[0]
        ## do this her while we don't have any event processing or waiting for response
        asyncio.create_task(self.send_command(f"GETPRESETBLK 1 {tokens[0]}"))

    def _GETPRESETBLK(self, tokens: list[str]):
        # NVM GETPRESETBLK 1 40 USED "Rás 1 RÚV 93.5 FM" INTERNET 0 NONE NORMAL
        # NVM GETPRESETBLK 2 40 USED "Rás 2 RÚV 90.1 FM" INTERNET 0 NONE NORMAL
        index: int = int(tokens[0])
        # max:int = int(tokens[1])
        state: str = tokens[2]
        name: str = tokens[3]
        transport: str = tokens[4]
        self.state.set_presetblk_entry(
            index, {"state": state, "name": name, "transport": transport}
        )
