# Getting Started with Mininet VM

## 1. Download the Virtual Machine

Download the preconfigured Mininet virtual machine from the following
link:\
https://drive.google.com/file/d/1qmQGnk1J11RhiNZUg0BECKoWKEUtc5I3/view?usp=sharing

This VM is based on the setup described in:\
https://medium.com/@jmwanderer/fun-with-routing-protocols-8a0677aab2fc

------------------------------------------------------------------------

## 2. Import the VM into VirtualBox

After downloading: - Open VirtualBox - Import the VM file (typically
`.ova`) - Start the virtual machine

------------------------------------------------------------------------

## 3. Login Credentials

Use the following credentials to log in:

-   **Username:** `ubuntu`
-   **Password:** `ubuntu`

------------------------------------------------------------------------

## 4. (Optional) Configure SSH Port Forwarding

For easier access, it is recommended to configure SSH port forwarding.

You can follow this guide:\
https://nsrc.org/workshops/2014/sanog23-virtualization/raw-attachment/wiki/Agenda/ex-virtualbox-portforward-ssh.htm

------------------------------------------------------------------------

## 5. Connect via SSH

Once port forwarding is configured (e.g., host port `2222` → guest port
`22`), you can connect using:

``` bash
ssh -Y -l ubuntu -p 2222 127.0.0.1
```

------------------------------------------------------------------------

## 6. Prepare Your Topology Script

After logging into the VM:

1.  Navigate to your working directory (e.g., home directory)

2.  Create a new file:

    ``` bash
    nano topo.py
    ```

3.  Paste the contents of your `topo.py` file from the GitHub repository

4.  Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`)

------------------------------------------------------------------------

## 7. Clean Previous Mininet State

Before running your topology, clean up any leftovers from previous runs:

``` bash
sudo mn -c
```

------------------------------------------------------------------------

## 8. Run the Mininet Topology

Start your topology with:

``` bash
sudo -E python3 topo.py
```

After initialization, you will enter the Mininet CLI.

------------------------------------------------------------------------

## 9. Basic Commands in Mininet

Once inside the CLI, you can:

-   Test connectivity:

    ``` bash
    pingall
    ```

-   View available commands:

    ``` bash
    help
    ```

------------------------------------------------------------------------

## 10. Open Terminal Windows for Individual Nodes

Mininet allows you to open separate terminal windows for specific nodes
(hosts or switches), which is useful for running commands interactively.

To open terminals for specific nodes (example for h1 and h2):

``` bash
xterm h1 h2
```

Each node will open in a separate terminal window, allowing you to
execute commands independently.

------------------------------------------------------------------------

## 11. Test Network Performance with iperf

You can use `iperf` to measure bandwidth between hosts in your Mininet
topology.

### Step 1: Start iperf server on one host

``` bash
xterm h1
#in xterm window for h1
iperf -s
```

### Step 2: Run iperf client on another host

``` bash
xterm h2
#in xterm window for h2
iperf -c 10.2.0.1 # ip oh host h1
```

This will generate a bandwidth report between `h2` (client) and `h1`
(server).

### Optional: UDP test

``` bash
xterm h1
iperf -s -u
```

``` bash
xterm h2
iperf -u -c 10.2.0.1
```

### Optional: Limit bandwidth

``` bash
xterm h1
iperf -s
```

``` bash
xterm h2
iperf -c 10.2.0.1 -b 10M
```

These tests help evaluate throughput and network performance within our
simulated topology.