### Run the setup

Before the setup is run, the data directories need to be created:

```
sudo ./create_data_directories.sh
```

Afterwards start with:
```
docker compose up -d
```

Then, Grafana should be available at `http://yourpi:3000`.

Default Username and Password is `admin` and `foobar`

To stop the monitoring use:
```
docker compose down
```

