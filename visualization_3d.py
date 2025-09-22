import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
import threading
import time
from queue import Queue

class PrinterVisualizer3D:
    def __init__(self):
        try:
            # Set backend first
            import matplotlib
            matplotlib.use('TkAgg')  # Use Tkinter backend
            
            self.fig = plt.figure(figsize=(12, 8))
            self.ax = self.fig.add_subplot(111, projection='3d')
            
            # Initialize plot elements with actual data
            self.toolhead_line, = self.ax.plot([0], [0], [0], 'ro-', markersize=8, linewidth=2, label='Toolhead')
            self.path_line, = self.ax.plot([0], [0], [0], 'b-', alpha=0.3, linewidth=1, label='Print Path')
            
            # Data storage
            self.x_data, self.y_data, self.z_data = [0], [0], [0]
            self.current_x, self.current_y, self.current_z = 0, 0, 0
            
            # Setup plot
            self.setup_plot()
            
            # Enable interactive mode
            plt.ion()
            plt.show(block=False)
            plt.pause(0.1)  # Initial render
            
            print("Visualizer initialized successfully!")
            
        except Exception as e:
            print(f"Error initializing visualizer: {e}")
            import traceback
            traceback.print_exc()
    
    def setup_plot(self):
        """Configure the 3D plot"""
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.set_zlabel('Z (mm)')
        self.ax.set_title('3D Printer Simulation - Live')
        self.ax.legend()
        self.ax.grid(True)
        
        # Set reasonable limits
        self.ax.set_xlim(-50, 50)
        self.ax.set_ylim(-50, 50)
        self.ax.set_zlim(0, 100)
        
        # Add printer bed
        import numpy as np
        xx, yy = np.meshgrid([-40, 40], [-40, 40])
        zz = np.zeros_like(xx)
        self.ax.plot_surface(xx, yy, zz, alpha=0.2, color='gray')
    
    def update_position(self, x, y, z, movement_type):
        """Update the current position"""
        try:
            self.current_x, self.current_y, self.current_z = x, y, z
            
            # Store path data
            self.x_data.append(x)
            self.y_data.append(y)
            self.z_data.append(z)
            
            # Update visualization immediately
            self._update_visualization(movement_type)
            
        except Exception as e:
            print(f"Error updating position: {e}")
    
    def _update_visualization(self, movement_type):
        """Update the 3D visualization"""
        try:
            # Update toolhead position
            self.toolhead_line.set_data([self.current_x], [self.current_y])
            self.toolhead_line.set_3d_properties([self.current_z])
            
            # Update path (show all points)
            self.path_line.set_data(self.x_data, self.y_data)
            self.path_line.set_3d_properties(self.z_data)
            
            # Auto-adjust view limits
            if len(self.x_data) > 1:
                margin = 10
                x_min, x_max = min(self.x_data), max(self.x_data)
                y_min, y_max = min(self.y_data), max(self.y_data)
                z_min, z_max = min(self.z_data), max(self.z_data)
                
                self.ax.set_xlim(x_min - margin, x_max + margin)
                self.ax.set_ylim(y_min - margin, y_max + margin)
                self.ax.set_zlim(max(0, z_min - margin), z_max + margin)
            
            # Color code movement types
            if movement_type == 'PRINT':
                self.path_line.set_color('blue')
                self.toolhead_line.set_color('red')
            elif movement_type == 'RAPID':
                self.path_line.set_color('green')
                self.toolhead_line.set_color('orange')
            
            # Force redraw
            self.fig.canvas.draw()
            self.fig.canvas.flush_events()
            plt.pause(0.001)  # Allow GUI to update
            
        except Exception as e:
            print(f"Error updating visualization: {e}")
    
    def keep_open(self):
        """Keep the window open after simulation"""
        try:
            plt.ioff()
            print("Simulation complete. Close the visualization window to exit.")
            plt.show(block=True)
        except Exception as e:
            print(f"Error keeping window open: {e}")