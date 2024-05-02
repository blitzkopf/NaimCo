
NaimCo
======
NaimCo (NaimController) is package to control Naim Mu-so sound systems.

The main purpose of this package integration with Home Assistant.

Nothing much to see for the moment but you can turn on the radio to preset #2:
::

  $ naim_control 192.168.1.183 --preset 2 --volume 10

  usage: naim_control.py [-h] [-i {IRADIO,DIGITAL1,SPOTIFY,USB,UPNP,TIDAL,FRONT} | -p PRESET | -o] [-v VOLUME] address

  Turn on Radio on naim Mu-so

  positional arguments:
    address               ip address of Mu-so

  options:
    -h, --help            show this help message and exit
    -i {IRADIO,DIGITAL1,SPOTIFY,USB,UPNP,TIDAL,FRONT}, --input {IRADIO,DIGITAL1,SPOTIFY,USB,UPNP,TIDAL,FRONT}
                          Select input
    -p PRESET, --preset PRESET
                          Preset [1-40]
    -o, --off             Turn receiver off
    -v VOLUME, --volume VOLUME
                          Volume [0-100]

Motivation
----------

Naim Mu-so implements DLNA to some extent and it is possible to control it in home automation systems.
Basic stuff like volume up down and play some media works.

But there are functions that as far as I can tell can't be controlled with upnp/DLNA such as:

- On/Off ( Standby off or standby on í Naim terms )
- Input selection
    - iRadio
    - Digital
    - Analog


Naim does not publish an API for the Mu-so, but there is an App. So after 5 years of waiting for someone else to figure it out I decided to have a look at how it communicates with my Mu-so.

Communication
-------------

Some information found here: `Sniffing <api_sniffing/sniffing.rst>`_
