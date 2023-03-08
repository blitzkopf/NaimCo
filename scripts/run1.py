import logging
import sys
import asyncio
import time

from naimco import NaimCo
_LOG = logging.getLogger(__name__)


async def replay(device):
    await asyncio.sleep(1)
    await device.initialize()
    print("Turning on")
    #await device.on()
    #await device.controller.send_command('GetUPnPMediaRendererList')
    await asyncio.sleep(1)
    await device.controller.send_command('GetApiVersion',{'item':{'name':'module','string':'NAIM'}})
    await device.controller.send_command('DebugGetModuleList')
    #await device.nvm_controller.send_command('GOTOPRESET 2')
    #await device.controller.send_command('GetViewState')
    #await device.controller.send_command('GetActiveList')
    await asyncio.sleep(2)
       

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

    device  = NaimCo('192.168.1.183')
    #await naim.connect_api()
    await device.startup()
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(device.run_connection())
        task2 = tg.create_task(replay(device))
    _LOG.info("Both tasks have completed now.")
  

if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    end = time.time()
    print(end - start)
