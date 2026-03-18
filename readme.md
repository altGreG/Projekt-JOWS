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
sudo python3 topo.py
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