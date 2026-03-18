# Good Start

1. Download VM with preinstalled mininet from: https://drive.google.com/file/d/1qmQGnk1J11RhiNZUg0BECKoWKEUtc5I3/view?usp=sharing. Our machine comes from this article: https://medium.com/@jmwanderer/fun-with-routing-protocols-8a0677aab2fc.

2. In order to use machine download it and import in VirtualBox software.

3. Credentials for VM are:

    User: ubuntu

    Password: ubuntu

4. For ease of use worth configuration is ssh port forwarding. Details are presented in this article: https://nsrc.org/workshops/2014/sanog23-virtualization/raw-attachment/wiki/Agenda/ex-virtualbox-portforward-ssh.htm

5. To log in into VM via ssh on Linux you can use for example this command: `ssh -Y -l ubuntu -p 2222 127.0.0.1`, 2222 is port number we used while setting up ssh port forwarding.

6. Next in order to start work with mininet, after you log in into VM in your home directory or any other directory you will create for project files, issue command ` nano topo.py` and paste in content of topo.py file from github repo. Save changes and close nano editor.

7. Before starting mininet script with our topology worth using is command `sudo mn -c`, this command will erase all leftover files created on previous run of mininet emulator.

8. In order to run script issue: `sudo python3 topo.py`. After a while topology will be created and you will be left on Mininet CLI, from this point you will be able for example chceck connectivity of devices in our topology by issuing `pingall` command or look for more options by issuing `help` command.