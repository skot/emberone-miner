# Hardware

PiAxe-Miner is the software needed to run the PiAxe and QAxe.

The repository with design files, BOM, ... can be found [here](https://github.com/shufps/piaxe)!


# Stratum Client Software

Fork of: https://github.com/crypto-jeronimo/pyminer <br>
Changes: 

- Removed Scrypt hashing and added Miner class
- Made it work with Python3
- added [PiAxe](https://github.com/shufps/piaxe) and [QAxe](https://github.com/shufps/qaxe) as miner
- added reconnect logic on broken connections

Influx and Grafana
==================

The repository contains a dockered setup running on the Pi that shows some statistics:



<img src="https://github.com/shufps/piaxe-miner/assets/3079832/8d34ec13-15bd-4dd4-abd3-9588c823c494" width="600px"/>

The "blocks found" counter is static of course ... 

PyMiner
=======

Currently supported algorithms:
- `sha256d`: SHA256d


Usage
-----
```
    python pyminer.py [-h] [-o URL] [-u USERNAME] [-p PASSWORD]
                         [-O USERNAME:PASSWORD] [-a ALGO] [-B] [-q]
                         [-P] [-d] [-v]

    -o URL, --url=              stratum mining server url
    -u USERNAME, --user=        username for mining server
    -p PASSWORD, --pass=        password for mining server
    -O USER:PASS, --userpass=   username:password pair for mining server

    -B, --background            run in the background as a daemon

    -q, --quiet                 suppress non-errors
    -P, --dump-protocol         show all JSON-RPC chatter
    -d, --debug                 show extra debug information

    -h, --help                  show the help message and exit
    -v, --version               show program's version number and exit


    Example:
        python pyminer.py -o stratum+tcp://foobar.com:3333 -u user -p passwd
```

---

# Setup Instructions

## Requirements
- Raspberry Pi 3 (Pi Zero doesn't run influx)
- Python 3.x PIP

## Installation

```
# install pip3
sudo apt install python3-pip

# clone repository
git clone https://github.com/shufps/piaxe-miner
cd piaxe-miner

# and install requirements
pip3 install -r requirements.txt --break-system-packages

# copy example files
cp config.yml.example config.yml
cp start_mainnet_publicpool_example.sh start.sh
```
In the new `start.sh` insert your `bc1...` address.

After copying the example files, edit them. The `config.yml` probably doesn't need changes if connecting a QAxe+.

### PiAxe
Depending on your Device change between
`piaxe` and `qaxe` in the `miner` setting.

Make sure to change to the correct USB Serial `PiAxe`:
```
  serial_port: "/dev/ttyS0"
``` 

### If running on Pi Zero (1 or 2)
Disable the influx or point it to your externally managed influxdb, with the most recent changes the pi zero can no longer run grafana.


## Start the miner

Change `start_mainnet_publicpool_example.sh` to your needs.


### For more detailed logging
Activate debug_bm1366 to get a more detailed output in shell.
