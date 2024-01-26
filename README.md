# Hardware

PiAxe-Miner is the software needed to run the PiAxe and QAxe.

The repository with design files, BOM, ... can be found [here](https://github.com/shufps/piaxe)!


# Stratum Client Software

Fork of: https://github.com/crypto-jeronimo/pyminer <br>
Changes: 

- Removed Scrypt hashing and added Miner class
- Made it work with Python3
- added [PiAxe](https://github.com/shufps/piaxe) as miner
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



Misc:
```
$ curl --user bitcoin --data-binary '{"jsonrpc": "1.0", "id": "curltest", "method": "createwallet", "params": ["piaxe-wallet"]}' -H 'content-type: text/plain;' http://127.0.0.1:18332/
$ curl --user bitcoin --data-binary '{"jsonrpc": "1.0", "id": "curltest", "method": "getnewaddress", "params": []}' -H 'content-type: text/plain;' http://127.0.0.1:18332/
```

---

# Setup Instructions

## Requirements
- Raspberry Pi 3 (Pi Zero doesn't run influx)
- Python 3.x PIP
- PIP dependencies 
`bech32==1.2.0
influxdb_client==1.38.0
pyserial==3.5b0
pytz==2021.1
PyYAML==6.0.1
Requests==2.31.0
rpi_hardware_pwm==0.1.4
smbus==1.1.post2
protobuf`

Extra info: if your miner failes to start you might need to downgrade protobuf. But the logs shall provide detailed information about that.

## Installation
configure the `config.yml` file to your needs
change values like the miner type and debug value

Depending on your Device change between
`piaxe` and `qaxe` in the `miner` setting.

Make sure to change to the correct USB Serial `PiAxe`:
```
  serial_port: "/dev/ttyS0"
``` 
</br>

Make sure to change to the correct USB Serial `QAxe`:
```
  serial_port_asic: "/dev/ttyACM0"
  serial_port_ctrl: "/dev/ttyACM1"
```
### If running on Pi Zero (1 or 2)
Disable the influx or point it to your externally managed influxdb, with the most recent changes the pi zero can no longer run grafana.


## Start the miner

Change `start_mainnet_publicpool_example.sh` to your needs.


### For more detailed logging
Activate debug_bm1366 to get a more detailed output in shell.