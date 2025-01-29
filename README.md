# myVaillant2MQTT Docker image

This is an addon to the [myPyllant-docker image|https://github.com/signalkraft/myPyllant]. It requests the registered systems an pushes the responded json to the configured mqtt topic every 5 minutes.

I tried to make this reusable. If something is missing to get it running on your machine, let me know.

## Build
```bash
docker build -t engelb/myvaillant2mqtt:<version> .
```

## Push
```bash
docker push engelb/myvaillant2mqtt:<version>
```

## Run
```bash
docker run -d \
--name='myvaillant2mqtt' \
--network=host \
-e MQTT_ID=<mqtt username> \
-e MQTT_PASS=<mqtt password> \
-e MQTT_HOST=<mqtt host> \
-e MQTT_PORT=<optional mqtt port, default: 1883> \
-e MQTT_TOPIC=<topic where to publish, default: test/vaillant> \
-e MQTT_USE_SSL=<True, if connection should be validated (read below), default: False> \
-e MQTT_TRUSTED_FINGERPRINT=<certificate\'s fingerprint to trust to (read below)> \
-e MYVAILLANT_USER=<username/email> \
-e MYVAILLANT_PASS=<password> \
-e MYVAILLANT_BRAND=<brand, default: vaillant> \ 
-e MYVAILLANT_COUNTRY=<country, default: germany> \ 
engelb/myvaillant2mqtt:latest
```

Hashes in variable values ​​should be avoided!

or by env-file:
```bash
docker run -d --env-file envfile.env engelb/myvaillant2mqtt:latest
```

## Validate TLS connection

In myVaillant2mqtt a light check of a ssl-connection is implemented by verifing the broker's certificate hash. To do so, set `MQTT_USE_SSL=True`. Start the container again and have a lock into the log. There should be a message like 
`No fingerprint set. The current certificate has following fingerprint: f50cdfdb6122d16b...` 
Copy the hash and add the attribute `MQTT_TRUSTED_FINGERPRINT=f50cdfdb6122d16b...` to your commandline.
