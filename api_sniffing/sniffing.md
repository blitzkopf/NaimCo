# Sniffing
## Connections 
The app will make the following connections to the Mu-so.
1. GET http://mymuso:8080/description.xml  DLNA service description ( actually makes multiple gets)
2. TCP port 15081 which is refused by Mu-so, I believe that is used by some other Naim equipment. [homebridge-naim-audio]( https://github.com/sicamois/homebridge-naim-audio )
3. HTTP GET different services of DLNA
    - http://192.168.1.183:8080/RenderingControl/desc.xml 
    - http://192.168.1.183:8080/ConnectionManager/desc.xml 
    - http://192.168.1.183:8080/AVTransport/desc.xml 
4. HTTP SUBSCRIBE with CALLBACK to a port on the phone, I have not yet seen anything on that port
    - http://192.168.1.183:8080/AVTransport/evt
    - http://192.168.1.183:8080/ConnectionManager/evt 
    - http://192.168.1.183:8080/RenderingControl/evt
5. TCP port 15555 this is where commands and responses flow.

## Commands and Responses
Traffic on port 15555 is a stream of xml commands one way and reply, events and errors the other.

Communication is aynchronous so the next incoming packet after a command is not necessarily your reply. 

Most reply messages are just aknowledgment with no payload. And if you are requesting some information it will be sent as events back. But in some cases there is some information in the reply. 

There are no markers on the response stream so when reading it you must keep track off xml elements. Each response can be split into multiple network packets and each network packet can contain more than one response element.

### Commands
```XML
<command>
    <name>SetHeartbeatTimeout</name>
    <id>2</id>
    <map>
        <item>
            <name>timeout</name>
            <int>10</int>
        </item>
    </map>
</command>
```
### Replies
Replies are semantically quite similar to commands but they are encoded using xml attributes rather than subelements  
```XML
<reply name="SetHeartbeatTimeout" id="2">
</reply>
```
reply with data:
```XML
<reply name="GetPlaylistStats" id="9">
	<map>
		<item name="active_idx" int="0" />
		<item name="count" int="0" />
		<item name="in_use" int="0" />
		<item name="max_size" int="500" />
	</map>
</reply>
```
### Events
Events are just like replies they just lack the id attribute
```XML
<event name="GetViewState">
	<map>
		<item name="state" string="play" />
	</map>
</event>
```
### Errors
Errors are coded like commands using subelements.
```XML
<error>
	<name>GetNowPlaying</name>
	<id>12</id>
	<code>1</code>
	<description>Not playing</description>
</error>
```
## NVM Tunnel 
There is a curiosity hidden in the communication stream. 
There are commands called TunnelToHost and events TunnelFromHost that have base64 encoded data.

```XML
<command>
    <name>TunnelToHost</name>
    <id>17</id>
    <map>
        <item>
            <name>data<name>
            <base64>Kk5WTSBHRVRCVUZGRVJTVEFURQ0=</base64>
        </item>
    </map>
</command>
```

```XML
<event name="TunnelFromHost">
	<map>
		<item name="data">
			<base64>I05WTSBFUlJPUjogWzExXSA=</base64>
		</item>
	</map>
</event>
```
When decoded they will spell things like  
```
*NVM PRODUCT
#NVM PRODUCT MUSO
*NVM VERSION
#NVM VERSION 2.00.000 14777 DEV BETA 
*NVM SETSTANDBY OFF
```
\* command
\# reply 

So it looks like there is a second controller module taking care of some basic functions of the player. T
he best part is that it will actually list all available commands if you send ```*NVM HELP``` base64 encoded of course and placed in XML envelope.

## Useful tools
I used PCAPdroid to capture the trafic from the Naim Focal app, it was surprisingly easy.

Then I used Wireshark to analyze the PCAP file on my PC.

