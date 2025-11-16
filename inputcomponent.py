#!/usr/bin/env python3
from __future__ import print_function
import struct
import sys
import argparse
import math
import os

PythonGateways = 'pythonGateways/'
sys.path.append(PythonGateways)

import VsiCommonPythonApi as vsiCommonPythonApi
import VsiTcpUdpPythonGateway as vsiEthernetPythonGateway


class MySignals:
    def __init__(self):
        # Outputs
        self.gcode_line = [0] * 512
        self.gcode_len = 0
        self.startSignal = 0
        self.refillCommand = 0


srcMacAddress = [0x12, 0x34, 0x56, 0x78, 0x90, 0x01]
ProcessorComponentMacAddress = [0x12, 0x34, 0x56, 0x78, 0x90, 0x02]
srcIpAddress = [192, 168, 2, 10]
ProcessorComponentIpAddress = [192, 168, 2, 11]

ProcessorComponentSocketPortNumber0 = 9000

InputComponent0 = 0


# Start of user custom code region. Please apply edits only within these regions:  Global Variables & Definitions
class GCodeFileReader:
    def __init__(self, signals):
        self.signals = signals
        self.gcode_file_path = "/data/tools/pave/innexis_home/vsi_2025.2/examples/vsiTutorials/3dprinter/file.txt"
        self.gcode_lines = []
        self.current_line_index = 0
        self.file_loaded = False
        
        # Load G-code from file
        self.load_gcode_file()
    
    def load_gcode_file(self):
        try:
            if os.path.exists(self.gcode_file_path):
                with open(self.gcode_file_path, 'r') as file:
                    self.gcode_lines = [line.strip() for line in file if line.strip() and not line.strip().startswith(';')]
                print(f"Loaded {len(self.gcode_lines)} G-code lines from {self.gcode_file_path}")
                self.file_loaded = True
            else:
                print(f"G-code file not found: {self.gcode_file_path}")
                # Create some sample G-code as fallback
                self.gcode_lines = [
                    "M104 S200",           # Set nozzle temperature
                    "M140 S60",            # Set bed temperature
                    "G28",                 # Home all axes
                    "G1 Z0.2 F1200",       # Move to layer height
                    "G1 X50 Y50 F3000",    # Move to start position
                    "G1 X100 Y50 E5",      # Print line 1
                    "G1 X100 Y100 E10",    # Print line 2
                    "G1 X50 Y100 E15",     # Print line 3
                    "G1 X50 Y50 E20",      # Print line 4
                    "M104 S0",             # Cool down nozzle
                    "M140 S0"              # Cool down bed
                ]
                self.file_loaded = True
                print("Using fallback G-code")
        except Exception as e:
            print(f"Error loading G-code file: {e}")
            self.file_loaded = False
    
    def send_next_gcode(self):
        if self.file_loaded and self.current_line_index < len(self.gcode_lines):
            gcode = self.gcode_lines[self.current_line_index]
            self.send_gcode(gcode)
            self.current_line_index += 1
            print(f"Sent G-code line {self.current_line_index}/{len(self.gcode_lines)}: {gcode}")
            return True
        return False
    
    def send_gcode(self, gcode_str):
        # Convert string to byte array
        gcode_bytes = gcode_str.encode('utf-8')
        gcode_len = min(len(gcode_bytes), 511)
        
        # Clear previous G-code
        self.signals.gcode_line = [0] * 512
        
        # Copy new G-code
        for i in range(gcode_len):
            self.signals.gcode_line[i] = gcode_bytes[i]
        
        self.signals.gcode_len = gcode_len
    
    def start_print(self):
        if self.file_loaded and self.gcode_lines:
            self.current_line_index = 0
            self.signals.startSignal = 1
            print(f"Starting print job with {len(self.gcode_lines)} G-code lines")
            return True
        else:
            print("No G-code loaded. Cannot start print.")
            return False
    
    def refill_filament(self):
        self.signals.refillCommand = 1
        print("Refill command sent")
    
    def has_more_gcode(self):
        return self.file_loaded and self.current_line_index < len(self.gcode_lines)
# End of user custom code region. Please don't edit beyond this point.

class InputComponent:
    def __init__(self, args):
        self.componentId = 0
        self.localHost = args.server_url
        self.domain = args.domain
        self.portNum = 50101
        
        self.simulationStep = 0
        self.stopRequested = False
        self.totalSimulationTime = 0
        
        self.receivedNumberOfBytes = 0
        self.receivedPayload = []

        self.numberOfPorts = 1
        self.clientPortNum = [0] * self.numberOfPorts
        self.receivedDestPortNumber = 0
        self.receivedSrcPortNumber = 0
        self.expectedNumberOfBytes = 0
        self.mySignals = MySignals()

        # Start of user custom code region. Please apply edits only within these regions:  Constructor
        self.gcode_reader = GCodeFileReader(self.mySignals)
        self.cycle_count = 0
        self.print_started = False
        self.gcode_sent = False
        # End of user custom code region. Please don't edit beyond this point.

    def mainThread(self):
        dSession = vsiCommonPythonApi.connectToServer(self.localHost, self.domain, self.portNum, self.componentId)
        vsiEthernetPythonGateway.initialize(dSession, self.componentId, bytes(srcMacAddress), bytes(srcIpAddress))
        try:
            vsiCommonPythonApi.waitForReset()

            # Start of user custom code region. Please apply edits only within these regions:  After Reset
            print("InputComponent initialized - waiting for connection...")
            # End of user custom code region. Please don't edit beyond this point.
            self.updateInternalVariables()

            if(vsiCommonPythonApi.isStopRequested()):
                raise Exception("stopRequested")
            self.establishTcpUdpConnection()
            nextExpectedTime = vsiCommonPythonApi.getSimulationTimeInNs()
            while(vsiCommonPythonApi.getSimulationTimeInNs() < self.totalSimulationTime):

                # Start of user custom code region. Please apply edits only within these regions:  Inside the while loop
                self.cycle_count += 1
                
                # Start print after 5 cycles to ensure connection is established
                if self.cycle_count == 5 and not self.print_started:
                    if self.gcode_reader.start_print():
                        self.print_started = True
                        self.gcode_sent = False
                
                # Send G-code lines sequentially
                if self.print_started and not self.gcode_sent and self.gcode_reader.has_more_gcode():
                    if self.gcode_reader.send_next_gcode():
                        self.gcode_sent = True
                
                # Auto-refill when cycle count reaches certain point
                if self.cycle_count == 50:
                    self.gcode_reader.refill_filament()
                # End of user custom code region. Please don't edit beyond this point.

                self.updateInternalVariables()

                if(vsiCommonPythonApi.isStopRequested()):
                    raise Exception("stopRequested")

                if(vsiEthernetPythonGateway.isTerminationOnGoing()):
                    print("Termination is on going")
                    break

                if(vsiEthernetPythonGateway.isTerminated()):
                    print("Application terminated")
                    break

                receivedData = vsiEthernetPythonGateway.recvEthernetPacket(ProcessorComponentSocketPortNumber0)
                if(receivedData[3] != 0):
                    self.decapsulateReceivedData(receivedData)

                # Start of user custom code region. Please apply edits only within these regions:  Before sending the packet
                # Reset one-shot signals right before sending to ensure they're captured
                # End of user custom code region. Please don't edit beyond this point.

                #Send ethernet packet to ProcessorComponent
                self.sendEthernetPacketToProcessorComponent()

                # Start of user custom code region. Please apply edits only within these regions:  After sending the packet
                # Reset one-shot signals after sending
                if self.mySignals.startSignal == 1:
                    self.mySignals.startSignal = 0
                if self.mySignals.refillCommand == 1:
                    self.mySignals.refillCommand = 0
                
                # Reset gcode_sent flag to allow sending next line
                if self.gcode_sent:
                    self.gcode_sent = False
                # End of user custom code region. Please don't edit beyond this point.

                print("\n+=InputComponent+=")
                print("  VSI time:", end = " ")
                print(vsiCommonPythonApi.getSimulationTimeInNs(), end = " ")
                print("ns")

                print("  Outputs:")
                gcode_str = ''.join(chr(b) for b in self.mySignals.gcode_line[:self.mySignals.gcode_len] if b != 0)
                print("\tgcode_line =", end = " ")
                print(f"\"{gcode_str}\"")
                print("\tgcode_len =", end = " ")
                print(self.mySignals.gcode_len)
                print("\tstartSignal =", end = " ")
                print(self.mySignals.startSignal)
                print("\trefillCommand =", end = " ")
                print(self.mySignals.refillCommand)
                print("\n\n")

                self.updateInternalVariables()

                if(vsiCommonPythonApi.isStopRequested()):
                    raise Exception("stopRequested")
                nextExpectedTime += self.simulationStep

                if(vsiCommonPythonApi.getSimulationTimeInNs() >= nextExpectedTime):
                    continue

                if(nextExpectedTime > self.totalSimulationTime):
                    remainingTime = self.totalSimulationTime - vsiCommonPythonApi.getSimulationTimeInNs()
                    vsiCommonPythonApi.advanceSimulation(remainingTime)
                    break

                vsiCommonPythonApi.advanceSimulation(nextExpectedTime - vsiCommonPythonApi.getSimulationTimeInNs())

            if(vsiCommonPythonApi.getSimulationTimeInNs() < self.totalSimulationTime):
                vsiEthernetPythonGateway.terminate()
        except Exception as e:
            if str(e) == "stopRequested":
                print("Terminate signal has been received from one of the VSI clients")
                # Advance time with a step that is equal to "simulationStep + 1" so that all other clients
                # receive the terminate packet before terminating this client
                vsiCommonPythonApi.advanceSimulation(self.simulationStep + 1)
            else:
                print(f"An error occurred: {str(e)}")
        except:
            # Advance time with a step that is equal to "simulationStep + 1" so that all other clients
            # receive the terminate packet before terminating this client
            vsiCommonPythonApi.advanceSimulation(self.simulationStep + 1)

    def establishTcpUdpConnection(self):
        if(self.clientPortNum[InputComponent0] == 0):
            self.clientPortNum[InputComponent0] = vsiEthernetPythonGateway.tcpConnect(bytes(ProcessorComponentIpAddress), ProcessorComponentSocketPortNumber0)

        if(self.clientPortNum[InputComponent0] == 0):
            print("Error: Failed to connect to port: ProcessorComponent on TCP port: ") 
            print(ProcessorComponentSocketPortNumber0)
            exit()

    def decapsulateReceivedData(self, receivedData):
        self.receivedDestPortNumber = receivedData[0]
        self.receivedSrcPortNumber = receivedData[1]
        self.receivedNumberOfBytes = receivedData[3]
        self.receivedPayload = [0] * (self.receivedNumberOfBytes)

        for i in range(self.receivedNumberOfBytes):
            self.receivedPayload[i] = receivedData[2][i]

    def sendEthernetPacketToProcessorComponent(self):
        bytesToSend = bytes()

        bytesToSend += self.packBytes('B', self.mySignals.gcode_line)

        bytesToSend += self.packBytes('L', self.mySignals.gcode_len)

        bytesToSend += self.packBytes('B', self.mySignals.startSignal)

        bytesToSend += self.packBytes('B', self.mySignals.refillCommand)

        #Send ethernet packet to ProcessorComponent
        vsiEthernetPythonGateway.sendEthernetPacket(ProcessorComponentSocketPortNumber0, bytes(bytesToSend))

        # Start of user custom code region. Please apply edits only within these regions:  Protocol's callback function

        # End of user custom code region. Please don't edit beyond this point.

    def packBytes(self, signalType, signal):
        if isinstance(signal, list):
            if signalType == 's':
                packedData = b''
                for str in signal:
                    str += '\0'
                    str = str.encode('utf-8')
                    packedData += struct.pack(f'={len(str)}s', str)
                return packedData
            else:
                return struct.pack(f'={len(signal)}{signalType}', *signal)
        else:
            if signalType == 's':
                signal += '\0'
                signal = signal.encode('utf-8')
                return struct.pack(f'={len(signal)}s', signal)
            else:
                return struct.pack(f'={signalType}', signal)

    def unpackBytes(self, signalType, packedBytes, signal = ""):
        if isinstance(signal, list):
            if signalType == 's':
                unpackedStrings = [''] * len(signal)
                for i in range(len(signal)):
                    nullCharacterIndex = packedBytes.find(b'\0')
                    if nullCharacterIndex == -1:
                        break
                    unpackedString = struct.unpack(f'={nullCharacterIndex}s', packedBytes[:nullCharacterIndex])[0].decode('utf-8')
                    unpackedStrings[i] = unpackedString
                    packedBytes = packedBytes[nullCharacterIndex + 1:]
                return unpackedStrings, packedBytes
            else:
                unpackedVariable = struct.unpack(f'={len(signal)}{signalType}', packedBytes[:len(signal)*struct.calcsize(f'={signalType}')])
                packedBytes = packedBytes[len(unpackedVariable)*struct.calcsize(f'={signalType}'):]
                return list(unpackedVariable), packedBytes
        elif signalType == 's':
            nullCharacterIndex = packedBytes.find(b'\0')
            unpackedVariable = struct.unpack(f'={nullCharacterIndex}s', packedBytes[:nullCharacterIndex])[0].decode('utf-8')
            packedBytes = packedBytes[nullCharacterIndex + 1:]
            return unpackedVariable, packedBytes
        else:
            numBytes = 0
            if signalType in ['?', 'b', 'B']:
                numBytes = 1
            elif signalType in ['h', 'H']:
                numBytes = 2
            elif signalType in ['f', 'i', 'I', 'L', 'l']:
                numBytes = 4
            elif signalType in ['q', 'Q', 'd']:
                numBytes = 8
            else:
                raise Exception('received an invalid signal type in unpackBytes()')
            unpackedVariable = struct.unpack(f'={signalType}', packedBytes[0:numBytes])[0]
            packedBytes = packedBytes[numBytes:]
            return unpackedVariable, packedBytes

    def updateInternalVariables(self):
        self.totalSimulationTime = vsiCommonPythonApi.getTotalSimulationTime()
        self.stopRequested = vsiCommonPythonApi.isStopRequested()
        self.simulationStep = vsiCommonPythonApi.getSimulationStep()

def main():
    inputArgs = argparse.ArgumentParser(" ")
    inputArgs.add_argument('--domain', metavar='D', default='AF_UNIX', help='Socket domain for connection with the VSI TLM fabric server')
    inputArgs.add_argument('--server-url', metavar='CO', default='localhost', help='server URL of the VSI TLM Fabric Server')

    # Start of user custom code region. Please apply edits only within these regions:  Main method

    # End of user custom code region. Please don't edit beyond this point.

    args = inputArgs.parse_args()
                      
    inputComponent = InputComponent(args)
    inputComponent.mainThread()

if __name__ == '__main__':
    main()