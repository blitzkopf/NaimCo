import logging
import sys
import asyncio
import time
import argparse 

from naimco import NaimCo

_LOG = logging.getLogger(__name__)


#create an ArgumentParser object
parser = argparse.ArgumentParser(description = 'Turn on Radio on naim Mu-so')
#declare arguments
parser.add_argument('-v','--volume', type = int, required = False, help='Volume 0-100')
parser.add_argument("address", type=str,help="ip address of Mu-so")
parser.add_argument("preset", type=int,help="preset iRadio channel")
args = parser.parse_args()

async def radio_on(device,preset,volume=None):
    await device.initialize()
    _LOG.info(f"Turning on radio preset {preset} volume {volume}")
    await device.on()
    await device.nvm_controller.send_command(f'GOTOPRESET {preset}')
    if(volume):
        await device.nvm_controller.send_command(f'SETRVOL {volume}')

    await device.tcp_controller.send_command('GetViewState')
    await device.tcp_controller.send_command('GetActiveList') 

async def main():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    filehandler = logging.FileHandler(filename='naimco.log')
    filehandler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    filehandler.setFormatter(formatter)
    root.addHandler(filehandler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    root.addHandler(handler)

    device  = NaimCo(args.address)
    #await naim.connect_api()
    await device.startup()
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(device.run_connection())
        task2 = tg.create_task(radio_on(device,args.preset,args.volume))
    _LOG.info("Both tasks have completed now.")
  

if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    end = time.time()
    print(end - start)
