from scapy.all import *
import re
import base64

re_b64 = re.compile(r'<base64>(.*)</base64>',re.DOTALL)

pcap_flow = rdpcap(sys.argv[1])
sessions = pcap_flow.sessions()
for sess in sessions:
    print(f"Session:{sess}")
    for packet in sessions[sess]:
        try:
            print(f"{packet[IP].src}:{packet[TCP].dport} -> {packet[IP].src}:{packet[TCP].sport} len({packet[IP].len})")
            if packet[TCP].dport == 15555 or packet[TCP].sport == 15555 :
                print("pk")
                payload=bytes(packet[TCP].payload).decode("utf-8")
                print(payload)
                if m:= re_b64.search(payload) :
                    print(base64.b64decode(m.group(1)).decode("utf-8"))
        except Exception as e:
            pass