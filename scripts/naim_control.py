"""naim Mu-so Controller.

Simple cmdline script to control your Mu-so.
"""

import logging
import sys
import asyncio
import time
import argparse

from naimco import NaimCo

root = logging.getLogger()
root.setLevel(logging.DEBUG)

filehandler = logging.FileHandler(filename="naimco.log")
filehandler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
filehandler.setFormatter(formatter)
root.addHandler(filehandler)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
root.addHandler(handler)
_LOG = logging.getLogger(__name__)


async def control(device, args):
    """Send commands to Mu-so runs as asyncio task"""
    # await device.initialize(10)
    if args.preset:
        _LOG.info(f"Turning on radio preset {args.preset}")
        await device.select_preset(args.preset)
    if args.input:
        _LOG.info(f"Selecting input {args.input}")
        await device.select_input(args.input)

    if args.volume:
        _LOG.info(f"Setting volume {args.volume}")

        await device.set_volume(args.volume)
    if args.off:
        _LOG.info("Turning off")
        await device.off()
    else:
        await device.on()

    await device.controller.send_command("GetViewState")
    await device.controller.send_command("GetNowPlaying")

    # await device.controller.send_command('GetActiveList')


def main():
    """Take care of parse cmdline and start communicating with Mu-so."""
    # create an ArgumentParser object
    parser = argparse.ArgumentParser(description="Turn on Radio on naim Mu-so")
    # declare arguments
    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "-i",
        "--input",
        type=str,
        required=False,
        help="Select input",
        choices=["IRADIO", "DIGITAL1", "SPOTIFY", "USB", "UPNP", "TIDAL", "FRONT"],
    )
    group.add_argument("-p", "--preset", type=int, required=False, help="Preset [1-40]")
    group.add_argument(
        "-o", "--off", required=False, help="Turn receiver off", action="store_true"
    )

    parser.add_argument(
        "-v", "--volume", type=int, required=False, help="Volume [0-100]"
    )
    parser.add_argument("address", type=str, help="ip address of Mu-so")
    args = parser.parse_args()
    asyncio.run(run(args))


async def run(args):
    device = NaimCo(args.address)
    # await naim.connect_api()
    await device.startup()
    # async with asyncio.TaskGroup() as tg:
    #    task1 = tg.create_task(device.run_connection())
    #    task2 = tg.create_task(control(device,args))
    await control(device, args)
    # _LOG.info("Both tasks have completed now.")
    await asyncio.sleep(1)

    _LOG.info(f"View State: {device.state.view_state} ")
    _LOG.info(f"Now Playing: {device.state.now_playing} ")
    _LOG.info(f"NVM VIEWSTATE: {device.state._viewstate} ")

    await device.shutdown()


if __name__ == "__main__":
    start = time.time()
    main()
    end = time.time()
    print(end - start)
