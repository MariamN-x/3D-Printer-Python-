#!/usr/bin/env python3
from __future__ import print_function
import struct
import sys
import argparse
import math

PythonGateways = 'pythonGateways/'
sys.path.append(PythonGateways)

import VsiCommonPythonApi as vsiCommonPythonApi
import VsiTcpUdpPythonGateway as vsiEthernetPythonGateway


class MySignals:
    def __init__(self):
        # Inputs
        self.gcode_line = [0] * 512
        self.gcode_len = 0
        self.startSignal = 0
        self.refillCommand = 0

        # Outputs
        self.headX = 0.0
        self.headY = 0.0
        self.headZ = 0.0
        self.nozzleTemp = 25.0
        self.bedTemp = 25.0
        self.filamentRemaining = 100.0
        self.printerState = 0  # 0=Idle, 1=Heating, 2=Printing, 3=Paused, 4=Error
        self.errorCode = 0


srcMacAddress = [0x12, 0x34, 0x56, 0x78, 0x90, 0x02]
InputComponentMacAddress = [0x12, 0x34, 0x56, 0x78, 0x90, 0x01]
srcIpAddress = [192, 168, 2, 11]
InputComponentIpAddress = [192, 168, 2, 10]

ProcessorComponentSocketPortNumber0 = 9000

InputComponent0 = 0


# Start of user custom code region. Please apply edits only within these regions:  Global Variables & Definitions
class PrinterSimulation:
    def __init__(self, signals):
        self.signals = signals
        self.gcode_queue = []
        self.is_heating = False
        self.is_printing = False
        self.target_nozzle_temp = 0.0
        self.target_bed_temp = 0.0
        self.gcode_processed = 0
        self.last_start_signal = 0
        self.last_refill_signal = 0
    
    def update_simulation(self):
        # Temperature control
        if self.is_heating or self.is_printing:
            # Heat up nozzle
            if self.signals.nozzleTemp < self.target_nozzle_temp:
                self.signals.nozzleTemp = min(self.signals.nozzleTemp + 2.0, self.target_nozzle_temp)
            elif self.signals.nozzleTemp > self.target_nozzle_temp:
                self.signals.nozzleTemp = max(self.signals.nozzleTemp - 1.0, self.target_nozzle_temp)
            
            # Heat up bed
            if self.signals.bedTemp < self.target_bed_temp:
                self.signals.bedTemp = min(self.signals.bedTemp + 1.0, self.target_bed_temp)
            elif self.signals.bedTemp > self.target_bed_temp:
                self.signals.bedTemp = max(self.signals.bedTemp - 0.5, self.target_bed_temp)
        else:
            # Cool down when not active
            if self.signals.nozzleTemp > 25.0:
                self.signals.nozzleTemp = max(self.signals.nozzleTemp - 0.5, 25.0)
            if self.signals.bedTemp > 25.0:
                self.signals.bedTemp = max(self.signals.bedTemp - 0.3, 25.0)
        
        # Process G-code from queue
        if self.is_printing and self.gcode_queue:
            gcode = self.gcode_queue.pop(0)
            self.process_gcode(gcode)
            self.gcode_processed += 1
        
        # Filament monitoring
        if self.is_printing:
            # Consume filament during printing
            self.signals.filamentRemaining = max(0, self.signals.filamentRemaining - 0.01)
            if self.signals.filamentRemaining <= 0:
                self.signals.errorCode = 1  # Out of filament error
                self.is_printing = False
                self.signals.printerState = 4
                print("ERROR: Out of filament!")
    
    def process_gcode(self, gcode_line):
        gcode_str = ''.join(chr(b) for b in gcode_line if b != 0).strip()
        if not gcode_str:
            return
        
        print(f"Processing G-code [{self.gcode_processed}]: {gcode_str}")
        
        if gcode_str.startswith('G1'):
            # Movement command
            parts = gcode_str.split()
            for part in parts:
                if part.startswith('X'):
                    self.signals.headX = float(part[1:])
                elif part.startswith('Y'):
                    self.signals.headY = float(part[1:])
                elif part.startswith('Z'):
                    self.signals.headZ = float(part[1:])
        
        elif gcode_str.startswith('M104'):
            # Set nozzle temperature
            parts = gcode_str.split()
            for part in parts:
                if part.startswith('S'):
                    self.target_nozzle_temp = float(part[1:])
                    self.is_heating = True
        
        elif gcode_str.startswith('M140'):
            # Set bed temperature
            parts = gcode_str.split()
            for part in parts:
                if part.startswith('S'):
                    self.target_bed_temp = float(part[1:])
                    self.is_heating = True
        
        elif gcode_str.startswith('G28'):
            # Home all axes
            self.signals.headX = 0.0
            self.signals.headY = 0.0
            self.signals.headZ = 0.0
            print("Homing all axes")
    
    def process_signals(self, start_signal, refill_signal, gcode_line, gcode_len):
        # Edge detection for start signal
        if start_signal == 1 and self.last_start_signal == 0:
            self.start_print()
        
        # Edge detection for refill signal
        if refill_signal == 1 and self.last_refill_signal == 0:
            self.refill_filament()
        
        # Store current values for edge detection
        self.last_start_signal = start_signal
        self.last_refill_signal = refill_signal
        
        # Add G-code to queue if there's valid data
        if gcode_len > 0:
            self.add_gcode(gcode_line[:gcode_len])
    
    def start_print(self):
        if self.signals.filamentRemaining > 0:
            self.is_printing = True
            self.is_heating = True
            self.signals.printerState = 2
            self.signals.errorCode = 0
            print("Print started - processing G-code queue")
        else:
            self.signals.errorCode = 1
            self.signals.printerState = 4
            print("ERROR: Cannot start print - out of filament!")
    
    def refill_filament(self):
        self.signals.filamentRemaining = 100.0
        self.signals.errorCode = 0
        if self.signals.printerState == 4:
            self.signals.printerState = 0
        print("Filament refilled to 100%")
    
    def add_gcode(self, gcode_line):
        """Add G-code to the processing queue"""
        self.gcode_queue.append(gcode_line.copy())
# End of user custom code region. Please don't edit beyond this point.

class ProcessorComponent:
    def __init__(self, args):
        self.componentId = 1
        self.localHost = args.server_url
        self.domain = args.domain
        self.portNum = 50102
        
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
        self.printer_sim = PrinterSimulation(self.mySignals)
        # End of user custom code region. Please don't edit beyond this point.

    def mainThread(self):
        dSession = vsiCommonPythonApi.connectToServer(self.localHost, self.domain, self.portNum, self.componentId)
        vsiEthernetPythonGateway.initialize(dSession, self.componentId, bytes(srcMacAddress), bytes(srcIpAddress))
        try:
            vsiCommonPythonApi.waitForReset()

            # Start of user custom code region. Please apply edits only within these regions:  After Reset
            print("ProcessorComponent initialized and waiting for G-code...")
            # End of user custom code region. Please don't edit beyond this point.
            self.updateInternalVariables()

            if(vsiCommonPythonApi.isStopRequested()):
                raise Exception("stopRequested")
            self.establishTcpUdpConnection()
            nextExpectedTime = vsiCommonPythonApi.getSimulationTimeInNs()
            while(vsiCommonPythonApi.getSimulationTimeInNs() < self.totalSimulationTime):

                # Start of user custom code region. Please apply edits only within these regions:  Inside the while loop
                # Update printer simulation
                self.printer_sim.update_simulation()
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

                receivedData = vsiEthernetPythonGateway.recvEthernetPacket(self.clientPortNum[InputComponent0])
                if(receivedData[3] != 0):
                    self.decapsulateReceivedData(receivedData)

                # Start of user custom code region. Please apply edits only within these regions:  Before sending the packet

                # End of user custom code region. Please don't edit beyond this point.

                # Start of user custom code region. Please apply edits only within these regions:  After sending the packet

                # End of user custom code region. Please don't edit beyond this point.

                print("\n+=ProcessorComponent+=")
                print("  VSI time:", end = " ")
                print(vsiCommonPythonApi.getSimulationTimeInNs(), end = " ")
                print("ns")
                print("  Inputs:")
                gcode_str = ''.join(chr(b) for b in self.mySignals.gcode_line[:self.mySignals.gcode_len] if b != 0)
                print("\tgcode_line =", end = " ")
                print(f"\"{gcode_str}\"")
                print("\tgcode_len =", end = " ")
                print(self.mySignals.gcode_len)
                print("\tstartSignal =", end = " ")
                print(self.mySignals.startSignal)
                print("\trefillCommand =", end = " ")
                print(self.mySignals.refillCommand)
                print("  Outputs:")
                print("\theadX =", end = " ")
                print(f"{self.mySignals.headX:.2f}")
                print("\theadY =", end = " ")
                print(f"{self.mySignals.headY:.2f}")
                print("\theadZ =", end = " ")
                print(f"{self.mySignals.headZ:.2f}")
                print("\tnozzleTemp =", end = " ")
                print(f"{self.mySignals.nozzleTemp:.1f}°C")
                print("\tbedTemp =", end = " ")
                print(f"{self.mySignals.bedTemp:.1f}°C")
                print("\tfilamentRemaining =", end = " ")
                print(f"{self.mySignals.filamentRemaining:.1f}%")
                state_names = ["Idle", "Heating", "Printing", "Paused", "Error"]
                print("\tprinterState =", end = " ")
                print(f"{self.mySignals.printerState} ({state_names[self.mySignals.printerState]})")
                print("\terrorCode =", end = " ")
                print(self.mySignals.errorCode)
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
            self.clientPortNum[InputComponent0] = vsiEthernetPythonGateway.tcpListen(ProcessorComponentSocketPortNumber0)

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

        if(self.receivedSrcPortNumber == self.clientPortNum[InputComponent0]):
            print("Received packet from InputComponent")
            receivedPayload = bytes(self.receivedPayload)
            self.mySignals.gcode_line, receivedPayload = self.unpackBytes('B', receivedPayload, signal = self.mySignals.gcode_line)

            self.mySignals.gcode_len, receivedPayload = self.unpackBytes('L', receivedPayload)

            self.mySignals.startSignal, receivedPayload = self.unpackBytes('B', receivedPayload)

            self.mySignals.refillCommand, receivedPayload = self.unpackBytes('B', receivedPayload)

        # Start of user custom code region. Please apply edits only within these regions:  Protocol's callback function
        # Process received signals
        self.printer_sim.process_signals(
            self.mySignals.startSignal,
            self.mySignals.refillCommand,
            self.mySignals.gcode_line,
            self.mySignals.gcode_len
        )
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
                      
    processorComponent = ProcessorComponent(args)
    processorComponent.mainThread()

if __name__ == '__main__':
    main()