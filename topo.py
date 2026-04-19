#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.node import CPULimitedHost
import re
import csv
from pathlib import Path
import time
import argparse


class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

class Topology( Topo ):
    "Custom topology"

    def build( self, N=4):

        # Link options
        # linkopts = dict(bw=30, delay='1ms', max_queue_size=500)
        linkopts = dict(bw=50, delay='1ms', max_queue_size=500, use_htb=True)
        # linkopts = dict(bw=50, delay='1ms', max_queue_size=500)
        # linkopts = dict(bw=30, delay='0.1ms', max_queue_size=200)

        # Create router
        router = self.addHost("Router", cls=LinuxRouter, ip="10.1.0.254/24")


        # Adding server with a default route
        server = self.addHost(name='server',
                          ip='10.1.0.1/24',
                          defaultRoute='via 10.1.0.254')
        
        # Adding link between server and router

        self.addLink(server,
                     router,
                     intfName2='router-eth1',
                     params2={'ip': '10.1.0.254/24'}, **linkopts)

        # Create switch
        switch = self.addSwitch("Switch", dpid='0000000000000001')


        # Connect switch to router
        self.addLink(switch,
                     router,
                     intfName2='router-eth2',
                     params2={'ip': '10.2.0.254/24'}, bw=1000, delay='1ms', max_queue_size=1000, use_htb=True)

        # Create hosts
        hosts = [ self.addHost( 'h%s' % h, ip='10.2.0.%s/24' %h, defaultRoute='via 10.2.0.254')
                  for h in range( 1, N+1 ) ]

        # Add switch-host links
        for host in hosts:
            self.addLink(host, switch, **linkopts)

def run_traffic(net, mode):



    print("Starting traffic geneation ...")

    server = net.get("server")
    server.cmd("iperf -s -p 5202 -e > server_tcp_iperf.txt 2>&1 &")
    server.cmd("iperf -s -u -e > server_udp_iperf.txt 2>&1 &")
    time.sleep(2)



    for h in net.hosts:
        hostname = h.name

        print(hostname)
        if hostname == "server":
            pass
        elif hostname == "Router":
            pass
        else:
            if mode == "tcp":
                h.cmd(f"iperf -c 10.1.0.1 -t 60 -S 0x00 -p 5202 -e> {hostname}_tcp_iperf.txt 2>&1 &")
                pass
            elif mode == "udp":
                h.cmd(f"iperf -c 10.1.0.1 -u -b 6M -t 60  -S 0x20 -e > {hostname}_udp_iperf.txt 2>&1 &")
                pass
            else:
                print("Wrong transport protocol selected!!!")

        # Additional TCP stream from H1 to Server
        if hostname == "h1":
            h.cmd(f"iperf -c 10.1.0.1 -t 60 -S 0x80 -p 5202 -e> {hostname}_tcp_iperf.txt 2>&1 &")

        h7 = net.get("h7")
        h7.cmd(f"ping 10.1.0.1 -i 1 -c 60 > h7_ping.txt 2>&1 &")

    print("Waiting for execution of traffic generation ...")
    time.sleep(60)
    

# QOS on Router


def setup_router_htb(net):
    r = net.get("Router")
    intf = "router-eth1"
    r.cmd(f"tc qdisc del dev {intf} root || true")

    # Główna klasa
    r.cmd(f"tc qdisc add dev {intf} root handle 1: htb default 50")
    r.cmd(f"tc class add dev {intf} parent 1: classid 1:1 htb rate 50mbit")

    # ICMP - Gwarantujemy niskie opóźnienie
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 htb rate 1mbit ceil 30mbit prio 0")
    r.cmd(f"tc qdisc add dev {intf} parent 1:10 fq_codel target 1ms interval 20ms")

    # TCP - 10-15 Mbps
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 htb rate 10mbit ceil 15mbit prio 1")
    r.cmd(f"tc qdisc add dev {intf} parent 1:20 fq_codel")

    # UDP - 1-5 Mbps (mały bufor, by nie generować mega opóźnień)
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:30 htb rate 5mbit ceil 35mbit prio 2")
    r.cmd(f"tc qdisc add dev {intf} parent 1:30 pfifo limit 50") # Zmniejszono z 200 na 50

    # Filtry
    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 1 u32 match ip protocol 1 0xff flowid 1:10")
    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 2 u32 match ip protocol 6 0xff flowid 1:20")
    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 3 u32 match ip protocol 17 0xff flowid 1:30")

def setup_router_hfsc(net):
    r = net.get("Router")
    intf = "router-eth1"

    r.cmd(f"tc qdisc del dev {intf} root || true")

    # ROOT: Default 30 (UDP)
    r.cmd(f"tc qdisc add dev {intf} root handle 1: hfsc default 30")

    # Główna klasa (Upper-Limit ustawiony na 30mbit - tyle co fizyczny link)
    r.cmd(f"tc class add dev {intf} parent 1: classid 1:1 "
          f"hfsc sc rate 50mbit ul rate 50mbit")

    # 1. ICMP: Real-Time dla ochrony opóźnienia. 
    # d 1ms m1 10mbit -> burst na start, potem m2 1mbit
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 "
          f"hfsc rt m1 10mbit d 1ms m2 1mbit ls rate 1mbit ul rate 30mbit")
    # Dodajemy agresywny fq_codel dla ICMP
    r.cmd(f"tc qdisc add dev {intf} parent 1:10 fq_codel target 1ms interval 20ms")

    # 2. TCP: Gwarancja 10mbit (ls), max 15mbit (ul)
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 "
          f"hfsc ls rate 10mbit ul rate 15mbit")
    r.cmd(f"tc qdisc add dev {intf} parent 1:20 fq_codel")

    # 3. UDP: Gwarancja 1mbit (ls), max 5mbit (ul)
    # Rezygnujemy z fq_codel na rzecz pfifo, by "utrudnić" życie UDP i wymusić opóźnienia
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:30 "
          f"hfsc ls rate 5mbit ul rate 35mbit")
    r.cmd(f"tc qdisc add dev {intf} parent 1:30 pfifo limit 50")

    # FILTRY (Niezmienione, u32 działa tak samo dla obu qdisc)
    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 1 u32 match ip protocol 1 0xff flowid 1:10")
    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 2 u32 match ip protocol 6 0xff flowid 1:20")
    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 3 u32 match ip protocol 17 0xff flowid 1:30")

def setup_router_cake(net):
    r = net.get("Router")
    intf = "router-eth1"

    r.cmd(f"tc qdisc del dev {intf} root || true")

    # bandwidth 30mbit: limit całkowity
    # besteffort: wyłączamy diffserv4, jeśli nie tagujemy pakietów (uproszczenie)
    # wash: czyści stare tagi DSCP, które mogą mylić CAKE
    # rtt 100ms: informujemy CAKE, że spodziewamy się większych opóźnień (przestanie tak mocno ucinac pakiety)
    r.cmd(
        f"tc qdisc add dev {intf} root cake "
        f"bandwidth 50mbit "
        f"rtt 100ms "
        f"raw "
        f"dual-srchost "
        f"nonat"
    )

# QoS on Hosts

def setup_hosts_htb(net, n_hosts):
    print("Applying HTB QoS on hosts...")
    for i in range(1, n_hosts + 1):
        h = net.get(f"h{i}")
        intf = f"h{i}-eth0"
        
        # Kluczowe: wyłączamy offloading, by pakiety nie były grupowane (lepszy ping)
        h.cmd(f"ethtool -K {intf} tso off gso off gro off")
        h.cmd(f"tc qdisc del dev {intf} root || true")

        # Główne pasmo hosta ustawiamy rozsądnie (np. 10mbit na hosta przy 30mbit łączu total)
        h.cmd(f"tc qdisc add dev {intf} root handle 1: htb default 30")
        h.cmd(f"tc class add dev {intf} parent 1: classid 1:1 htb rate 10mbit ceil 15mbit")

        # ICMP - Gwarancja pasma i najniższy priorytet opóźnienia
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 htb rate 1mbit ceil 10mbit prio 0")
        h.cmd(f"tc qdisc add dev {intf} parent 1:10 fq_codel target 1ms interval 20ms")

        # TCP - 10-15 Mbps (dzielone przez hosty)
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 htb rate 10mbit ceil 15mbit prio 1")
        h.cmd(f"tc qdisc add dev {intf} parent 1:20 fq_codel")

        # UDP - Mocno limitujemy u źródła (max 2-5mb)
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:30 htb rate 1mbit ceil 5mbit prio 2")
        h.cmd(f"tc qdisc add dev {intf} parent 1:30 pfifo limit 50")

        # FILTRY (Dodano protokół ip do komendy)
        h.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 1 u32 match ip protocol 1 0xff flowid 1:10")
        h.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 2 u32 match ip protocol 6 0xff flowid 1:20")
        h.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 3 u32 match ip protocol 17 0xff flowid 1:30")


def setup_hosts_hfsc(net, n_hosts):
    print("Applying HFSC + fq_codel QoS on hosts (Router-like)...")
    for i in range(1, n_hosts + 1):
        h = net.get(f"h{i}")
        intf = f"h{i}-eth0"
        
        # 1. Czyszczenie i optymalizacja interfejsu
        h.cmd(f"ethtool -K {intf} tso off gso off gro off")
        h.cmd(f"tc qdisc del dev {intf} root || true")

        # 2. ROOT: HFSC z domyślną klasą 1:30 (UDP)
        h.cmd(f"tc qdisc add dev {intf} root handle 1: hfsc default 30")

        # Główna klasa (Limit całkowity hosta: 15mbit)
        h.cmd(f"tc class add dev {intf} parent 1: classid 1:1 "
              f"hfsc sc rate 15mbit ul rate 15mbit")

        # 3. Klasa 1:10 - ICMP (Najwyższy priorytet - Real-Time)
        # Gwarancja pasma i burst (d 1ms m1 10mbit) dla minimalnego pingu
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 "
              f"hfsc rt m1 10mbit d 1ms m2 2mbit ls rate 2mbit")
        # fq_codel z agresywnym targetem dla ICMP
        h.cmd(f"tc qdisc add dev {intf} parent 1:10 fq_codel target 1ms interval 20ms")

        # 4. Klasa 1:20 - TCP (Średni priorytet)
        # Gwarancja 10mbit, max 15mbit
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 "
              f"hfsc ls rate 10mbit ul rate 15mbit")
        # Standardowy fq_codel dla sprawiedliwego podziału strumieni TCP
        h.cmd(f"tc qdisc add dev {intf} parent 1:20 fq_codel")

        # 5. Klasa 1:30 - UDP (Najniższy priorytet / Limit 5mbit)
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:30 "
              f"hfsc ls rate 2mbit ul rate 5mbit")
        # pfifo limit 50 - brak AQM, by "karać" nadmiarowy ruch UDP (jak na routerze)
        h.cmd(f"tc qdisc add dev {intf} parent 1:30 pfifo limit 200")

        # 6. FILTRY u32 (Klasyfikacja protokołów)
        # ICMP -> 1:10
        h.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 1 u32 match ip protocol 1 0xff flowid 1:10")
        # TCP -> 1:20
        h.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 2 u32 match ip protocol 6 0xff flowid 1:20")

def setup_hosts_cake(net, n_hosts):
    print("Applying CAKE QoS on hosts...")
    for i in range(1, n_hosts + 1):
        h = net.get(f"h{i}")
        intf = f"h{i}-eth0"
        h.cmd(f"ethtool -K {intf} tso off gso off gro off")
        h.cmd(f"tc qdisc del dev {intf} root || true")

        # bandwidth: ustawiamy na 10-15mbit, by host nie "zalał" routera
        # triple-isolate: sprawia, że ping i iperf wewnątrz jednego hosta są traktowane osobno
        h.cmd(
            f"tc qdisc add dev {intf} root cake "
            f"bandwidth 15mbit "
            f"rtt 20ms "
            f"raw "
            f"dual-srchost "
            f"nonat"
        )


def run():
    
    parser = argparse.ArgumentParser(description="QoS JOWS")

    parser.add_argument("--placement", help="router or hosts")
    parser.add_argument("--type", help="1 - HTB + fq_codel, 2 - HSFC + fq_codel, 3 - CAKE")
    args = parser.parse_args()

    print(f"Placement: {args.placement}")
    print(f"Type: {args.type}")

    n_hosts = 7
    mode = "udp"
    results_folder = Path(".")

    topo = Topology(n_hosts)
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)

    for i, host in enumerate(net.hosts):
        if host.name == "server":
            print("Server cpu set!")
            host.cpu = 1    
        elif host.name == "Router":
            print("Router cpu set!")
            host.cpu = 1
        else:
            host.cpu = 1 / n_hosts

    time.sleep(1)

    net.start()


    # QoS Selection

    if args.placement == "router":
        print(f"Placement: router")
        if args.type == "1":
            print("QoS: HTB")
            setup_router_htb(net)
        elif args.type == "2":
            print("QoS: HFSC")
            setup_router_hfsc(net)
        elif args.type == "3":
            print("QoS: CAKE")
            setup_router_cake(net)
    elif args.placement == "hosts":
        print(f"Placement: host")
        if args.type == "1":
            print("QoS: HTB")
            setup_hosts_htb(net, 7)
        elif args.type == "2":
            print("QoS: HSFC")
            setup_hosts_hfsc(net,7)
        elif args.type == "3":
            print("QoS: CAKE")
            setup_hosts_cake(net, 7)
    else:
        print("Without QoS!")

    net.pingAll()

    time.sleep(5)

    run_traffic(net, mode=mode)

    # txt_results_to_csv(results_folder, mode)

    # CLI(net)
    time.sleep(5)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
