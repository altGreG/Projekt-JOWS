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
        linkopts = dict(bw=150, delay='1ms', loss=0, max_queue_size=1000, use_htb=True)

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
    h1.cmd(f"ping 10.1.0.1 -i 1 -c 180 > h1_ping.txt 2>&1 &")
    time.sleep(60)

    print("Starting traffic geneation ...")

    for h in net.hosts:
        hostname = h.name

        print(hostname)
        if hostname == "server":
            h.cmd("iperf -s -p 5202 -e > server_tcp_iperf.txt 2>&1 &")
            h.cmd("iperf -s -u -e > server_udp_iperf.txt 2>&1 &")
        elif hostname == "Router":
            pass
        else:
            if mode == "tcp":
                h.cmd(f"iperf -c 10.1.0.1 -t 60 -p 5202 -e> {hostname}_tcp_iperf.txt 2>&1 &")
                pass
            elif mode == "udp":
                h.cmd(f"iperf -c 10.1.0.1 -u -b 5M -t 60 -e > {hostname}_udp_iperf.txt 2>&1 &")
                pass
            else:
                print("Wrong transport protocol selected!!!")

        # Additional TCP stream from H1 to Server
        if hostname == "h1":
            h.cmd(f"iperf -c 10.1.0.1 -t 60 -p 5202 -e> {hostname}_tcp_iperf.txt 2>&1 &")

    print("Waiting for execution of traffic generation ...")
    time.sleep(120)
    
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

def setup_per_host_qos(net, n_hosts):
    router = net.get("Router")

    # Reset tc
    router.cmd("tc qdisc del dev router-eth2 root || true")

    # Root HTB
    router.cmd("tc qdisc add dev router-eth2 root handle 1: htb default 999")

    # Total bandwidth class
    router.cmd("tc class add dev router-eth2 parent 1: classid 1:1 htb rate 150mbit")

    base_rate = int(150 / n_hosts)

    for i in range(1, n_hosts + 1):
        class_id = 10 + i

        # Create class per host
        router.cmd(
            f"tc class add dev router-eth2 parent 1:1 classid 1:{class_id} "
            f"htb rate {base_rate}mbit ceil 150mbit"
        )

        # Attach fair queue inside each class
        router.cmd(
            f"tc qdisc add dev router-eth2 parent 1:{class_id} handle {class_id}: fq_codel"
        )

        # Match traffic from host IP
        router.cmd(
            f"tc filter add dev router-eth2 protocol ip parent 1: prio 1 u32 "
            f"match ip src 10.2.0.{i} flowid 1:{class_id}"
        )

# def setup_host_rate_limit(net, n_hosts, rate="20mbit"):
#     """
#     QoS mechanism 0 (existing): Token Bucket Filter (TBF) on each host's egress.

#     Applied directly on each host NIC. Enforces a hard rate ceiling on outgoing
#     traffic using a token bucket. Simple and stateless — no traffic classification,
#     no prioritization between flows. Excess packets are delayed (up to 'latency')
#     then dropped.

#     Parameters
#     ----------
#     net     : Mininet network object
#     n_hosts : number of client hosts (h1 .. hN)
#     rate    : egress rate limit per host (e.g. "20mbit")
#     """
#     print("Applying per-host rate limiting (TBF)...")

#     for i in range(1, n_hosts + 1):
#         h = net.get(f"h{i}")
#         intf = f"h{i}-eth0"

#         print(f"Configuring {h.name} on {intf}")

#         # Remove existing qdisc (important!)
#         h.cmd(f"tc qdisc del dev {intf} root || true")

#         # Apply Token Bucket Filter
#         h.cmd(
#             f"tc qdisc add dev {intf} root tbf "
#             f"rate {rate} burst 32kbit latency 400ms"
#         )


# # =============================================================================
# # QoS MECHANISM 1 — HTB + fq_codel with traffic classification (per host)
# # =============================================================================
# #
# # Replaces the flat TBF with a two-class HTB tree on every host's egress:
# #
# #   root (HTB)
# #   ├── class 1:10  ICMP / interactive  — guaranteed 30% of rate, high priority
# #   │     └── fq_codel   (AQM: low latency, fair between sub-flows)
# #   └── class 1:20  bulk (UDP/TCP)      — remaining bandwidth, can borrow up to ceil
# #         └── fq_codel
# #
# # ICMP is matched by protocol number (1). All other traffic falls into the
# # bulk class via HTB's "default 20" setting.  fq_codel inside each class
# # prevents bufferbloat and keeps individual flows fair without starvation.
# #
# # Key benefit over TBF: ping RTT stays low even when iperf saturates the link,
# # because ICMP packets enter the high-priority class queue, not the bulk queue.
# #
# def setup_host_htb_fq_codel(net, n_hosts, total_rate="20mbit",
#                               icmp_rate="6mbit", bulk_rate="14mbit",
#                               ceil_rate="20mbit"):
#     """
#     Apply HTB + fq_codel egress shaping on every client host.

#     Traffic is split into two classes:
#       - ICMP / interactive  → class 1:10  (icmp_rate guaranteed, prio 1)
#       - Bulk (everything else) → class 1:20  (bulk_rate guaranteed, prio 2)
#     Both classes can borrow up to ceil_rate when the other is idle.
#     fq_codel is attached as the leaf qdisc in each class.

#     Parameters
#     ----------
#     net        : Mininet network object
#     n_hosts    : number of client hosts (h1 .. hN)
#     total_rate : overall HTB root rate (should equal link capacity)
#     icmp_rate  : guaranteed rate for the ICMP / interactive class
#     bulk_rate  : guaranteed rate for the bulk data class
#     ceil_rate  : maximum rate either class can burst to (borrowing)
#     """
#     print("Applying per-host HTB + fq_codel egress shaping...")

#     for i in range(1, n_hosts + 1):
#         h = net.get(f"h{i}")
#         intf = f"h{i}-eth0"

#         print(f"Configuring {h.name} on {intf}")

#         # Remove any existing root qdisc
#         h.cmd(f"tc qdisc del dev {intf} root || true")

#         # Root HTB qdisc — unclassified traffic falls into class 1:20 (bulk)
#         h.cmd(f"tc qdisc add dev {intf} root handle 1: htb default 20")

#         # Root class — shapes total egress to total_rate
#         h.cmd(f"tc class add dev {intf} parent 1: classid 1:1 "
#               f"htb rate {total_rate} ceil {ceil_rate}")

#         # Class 1:10 — ICMP / interactive, high priority (prio 1)
#         h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 "
#               f"htb rate {icmp_rate} ceil {ceil_rate} prio 1")

#         # Class 1:20 — Bulk data (default), lower priority (prio 2)
#         h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 "
#               f"htb rate {bulk_rate} ceil {ceil_rate} prio 2")

#         # Attach fq_codel as leaf qdisc inside each class
#         # fq_codel provides AQM (active queue management) and per-flow fairness
#         h.cmd(f"tc qdisc add dev {intf} parent 1:10 handle 10: fq_codel")
#         h.cmd(f"tc qdisc add dev {intf} parent 1:20 handle 20: fq_codel")

#         # Filter: steer ICMP (protocol 1) into the interactive class
#         h.cmd(f"tc filter add dev {intf} parent 1: protocol ip prio 1 "
#               f"u32 match ip protocol 1 0xff flowid 1:10")

#         # All remaining IP traffic is caught by HTB's default 20 — no extra filter needed


# # =============================================================================
# # QoS MECHANISM 2 — HFSC with latency + bandwidth guarantees (per host)
# # =============================================================================
# #
# # HFSC (Hierarchical Fair Service Curve) extends HTB by letting you specify
# # *two* service curves per class:
# #
# #   - Real-time curve (rt)  : hard latency / burst guarantee, served first
# #   - Link-share curve (ls) : long-run fair-share of bandwidth
# #
# # This makes it possible to say "ICMP must get its packets out within X ms
# # regardless of bulk load", which TBF and HTB cannot express.
# #
# # Tree layout (same two-class split as the HTB version):
# #
# #   root (HFSC)
# #   ├── class 1:10  ICMP / interactive
# #   │     rt  = small burst with tight deadline  (low latency guarantee)
# #   │     ls  = 30% of link
# #   │     └── fq_codel
# #   └── class 1:20  bulk (UDP/TCP)
# #         ls  = 70% of link  (no rt curve — bulk tolerates delay)
# #         └── fq_codel
# #
# # The rt curve is expressed as "m1 d m2":
# #   m1 = initial burst rate   (served immediately up to d microseconds)
# #   d  = burst duration in µs
# #   m2 = sustained rate after burst
# #
# def setup_host_hfsc(net, n_hosts, total_rate="20mbit",
#                     icmp_rate="6mbit", bulk_rate="14mbit",
#                     icmp_rt_burst="20mbit", icmp_rt_delay_us=5000):
#     """
#     Apply HFSC egress shaping on every client host.

#     Provides both bandwidth fairness (link-share curve) and a hard latency
#     bound for ICMP / interactive traffic (real-time curve).

#     Class layout:
#       1:10  ICMP  — rt curve: burst at icmp_rt_burst for icmp_rt_delay_us µs,
#                     then icmp_rate sustained; ls: icmp_rate long-term share
#       1:20  Bulk  — ls only: bulk_rate long-term share, no latency guarantee

#     Parameters
#     ----------
#     net              : Mininet network object
#     n_hosts          : number of client hosts (h1 .. hN)
#     total_rate       : overall HFSC root rate
#     icmp_rate        : sustained link-share rate for ICMP class
#     bulk_rate        : link-share rate for bulk class
#     icmp_rt_burst    : initial burst rate for ICMP real-time curve (m1)
#     icmp_rt_delay_us : burst duration for ICMP real-time curve in microseconds (d)
#     """
#     print("Applying per-host HFSC egress shaping...")

#     for i in range(1, n_hosts + 1):
#         h = net.get(f"h{i}")
#         intf = f"h{i}-eth0"

#         print(f"Configuring {h.name} on {intf}")

#         # Remove any existing root qdisc
#         h.cmd(f"tc qdisc del dev {intf} root || true")

#         # Root HFSC qdisc — unclassified traffic falls into class 1:20 (bulk)
#         h.cmd(f"tc qdisc add dev {intf} root handle 1: hfsc default 20")

#         # Root class — sets the total egress rate ceiling
#         h.cmd(f"tc class add dev {intf} parent 1: classid 1:1 "
#               f"hfsc sc rate {total_rate} ul rate {total_rate}")

#         # Class 1:10 — ICMP / interactive
#         #   Real-time curve: burst at icmp_rt_burst for icmp_rt_delay_us µs,
#         #                    then fall back to icmp_rate
#         #   Link-share curve: icmp_rate long-term share
#         h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 "
#               f"hfsc rt m1 {icmp_rt_burst} d {icmp_rt_delay_us}us m2 {icmp_rate} "
#               f"ls m1 {icmp_rt_burst} d {icmp_rt_delay_us}us m2 {icmp_rate}")

#         # Class 1:20 — Bulk data (link-share only, no real-time guarantee)
#         h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 "
#               f"hfsc ls rate {bulk_rate}")

#         # Leaf qdiscs: fq_codel inside each class for AQM + sub-flow fairness
#         h.cmd(f"tc qdisc add dev {intf} parent 1:10 handle 10: fq_codel")
#         h.cmd(f"tc qdisc add dev {intf} parent 1:20 handle 20: fq_codel")

#         # Filter: steer ICMP (protocol 1) into the real-time class
#         h.cmd(f"tc filter add dev {intf} parent 1: protocol ip prio 1 "
#               f"u32 match ip protocol 1 0xff flowid 1:10")

#         # Bulk traffic is caught by HFSC's default 20 — no extra filter needed


# # =============================================================================
# # QoS MECHANISM 3 — IFB-based ingress shaping (per host)
# # =============================================================================
# #
# # Linux cannot truly *shape* ingress traffic — the kernel processes arriving
# # packets before any qdisc can delay them, so only hard policing (drop) is
# # available on a real ingress qdisc.
# #
# # The workaround is an IFB (Intermediate Functional Block) virtual device:
# #   1. Attach an ingress qdisc to eth0 and redirect ALL arriving packets to ifbX
# #   2. Attach a full HTB + fq_codel shaping tree to ifbX's *egress*
# #   3. The kernel now shapes the redirected traffic just like outgoing packets
# #
# # Result: arriving packets are held in the ifb queue, shaped to ingress_rate,
# # then handed up the network stack — genuine ingress rate limiting without
# # dropping packets above the limit.
# #
# # One IFB device is created per host (ifb0 on h1, ifb1 on h2, …).
# # The ifb kernel module must be available in the Mininet host namespace.
# #
# def setup_host_ifb_ingress(net, n_hosts, ingress_rate="20mbit",
#                             ceil_rate="20mbit"):
#     """
#     Apply IFB-based ingress shaping on every client host.

#     Redirects all incoming packets on eth0 to a per-host IFB virtual device,
#     then applies HTB + fq_codel shaping on the IFB's egress. This achieves
#     true ingress rate limiting (with buffering, not just hard drops).

#     Parameters
#     ----------
#     net           : Mininet network object
#     n_hosts       : number of client hosts (h1 .. hN)
#     ingress_rate  : target ingress rate limit per host
#     ceil_rate     : maximum burst rate (should equal ingress_rate for strict limit)
#     """
#     print("Applying per-host IFB ingress shaping...")

#     for i in range(1, n_hosts + 1):
#         h = net.get(f"h{i}")
#         intf = f"h{i}-eth0"
#         ifb_dev = f"ifb{i - 1}"   # ifb0 for h1, ifb1 for h2, …

#         print(f"Configuring {h.name}: {intf} → {ifb_dev}")

#         # Load the ifb kernel module (idempotent)
#         h.cmd("modprobe ifb numifbs={}".format(n_hosts))

#         # Bring up the IFB device
#         h.cmd(f"ip link set dev {ifb_dev} up")

#         # ── Step 1: ingress redirect on the real NIC ──────────────────────────
#         # Remove any existing ingress qdisc on eth0
#         h.cmd(f"tc qdisc del dev {intf} ingress || true")

#         # Attach a bare ingress qdisc — its only job is to hold filters
#         h.cmd(f"tc qdisc add dev {intf} ingress")

#         # Redirect ALL incoming packets to ifb device (action mirred)
#         h.cmd(
#             f"tc filter add dev {intf} parent ffff: protocol ip u32 "
#             f"match u32 0 0 "
#             f"action mirred egress redirect dev {ifb_dev}"
#         )

#         # ── Step 2: HTB + fq_codel shaping on the IFB egress ─────────────────
#         # Remove any existing root qdisc on the IFB device
#         h.cmd(f"tc qdisc del dev {ifb_dev} root || true")

#         # Root HTB qdisc on IFB
#         h.cmd(f"tc qdisc add dev {ifb_dev} root handle 1: htb default 10")

#         # Single class — shapes all redirected (= incoming) traffic
#         h.cmd(f"tc class add dev {ifb_dev} parent 1: classid 1:1 "
#               f"htb rate {ingress_rate} ceil {ceil_rate}")

#         h.cmd(f"tc class add dev {ifb_dev} parent 1:1 classid 1:10 "
#               f"htb rate {ingress_rate} ceil {ceil_rate}")

#         # fq_codel as the leaf — AQM + sub-flow fairness on shaped ingress
#         h.cmd(f"tc qdisc add dev {ifb_dev} parent 1:10 handle 10: fq_codel")


# QOS on Router

def setup_router_htb(net):
    r = net.get("Router")
    intf = "router-eth2"

    r.cmd(f"tc qdisc del dev {intf} root || true")

    # ROOT
    r.cmd(f"tc qdisc add dev {intf} root handle 1: htb default 30")

    # TOTAL
    r.cmd(f"tc class add dev {intf} parent 1: classid 1:1 htb rate 150mbit")

    # ICMP (HIGH PRIORITY)
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 "
          f"htb rate 10mbit ceil 150mbit prio 0")

    # TCP (CONTROLLED)
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 "
          f"htb rate 15mbit ceil 30mbit prio 1")

    # UDP (LOW PRIORITY)
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:30 "
          f"htb rate 5mbit ceil 20mbit prio 2")

    # fq_codel
    r.cmd(f"tc qdisc add dev {intf} parent 1:10 fq_codel")
    r.cmd(f"tc qdisc add dev {intf} parent 1:20 fq_codel")
    r.cmd(f"tc qdisc add dev {intf} parent 1:30 fq_codel")

    # FILTERS
    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 1 "
          f"u32 match ip protocol 1 0xff flowid 1:10")  # ICMP

    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 2 "
          f"u32 match ip protocol 6 0xff flowid 1:20")  # TCP

    r.cmd(f"tc filter add dev {intf} protocol ip parent 1: prio 3 "
          f"u32 match ip protocol 17 0xff flowid 1:30") # UDP

def setup_router_hfsc(net):
    r = net.get("Router")
    intf = "router-eth2"

    r.cmd(f"tc qdisc del dev {intf} root || true")

    r.cmd(f"tc qdisc add dev {intf} root handle 1: hfsc default 30")

    r.cmd(f"tc class add dev {intf} parent 1: classid 1:1 "
          f"hfsc sc rate 150mbit ul rate 150mbit")

    # ICMP (REAL-TIME)
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 "
          f"hfsc rt m1 50mbit d 5000us m2 10mbit ls rate 10mbit")

    # TCP
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 "
          f"hfsc ls rate 15mbit")

    # UDP
    r.cmd(f"tc class add dev {intf} parent 1:1 classid 1:30 "
          f"hfsc ls rate 5mbit")

    r.cmd(f"tc qdisc add dev {intf} parent 1:10 fq_codel")
    r.cmd(f"tc qdisc add dev {intf} parent 1:20 fq_codel")
    r.cmd(f"tc qdisc add dev {intf} parent 1:30 fq_codel")

    # FILTERS
    r.cmd(f"tc filter add dev {intf} parent 1: prio 1 "
          f"u32 match ip protocol 1 0xff flowid 1:10")

    r.cmd(f"tc filter add dev {intf} parent 1: prio 2 "
          f"u32 match ip protocol 6 0xff flowid 1:20")

    r.cmd(f"tc filter add dev {intf} parent 1: prio 3 "
          f"u32 match ip protocol 17 0xff flowid 1:30")

def setup_router_cake(net):
    r = net.get("Router")
    intf = "router-eth2"

    r.cmd(f"tc qdisc del dev {intf} root || true")

    r.cmd(
        f"tc qdisc add dev {intf} root cake "
        f"bandwidth 150mbit "
        f"diffserv4 "
        f"nat "
        f"dual-srchost "
        f"ack-filter"
    )

# QoS on Hosts

def setup_hosts_htb(net, n_hosts):
    print("Applying HTB QoS on hosts...")

    for i in range(1, n_hosts + 1):
        h = net.get(f"h{i}")
        intf = f"h{i}-eth0"

        h.cmd(f"tc qdisc del dev {intf} root || true")

        # ROOT
        h.cmd(f"tc qdisc add dev {intf} root handle 1: htb default 30")

        # TOTAL (per host!)
        h.cmd(f"tc class add dev {intf} parent 1: classid 1:1 htb rate 20mbit")

        # ICMP
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 "
              f"htb rate 5mbit ceil 20mbit prio 0")

        # TCP
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 "
              f"htb rate 15mbit ceil 20mbit prio 1")

        # UDP
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:30 "
              f"htb rate 2mbit ceil 10mbit prio 2")

        # fq_codel
        h.cmd(f"tc qdisc add dev {intf} parent 1:10 fq_codel")
        h.cmd(f"tc qdisc add dev {intf} parent 1:20 fq_codel")
        h.cmd(f"tc qdisc add dev {intf} parent 1:30 fq_codel")

        # FILTERS
        h.cmd(f"tc filter add dev {intf} parent 1: prio 1 "
              f"u32 match ip protocol 1 0xff flowid 1:10")

        h.cmd(f"tc filter add dev {intf} parent 1: prio 2 "
              f"u32 match ip protocol 6 0xff flowid 1:20")

        h.cmd(f"tc filter add dev {intf} parent 1: prio 3 "
              f"u32 match ip protocol 17 0xff flowid 1:30")

def setup_hosts_hfsc(net, n_hosts):
    print("Applying HFSC QoS on hosts...")

    for i in range(1, n_hosts + 1):
        h = net.get(f"h{i}")
        intf = f"h{i}-eth0"

        h.cmd(f"tc qdisc del dev {intf} root || true")

        h.cmd(f"tc qdisc add dev {intf} root handle 1: hfsc default 30")

        h.cmd(f"tc class add dev {intf} parent 1: classid 1:1 "
              f"hfsc sc rate 20mbit ul rate 20mbit")

        # ICMP (REAL-TIME)
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:10 "
              f"hfsc rt m1 20mbit d 5000us m2 5mbit ls rate 5mbit")

        # TCP
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:20 "
              f"hfsc ls rate 15mbit")

        # UDP
        h.cmd(f"tc class add dev {intf} parent 1:1 classid 1:30 "
              f"hfsc ls rate 2mbit")

        h.cmd(f"tc qdisc add dev {intf} parent 1:10 fq_codel")
        h.cmd(f"tc qdisc add dev {intf} parent 1:20 fq_codel")
        h.cmd(f"tc qdisc add dev {intf} parent 1:30 fq_codel")

        # FILTERS
        h.cmd(f"tc filter add dev {intf} parent 1: prio 1 "
              f"u32 match ip protocol 1 0xff flowid 1:10")

        h.cmd(f"tc filter add dev {intf} parent 1: prio 2 "
              f"u32 match ip protocol 6 0xff flowid 1:20")

        h.cmd(f"tc filter add dev {intf} parent 1: prio 3 "
              f"u32 match ip protocol 17 0xff flowid 1:30")

def setup_hosts_cake(net, n_hosts):
    print("Applying CAKE QoS on hosts...")

    for i in range(1, n_hosts + 1):
        h = net.get(f"h{i}")
        intf = f"h{i}-eth0"

        h.cmd(f"tc qdisc del dev {intf} root || true")

        h.cmd(
            f"tc qdisc add dev {intf} root cake "
            f"bandwidth 20mbit "
            f"diffserv4 "
            f"nat "
            f"dual-srchost"
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

    # ── Router-side QoS (original) ────────────────────────────────────────────
    #setup_per_host_qos(net, n_hosts)

    # ── Host-side QoS — pick ONE of the four below ───────────────────────────

    # Mechanism 0 (original): flat TBF rate limit on every host's egress
    #setup_host_rate_limit(net, n_hosts)

    # Mechanism 1: HTB + fq_codel — two-class egress (ICMP vs bulk) per host
    # setup_host_htb_fq_codel(net, n_hosts, total_rate="20mbit",
    #                         icmp_rate="6mbit", bulk_rate="14mbit",
    #                         ceil_rate="20mbit")
    # makes loses about 25%
    # Mechanism 2: HFSC — latency + bandwidth guarantees per host
    # setup_host_hfsc(net, n_hosts, total_rate="20mbit",
    #                icmp_rate="6mbit", bulk_rate="14mbit",
    #                icmp_rt_burst="20mbit", icmp_rt_delay_us=5000)
    # makes loses about 27%
    #Mechanism 3: IFB ingress shaping — genuine ingress rate limit per host
    # setup_host_ifb_ingress(net, n_hosts, ingress_rate="20mbit",
    #                        ceil_rate="20mbit")
    # makes loses about 31%


    # QoS Selection

    if args.placement == "router":
        if args.type == 1:
            setup_router_htb(net)
        elif args.type == 2:
            setup_router_hfsc(net)
        elif args.type == 3:
            setup_router_cake(net)
    elif args.placement == "hosts":
        if args.type == 1:
            setup_hosts_htb(net)
        elif args.type == 2:
            setup_hosts_hfsc(net)
        elif args.type == 3:
            setup_hosts_cake(net)
    else:
        pass


    net.pingAll()

    time.sleep(5)

    run_traffic(net, mode=mode)

    txt_results_to_csv(results_folder, mode)

    # CLI(net)
    time.sleep(5)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
