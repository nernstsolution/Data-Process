import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os
from pathlib import Path
import glob
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime
import threading
import time
import platform

# macOS-specific fixes will be applied after root window creation

class ElectrolyzerDataAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Electrolyzer Data Analyzer")
        self.root.geometry("1000x700")
        
        # macOS-specific optimizations for better responsiveness
        if platform.system() == "Darwin":  # macOS
            import tkinter.font as tkFont
            # Set better font rendering (after root window is created)
            try:
                tkFont.nametofont("TkDefaultFont").configure(size=11)
                tkFont.nametofont("TkTextFont").configure(size=11)
                tkFont.nametofont("TkFixedFont").configure(size=11)
            except:
                pass  # Font configuration failed, continue without it
            
            # Improve touchpad responsiveness
            self.root.configure(bg='#f0f0f0')  # Light background
            # Set better focus handling
            self.root.focus_set()
            # Configure better event handling
            self.root.bind('<Button-1>', self._on_click)
            self.root.bind('<ButtonRelease-1>', self._on_release)
        
        # Set default path
        self.default_path = os.path.join(os.getcwd(), "InfluxDB raw data")
        self.current_path = self.default_path
        self.selected_files = []
        self.dataframes = {}
        self.combined_df = None
        self.timestamp_columns = []
        self.data_columns = []
        self.y_axis_selections = []
        self.processing_thread = None
        self.plotting_thread = None
        self.polarization_tests = []
        self.pol_plotting_thread = None
        
        self.create_widgets()
        
    def create_widgets(self):
        # Create main canvas with scrollbar for the entire window
        self.main_canvas = tk.Canvas(self.root)
        self.main_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas)
        
        # Configure scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        
        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        
        # Pack canvas and scrollbar
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.main_scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas
        self.main_canvas.bind("<MouseWheel>", self._on_mousewheel)
        
        # Main frame inside scrollable area
        main_frame = ttk.Frame(self.scrollable_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.scrollable_frame.columnconfigure(0, weight=1)
        self.scrollable_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Section 1: Raw Data Folder Navigation
        self.create_folder_navigation_section(main_frame)
        
        # Section 2: File List Reader (placeholder for future sections)
        self.create_file_list_section(main_frame)
        
    def create_folder_navigation_section(self, parent):
        # Section 1: Raw Data Folder Navigation
        folder_frame = ttk.LabelFrame(parent, text="1. Raw Data Folder Navigation", padding="10")
        folder_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        folder_frame.columnconfigure(1, weight=1)
        
        # Directory path label
        ttk.Label(folder_frame, text="Directory Path:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        # Directory path entry
        self.path_var = tk.StringVar(value=self.current_path)
        self.path_entry = ttk.Entry(folder_frame, textvariable=self.path_var, width=50)
        self.path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # Browse button
        browse_btn = ttk.Button(folder_frame, text="Browse", command=self.browse_folder)
        browse_btn.grid(row=0, column=2, padx=(0, 10))
        
        # Read button
        read_btn = ttk.Button(folder_frame, text="Read Files", command=self.read_files)
        read_btn.grid(row=0, column=3)
        
    def create_file_list_section(self, parent):
        # Section 2: File List Reader
        file_frame = ttk.LabelFrame(parent, text="2. File List Reader", padding="10")
        file_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)
        file_frame.rowconfigure(1, weight=1)
        
        # File list label
        ttk.Label(file_frame, text="Available Files:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        # File listbox with scrollbar (smaller height)
        list_frame = ttk.Frame(file_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Smaller file list with better scrolling
        self.file_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, height=8)
        self.file_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar for file list
        self.file_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=self.file_scrollbar.set)
        
        # Bind mousewheel to file list
        self.file_listbox.bind("<MouseWheel>", self._on_file_list_mousewheel)
        
        # Selected files info
        self.selected_info = ttk.Label(file_frame, text="No files selected")
        self.selected_info.grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        
        # Process button
        self.process_btn = ttk.Button(file_frame, text="Process Selected Files", command=self.process_files)
        self.process_btn.grid(row=3, column=0, pady=(10, 0))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(file_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Progress label
        self.progress_label = ttk.Label(file_frame, text="")
        self.progress_label.grid(row=5, column=0, sticky=tk.W, pady=(2, 0))
        
        # Bind selection change event with improved responsiveness
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_selection_change)
        
        # macOS-specific listbox improvements
        if platform.system() == "Darwin":  # macOS
            # Improve listbox responsiveness
            self.file_listbox.bind('<Button-1>', self._on_listbox_click)
            self.file_listbox.bind('<ButtonRelease-1>', self._on_listbox_release)
            # Configure better scrolling
            self.file_listbox.configure(relief='flat', borderwidth=1)
        
        # Placeholder sections for future development
        self.create_placeholder_sections(parent)
        
    def create_placeholder_sections(self, parent):
        # Section 3: Data Processing
        self.create_data_processing_section(parent)
        
        # Section 4: Data Visualization
        self.create_data_visualization_section(parent)
        
        # Section 5: Polarization Analyzer
        self.create_polarization_analyzer_section(parent)
        
        # Section 6: Export/Report (placeholder)
        export_frame = ttk.LabelFrame(parent, text="6. Export/Report", padding="10")
        export_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Label(export_frame, text="Export and reporting features will be implemented in future steps").pack()
        
    def create_data_processing_section(self, parent):
        # Section 3: Data Processing
        process_frame = ttk.LabelFrame(parent, text="3. Data Processing", padding="10")
        process_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        process_frame.columnconfigure(0, weight=1)
        
        # Processing status
        self.processing_status = ttk.Label(process_frame, text="No data processed yet")
        self.processing_status.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # Data info display
        info_frame = ttk.Frame(process_frame)
        info_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)
        
        ttk.Label(info_frame, text="Combined DataFrame:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.df_info = ttk.Label(info_frame, text="No data")
        self.df_info.grid(row=0, column=1, sticky=tk.W)
        
    def create_data_visualization_section(self, parent):
        # Section 4: Data Visualization
        viz_frame = ttk.LabelFrame(parent, text="4. Data Visualization", padding="10")
        viz_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        viz_frame.columnconfigure(0, weight=1)
        viz_frame.rowconfigure(2, weight=1)
        
        # Control frame for axis selection
        control_frame = ttk.Frame(viz_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(3, weight=1)
        
        # X-axis selection
        ttk.Label(control_frame, text="X-axis (Time):").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.x_axis_var = tk.StringVar()
        self.x_axis_combo = ttk.Combobox(control_frame, textvariable=self.x_axis_var, state="readonly")
        self.x_axis_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 20))
        
        # Y-axis selection frame
        y_frame = ttk.Frame(control_frame)
        y_frame.grid(row=0, column=2, columnspan=2, sticky=(tk.W, tk.E))
        y_frame.columnconfigure(1, weight=1)
        
        ttk.Label(y_frame, text="Y-axis:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.y_axis_var = tk.StringVar()
        self.y_axis_combo = ttk.Combobox(y_frame, textvariable=self.y_axis_var, state="readonly")
        self.y_axis_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # Add more Y-axis button
        add_y_btn = ttk.Button(y_frame, text="Add Y-axis", command=self.add_y_axis)
        add_y_btn.grid(row=0, column=2)
        
        # Y-axis list frame
        self.y_axis_frame = ttk.Frame(viz_frame)
        self.y_axis_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Plot button
        plot_btn = ttk.Button(viz_frame, text="Generate Plot", command=self.generate_plot)
        plot_btn.grid(row=1, column=0, sticky=tk.E, pady=(0, 10))
        
        # Plot display area
        plot_frame = ttk.Frame(viz_frame)
        plot_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        
        # Create matplotlib figure (smaller size)
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Initial empty plot
        self.ax.set_title("No data to display")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Value")
        self.canvas.draw()
        
    def create_polarization_analyzer_section(self, parent):
        # Section 5: Polarization Analyzer
        pol_frame = ttk.LabelFrame(parent, text="5. Polarization Analyzer", padding="10")
        pol_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        pol_frame.columnconfigure(0, weight=1)
        pol_frame.rowconfigure(2, weight=1)
        
        # Control frame
        control_frame = ttk.Frame(pol_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)
        
        # Analyze button
        analyze_btn = ttk.Button(control_frame, text="Analyze Polarization Tests", command=self.analyze_polarization_tests)
        analyze_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Status label
        self.pol_status = ttk.Label(control_frame, text="No polarization analysis performed")
        self.pol_status.grid(row=0, column=1, sticky=tk.W)
        
        # Polarization tests list frame
        list_frame = ttk.Frame(pol_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Tests listbox
        ttk.Label(list_frame, text="Detected Polarization Tests:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        tests_list_frame = ttk.Frame(list_frame)
        tests_list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tests_list_frame.columnconfigure(0, weight=1)
        tests_list_frame.rowconfigure(0, weight=1)
        
        self.pol_tests_listbox = tk.Listbox(tests_list_frame, selectmode=tk.MULTIPLE, height=6)
        self.pol_tests_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar for tests list
        pol_scrollbar = ttk.Scrollbar(tests_list_frame, orient=tk.VERTICAL, command=self.pol_tests_listbox.yview)
        pol_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.pol_tests_listbox.configure(yscrollcommand=pol_scrollbar.set)
        
        # Plot polarization button
        plot_pol_btn = ttk.Button(list_frame, text="Plot Selected Tests", command=self.plot_polarization_tests)
        plot_pol_btn.grid(row=2, column=0, pady=(10, 0))
        
        # Polarization plot frame
        pol_plot_frame = ttk.Frame(pol_frame)
        pol_plot_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        pol_plot_frame.columnconfigure(0, weight=1)
        pol_plot_frame.rowconfigure(0, weight=1)
        
        # Create polarization plot
        self.pol_fig, self.pol_ax = plt.subplots(figsize=(8, 4))
        self.pol_canvas = FigureCanvasTkAgg(self.pol_fig, pol_plot_frame)
        self.pol_canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Initial empty polarization plot
        self.pol_ax.set_title("No polarization data to display")
        self.pol_ax.set_xlabel("Current Density (A/cm²)")
        self.pol_ax.set_ylabel("Voltage (V)")
        self.pol_canvas.draw()
        
    def browse_folder(self):
        """Open directory browser and update path"""
        folder_path = filedialog.askdirectory(initialdir=self.current_path)
        if folder_path:
            self.current_path = folder_path
            self.path_var.set(folder_path)
            self.clear_file_list()
            
    def read_files(self):
        """Read CSV files from the selected directory"""
        try:
            if not os.path.exists(self.current_path):
                messagebox.showerror("Error", f"Directory does not exist: {self.current_path}")
                return
                
            # Find all CSV files in the directory
            csv_files = glob.glob(os.path.join(self.current_path, "*.csv"))
            
            if not csv_files:
                messagebox.showwarning("Warning", "No CSV files found in the selected directory")
                return
                
            # Clear existing file list
            self.file_listbox.delete(0, tk.END)
            
            # Add files to listbox
            for file_path in sorted(csv_files):
                filename = os.path.basename(file_path)
                self.file_listbox.insert(tk.END, filename)
                
            messagebox.showinfo("Success", f"Found {len(csv_files)} CSV files")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error reading files: {str(e)}")
            
    def clear_file_list(self):
        """Clear the file list"""
        self.file_listbox.delete(0, tk.END)
        self.selected_files = []
        self.selected_info.config(text="No files selected")
        
    def on_file_selection_change(self, event):
        """Handle file selection change"""
        selected_indices = self.file_listbox.curselection()
        self.selected_files = [self.file_listbox.get(i) for i in selected_indices]
        
        if self.selected_files:
            self.selected_info.config(text=f"Selected {len(self.selected_files)} file(s): {', '.join(self.selected_files)}")
        else:
            self.selected_info.config(text="No files selected")
            
    def process_files(self):
        """Process selected files and create combined dataframe (non-blocking)"""
        if not self.selected_files:
            messagebox.showwarning("Warning", "Please select at least one file")
            return
            
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showinfo("Info", "Processing is already in progress. Please wait.")
            return
            
        # Disable process button and show progress
        self.process_btn.config(state='disabled', text="Processing...")
        self.progress_var.set(0)
        self.progress_label.config(text="Starting file processing...")
        
        # Start processing in background thread
        self.processing_thread = threading.Thread(target=self._process_files_thread)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
    def _process_files_thread(self):
        """Background thread for processing files"""
        try:
            self.dataframes = {}
            total_rows = 0
            file_count = len(self.selected_files)
            
            for i, filename in enumerate(self.selected_files):
                # Update progress
                progress = (i / file_count) * 100
                self.root.after(0, lambda p=progress, f=filename: self._update_progress(p, f"Reading {f}..."))
                
                file_path = os.path.join(self.current_path, filename)
                
                # Read CSV file with optimized settings
                df = pd.read_csv(file_path, skiprows=3, low_memory=False)
                
                # Clean column names
                df.columns = df.columns.str.strip()
                
                # Add source file column
                df['source_file'] = filename
                
                # Store dataframe
                self.dataframes[filename] = df
                total_rows += len(df)
                
                # Small delay to keep UI responsive
                time.sleep(0.01)
            
            # Update progress
            self.root.after(0, lambda: self._update_progress(90, "Combining data..."))
            
            # Combine all dataframes
            if self.dataframes:
                self.combined_df = pd.concat(self.dataframes.values(), ignore_index=True)
                
                # Sort by timestamp if available
                timestamp_cols = [col for col in self.combined_df.columns if 'time' in col.lower()]
                if timestamp_cols:
                    self.combined_df = self.combined_df.sort_values(timestamp_cols[0])
                
                # Update progress
                self.root.after(0, lambda: self._update_progress(95, "Updating column lists..."))
                
                # Update column lists
                self.update_column_lists()
                
                # Complete processing
                self.root.after(0, lambda: self._processing_complete(len(self.selected_files), total_rows))
            
        except Exception as e:
            self.root.after(0, lambda: self._processing_error(str(e)))
            
    def _update_progress(self, progress, message):
        """Update progress bar and label (thread-safe)"""
        self.progress_var.set(progress)
        self.progress_label.config(text=message)
        
    def _processing_complete(self, file_count, total_rows):
        """Complete processing (thread-safe)"""
        self.processing_status.config(text=f"Successfully processed {file_count} file(s)")
        self.df_info.config(text=f"{len(self.combined_df):,} rows, {len(self.combined_df.columns)} columns")
        
        self.progress_var.set(100)
        self.progress_label.config(text="Processing complete!")
        self.process_btn.config(state='normal', text="Process Selected Files")
        
        messagebox.showinfo("Success", f"Processed {file_count} file(s) with {total_rows:,} total rows")
        
    def _processing_error(self, error_msg):
        """Handle processing error (thread-safe)"""
        self.progress_label.config(text="Processing failed!")
        self.process_btn.config(state='normal', text="Process Selected Files")
        messagebox.showerror("Error", f"Error processing data: {error_msg}")
            
    def update_column_lists(self):
        """Update timestamp and data column lists"""
        if self.combined_df is None:
            return
            
        # Find timestamp columns
        self.timestamp_columns = [col for col in self.combined_df.columns 
                                if 'time' in col.lower() or 'timestamp' in col.lower()]
        
        # Find data columns (exclude timestamp and source file columns)
        self.data_columns = [col for col in self.combined_df.columns 
                           if col not in self.timestamp_columns and col != 'source_file']
        
        # Update combo boxes
        self.x_axis_combo['values'] = self.timestamp_columns
        if self.timestamp_columns:
            self.x_axis_var.set(self.timestamp_columns[0])
            
        self.y_axis_combo['values'] = self.data_columns
        if self.data_columns:
            self.y_axis_var.set(self.data_columns[0])
            
    def add_y_axis(self):
        """Add another Y-axis selection"""
        if not self.data_columns:
            messagebox.showwarning("Warning", "No data columns available. Please process files first.")
            return
            
        # Create new Y-axis selection frame
        y_axis_frame = ttk.Frame(self.y_axis_frame)
        y_axis_frame.pack(fill=tk.X, pady=2)
        
        # Y-axis combo box
        y_var = tk.StringVar()
        y_combo = ttk.Combobox(y_axis_frame, textvariable=y_var, values=self.data_columns, state="readonly")
        y_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Remove button
        remove_btn = ttk.Button(y_axis_frame, text="Remove", 
                              command=lambda: self.remove_y_axis(y_axis_frame))
        remove_btn.pack(side=tk.RIGHT)
        
        # Store reference
        y_axis_info = {
            'frame': y_axis_frame,
            'var': y_var,
            'combo': y_combo
        }
        self.y_axis_selections.append(y_axis_info)
        
    def remove_y_axis(self, frame):
        """Remove a Y-axis selection"""
        # Find and remove from list
        for i, y_info in enumerate(self.y_axis_selections):
            if y_info['frame'] == frame:
                self.y_axis_selections.pop(i)
                break
        frame.destroy()
        
    def generate_plot(self):
        """Generate plot with selected axes (optimized for large datasets)"""
        if self.combined_df is None:
            messagebox.showwarning("Warning", "No data available. Please process files first.")
            return
            
        x_col = self.x_axis_var.get()
        if not x_col:
            messagebox.showwarning("Warning", "Please select an X-axis (time) column.")
            return
            
        # Get Y-axis selections
        y_cols = []
        if self.y_axis_var.get():
            y_cols.append(self.y_axis_var.get())
        
        for y_info in self.y_axis_selections:
            if y_info['var'].get():
                y_cols.append(y_info['var'].get())
                
        if not y_cols:
            messagebox.showwarning("Warning", "Please select at least one Y-axis column.")
            return
            
        if self.plotting_thread and self.plotting_thread.is_alive():
            messagebox.showinfo("Info", "Plot generation is already in progress. Please wait.")
            return
            
        # Start plotting in background thread
        self.plotting_thread = threading.Thread(target=self._generate_plot_thread, args=(x_col, y_cols))
        self.plotting_thread.daemon = True
        self.plotting_thread.start()
        
    def _generate_plot_thread(self, x_col, y_cols):
        """Background thread for generating plots"""
        try:
            # Update UI
            self.root.after(0, lambda: self.progress_label.config(text="Preparing plot data..."))
            
            # Sample data for large datasets (max 10,000 points for performance)
            max_points = 10000
            if len(self.combined_df) > max_points:
                # Sample data evenly
                step = len(self.combined_df) // max_points
                plot_df = self.combined_df.iloc[::step].copy()
                self.root.after(0, lambda: self.progress_label.config(text=f"Sampling {len(plot_df):,} points from {len(self.combined_df):,} total..."))
            else:
                plot_df = self.combined_df.copy()
            
            # Convert timestamp to datetime if needed
            if x_col in plot_df.columns:
                x_data = pd.to_datetime(plot_df[x_col], errors='coerce')
                
                # Convert timezone-aware timestamps to timezone-naive for matplotlib compatibility
                if x_data.dt.tz is not None:
                    x_data = x_data.dt.tz_convert(None)
                
                # Prepare plot data
                plot_data = []
                for y_col in y_cols:
                    if y_col in plot_df.columns:
                        y_data = pd.to_numeric(plot_df[y_col], errors='coerce')
                        plot_data.append((x_data, y_data, y_col))
                
                # Update UI and create plot
                self.root.after(0, lambda: self._create_plot(plot_data, x_col, len(self.combined_df) > max_points))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error generating plot: {str(e)}"))
            
    def _create_plot(self, plot_data, x_col, is_sampled):
        """Create the actual plot (thread-safe)"""
        try:
            # Clear previous plot
            self.ax.clear()
            
            # Plot each Y-axis
            for x_data, y_data, y_col in plot_data:
                self.ax.plot(x_data, y_data, label=y_col, linewidth=1, alpha=0.8)
            
            # Format plot
            title = f"Electrolyzer Data: {', '.join([data[2] for data in plot_data])} vs {x_col}"
            if is_sampled:
                title += f" (Sampled: {len(plot_data[0][0]):,} points)"
            
            self.ax.set_title(title)
            self.ax.set_xlabel(x_col)
            self.ax.set_ylabel("Value")
            self.ax.legend()
            self.ax.grid(True, alpha=0.3)
            
            # Rotate x-axis labels for better readability
            plt.setp(self.ax.xaxis.get_majorticklabels(), rotation=45)
            
            # Adjust layout
            self.fig.tight_layout()
            self.canvas.draw()
            
            self.progress_label.config(text="Plot generated successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error creating plot: {str(e)}")
            
    def load_selected_dataframes(self):
        """Load dataframes from selected files (legacy method)"""
        return self.process_files()
        
    def _on_click(self, event):
        """Handle click events for better responsiveness"""
        if platform.system() == "Darwin":  # macOS
            # Force immediate focus
            self.root.focus_set()
            
    def _on_release(self, event):
        """Handle click release events"""
        if platform.system() == "Darwin":  # macOS
            # Ensure proper focus handling
            pass
            
    def _on_listbox_click(self, event):
        """Handle listbox click events for better responsiveness"""
        if platform.system() == "Darwin":  # macOS
            # Force immediate response
            self.root.update_idletasks()
            
    def _on_listbox_release(self, event):
        """Handle listbox release events"""
        if platform.system() == "Darwin":  # macOS
            # Ensure selection is processed
            self.root.after(10, self.on_file_selection_change, None)
            
    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling for main window"""
        self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def _on_file_list_mousewheel(self, event):
        """Handle mousewheel scrolling for file list"""
        self.file_listbox.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def analyze_polarization_tests(self):
        """Analyze data to detect polarization tests"""
        if self.combined_df is None:
            messagebox.showwarning("Warning", "No data available. Please process files first.")
            return
            
        try:
            self.pol_status.config(text="Analyzing polarization tests...")
            self.root.update()
            
            # Detect polarization tests
            self.polarization_tests = self._detect_polarization_tests()
            
            # Update listbox
            self.pol_tests_listbox.delete(0, tk.END)
            for i, test in enumerate(self.polarization_tests):
                start_time = test['start_time'].strftime('%Y-%m-%d %H:%M:%S')
                test_type = test['type']
                duration = test['duration']
                self.pol_tests_listbox.insert(tk.END, f"{i+1}. {start_time} - {test_type} ({duration:.1f}s)")
            
            self.pol_status.config(text=f"Found {len(self.polarization_tests)} polarization tests")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error analyzing polarization tests: {str(e)}")
            self.pol_status.config(text="Analysis failed")
            
    def _detect_polarization_tests(self):
        """Detect polarization tests in the data"""
        tests = []
        
        # Look for current and voltage columns
        current_cols = [col for col in self.combined_df.columns if 'current' in col.lower()]
        voltage_cols = [col for col in self.combined_df.columns if 'voltage' in col.lower()]
        
        if not current_cols or not voltage_cols:
            return tests
            
        # Use the first current and voltage columns found
        current_col = current_cols[0]
        voltage_col = voltage_cols[0]
        
        # Get time column
        time_col = self.timestamp_columns[0] if self.timestamp_columns else None
        if not time_col:
            return tests
            
        # Convert to numeric
        current_data = pd.to_numeric(self.combined_df[current_col], errors='coerce')
        voltage_data = pd.to_numeric(self.combined_df[voltage_col], errors='coerce')
        
        # Remove NaN values
        valid_mask = ~(current_data.isna() | voltage_data.isna())
        current_clean = current_data[valid_mask]
        voltage_clean = voltage_data[valid_mask]
        time_clean = self.combined_df[time_col][valid_mask]
        
        if len(current_clean) < 10:  # Need minimum data points
            return tests
            
        # Detect ramp patterns in current
        current_diff = current_clean.diff()
        
        # Define thresholds for ramp detection
        ramp_threshold = current_clean.std() * 0.1  # 10% of standard deviation
        min_ramp_length = 5  # Minimum consecutive points for a ramp
        
        # Find ramp-up and ramp-down sequences
        ramp_up_mask = current_diff > ramp_threshold
        ramp_down_mask = current_diff < -ramp_threshold
        
        # Group consecutive ramp points
        ramp_up_groups = self._group_consecutive(ramp_up_mask)
        ramp_down_groups = self._group_consecutive(ramp_down_mask)
        
        # Process ramp-up tests
        for group in ramp_up_groups:
            if len(group) >= min_ramp_length:
                start_idx = group[0]
                end_idx = group[-1]
                
                test_data = {
                    'start_time': time_clean.iloc[start_idx],
                    'end_time': time_clean.iloc[end_idx],
                    'start_idx': start_idx,
                    'end_idx': end_idx,
                    'type': 'Ramp Up',
                    'duration': (time_clean.iloc[end_idx] - time_clean.iloc[start_idx]).total_seconds(),
                    'current_data': current_clean.iloc[start_idx:end_idx+1],
                    'voltage_data': voltage_clean.iloc[start_idx:end_idx+1],
                    'time_data': time_clean.iloc[start_idx:end_idx+1]
                }
                tests.append(test_data)
        
        # Process ramp-down tests
        for group in ramp_down_groups:
            if len(group) >= min_ramp_length:
                start_idx = group[0]
                end_idx = group[-1]
                
                test_data = {
                    'start_time': time_clean.iloc[start_idx],
                    'end_time': time_clean.iloc[end_idx],
                    'start_idx': start_idx,
                    'end_idx': end_idx,
                    'type': 'Ramp Down',
                    'duration': (time_clean.iloc[end_idx] - time_clean.iloc[start_idx]).total_seconds(),
                    'current_data': current_clean.iloc[start_idx:end_idx+1],
                    'voltage_data': voltage_clean.iloc[start_idx:end_idx+1],
                    'time_data': time_clean.iloc[start_idx:end_idx+1]
                }
                tests.append(test_data)
        
        # Sort tests by start time
        tests.sort(key=lambda x: x['start_time'])
        
        return tests
        
    def _group_consecutive(self, mask):
        """Group consecutive True values in a boolean mask"""
        groups = []
        current_group = []
        
        for i, value in enumerate(mask):
            if value:
                current_group.append(i)
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
        
        if current_group:
            groups.append(current_group)
            
        return groups
        
    def plot_polarization_tests(self):
        """Plot selected polarization tests"""
        if not self.polarization_tests:
            messagebox.showwarning("Warning", "No polarization tests available. Please analyze first.")
            return
            
        selected_indices = self.pol_tests_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select at least one polarization test to plot.")
            return
            
        if self.pol_plotting_thread and self.pol_plotting_thread.is_alive():
            messagebox.showinfo("Info", "Plot generation is already in progress. Please wait.")
            return
            
        # Start plotting in background thread
        self.pol_plotting_thread = threading.Thread(target=self._plot_polarization_thread, args=(selected_indices,))
        self.pol_plotting_thread.daemon = True
        self.pol_plotting_thread.start()
        
    def _plot_polarization_thread(self, selected_indices):
        """Background thread for plotting polarization tests"""
        try:
            # Update UI
            self.root.after(0, lambda: self.pol_status.config(text="Generating polarization plot..."))
            
            # Get selected tests
            selected_tests = [self.polarization_tests[i] for i in selected_indices]
            
            # Update UI and create plot
            self.root.after(0, lambda: self._create_polarization_plot(selected_tests))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error generating polarization plot: {str(e)}"))
            
    def _create_polarization_plot(self, tests):
        """Create the polarization plot (thread-safe)"""
        try:
            # Clear previous plot
            self.pol_ax.clear()
            
            # Plot each test
            colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
            
            for i, test in enumerate(tests):
                color = colors[i % len(colors)]
                
                # Calculate current density (assuming cell area - you may need to adjust this)
                # For now, using current directly - you can modify this based on your cell area
                current_density = test['current_data']  # A/cm² (adjust based on your cell area)
                
                # Plot voltage vs current density
                self.pol_ax.plot(current_density, test['voltage_data'], 
                               label=f"{test['type']} - {test['start_time'].strftime('%H:%M:%S')}",
                               color=color, linewidth=2, marker='o', markersize=3)
            
            # Format plot
            self.pol_ax.set_title(f"Polarization Curves - {len(tests)} Test(s)")
            self.pol_ax.set_xlabel("Current Density (A/cm²)")
            self.pol_ax.set_ylabel("Voltage (V)")
            self.pol_ax.legend()
            self.pol_ax.grid(True, alpha=0.3)
            
            # Adjust layout
            self.pol_fig.tight_layout()
            self.pol_canvas.draw()
            
            self.pol_status.config(text=f"Plotted {len(tests)} polarization test(s)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error creating polarization plot: {str(e)}")

def main():
    root = tk.Tk()
    app = ElectrolyzerDataAnalyzer(root)
    root.mainloop()

if __name__ == "__main__":
    main()
