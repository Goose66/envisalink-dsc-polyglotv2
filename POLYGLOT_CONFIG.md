## EnvisaLink DSC Nodeserver Configuration
##### Advanced Configuration:
- key: shortPoll, value: polling interval for connection status of Envisalink and zone timers (defaults to 30 seconds)
NOTE: The alarm panel reports status changes immediately and has a 4 minute keep alive broadcast, so frequent polling for state is not required.
- key: longPoll, value: interval for watchdog timer resets if watchdog timer is disabled (see below, defaults to 600 seconds)
NOTE: Needs to be less than 20 minutes to prevent EnvisaLink from rebooting if firewalled.

##### Custom Configuration Parameters:
Required:
- key: ipaddress, value: locally accessible IP address of EnvisaLink EVL-3/4 (e.g., "192.168.1.145")
- key: password, value: password for EnvisaLink device
- key: usercode, value: user code for disarming alarm panel

Optional:
- key: numpartitions, value: number of partition nodes to generate (defaults to 1)
- key: numzones, value: number of zone nodes to generate (defaults to 8)
- key: numcmdouts, value: number of command output nodes to generate (defaults to 4)
- key: disablewatchdog, value: 0 or 1 for whether EyezOn cloud service watchdog timer should be disabled (defaults to 0 - not disabled)
