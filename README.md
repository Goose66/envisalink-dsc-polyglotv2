# envisalink-dsc-polyglotv2
A Nodeserver for Polyglot v2 that interfaces with a DSC PowerSeries alarm panel through an EnvisaLink EVL-3/4 adapater. See http://www.eyezon.com/?page_id=176 for more information on the EnvisaLink EVL-4.

Instructions for manual, co-resident installation:

1. Copy the files from this repository to the folder ~/.polyglot/nodeservers/EnvisaLink-DSC in your Polyglot v2 installation.
2. Log into the Polyglot Version 2 Dashboard (https://(Polyglot IP address):3000)
3. Add the EnvisaLink-DSC nodeserver as a Local nodeserver type.
4. Add the following required Custom Configuration Parameters under Configuration:
```
    key: ipaddress, value: locally accessible IP address of EnvisaLink EVL-3/4 (e.g., "192.168.1.145")
    key: password, value: password for EnvisaLink device
    key: usercode, value: user code for disarming alarm panel
```
5. Add the following optional Custom Configuration Parameters:
```
    key: numpartitions, value: number of partition nodes to generate (defaults to 1)
    key: numzones, value: number of zone nodes to generate (defaults to 8)
    key: numcmdouts, value: number of command output nodes to generate (defaults to 4)
    key: disablewatchdog, value: 0 or 1 for whether EyezOn cloud service watchdog timer should be disabled (defaults to 0 - not disabled)
    key: zonetimerdumpflag, value: numeric flag indicating whether dumping of the zone timers should be done on shortpoll (1), longpoll (2), or disabled altogether (0) (defaults to 1 - shortpoll)
```
The nodes of the EnvisaLink Nodeserver generate the following commands in the ISY, allowing the nodes to be added as controllers to scenes:

ZONE
- Sends a *DON* command when the zone is opened
- Sends a *DOF* command when the zone is closed

PARTITION
- Sends a *DON* command when the partition is alarming
- Sends a *DOF* command when the partition is disarmed

COMMAND_OUTPUT
- Sends a *DON* command when the command output is activated

CONTROLLER
- Sends a *DON* command when a smoke/panic alarm is activated
- Sends a *DOF* command when an active smoke/panic alarm is cleared
- Sends a *AWAKE* command periodically for heartbeat monitoring

Here are some things to know about this version:

1. The command output nodes are currently limited to partition 1 only. These Command Output nodes send *DON* commands, but not *DOF* commands.
2. Initially, there are several state values that are unknown when the nodeserver starts and will default to 0 (or last known value if restarted). This includes trouble states, door chime, and the like. These state values may not be correct until the status is changed while the nodeserver is running.
3. The connection to the EnvisaLink and alarm panel is not made until the first short poll (e.g., 30 seconds after start). The various state values (zone states, zone bypass, zone timers, etc.) are updated over subsequent short polls. Therefore, depending on the "shortPoll" configuration setting and the number of partitions, it may take a few minutes after starting the nodeserver for all the states to be updated.
4. If the connection to the EnvisaLink is lost, or if the nodeserver doesn't hear from the EnvisaLink for 10 minutes (including the expected four-minute keepalive), then the connection is reset and the nodeserver will attempt reconnect on the next short poll and every subsequent short poll until connection is reestablished or the nodeserver is shutdown.
5. The nodeserver sends an AWAKE command (heartbeat) to the controller node every four minutes (when the keepalive is received from the alarm panel). You can check for this in a program on the ISY to monitor the connection. There is also an "Alarm Panel Connected" driver value that reflects whether the connection to the EnvisaLink/alarm panel is active, but this may not get updated if the nodeserver fails.
6. If your EnvisaLink is firewalled and can not connect to the EyezOn web service, then the EnvisaLink will reboot every 20 minutes ("Watchdog Timer") in order to try and reestablish the connection to the web service. This will kill the connection to the nodeserver as well and it will (attempt to) reconnect on the next short poll. If you set the "diablewatchdog" configuration setting to 1, the nodeserver will send a periodic poll to the EnvisaLink to reset the Watchdog Timer so that the EnvisaLink won't reboot. The poll is sent every long poll if the "diablewatchdog" configuration parameter is set, so the "longpoll" configuration setting needs to be less than 1200 seconds (20 minutes).
7. During the intial connecting and status reporting on startup, the nodeserver sends keystrokes to the keypad to dump bypass zones to set the initial zone bypass attributes. This may cause the status lights on the keypads to blink briefly and a Security Event alert (text and/or email) to be generated by EyezON.
8. The zone timers ("Time Closed") represent the time since the last closing of the zone, in seconds, and are calculated in 5 second intervals. The timers have a maximum value of 327675 seconds (91 hours) and won't count up beyond that. The timing of the zone timer updates is based on the configured zonetimerdumpflag parameter (defaults to every short poll).  
9. The reporting of trouble states through EnvsiaLink's TPI doesn't seem to align exactly with the description of the various trouble states in the documentation for the DSC panels. In addition, depending on how your panel is programmed, the panel may not send trouble reporting commands for certain conditions (e.g., AC power out). The nodeserver updates the trouble driver values for the controller (Alarm Panel) node from both specific trouble reporting commands from the EnvsiaLink and the state of keypad LEDs for partition 1.

