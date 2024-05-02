import logging
import socket
import asyncio

from .controllers import Controller

_LOG = logging.getLogger(__name__)


class NaimCo:
    """The main class for interacting with a Naim Mu-so device.

    This is the class that the "end user" will interact with.
    This is the class that the "end user" will interact with.
    """

    def __init__(self, ip_address):
        """Initialize a NaimCo instance.

        Parameters
        ----------
        ip_address : str
            IP-address of the Mu-so speaker.

        Raises
        ------
        ValueError
            If `ip_address` is not a valid IP address string.
        """
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
        self.version = None
        _LOG.debug("Created NaimCo instance for ip: %s", ip_address)

    async def startup(self, timeout=None):
        """Connect to the Mu-so device and get the initial state.

        This method should be called before any other interaction with the device.
        """
        # Note: This method should be called after the event loop is running
        # and before any other interaction with the device is attempted.
        _LOG.debug("Starting up NaimCo instance for ip: %s", self.ip_address)
        self.controller = Controller(self)
        await self.controller.startup(timeout)

    async def shutdown(self):
        """Close the connection to the Mu-so device."""
        await self.controller.shutdown()

    async def on(self):
        await self.controller.nvm.send_command("SETSTANDBY OFF")
        await asyncio.sleep(3)
        await self.controller.nvm.send_command("GETSTANDBYSTATUS")

    async def off(self):
        await self.controller.nvm.send_command("SETSTANDBY ON")

    @property
    def standbystatus(self):
        return self.state.standbystatus

    @property
    def volume(self):
        return self.state.volume

    async def set_volume(self, volume):
        await self.controller.nvm.send_command(f"SETRVOL {volume}")

    async def volume_up(self):
        await self.controller.nvm.send_command("VOL+")

    async def volume_down(self):
        await self.controller.nvm.send_command("VOL-")

    @property
    def input(self):
        return self.state.input

    @property
    def product(self):
        return self.state.product

    @property
    def serialnum(self):
        return self.state.serialnum

    @property
    def roomname(self):
        return self.state.roomname

    @property
    def name(self):
        return self.state.roomname

    @property
    def inputs(self) -> dict[int, dict]:
        return {inp["id"]: inp["name"] for inp in self.state.inputblk.values()}

    @property
    def presets(self) -> dict[int, dict]:
        return {index: preset["name"] for index, preset in self.state.presetblk.items()}

    async def select_input(self, input):
        await self.controller.nvm.send_command(f"SETINPUT {input}")

    async def select_preset(self, preset):
        await self.controller.nvm.send_command(f"GOTOPRESET {preset}")

    @property
    def viewstate(self):
        return self.state.viewstate

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if not self.state.briefnp:
            return None
        return self.state.briefnp.get("logo_url", None)
        # self.state.briefnp = {'state':state,'description':description,'logo_url':logo_url}

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        # it depends on what it playing, leave it at True for now
        return True

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if not self.state.now_playing:
            return None
        return self.state.now_playing.get("title", None)

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if not self.state.now_playing:
            return None
        if metadata := self.state.now_playing.get("metadata", None):
            return metadata.get("artist", None)
        return None

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if not self.state.now_playing:
            return None
        if metadata := self.state.now_playing.get("metadata", None):
            return metadata.get("album", None)
        return None

    def get_now_playing(self):
        resp = {}
        try:
            md = self.state.now_playing["metadata"]
            resp["artist"] = md.get("artist")
            resp["album"] = md.get("album")
        except Exception:
            # _LOG.debug("No metadata for now playing")
            pass
        try:
            resp["source"] = self.state.now_playing["source"]
            resp["title"] = self.state.now_playing.get("title")
        except Exception:
            # _LOG.debug(f"No playback for now playing {self.state.now_playing}")
            pass
        try:
            if resp["source"] == "iradio":
                resp["string"] = f'{resp.get("artist")} {resp.get("title")}'
            else:
                resp["string"] = (
                    f'{resp.get("artist")} / {resp.get("title")} / {resp.get("album")}'
                )

        except Exception:
            # _LOG.debug(f"failed to make string {resp} {e}")
            resp["string"] = "No information available"
        return resp


class NaimState:
    def __init__(self):
        # NVM properties
        self._input: str = None
        self._volume: int = None
        self._standbystatus: dict = None
        self._bufferstate: int = None
        self._inputblk: dict[int, dict] = {}
        self._viewstate: dict = None
        self._briefnp: dict = None
        self._product: str = None
        self._serialnum: str = None
        self._roomname: str = None
        self._totalpresets: int | None = None
        self._presetblk: dict[int, dict] = {}

        # XML properties
        self.view_state = None
        self.now_playing = None
        self.now_playing_time = None
        self.active_list = None
        self.bridge_co_app_versions = None

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, volume: int):
        self._volume = volume

    @property
    def input(self) -> str:
        return self._input

    @input.setter
    def input(self, input: str):
        self._input = input

    @property
    def viewstate(self) -> dict:
        return self._viewstate

    @viewstate.setter
    def viewstate(self, state: dict):
        """NVM view state"""
        self._viewstate = state

    @property
    def briefnp(self) -> dict:
        return self._briefnp

    @briefnp.setter
    def briefnp(self, briefnp):
        self._briefnp = briefnp

    @property
    def bufferstate(self) -> int:
        return self._bufferstate

    @bufferstate.setter
    def bufferstate(self, bufferstate: int):
        self._bufferstate = bufferstate

    @property
    def standbystatus(self) -> dict:
        return self._standbystatus

    @standbystatus.setter
    def standbystatus(self, standbystatus: dict):
        self._standbystatus = standbystatus

    @property
    def inputblk(self) -> list[dict]:
        return self._inputblk

    def set_inputblk_entry(self, index: int, val: dict):
        self._inputblk[index] = val

    @property
    def product(self) -> str:
        return self._product

    @product.setter
    def product(self, product: str):
        self._product = product

    @property
    def serialnum(self) -> str:
        return self._serialnum

    @serialnum.setter
    def serialnum(self, serialnum: str):
        self._serialnum = serialnum

    @property
    def roomname(self) -> str:
        return self._roomname

    @roomname.setter
    def roomname(self, roomname: str):
        self._roomname = roomname

    @property
    def totalpresets(self) -> int | None:
        return self._totalpresets

    @totalpresets.setter
    def totalpresets(self, totalpresets: int | None):
        self._totalpresets = totalpresets

    @property
    def presetblk(self) -> list[dict]:
        return self._presetblk

    def set_presetblk_entry(self, index: int, val: dict):
        _LOG.debug(f"presetblk_entry {index} {val}")
        if val["state"] == "USED":
            self._presetblk[index] = val
        else:
            self._presetblk.pop(index, None)

    def set_view_state(self, state):
        self.view_state = state

    def set_now_playing(self, state):
        self.now_playing = state

    def set_active_list(self, state):
        self.active_list = state

    def set_now_playing_time(self, state):
        self.now_playing_time = state

    def set_bridge_co_app_versions(self, state):
        self.bridge_co_app_versions = state
