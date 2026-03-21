#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink
import time

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
        linkopts = dict(bw=1000, delay='5ms', loss=0, max_queue_size=1000, use_htb=True)

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
                     params2={'ip': '10.2.0.254/24'}, **linkopts)

        # Create hosts
        hosts = [ self.addHost( 'h%s' % h, ip='10.2.0.%s/24' %h, defaultRoute='via 10.2.0.254')
                  for h in range( 1, N+1 ) ]

        # Add switch-host links
        for host in hosts:
            self.addLink(host, switch, **linkopts)

def run_traffic(net, mode):

    h1 = net.get("h1")
    h1.cmd(f"ping 10.1.0.1 -i 0.5 -c 800 > h1_ping.txt 2>&1 &")
    time.sleep(10)

    print("Starting traffic geneation ...")

    for h in net.hosts:
        hostname = h.name

        print(hostname)
        if hostname == "server":
            h.cmd("iperf -s > server_tcp_iperf.txt 2>&1 &")
            h.cmd("iperf -s -u > server_udp_iperf.txt 2>&1 &")
        elif hostname == "Router":
            pass
        else:
            if mode == "tcp":
                h.cmd(f"iperf -c 10.1.0.1 -t 60 > {hostname}_tcp_iperf.txt 2>&1 &")
                pass
            elif mode == "udp":
                h.cmd(f"iperf -c 10.1.0.1 -u -b 100M -t 60 > {hostname}_udp_iperf.txt 2>&1 &")
                pass
            else:
                print("Wrong transport protocol selected!!!")

    print("Waiting for execution of traffic generation ...")
    time.sleep(70)
    

def run():
    n_hosts = 7

    topo = Topology(n_hosts)
    net = Mininet(topo=topo, link=TCLink)

    net.start()

    run_traffic(net, mode="udp")

    CLI(net)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
