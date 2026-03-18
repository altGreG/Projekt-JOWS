#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel
from mininet.cli import CLI


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
        linkopts = dict(bw=1000, delay='1ms', loss=0, max_queue_size=1000, use_htb=True)

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

def run():
    n_hosts = 7

    topo = Topology(n_hosts)
    net = Mininet(topo=topo)

    net.start()
    CLI(net)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()