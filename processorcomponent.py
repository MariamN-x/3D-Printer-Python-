#!/usr/bin/env python3
from __future__ import print_function
import struct
import sys
import argparse
import math
import simpy
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
        self.printerState = 0  # 0=Idle,1=Heating,2=Printing,3=Paused,4=Error
        self.errorCode = 0


srcMacAddress = [0x12, 0x34, 0x56, 0x78, 0x90, 0x02]
InputComponentMacAddress = [0x12, 0x34, 0x56, 0x78, 0x90, 0x01]
srcIpAddress = [192, 168, 2, 11]
InputComponentIpAddress = [192, 168, 2, 10]

ProcessorComponentSocketPortNumber0 = 9000

InputComponent0 = 0


# Start of user custom code region. Please apply edits only within these regions:  Global Variables & Definitions
class PrinterSimulation:
    """
    Full SimPy printer model:
      - heating (nozzle & bed)
      - cooling
      - motion (headX/Y/Z)
      - gcode timing & execution
      - extrusion delay & filament consumption
    The model updates shared MySignals in-place.
    """
    def __init__(self, env, signals):
        self.env = env
        self.signals = signals

        # internal state
        self.gcode_queue = []
        self.current_gcode = None
        self.is_heating = False
        self.is_printing = False
        self.target_nozzle_temp = 25.0
        self.target_bed_temp = 25.0
        self.motion_speed = 50.0    # mm/s for simple motion model
        self.motion_tolerance = 0.001

        # processes
        self.env.process(self.heat_process())
        self.env.process(self.motion_process())
        self.env.process(self.gcode_executor_process())
        self.env.process(self.cooling_monitor_process())

    def heat_process(self):
        while True:
            dt = 0.01
            # nozzle heating/cooling dynamics
            if self.signals.nozzleTemp < self.target_nozzle_temp:
                rate = 5.0 if (self.is_heating or self.is_printing) else 1.0
                self.signals.nozzleTemp = min(self.signals.nozzleTemp + rate * dt, self.target_nozzle_temp)
            elif self.signals.nozzleTemp > self.target_nozzle_temp:
                self.signals.nozzleTemp = max(self.signals.nozzleTemp - 1.0 * dt, self.target_nozzle_temp)

            # bed heating/cooling
            if self.signals.bedTemp < self.target_bed_temp:
                rate_bed = 2.0 if (self.is_heating or self.is_printing) else 0.5
                self.signals.bedTemp = min(self.signals.bedTemp + rate_bed * dt, self.target_bed_temp)
            elif self.signals.bedTemp > self.target_bed_temp:
                self.signals.bedTemp = max(self.signals.bedTemp - 0.2 * dt, self.target_bed_temp)

            # update printerState
            if (self.signals.nozzleTemp < self.target_nozzle_temp - 1) or (self.signals.bedTemp < self.target_bed_temp - 1):
                if self.is_printing:
                    self.signals.printerState = 1
                else:
                    self.signals.printerState = 1 if self.is_heating else 0
            else:
                if self.is_printing:
                    self.signals.printerState = 2
                else:
                    self.signals.printerState = 0

            if self.signals.filamentRemaining <= 0:
                self.signals.errorCode = 1
                self.is_printing = False
                self.signals.printerState = 4

            yield self.env.timeout(dt)

    def cooling_monitor_process(self):
        while True:
            dt = 0.5
            if not self.is_heating and not self.is_printing:
                if self.signals.nozzleTemp > 25.0:
                    self.signals.nozzleTemp = max(25.0, self.signals.nozzleTemp - 0.5 * dt)
                if self.signals.bedTemp > 25.0:
                    self.signals.bedTemp = max(25.0, self.signals.bedTemp - 0.2 * dt)
            yield self.env.timeout(dt)

    def motion_process(self):
        while True:
            dt = 0.01
            if hasattr(self, '_motion_target'):
                tx, ty, tz = self._motion_target
                for coord, name in ((0, 'headX'), (1, 'headY'), (2, 'headZ')):
                    pos = getattr(self.signals, ['headX', 'headY', 'headZ'][coord])
                    targ = (tx, ty, tz)[coord]
                    if abs(pos - targ) > self.motion_tolerance:
                        direction = 1 if targ > pos else -1
                        step = direction * min(self.motion_speed * dt, abs(targ - pos))
                        if coord == 0:
                            self.signals.headX += step
                        elif coord == 1:
                            self.signals.headY += step
                        else:
                            self.signals.headZ += step
            yield self.env.timeout(dt)

    def gcode_executor_process(self):
        while True:
            if self.gcode_queue:
                line = self.gcode_queue.pop(0)
                gcode_str = ''.join(chr(b) for b in line if b != 0).strip()
                if not gcode_str:
                    yield self.env.timeout(0.001)
                    continue

                if gcode_str.startswith('G1'):
                    tx = self.signals.headX
                    ty = self.signals.headY
                    tz = self.signals.headZ
                    feed = None
                    e_amount = 0.0
                    parts = gcode_str.split()
                    for part in parts:
                        if part.startswith('X'):
                            tx = float(part[1:])
                        elif part.startswith('Y'):
                            ty = float(part[1:])
                        elif part.startswith('Z'):
                            tz = float(part[1:])
                        elif part.startswith('F'):
                            feed = float(part[1:])
                        elif part.startswith('E'):
                            try:
                                e_amount = float(part[1:])
                            except:
                                e_amount = 0.0

                    dist = math.sqrt((tx - self.signals.headX)**2 + (ty - self.signals.headY)**2 + (tz - self.signals.headZ)**2)
                    speed = (feed/60.0) if feed and feed > 0 else self.motion_speed
                    duration = dist / max(0.0001, speed)
                    self._motion_target = (tx, ty, tz)

                    extrude_time = duration
                    if e_amount > 0 and extrude_time > 0:
                        consumption = e_amount * 0.1
                        steps = max(1, int(extrude_time / 0.05))
                        for _ in range(steps):
                            if self.signals.filamentRemaining > 0:
                                self.signals.filamentRemaining = max(0.0, self.signals.filamentRemaining - (consumption / steps))
                            yield self.env.timeout(extrude_time / steps)
                    else:
                        yield self.env.timeout(duration if duration > 0 else 0.001)

                elif gcode_str.startswith('M104'):
                    for token in gcode_str.split():
                        if token.startswith('S'):
                            self.target_nozzle_temp = float(token[1:])
                            self.is_heating = True
                    yield self.env.timeout(0.01)

                elif gcode_str.startswith('M140'):
                    for token in gcode_str.split():
                        if token.startswith('S'):
                            self.target_bed_temp = float(token[1:])
                            self.is_heating = True
                    yield self.env.timeout(0.01)

                elif gcode_str.startswith('G28'):
                    self._motion_target = (0.0, 0.0, 0.0)
                    yield self.env.timeout(0.05)

                else:
                    yield self.env.timeout(0.005)

                if self.signals.nozzleTemp >= self.target_nozzle_temp - 1 and self.signals.bedTemp >= self.target_bed_temp - 1:
                    if self.is_printing:
                        self.signals.printerState = 2

                if self.signals.filamentRemaining <= 0:
                    self.signals.errorCode = 1
                    self.is_printing = False
                    self.signals.printerState = 4

                yield self.env.timeout(0.001)
            else:
                yield self.env.timeout(0.01)

    def process_signals(self, start_signal, refill_signal, gcode_line, gcode_len):
        if refill_signal == 1:
            self.signals.filamentRemaining = 100.0
            self.signals.errorCode = 0
            if self.signals.printerState == 4:
                self.signals.printerState = 0
            print(f"[{self.env.now:.3f}s] Filament refilled to 100%")

        if start_signal == 1:
            self.is_printing = True
            self.is_heating = True
            self.signals.printerState = 1
            print(f"[{self.env.now:.3f}s] Start signal received. Printing enabled.")

        if gcode_len > 0:
            raw = gcode_line[:gcode_len]
            self.gcode_queue.append(list(raw))
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
        self.env = simpy.Environment()
        self.printer_sim = PrinterSimulation(self.env, self.mySignals)
        # End of user custom code region. Please don't edit beyond this point.

    def mainThread(self):
        dSession = vsiCommonPythonApi.connectToServer(self.localHost, self.domain, self.portNum, self.componentId)
        vsiEthernetPythonGateway.initialize(dSession, self.componentId, bytes(srcMacAddress), bytes(srcIpAddress))
        try:
            vsiCommonPythonApi.waitForReset()

            # Start of user custom code region. After Reset
            print("ProcessorComponent initialized and waiting for G-code...")
            # End of user custom code region.
            self.updateInternalVariables()

            if vsiCommonPythonApi.isStopRequested():
                raise Exception("stopRequested")
            self.establishTcpUdpConnection()
            nextExpectedTime = vsiCommonPythonApi.getSimulationTimeInNs()
            while vsiCommonPythonApi.getSimulationTimeInNs() < self.totalSimulationTime:

                # keep internal vars up-to-date
                self.updateInternalVariables()

                # Start of user custom code region. Inside the while loop
                # Run SimPy for one VSI step (synchronized)
                dt = self.simulationStep / 1e9  # ns -> s
                if dt <= 0:
                    dt = 1e-6
                self.env.run(until=self.env.now + dt)
                # End of user custom code region.

                if vsiCommonPythonApi.isStopRequested():
                    raise Exception("stopRequested")

                if vsiEthernetPythonGateway.isTerminationOnGoing():
                    print("Termination is on going")
                    break

                if vsiEthernetPythonGateway.isTerminated():
                    print("Application terminated")
                    break

                receivedData = vsiEthernetPythonGateway.recvEthernetPacket(self.clientPortNum[InputComponent0])
                if receivedData[3] != 0:
                    self.decapsulateReceivedData(receivedData)

                # Process received signals into SimPy model
                # Start of user custom code region. Protocol's callback function
                self.printer_sim.process_signals(
                    self.mySignals.startSignal,
                    self.mySignals.refillCommand,
                    self.mySignals.gcode_line,
                    self.mySignals.gcode_len
                )
                # reset one-shot signals
                self.mySignals.startSignal = 0
                self.mySignals.refillCommand = 0
                # End of user custom code region.

                # Build/send outputs here if needed (kept original prints)
                print("\n+=ProcessorComponent+=")
                print("  VSI time:", end=" ")
                print(vsiCommonPythonApi.getSimulationTimeInNs(), end=" ")
                print("ns")
                print("  Inputs:")
                gcode_str = ''.join(chr(b) for b in self.mySignals.gcode_line[:self.mySignals.gcode_len] if b != 0)
                print("\tgcode_line =", end=" ")
                print(f"\"{gcode_str}\"")
                print("\tgcode_len =", end=" ")
                print(self.mySignals.gcode_len)
                print("\tstartSignal =", end=" ")
                print(self.mySignals.startSignal)
                print("\trefillCommand =", end=" ")
                print(self.mySignals.refillCommand)
                print("  Outputs:")
                print("\theadX =", end=" ")
                print(f"{self.mySignals.headX:.2f}")
                print("\theadY =", end=" ")
                print(f"{self.mySignals.headY:.2f}")
                print("\theadZ =", end=" ")
                print(f"{self.mySignals.headZ:.2f}")
                print("\tnozzleTemp =", end=" ")
                print(f"{self.mySignals.nozzleTemp:.1f}°C")
                print("\tbedTemp =", end=" ")
                print(f"{self.mySignals.bedTemp:.1f}°C")
                print("\tfilamentRemaining =", end=" ")
                print(f"{self.mySignals.filamentRemaining:.1f}%")
                state_names = ["Idle", "Heating", "Printing", "Paused", "Error"]
                sidx = int(self.mySignals.printerState) if 0 <= int(self.mySignals.printerState) < len(state_names) else 4
                print("\tprinterState =", end=" ")
                print(f"{int(self.mySignals.printerState)} ({state_names[sidx]})")
                print("\terrorCode =", end=" ")
                print(self.mySignals.errorCode)
                print("\n\n")

                self.updateInternalVariables()

                if vsiCommonPythonApi.isStopRequested():
                    raise Exception("stopRequested")
                nextExpectedTime += self.simulationStep

                if vsiCommonPythonApi.getSimulationTimeInNs() >= nextExpectedTime:
                    continue

                if nextExpectedTime > self.totalSimulationTime:
                    remainingTime = self.totalSimulationTime - vsiCommonPythonApi.getSimulationTimeInNs()
                    vsiCommonPythonApi.advanceSimulation(remainingTime)
                    break

                vsiCommonPythonApi.advanceSimulation(nextExpectedTime - vsiCommonPythonApi.getSimulationTimeInNs())

            if vsiCommonPythonApi.getSimulationTimeInNs() < self.totalSimulationTime:
                vsiEthernetPythonGateway.terminate()
        except Exception as e:
            if str(e) == "stopRequested":
                print("Terminate signal has been received from one of the VSI clients")
                vsiCommonPythonApi.advanceSimulation(self.simulationStep + 1)
            else:
                print(f"An error occurred: {str(e)}")
                vsiCommonPythonApi.advanceSimulation(self.simulationStep + 1)
        except:
            vsiCommonPythonApi.advanceSimulation(self.simulationStep + 1)

    def establishTcpUdpConnection(self):
        if self.clientPortNum[InputComponent0] == 0:
            self.clientPortNum[InputComponent0] = vsiEthernetPythonGateway.tcpListen(ProcessorComponentSocketPortNumber0)

        if self.clientPortNum[InputComponent0] == 0:
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

        if self.receivedSrcPortNumber == self.clientPortNum[InputComponent0]:
            print("Received packet from InputComponent")
            receivedPayload = bytes(self.receivedPayload)
            self.mySignals.gcode_line, receivedPayload = self.unpackBytes('B', receivedPayload, signal=self.mySignals.gcode_line)

            self.mySignals.gcode_len, receivedPayload = self.unpackBytes('L', receivedPayload)

            self.mySignals.startSignal, receivedPayload = self.unpackBytes('B', receivedPayload)

            self.mySignals.refillCommand, receivedPayload = self.unpackBytes('B', receivedPayload)

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

    def unpackBytes(self, signalType, packedBytes, signal=""):
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

    args = inputArgs.parse_args()

    processorComponent = ProcessorComponent(args)
    processorComponent.mainThread()


if __name__ == '__main__':
    main()
