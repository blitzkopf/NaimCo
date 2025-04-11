import logging
import socket
import asyncio
import datetime as dt
from .controllers import Controller

_LOG = logging.getLogger(__name__)


class NaimCo:
    """The main class for interacting with a Naim Mu-so device.

    This is the class that the "end user" will interact with.
    """

    def __init__(self, ip_address, callback=None):
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
        self.last_scn = self.state.scn
        self.controller = None
        self.version = None
        self.callback = callback
        _LOG.debug("Created NaimCo instance for ip: %s", ip_address)

    async def startup(self, timeout=None):
        """Connect to the Mu-so device and get the initial state.

        This method should be called before any other interaction with the device.
        """
        # Note: This method should be called after the event loop is running
        # and before any other interaction with the device is attempted.
        _LOG.debug("Starting up NaimCo instance for ip: %s", self.ip_address)
        self._tasks = asyncio.create_task(self.run_tasks(timeout))

    async def update_data(self):
        if self.controller:
            _LOG.info("Requesting data update")
            await self.controller.request_data_update()
            return True
        _LOG.error("No controller to update data")

        return False

    async def runner_task(self):
        """Coroutine that need to run in seperate task to take care of reading data from
        the Mu-so device
        """
        await self.controller.connection_runner()

    async def run_tasks(self, interval: int | None):
        """Run tasks in parallel."""
        reconnect_backoff_time = 10
        while True:
            self.controller = Controller(self)
            try:
                await self.controller.connect()
                await self.initialize(interval)
            except Exception as e:
                _LOG.error(f"Failed to connect to controller {e}")
                await asyncio.sleep(reconnect_backoff_time)
                reconnect_backoff_time += 10
                reconnect_backoff_time = min(reconnect_backoff_time, 120)
                continue
            reconnect_backoff_time = 10
            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self.runner_task())
                    if interval:
                        tg.create_task(self.controller.keep_alive(interval))
                    await self.controller.request_data_update()
            except* Exception as e:
                _LOG.info(f"Tasks failed! {e.exceptions}")
                try:
                    await self.controller.shutdown()
                except Exception as e:
                    _LOG.error(f"Failed to shutdown controller {e}")
                finally:
                    self.controller = None
                    await asyncio.sleep(reconnect_backoff_time)

                # await self._device_disconnect()

    async def initialize(self, timeout=None):
        """Initialize the device so it is ready to accept commands.

        Optionally set timeout interval in seconds for Mu-so device, if Mu-so does not receive
        a message in that interval it will disconnect.
        """
        await self.controller.initialize()
        if timeout:
            await self.controller.set_heartbeat_timout(timeout)

    async def shutdown(self):
        """Close the connection to the Mu-so device."""
        if self._tasks:
            self._tasks.cancel()
            try:
                await self._tasks
            except asyncio.CancelledError:
                _LOG.debug("Tasks cancelled")
        await self.controller.shutdown()

    async def _call_callback(self):
        """Call the callback function if it is set and state.scn has changed"""
        if self.callback and self.state.scn != self.last_scn:
            self.last_scn = self.state.scn
            await self.callback(self.state)

    async def on(self):
        await self.controller.nvm.send_command("SETSTANDBY OFF")
        await asyncio.sleep(3)
        await self.controller.nvm.send_command("GETSTANDBYSTATUS")

    async def off(self):
        await self.controller.nvm.send_command("SETSTANDBY ON")

    async def play(self):
        await self.controller.nvm.send_command("PLAY")

    async def stop(self):
        await self.controller.nvm.send_command("STOP")

    async def pause(self):
        await self.controller.nvm.send_command("PAUSE ON")

    async def nexttrack(self):
        await self.controller.nvm.send_command("NEXTTRACK")

    async def prevtrack(self):
        await self.controller.nvm.send_command("PREVTRACK")

    async def mute(self, mute: bool):
        """Mute the Mu-so device."""
        if mute:
            await self.controller.nvm.send_command("SETMUTE ON")
        else:
            await self.controller.nvm.send_command("SETMUTE OFF")

    @property
    def standbystatus(self):
        return self.state.standbystatus

    @property
    def volume(self):
        return self.state.volume

    @property
    def is_muted(self):
        return self.state.mute

    async def set_volume(self, volume):
        await self.controller.nvm.send_command(f"SETRVOL {volume}")

    async def volume_up(self):
        await self.controller.nvm.send_command("VOL+")

    async def volume_down(self):
        await self.controller.nvm.send_command("VOL-")

    async def set_illum(self, illum):
        await self.controller.nvm.send_command(
            f"SETILLUM {illum}", wait_for_reply_timeout=0.02
        )
        # Setillum does not always return a reply, so we need to update the state manually
        await self.controller.nvm.send_command("GETILLUM")

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

    async def play_row(self, row):
        await self.controller.nvm.send_command(f"PLAYROW {row}")

    async def select_row(self, row, wait_for_reply_timeout=None):
        await self.controller.nvm.send_command(
            f"SELECTROW {row}", wait_for_reply_timeout
        )

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

    @property
    def media_source(self) -> str | None:
        """Source of current playing media."""
        # maybe this should just use input ?
        return self.state.now_playing and self.state.now_playing.get("source", None)

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing track in seconds."""
        if not self.state.now_playing:
            return None
        # spotify uses track_time
        return self.state.now_playing.get("track_time", None)

    @property
    def now_playing_time(self) -> int | None:
        return self.state.now_playing_time

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
                resp["string"] = f"{resp.get('artist')} {resp.get('title')}"
            else:
                resp["string"] = (
                    f"{resp.get('artist')} / {resp.get('title')} / {resp.get('album')}"
                )

        except Exception:
            # _LOG.debug(f"failed to make string {resp} {e}")
            resp["string"] = "No information available"
        return resp


class NaimState:
    def __init__(self):
        # Sequence number, increment to send new state to HA
        self.scn = int(0)
        self.last_update = {}
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
        self._mute: bool = False
        self._unit_temps: dict = {}
        self._voltages: dict = {}
        self._illum: int | None = None

        # XML properties
        self.view_state = None
        self.now_playing = None
        self.now_playing_time = None
        self.active_list = None
        self.rows = None
        self.bridge_co_app_versions = None

    def inc_scn(self):
        self.scn += 1

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, volume: int):
        if volume != self._volume:
            self._volume = volume
            self.inc_scn()

    @property
    def mute(self) -> bool:
        return self._mute

    @mute.setter
    def mute(self, mute: bool):
        if mute != self._mute:
            self._mute = mute
            self.inc_scn()

    @property
    def input(self) -> str:
        return self._input

    @input.setter
    def input(self, input: str):
        if input != self._input:
            self._input = input
            self.inc_scn()

    @property
    def viewstate(self) -> dict:
        return self._viewstate

    @viewstate.setter
    def viewstate(self, state: dict):
        """NVM view state"""
        if state != self._viewstate:
            self._viewstate = state
            self.inc_scn()

    @property
    def briefnp(self) -> dict:
        return self._briefnp

    @briefnp.setter
    def briefnp(self, briefnp):
        if briefnp != self._briefnp:
            self._briefnp = briefnp
            self.inc_scn()

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
        if standbystatus != self._standbystatus:
            self._standbystatus = standbystatus
            self.inc_scn()

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
        if self.now_playing != state:
            self.now_playing = state
            self.last_update["now_playing"] = dt.datetime.utcnow()

            self.inc_scn()

    def set_active_list(self, state):
        self.active_list = state

    def set_rows(self, state):
        self.rows = state

    def set_now_playing_time(self, state):
        if self.now_playing_time != state:
            self.now_playing_time = state
            self.last_update["now_playing_time"] = dt.datetime.utcnow()

            self.inc_scn()

    def set_bridge_co_app_versions(self, state):
        self.bridge_co_app_versions = state

    def set_unit_temp(self, unit: str, val: dict):
        self._unit_temps[unit] = val

    def set_voltage(self, output, val):
        self._voltages[output] = val

    @property
    def illum(self) -> int | None:
        return self._illum

    @illum.setter
    def illum(self, illum: int | None):
        if illum != self._illum:
            self._illum = illum
            self.inc_scn()
