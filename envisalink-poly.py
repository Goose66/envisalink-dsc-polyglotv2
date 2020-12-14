#!/usr/bin/python3
# Polyglot Node Server for EnvisaLink EVL 3/4 Device (DSC)

import sys
import time
import envisalinktpi as EVL
import polyinterface

# contstants for ISY Nodeserver interface
_ISY_BOOL_UOM = 2 # Used for reporting status values for Controller node
_ISY_INDEX_UOM = 25 # Index UOM for custom states (must match editor/NLS in profile):
_ISY_USER_NUM_UOM = 70 # User Number UOM for reporting last user number
_ISY_MINUTES_UOM = 45 # Used for reporting duration in minutes
_ISY_SECONDS_UOM = 58 # used for reporting duration in seconds


_LOGGER = polyinterface.LOGGER

_PART_ADDR_FORMAT_STRING = "partition%1d"
_ZONE_ADDR_FORMAT_STRING = "zone%02d"
_CMD_OUTPUT_ADDR_FORMAT_STRING = "cmdout%02d"

_PARM_IP_ADDRESS_NAME = "ipaddress"
_PARM_PASSWORD_NAME = "password"
_PARM_USER_CODE_NAME = "usercode"
_PARM_NUM_PARTITIONS_NAME = "numpartitions"
_PARM_NUM_ZONES_NAME = "numzones"
_PARM_NUM_CMD_OUTS_NAME = "numcmdouts"
_PARM_DISABLE_WATCHDOG_TIMER = "disablewatchdog"

_DEFAULT_IP_ADDRESS = "0.0.0.0"
_DEFAULT_PASSWORD = "user"
_DEFAULT_USER_CODE = "5555"
_DEFAULT_NUM_PARTITIONS = 1
_DEFAULT_NUM_ZONES = 16
_DEFAULT_NUM_CMDOUTS = 4

# constants from nodeserver profile
_IX_ALARM_STATE_OK = 0
_IX_ALARM_STATE_SMOKE = 1
_IX_ALARM_STATE_PANIC_FIRE = 2
_IX_ALARM_STATE_PANIC_AUX = 3
_IX_ALARM_STATE_PANIC_POLICE = 4

_IX_ZONE_STATE_CLOSED = 0
_IX_ZONE_STATE_OPEN = 1
_IX_ZONE_STATE_ALARMING = 2

_IX_PARTITION_STATE_READY = 0
_IX_PARTITION_STATE_NOT_READY = 1
_IX_PARTITION_STATE_ARMED_AWAY = 2
_IX_PARTITION_STATE_ARMED_STAY = 3
_IX_PARTITION_STATE_ARMED_AWAY_ZE = 4
_IX_PARTITION_STATE_ARMED_STAY_ZE = 5
_IX_PARTITION_STATE_ALARMING = 6
_IX_PARTITION_STATE_DELAY_EXIT = 7
_IX_PARTITION_STATE_DELAY_ENTRY = 8

_IX_COMMAND_STATE_OFF = 0
_IX_COMMAND_STATE_ACTIVE = 1

# Node class for partitions
class Partition(polyinterface.Node):

    id = "PARTITION"

    # Override init to handle partition number
    def __init__(self, controller, primary, partNum):
        super(Partition, self).__init__(controller, primary, _PART_ADDR_FORMAT_STRING % partNum, "Partition %1d" % partNum)
        self.partitionNum = partNum
        self.initialBypassZoneDump = False
        self.readyState = False

    # Update the driver values based on the command received from the EnvisaLink for the partition
    def update_state_values(self, cmd, data):

        # update the ST value
        if cmd in (EVL.CMD_PARTITION_READY, EVL.CMD_PARTITION_READY_FORCE_ARM):
            self.setDriver("ST", _IX_PARTITION_STATE_READY) # Ready

            self.readyState = True

        elif cmd == EVL.CMD_PARTITION_NOT_READY:
            self.setDriver("ST", _IX_PARTITION_STATE_NOT_READY) # Not Ready

            self.readyState = False

        elif cmd == EVL.CMD_PARTITION_ARMED:

            # get the arming mode from the data
            armingMode = data[-1:]
            if armingMode == "0":  # Armed Away
                self.setDriver("ST", _IX_PARTITION_STATE_ARMED_AWAY)
            elif armingMode == "1":  # Armed Stay
                self.setDriver("ST", _IX_PARTITION_STATE_ARMED_STAY)
            elif armingMode == "2": # Armed Away Zero-Entry
                self.setDriver("ST", _IX_PARTITION_STATE_ARMED_AWAY_ZE)
            elif armingMode == "3": # Armed Stay Zero-Entry
                self.setDriver("ST", _IX_PARTITION_STATE_ARMED_STAY_ZE)

            self.readyState = False
            
        elif cmd == EVL.CMD_PARTITION_IN_ALARM:

            # send a DON commmand when the partition goes to an alarming state
            self.reportCmd("DON")

            # set the status to Alarming
            self.setDriver("ST", _IX_PARTITION_STATE_ALARMING)

            self.readyState = False

        elif cmd == EVL.CMD_PARTITION_DISARMED:
            
            # send a DOF commmand when the partition is disarmed
            self.reportCmd("DOF")

        elif cmd == EVL.CMD_EXIT_DELAY_IN_PROGRESS:
            self.setDriver("ST", _IX_PARTITION_STATE_DELAY_EXIT) 

            self.readyState = False

        elif cmd == EVL.CMD_ENTRY_DELAY_IN_PROGRESS:
            self.setDriver("ST", _IX_PARTITION_STATE_DELAY_ENTRY) 

            self.readyState = False

        # update the GV0 (chime enabled) value
        elif cmd == EVL.CMD_CHIME_ENABLED:
            self.setDriver("GV0", 1)

        elif cmd == EVL.CMD_CHIME_DISABLED:
            self.setDriver("GV0", 0)

        # update the GV1 (last disarming user) value
        elif cmd in (EVL.CMD_SPECIAL_OPENING, EVL.CMD_SPECIAL_CLOSING):
            self.setDriver("GV1", 0)

        elif cmd in (EVL.CMD_USER_CLOSING, EVL.CMD_USER_OPENING):
            userNum = int(data[-4:])
            self.setDriver("GV1", userNum)

    # Arm the partition in Away mode (the listener thread will update the corresponding driver values)
    def arm_away(self, command):

        _LOGGER.info("Arming partition %d in away mode in arm_away()...", self.partitionNum)

        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Arm the partition in Stay mode (the listener thread will update the corresponding driver values)
    def arm_stay(self, command):

        _LOGGER.info("Arming partition %d in stay mode in arm_stay()...", self.partitionNum)
        
        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION_STAY, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Arm the partition in Zero Entry mode (the listener thread will update the corresponding driver values)
    def arm_zero_entry(self, command):
        
        _LOGGER.info("Arming partition %d in zero_entry mode in arm_zero_entry()...", self.partitionNum)

        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION_NO_ENTRY_DELAY, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Disarm the partition (the listener thread will update the corresponding driver values)
    def disarm(self, command):
        
        _LOGGER.info("Disarming partition %d in disarm()...", self.partitionNum)

        # send disarm command and user code to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_DISARM_PARTITION, "%1d%s" % (self.partitionNum, self.controller.userCode)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to disarm partition failed for node %s.", self.address)

    # Toggle the door chime for the partition (the listener thread will update the corresponding driver values)
    def toggle_chime(self, command):

        _LOGGER.info("Toggling door chime for partition %d in toggle_chime()...", self.partitionNum)

        # send door chime toggle keystrokes to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_SEND_KEYSTROKES, "%1d%s" % (self.partitionNum, EVL.KEYS_TOGGLE_DOOR_CHIME)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to toggle door chime failed for node %s.", self.address)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV1", "value": 0, "uom": _ISY_USER_NUM_UOM}
    ]
    commands = {
        "DISARM": disarm,
        "ARM_AWAY": arm_away,
        "ARM_STAY": arm_stay,
        "ARM_ZEROENTRY": arm_zero_entry,
        "TOGGLE_CHIME": toggle_chime
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

            self.setDriver("ST", _IX_ZONE_STATE_CLOSED) 

        elif cmd == EVL.CMD_ZONE_OPEN:

            # send the DON command for the node - allows node to be scene controller
            self.reportCmd("DON")

            # update the driver value and preset the zone timer to zero (will be updated on next short poll)
            self.setDriver("ST", _IX_ZONE_STATE_OPEN) 
            self.setDriver("GV1", 0)

        elif cmd == EVL.CMD_ZONE_ALARM:
            self.setDriver("ST", _IX_ZONE_STATE_ALARMING)

        elif cmd == EVL.CMD_ZONE_ALARM_RESTORED:
            self.setDriver("ST", _IX_ZONE_STATE_CLOSED)

    # Set the bypasse driver value
    def set_bypass(self, bypass):
        self.setDriver("GV0", bypass)

    # Set the zone timer driver value
    def set_timer(self, time):
        self.setDriver("GV1", time)
        
    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV1", "value": 327675, "uom": _ISY_SECONDS_UOM},
    ]
    commands = {}

# Node class for zones
class CommandOutput(polyinterface.Node):

    id = "COMMAND_OUTPUT"

    # Override init to handle partition number
    def __init__(self, controller, primary, cmdOutNum):
        super(CommandOutput, self).__init__(controller, primary, _CMD_OUTPUT_ADDR_FORMAT_STRING % cmdOutNum, "Command Output %02d" % cmdOutNum)
        self.partitionNum = 1 # partition 1 only
        self.cmdOutputNum = cmdOutNum  

    # Update ST driver value based on the command received from the EnvisaLink for the command output
    def set_active_state(self):

        # send the DON command for the node - allows node to be scene controller
            self.reportCmd("DON")
            self.setDriver("ST", _IX_COMMAND_STATE_ACTIVE) 

    def clear_active_state(self):
        
            self.setDriver("ST", _IX_COMMAND_STATE_OFF) 

    # Activate the command output on the DSC Alarm Panel (the listener thread will update the corresponding driver value)
    def cmd_don(self, command):

        _LOGGER.info("Activating command output %d for partition %d in cmd_on()...", self.cmdOutputNum, self.partitionNum)
        
        # Activate the command output
        if self.controller.envisalink.send_command(EVL.CMD_ACTIVATE_CMD_OUTPUT, "%1d%1d" % (self.partitionNum, self.cmdOutputNum)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to activate command output failed for node %s.", self.address)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM}
    ]
    commands = {
        "DON": cmd_don
    }

# Node class for controller
class AlarmPanel(polyinterface.Controller):

    id = "CONTROLLER"

    def __init__(self, poly):
        super(AlarmPanel, self).__init__(poly)
        self.ip = ""
        self.password = ""
        self.name = "Alarm Panel"
        self.envisalink = None
        self.userCode = ""
        self.numPartitions = 0

    # Create nodes for zones, partitions, and command outputs as specified by the parameters
    def build_nodes(self, numPartitions, numZones, numCmdOuts):

        # create partition nodes for the number of partitions specified
        for i in range(0, numPartitions):
            
            # create a partition node and add it to the node list
            self.addNode(Partition(self, self.address, i+1))

        # create zone nodes for the number of partitions specified
        for i in range(0, numZones):
            
            # create a partition node and add it to the node list
            self.addNode(Zone(self, self.address, i+1))

        # create command output nodes for the number of command outputs specified
        for i in range(0, numCmdOuts):
            
            # create a command output node and add it to the node list
            self.addNode(CommandOutput(self, self.address, i+1))
            
    # Update the driver values based on the command received from the EnvisaLink for the partition
    def update_state_values(self, cmd, data):

        # update the GV0 value (System Alarm State)
        if cmd in (EVL.CMD_2_WIRE_SMOKE_ALARM, EVL.CMD_FIRE_KEY_ALARM, EVL.CMD_AUX_KEY_ALARM, EVL.CMD_PANIC_KEY_ALARM):
            
            # send the DON command to the ISY
            _LOGGER.info("Sending Alarm Triggered (DON) command to Alarm Panel node...")
            self.reportCmd("DON")
        
            # set the system alarm status value
            if cmd == EVL.CMD_2_WIRE_SMOKE_ALARM:
                self.setDriver("GV0", _IX_ALARM_STATE_SMOKE) 
            elif cmd == EVL.CMD_FIRE_KEY_ALARM:
                self.setDriver("GV0", _IX_ALARM_STATE_PANIC_FIRE) 
            elif cmd == EVL.CMD_AUX_KEY_ALARM:
                self.setDriver("GV0", _IX_ALARM_STATE_PANIC_AUX) 
            elif cmd == EVL.CMD_PANIC_KEY_ALARM:
                self.setDriver("GV0", _IX_ALARM_STATE_PANIC_POLICE) 
       
        # Clear the GV0 value (System Alarm State)
        elif cmd in (EVL.CMD_2_WIRE_SMOKE_RESTORED, EVL.CMD_FIRE_KEY_RESTORED, EVL.CMD_AUX_KEY_RESTORED, EVL.CMD_PANIC_KEY_RESTORED):

            # send the DOF command to the ISY
            _LOGGER.info("Sending Alarm Cleared (DOF) command to Alarm Panel node...")
            self.reportCmd("DOF")
 
            # Clear the system alarm state
            self.setDriver("GVO", _IX_ALARM_STATE_OK) # Not Alarming

        # update the GV4 (Bell Trouble) value
        elif cmd == EVL.CMD_BELL_TROUBLE:
            self.setDriver("GV4", 1) 
        elif cmd == EVL.CMD_BELL_TROUBLE_RESORED:
            self.setDriver("GV4", 0) 

        # update the GV5 (Battery Trouble) value
        elif cmd == EVL.CMD_BATTERY_TROUBLE:
            self.setDriver("GV5", 1) 
        elif cmd == EVL.CMD_BATTERY_TROUBLE_RESTORED:
            self.setDriver("GV5", 0) 

        # update the GV6 (AC Trouble) value
        elif cmd == EVL.CMD_AC_TROUBLE:
            self.setDriver("GV6", 1)
        elif cmd == EVL.CMD_AC_TROUBLE_RESTORED:
            self.setDriver("GV6", 0)

        # update the GV7 (FTC Trouble) value
        elif cmd == EVL.CMD_FTC_TROUBLE:
            self.setDriver("GV7", 1)
        elif cmd == EVL.CMD_FTC_TROUBLE_RESTORED:
            self.setDriver("GV7", 0)

        # update the GV8 (Tamper Trouble) value
        elif cmd == EVL.CMD_SYSTEM_TAMPER:
            self.setDriver("GV8", 1)
        elif cmd == EVL.CMD_SYSTEM_TAMPER_RESTORED:
            self.setDriver("GV8", 0)

    # Trigger the panic fire alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_fire(self, command):

        _LOGGER.info("Triggering panic alarm (fire) for alarm panel in trigger_panic_fire()...")

        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "1"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)

    # Trigger the panic aux alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_aux(self, command):

        _LOGGER.info("Triggering panic alarm (aux) for alarm panel in trigger_panic_fire()...")

        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "2"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)

    # Trigger the panic fire alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_police(self, command):
        
        _LOGGER.info("Triggering panic alarm (police) for alarm panel in trigger_panic_fire()...")

        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "3"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)

        # Update the profile on the ISY
    def cmd_updateProfile(self, command):

        _LOGGER.info("Installing profile in cmd_updateProfile()...")
        
        self.poly.installprofile()
        
    # Update the profile on the ISY
    def cmd_setLogLevel(self, command):

        _LOGGER.info("Setting logging level in cmd_setLogLevel(): %s", str(command))

        # retrieve the parameter value for the command
        value = int(command.get("value"))
 
        # set the current logging level
        _LOGGER.setLevel(value)

        # store the new loger level in custom data
        self.addCustomData("loggerlevel", value)
        self.saveCustomData(self._customData)
        
        # update the state driver to the level set
        self.setDriver("GV20", value)
        
    def cmd_query(self):

        # Force EnvisaLink to report all statuses available for reporting

        # check for existing EnvisaLink connection
        if self.envisalink is None or not self.envisalink.connected():

            # Update the alarm panel connected status
            self.setDriver("GV1", 1, True, True)

            # send the status polling command to the EnvisaLink device
            self.envisalink.send_command(EVL.CMD_STATUS_REPORT)


        else:

            # Update the alarm panel connected status
            self.setDriver("GV1", 0, True, True)

    # Start the nodeserver
    def start(self):

        _LOGGER.info("Starting envisaink Nodeserver...")

        # remove all notices from ISY Admin Console
        self.removeNoticesAll()

        # load custom data from polyglot
        self._customData = self.polyConfig["customData"]

        # If a logger level was stored for the controller, then use to set the logger level
        level = self.getCustomData("loggerlevel")
        if level is not None:
            _LOGGER.setLevel(int(level))
        
        # get custom configuration parameters
        configComplete = self.getCustomParams()

        # if the configuration is not complete, stop the nodeserver
        if not configComplete:
            self.poly.stop()
            return

        else:

            #  setup the nodes based on the counts of zones and partition in the configuration parameters
            self.build_nodes(self.numPartitions, self.numZones, self.numCmdOuts)

            # setting up the interface moved to shortpoll so that it is retried if initial attempt to connection fails
            # NOTE: this is for, e.g., startup after power failure where Polyglot may restart faster than network or
            # EnvisaLink

        # Set the nodeserver status flag to indicate nodeserver is running
        self.setDriver("ST", 1, True, True)

        # Report initial alarm panel connection status
        self.setDriver("GV1", 0, True, True)

        # Report the logger level to the ISY
        self.setDriver("GV20", _LOGGER.level, True, True)
                       
    # Called when the nodeserver is stopped
    def stop(self):
        
        # shudtown the connection to the EnvisaLink device
        if not self.envisalink is None:
            self.envisalink.shutdown()

            # Update the alarm panel connected status
            self.setDriver("GV1", 0, True, True)

        # Set the nodeserver status flag to indicate nodeserver is stopped
        # Note: this is currently not effective
        self.setDriver("ST", 0, True, True)
        
        
    # called every long_poll seconds
    def longPoll(self):

        # if the EVL's watchdog timer is to be disabled, send a poll command to reset the timer
        # NOTE: this prevents the EnvisaLink from resetting the connection if it can't communicate with EyezON service
        if self.disableWDTimer and self.envisalink is not None and self.envisalink.connected():
            self.envisalink.send_command(EVL.CMD_POLL)
    
    # called every short_poll seconds
    def shortPoll(self):

        # check for existing EnvisaLink connection
        if self.envisalink is None or not self.envisalink.connected():

            # Setup the interface to the EnvisaLink device and connect (starts the listener thread)
            self.envisalink = EVL.EnvisaLinkInterface(_LOGGER)
            
            _LOGGER.info("Establishing connection to EnvisaLink device...")

            if self.envisalink.connect(self.ip, self.password, self.process_command, self.process_heartbeat):

                # clear any prior connection failure notices
                self.removeNotice("no_connect")

                # set alarm panel connected status
                self.setDriver("GV1", 1, True, True)

                # send the status polling command to the EnvisaLink device
                # Only generates general zone status and trouble LED on keypad
                self.envisalink.send_command(EVL.CMD_STATUS_REPORT)

            else:
                
                # set alarm panel connected status
                self.setDriver("GV1", 0, True, True)

                # Format errors
                _LOGGER.warning("Could not connect to EnvisaLink device at %s.", self.ip)
                self.addNotice({"no_connect": "Could not connect to EnvisaLink device. Please check the network and configuration parameters and restart the nodeserver."})
                self.envisalink = None              

        else:
            
            # make sure the bypass zones are dumped for each partition
            # NOTE this is done in a subsequent short poll after the intiial connection is established,
            # but only once for each partition
            for part in range(1, self.numPartitions + 1):
                    
                # get the node for the partition
                partition = self.nodes[_PART_ADDR_FORMAT_STRING % part]

                # If the zone bypass dump for the partition has not yet been performed and the partition is ready
                if not partition.initialBypassZoneDump and partition.readyState:
                            
                    # force a bypass zone dump through the keypad for the partition
                    self.envisalink.send_command(EVL.CMD_SEND_KEYSTROKES, "%1d%s" % (partition.partitionNum, EVL.KEYS_DUMP_BYPASS_ZONES))
                    partition.initialBypassZoneDump = True

                    # exit the function leaving the remaining partitions for a subsequent shortPoll()
                    return
        
            # if connection and all partitions have had zone bypass dumps, then force a zone timer dump
            self.envisalink.send_command(EVL.CMD_DUMP_ZONE_TIMERS)
             
    # Get custom configuration parameter values
    def getCustomParams(self):

        customParams = self.poly.config["customParams"] 
        complete = True

        # get IP address of the EnvisaLink device from custom parameters
        try:
            self.ip = customParams[_PARM_IP_ADDRESS_NAME]      
        except KeyError:
            _LOGGER.error("Missing IP address for EnvisaLink device in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice({"missing_ip": "Please update the '%s' parameter value in the nodeserver custom parameters and restart the nodeserver." % _PARM_IP_ADDRESS_NAME})

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_IP_ADDRESS_NAME: _DEFAULT_IP_ADDRESS})
            complete = False
            
        # get the password of the EnvisaLink device from custom parameters
        try:
            self.password = customParams[_PARM_PASSWORD_NAME]
        except KeyError:
            _LOGGER.error("Missing password for EnvisaLink device in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice({"missing_pwd": "Please update the '%s' parameter value in the nodeserver custom parameters and restart the nodeserver." % _PARM_PASSWORD_NAME})

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_PASSWORD_NAME: _DEFAULT_PASSWORD})
            complete = False

        # get the user code for the DSC panel from custom parameters
        try:
            self.userCode = customParams[_PARM_USER_CODE_NAME]
        except KeyError:
            _LOGGER.error("Missing user code for DSC panel in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice({"missing_code": "Please update the '%s' custom configuration parameter value in the nodeserver configuration and restart the nodeserver." % _PARM_USER_CODE_NAME})

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_USER_CODE_NAME: _DEFAULT_USER_CODE})
            complete = False

        # get the optional number of partitions, zones, and command outputs to create nodes for
        try:
            self.numPartitions = int(customParams[_PARM_NUM_PARTITIONS_NAME])
        except (KeyError, ValueError, TypeError):
            self.numPartitions = _DEFAULT_NUM_PARTITIONS

        try:
            self.numZones = int(customParams[_PARM_NUM_ZONES_NAME])
        except (KeyError, ValueError, TypeError):
            self.numZones = _DEFAULT_NUM_ZONES

        try:
            self.numCmdOuts = int(customParams[_PARM_NUM_CMD_OUTS_NAME])
        except (KeyError, ValueError, TypeError):
            self.numCmdOuts = _DEFAULT_NUM_CMDOUTS

        # get optional settings for watchdog timer
        try:
            self.disableWDTimer = (int(customParams[_PARM_DISABLE_WATCHDOG_TIMER]) == 1)
        except (KeyError, ValueError, TypeError):
            self.disableWDTimer = False

        self.poly.saveCustomParams(customParams)

        return complete

    # Callback function for listener thread
    def process_command(self, cmd, data):

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
            EVL.CMD_CHIME_DISABLED,
            EVL.CMD_USER_OPENING,
            EVL.CMD_USER_CLOSING,
            EVL.CMD_SPECIAL_OPENING,
            EVL.CMD_SPECIAL_CLOSING
        ):

            # get the partition number from the data
            partNum = int(data[:1])

            # check if node for partition exists
            for addr in self.nodes:
                if addr == _PART_ADDR_FORMAT_STRING % partNum:

                    # update the driver values of the node from the commands
                    self.nodes[addr].update_state_values(cmd, data)
                    break

            # if the command is partition ready for partition 1, also clear any active command output state flags
            if cmd == EVL.CMD_PARTITION_READY and partNum == 1:
                for addr in self.nodes:
                    if addr[:6] == _CMD_OUTPUT_ADDR_FORMAT_STRING[:6]:
                        self.nodes[addr].clear_active_state()
        
        # Pass zone status commands to correct zone node
        elif cmd in (
            EVL.CMD_ZONE_RESTORED,
            EVL.CMD_ZONE_OPEN,
            EVL.CMD_ZONE_ALARM,
            EVL.CMD_ZONE_ALARM_RESTORED
        ):

            # get the zone number from the data
            zoneNum = int(data[-3:])

            # check if node for zone
            for addr in self.nodes:
                if addr == _ZONE_ADDR_FORMAT_STRING % zoneNum:
                    
                    # update the driver values of the node from the commands
                    self.nodes[addr].update_state_values(cmd, data)
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

            # update the driver values of the node from the commands
            self.update_state_values(cmd, data)

        # handle zone bypass dump
        elif cmd == EVL.CMD_BYPASSED_ZONES_DUMP:
            
            # resequence the hex string in the data to be a big-endian representation
            # of the 64-bit bitfield
            leHexString = data
            beHexString = (leHexString[14:]
                           + leHexString[12:14]
                           + leHexString[10:12]
                           + leHexString[8:10]
                           + leHexString[6:8]
                           + leHexString[4:6]
                           + leHexString[2:4]
                           + leHexString[:2])
            
            # convert the big-endian hex string to a 64-bit bitfield representing the
            # bypass status of each of the 64 zones
            bypassFlags = bin(int(beHexString, base=16))[2:].zfill(64)    
            
            # iterate through the zone nodes and set the bypass flag from the bitfield
            for addr in self.nodes:
                node = self.nodes[addr]
                if node.id == "ZONE":
                    node.set_bypass(int(bypassFlags[-node.zoneNum]))

        # handle zone timer dump
        elif cmd == EVL.CMD_ZONE_TIMER_DUMP:
            
            # spilt the 256 bytes of data into 64 individual 4-byte hex values 
            zoneTimerHexValues = [data[i:i+4] for i in range(0, len(data), 4)]

            # convert the 4-byte hex values to a list of integer zone timers
            # Note: Each 4-byte hex value is a little-endian countdown of 5-second
            # intervals, i.e. FFFF = 0, FEFF = 5, FDFF = 10, etc.  
            zoneTimers = []
            for leHexString in zoneTimerHexValues:
                beHexString = leHexString[2:] + leHexString[:2]
                time = (int(beHexString, base=16) ^ 0xFFFF) * 5
                zoneTimers.append(time)
                            
            # iterate through the zone nodes and set the bypass flag from the bitfield
            for addr in self.nodes:
                node = self.nodes[addr]
                if node.id == "ZONE":
                    node.set_timer(zoneTimers[node.zoneNum - 1])
                    
        elif cmd in (EVL.CMD_COMMAND_OUTPUT_PRESSED):
            
            # get the partition and command output number from the data
            partNum = int(data[0:1])
            cmdOutNum = int(data[1:2])
    
            # set the active state in the corresponding command output node
            for addr in self.nodes:
                if addr == _CMD_OUTPUT_ADDR_FORMAT_STRING % cmdOutNum:
                    self.nodes[addr].set_active_state()

        # handle user code request
        elif cmd in (EVL.CMD_CODE_REQD):

            # send the user code
            self.envisalink.send_command(EVL.CMD_SEND_CODE, self.userCode)

        else:
            _LOGGER.debug("Unhandled command received from EnvisaLink. Command: %s, Data: %s", cmd.decode("ascii"), data)
    
    # Callback function for heartbeat
    def process_heartbeat(self):

        # send heartbeat command to alarm panel (controller) node 
        _LOGGER.info("Sending Heartbeat command to Alarm Panel node...")
        self.reportCmd("AWAKE")

        # helper method for storing custom data
    def addCustomData(self, key, data):

        # add specififed data to custom data for specified key
        self._customData.update({key: data})

    # helper method for retrieve custom data
    def getCustomData(self, key):

        # return data from custom data for key
        return self._customData.get(key)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV1", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV4", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV5", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV6", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV7", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV8", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV20", "value": 0, "uom": _ISY_INDEX_UOM}
    ]

    commands = {
        "QUERY": cmd_query,
	    "PANIC_FIRE": trigger_panic_fire,
		"PANIC_AUX": trigger_panic_aux, 
		"PANIC_POLICE": trigger_panic_police,
        "UPDATE_PROFILE" : cmd_updateProfile,
        "SET_LOGLEVEL": cmd_setLogLevel        
    }

# Main function to establish Polyglot connection
if __name__ == "__main__":
    try:
        poly = polyinterface.Interface()
        poly.start()
        controller = AlarmPanel(poly)
        controller.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
