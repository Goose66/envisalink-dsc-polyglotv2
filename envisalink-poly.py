#!/usr/bin/python3
# Polyglot Node Server for EnvisaLink EVL 3/4 Device (DSC)

import sys
import time

import envisalinktpi as EVL
import polyinterface

_ISY_BOOL_UOM = 2 # Used for reporting status values for Controller node
_ISY_INDEX_UOM = 25 # Index UOM for custom states (must match editor/NLS in profile):
_ISY_MINUTES_UOM = 45 # Used for reporting duration in minutes

_LOGGER = polyinterface.LOGGER

_PART_ADDR_FORMAT_STRING = "partition%1d"
_ZONE_ADDR_FORMAT_STRING = "zone%02d"

# Node class for partitions
class Partition(polyinterface.Node):

    id = "PARTITION"

    # Override init to handle partition number
    def __init__(self, controller, primary, partNum):
        super(Partition, self).__init__(controller, primary, _PART_ADDR_FORMAT_STRING % partNum, "Partition %1d" % partNum)
        self.partitionNum = partNum       

    # Update the driver values based on the command received from the EnvisaLink for the partition
    def update_state_values(self, cmd, data):

        # update the ST value
        if cmd == EVL.CMD_PARTITION_READY:
            self.setDriver("ST", 0) # Ready

        elif cmd == EVL.CMD_PARTITION_NOT_READY:
            self.setDriver("ST", 1) # Not Ready

        elif cmd == EVL.CMD_PARTITION_ARMED:

            # get the arming mode from the data
            armingMode = data.decode("ascii")[-1:]
            if armingMode == "0":
                self.setDriver("ST", 2) # Armed Away
            elif armingMode == "1":
                self.setDriver("ST", 3) # Armed Stay
            elif armingMode == "2":
                self.setDriver("ST", 4) # Armed Away Zero-Entry
            elif armingMode == "3":
                self.setDriver("ST", 5) # Armed Stay Zero-Entry
              
        elif cmd == EVL.CMD_PARTITION_IN_ALARM:
            self.setDriver("ST", 6) # Alarming

        elif cmd == EVL.CMD_PARTITION_DISARMED:
            self.setDriver("ST", 0) # Ready

        elif cmd == EVL.CMD_EXIT_DELAY_IN_PROGRESS:
            self.setDriver("ST", 7) # Exit Delay

        elif cmd == EVL.CMD_ENTRY_DELAY_IN_PROGRESS:
            self.setDriver("ST", 8) # Entry Delay

        # update the GV0 (chime enabled) value
        elif cmd == EVL.CMD_CHIME_ENABLED:
            self.setDriver("GV0", 1)

        elif cmd == EVL.CMD_CHIME_DISABLED:
            self.setDriver("GV0", 0)

    # Arm the partition in Away mode (the listener thread will update the corresponding driver values)
    def arm_away(self, command):
        
        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Arm the partition in Stay mode (the listener thread will update the corresponding driver values)
    def arm_stay(self, command):
        
        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION_STAY, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Arm the partition in Zero Entry mode (the listener thread will update the corresponding driver values)
    def arm_zero_entry(self, command):
        
        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION_NO_ENTRY_DELAY, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Disarm the partition (the listener thread will update the corresponding driver values)
    def disarm(self, command):
        
        # send disarm command and user code to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_DISARM_PARTITION, "%1d%s" % (self.partitionNum, self.controller.userCode)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to disarm partition failed for node %s.", self.address)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_BOOL_UOM}
    ]
    commands = {
        "DISARM": disarm,
        "ARM_AWAY": arm_away,
        "ARM_STAY": arm_stay,
        "ARM_ZEROENTRY": arm_zero_entry
    }

# Node class for zones
class Zone(polyinterface.Node):

    id = "ZONE"

    # Override init to handle partition number
    def __init__(self, controller, primary, zoneNum):
        super(Zone, self).__init__(controller, primary, _ZONE_ADDR_FORMAT_STRING % zoneNum, "Zone %02d" % zoneNum)
        self.zoneNum = zoneNum       

    # Update ST driver value based on the command received from the EnvisaLink for the zone
    def update_state_values(self, cmd, data):

        # update the ST value
        if cmd == EVL.CMD_ZONE_RESTORED:

            # send the DOF command for the node - allows node to be scene controller
            self.reportCmd("DOF")

            self.setDriver("ST", 0) # Closed

        elif cmd == EVL.CMD_ZONE_OPEN:

            # send the DON command for the node - allows node to be scene controller
            self.reportCmd("DON")

            self.setDriver("ST", 1) # Open

        elif cmd == EVL.CMD_ZONE_ALARM:
            self.setDriver("ST", 2) # Alarming

        elif cmd == EVL.CMD_ZONE_ALARM_RESTORED:
            self.setDriver("ST", 0) # Closed

    # Set the bypasse driver value
    def set_bypass(self, bypass):
        self.setDriver("GV0", bypass)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_BOOL_UOM}
    ]
    commands = {}

# Node class for controller
class AlarmPanel(polyinterface.Controller):

    id = "CONTROLLER"

    def __init__(self, poly):
        super(AlarmPanel, self).__init__(poly)
        self.name = "Alarm Panel"
        self.envisalink = None
        self.userCode = ""
        self.pollingInterval = 60

    # Update the driver values based on the command received from the EnvisaLink for the partition
    def update_state_values(self, cmd, data):

        # update the GV0 (Smoke Alarm) value
        if cmd == EVL.CMD_2_WIRE_SMOKE_ALARM:
            self.setDriver("GV0", 1) # Alarming
        elif cmd == EVL.CMD_2_WIRE_SMOKE_RESTORED:
            self.setDriver("GVO", 0) # Not Alarming

        # update the GV1 (Fire Panic Alarm) value
        if cmd == EVL.CMD_FIRE_KEY_ALARM:
            self.setDriver("GV1", 1) # Alarming
        elif cmd == EVL.CMD_FIRE_KEY_RESTORED:
            self.setDriver("GV1", 0) # Not Alarming

        # update the GV2 (Aux Panic Alarm) value
        if cmd == EVL.CMD_AUX_KEY_ALARM:
            self.setDriver("GV2", 1) # Alarming
        elif cmd == EVL.CMD_AUX_KEY_RESTORED:
            self.setDriver("GV2", 0) # Not Alarming

        # update the GV3 (Police Panic Alarm) value
        if cmd == EVL.CMD_PANIC_KEY_ALARM:
            self.setDriver("GV3", 1) # Alarming
        elif cmd == EVL.CMD_PANIC_KEY_RESTORED:
            self.setDriver("GV3", 0) # Not Alarming

        # update the GV4 (Bell Trouble) value
        if cmd == EVL.CMD_BELL_TROUBLE:
            self.setDriver("GV4", True) 
        elif cmd == EVL.CMD_BELL_TROUBLE_RESORED:
            self.setDriver("GV4", False) 

        # update the GV5 (Battery Trouble) value
        if cmd == EVL.CMD_BATTERY_TROUBLE:
            self.setDriver("GV5", True) 
        elif cmd == EVL.CMD_BATTERY_TROUBLE_RESTORED:
            self.setDriver("GV5", False) 

        # update the GV6 (AC Trouble) value
        if cmd == EVL.CMD_AC_TROUBLE:
            self.setDriver("GV6", True)
        elif cmd == EVL.CMD_AC_TROUBLE_RESTORED:
            self.setDriver("GV6", False)

        # update the GV7 (FTC Trouble) value
        if cmd == EVL.CMD_FTC_TROUBLE:
            self.setDriver("GV7", True)
        elif cmd == EVL.CMD_FTC_TROUBLE_RESTORED:
            self.setDriver("GV7", False)

        # update the GV8 (Tamper Trouble) value
        if cmd == EVL.CMD_SYSTEM_TAMPER:
            self.setDriver("GV8", True)
        elif cmd == EVL.CMD_SYSTEM_TAMPER_RESTORED:
            self.setDriver("GV8", False)

    # Trigger the panic fire alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_fire(self, command):
        
        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "1"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)

    # Trigger the panic aux alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_aux(self, command):
        
        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "2"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)

    # Trigger the panic fire alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_police(self, command):
        
        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "3"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)
      
    # Override query
    def query(self):
        
        # since status commands are returned asynchronously after polling, there's no point
        # in polling for status here, just return driver values for all nodes
        for addr in self.nodes:
            self.nodes[addr].reportDrivers()

    # Start the nodeserver
    def start(self):

        _LOGGER.info("Starting envisalink Nodeserver...")

        # get controller information from custom parameters
        try:
            customParams = self.poly.config["customParams"]
            ip = customParams["ipaddress"]
            password = customParams["password"]
            self.userCode = customParams["usercode"]
            numPartitions = int(customParams["numpartitions"])
            numZones = int(customParams["numzones"])
        except KeyError:
            _LOGGER.error("Missing controller settings in configuration.")
            raise

        # get polling intervals and configuration settings from custom parameters
        try:
            self.pollingInterval = int(customParams["pollinginterval"])
        except (KeyError, ValueError):
            self.pollingInterval = 60

        # dump the self._nodes to the log
        #_LOGGER.debug("Current Node Configuration: %s", str(self._nodes))

        # Setup the interface to the EnvisaLink device (starts the listener thread)
        self.envisalink = EVL.EnvisaLinkInterface(ip, password, self.process_command, _LOGGER)

        #  setup the nodes based on the counts of zones and partition in the configuration parameters
        self.build_nodes(numPartitions, numZones)

        # perform an initial polling
        self.initial_poll()
        self.lastPoll = time.time()     
    
    # Called when the nodeserver is stopped
    def stop(self):
        
        # shudtown the connection to the EnvisaLink device
        self.envisalink.shutdown()
        
    # called every long_poll seconds
    def longPoll(self):

        pass
    
    # called every short_poll seconds
    def shortPoll(self):

        pass
        
        # if node server is not setup yet, return
        #if self.envisalink is None:
            #return

        #currentTime = time.time()

        # check for elapsed polling interval
        #if (currentTime - self.lastPoll) >= self.pollingInterval:

            # poll the device to generate state commands
            #self.poll_device()
            #self.lastPoll = currentTime

    # Create nodes for zones and partitions as specified by the parameters
    def build_nodes(self, numPartitions, numZones):

        # create partition nodes for the number of partitions specified
        for i in range(0, numPartitions):
            
            # create a partition node and add it to the node list
            self.addNode(Partition(self, self.address, i+1))

        # create zone nodes for the number of partitions specified
        for i in range(0, numZones):
            
            # create a partition node and add it to the node list
            self.addNode(Zone(self, self.address, i+1))
                       
    # Intially poll the EnvisaLink for status
    def initial_poll(self):

        # send the status polling command to the EnvisaLink device
        # Only generates general zone status and trouble LED updates
        self.envisalink.send_command(EVL.CMD_STATUS_REPORT)

        # wait for one second
        time.sleep(1)

        # dump the bypass zones by entering and leaving the bypass function on the keypad for
        # partition 1
        self.envisalink.send_command(EVL.CMD_SEND_KEYSTROKES, "1*1#")

    # Callback function for listener thread
    def process_command(self, cmd, data):

        retVal = False

        # Pass partition status commands to correct partition node
        if cmd in (
            EVL.CMD_PARTITION_READY,
            EVL.CMD_PARTITION_NOT_READY,
            EVL.CMD_PARTITION_ARMED,
            EVL.CMD_PARTITION_IN_ALARM,
            EVL.CMD_PARTITION_DISARMED,
            EVL.CMD_EXIT_DELAY_IN_PROGRESS,
            EVL.CMD_ENTRY_DELAY_IN_PROGRESS,
            EVL.CMD_CHIME_ENABLED,
            EVL.CMD_CHIME_DISABLED
        ):

            # get the partition number from the data
            partNum = int(data.decode("ascii")[:1])

            # check if node for partition
            for addr in self.nodes:
                if addr == _PART_ADDR_FORMAT_STRING % partNum:

                    # update the driver values of the node from the commands
                    self.nodes[addr].update_state_values(cmd, data)
                    retVal = True
                    break

        # Pass zone status commands to correct zone node
        elif cmd in (EVL.CMD_ZONE_RESTORED, EVL.CMD_ZONE_OPEN, EVL.CMD_ZONE_ALARM, EVL.CMD_ZONE_ALARM_RESTORED):

            # get the zone number from the data
            zoneNum = int(data.decode("ascii")[-3:])

            # check if node for zone
            for addr in self.nodes:
                if addr == _ZONE_ADDR_FORMAT_STRING % zoneNum:
                    
                    # update the driver values of the node from the commands
                    self.nodes[addr].update_state_values(cmd, data)
                    retVal = True
                    break

        # handle panel status commands in the controller node
        elif cmd in (
            EVL.CMD_2_WIRE_SMOKE_ALARM,
            EVL.CMD_2_WIRE_SMOKE_RESTORED,
            EVL.CMD_FIRE_KEY_ALARM,
            EVL.CMD_FIRE_KEY_RESTORED,
            EVL.CMD_AUX_KEY_ALARM,
            EVL.CMD_AUX_KEY_RESTORED,
            EVL.CMD_PANIC_KEY_ALARM,
            EVL.CMD_PANIC_KEY_RESTORED,
            EVL.CMD_BELL_TROUBLE,
            EVL.CMD_BELL_TROUBLE_RESORED,
            EVL.CMD_BATTERY_TROUBLE,
            EVL.CMD_BATTERY_TROUBLE_RESTORED,
            EVL.CMD_AC_TROUBLE,
            EVL.CMD_AC_TROUBLE_RESTORED,
            EVL.CMD_FTC_TROUBLE,
            EVL.CMD_FTC_TROUBLE_RESTORED,
            EVL.CMD_SYSTEM_TAMPER,
            EVL.CMD_SYSTEM_TAMPER_RESTORED
        ):
            self.update_state_values(cmd, data)

            retVal = True

        # handle zone bypass dump
        elif cmd == EVL.CMD_BYPASSED_ZONES_DUMP:
            
            # resequence the hex string in the data to be a big-endian representation
            # of the 64-bit bitfield
            leHexString = data.decode("ascii")
            beHexString = (leHexString[14:]
                           + leHexString[12:14]
                           + leHexString[10:12]
                           + leHexString[8:10]
                           + leHexString[6:8]
                           + leHexString[4:6]
                           + leHexString[2:4]
                           + leHexString[:2])
            
            # convert the hex string to a 64-bit bitfield representing the
            # bypass status of each of the 64 zones
            bypassFlags = bin(int(beHexString, base=16))[2:].zfill(64)    
            
            # iterate through the zone nodes and set the bypass flag from the bitfield
            for addr in self.nodes:
                node = self.nodes[addr]
                if node.id == "ZONE":
                    node.set_bypass(int(bypassFlags[-node.zoneNum]))
            
            retVal = True

        # handle user code request
        elif cmd in (EVL.CMD_CODE_REQD, EVL.CMD_COMMAND_OUTPUT_PRESSED):

            # send the user code
            self.envisalink.send_command(CMD_SEND_CODE, self.userCode)

            retVal = True

        return retVal

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV1", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV2", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV3", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV4", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV5", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV6", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV7", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV8", "value": 0, "uom": _ISY_BOOL_UOM}
    ]

    commands = {
        "QUERY": query,
	    "PANIC_FIRE": trigger_panic_fire,
		"PANIC_AUX": trigger_panic_aux, 
		"PANIC_POLICE": trigger_panic_police
    }

# Main function to establish Polyglot connection
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface()
        polyglot.start()
        control = AlarmPanel(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
