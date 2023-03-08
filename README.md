# NaimCo
NaimCo (NaimController)  is package to control Naim Mu-so sound systems.

Nothing much to see for the moment but you can turn on the radio to preset #2:
```
$ python scripts/radio_on.py 192.168.1.183 2 --volume 10
```

## Motivation
Naim Mu-so implements DLNA to some extent and it is possible to control it in home automation systems. 
Basic stuff like volume up down and play some media works.

But there are functions that as far as I can tell can't be controlled with upnp/DLNA such as:
- On/Off ( Standby off or standby on í Naim terms )
- Input selection 
    - iRadio
    - Digital
    - Analog


Naim does not publish an API for the Mu-so, but there is an App. So after 5 years of waiting for someone else to figure it out I decided to have a look at how it communicates with my Mu-so.

## Communication
Some information found here: [Sniffing](api_sniffing/sniffing.md)

