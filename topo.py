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

def run_traffic(net, mode):

    h1 = net.get("h1")
    h1.cmd(f"ping 10.1.0.1 -i 1 -c 100 > h1_ping.txt 2>&1 &")
    time.sleep(20)

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
    time.sleep(80)
    
def txt_results_to_csv(path, mode):

    print("Starting data parsing form ping and iperf output files...")

    iperf_data = []
    ping_data = []

    for p in path.glob("*.txt"):
        if p.name == "server_tcp_iperf.txt":
            pass
        elif p.name == "server_udp_iperf.txt":
            pass
        elif p.name == "h1_ping.txt":
            with open(p) as f:
                dest_ip = None
                for line in f:

                    if line.startswith("PING"):
                        m_ip = re.search(r'PING .* \((\d+\.\d+\.\d+\.\d+)\)', line)
                        if m_ip:
                            dest_ip = m_ip.group(1)


                    m_reply = re.search(r'icmp_seq=(\d+) ttl=(\d+) time=([\d\.]+) ms', line)
                    if m_reply and dest_ip:
                        icmp_seq = m_reply.group(1)
                        ttl = m_reply.group(2)
                        time_ms = m_reply.group(3)

                        ping_data.append([p.name, dest_ip, icmp_seq, ttl, time_ms])

        else:
            if mode == "udp":
                with open(p) as f:

                    local_ip = server_ip = None
                    for line in f:
                        # Szukamy linii z połączeniem
                        m_conn = re.search(r'local (\d+\.\d+\.\d+\.\d+) port \d+ connected with (\d+\.\d+\.\d+\.\d+) port \d+', line)
                        if m_conn:
                            local_ip = m_conn.group(1)
                            server_ip = m_conn.group(2)

                        # Szukamy linii Server Report
                        m_report = re.search(r'\[\s*\d+\] \d+\.\d+-\d+\.\d+ sec\s+\d+ MBytes\s+([\d\.]+) Mbits/sec\s+([\d\.]+) ms\s+(\d+)/(\d+)', line)
                        if m_report and local_ip and server_ip:
                            bandwidth = m_report.group(1)
                            jitter = m_report.group(2)
                            lost = m_report.group(3)
                            total = m_report.group(4)

                    iperf_data.append([p.name, local_ip, server_ip, bandwidth, jitter, lost, total])
            
            if mode == "tcp":
                pass
    
    # print(iperf_data)
    # for d in iperf_data:
        # print(d)

    iperf_csv = Path("./iperf.csv")

    if mode == "udp":

        with open(iperf_csv, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["host_file","local_ip", "server_ip", "bandwidth_Mbps", "jitter_ms", "lost_datagrams", "total_datagrams"])
            for d in iperf_data:
                writer.writerow(d)

    if mode == "tcp":
        pass

    ping_csv = Path("./ping.csv")
    with open(ping_csv, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["host_name","destination_ip", "icmp_seq", "ttl", "time_ms"])
            for d in ping_data:
                writer.writerow(d)

    print("Saved parsed data in iperf.csv and ping.csv")


def run():
    n_hosts = 7
    mode = "udp"
    results_folder = Path(".")


    topo = Topology(n_hosts)
    net = Mininet(topo=topo, host=CPULimitedHost,link=TCLink)
    # net = Mininet(topo=topo, link=TCLink)

    for i, host in enumerate(net.hosts):
        host.cpu = 1/n_hosts

    time.sleep(1)

    net.start()

    net.pingAll()

    time.sleep(1)

    run_traffic(net, mode=mode)

    txt_results_to_csv(results_folder, mode)

    CLI(net)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
