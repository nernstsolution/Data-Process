import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os
from pathlib import Path
import glob
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import font_manager
import numpy as np
from datetime import datetime
import threading
import time
import platform


def _configure_plot_fonts():
    """Reduce font sizes and prefer the Arial typeface for all Matplotlib plots."""
    base_size = 9
    tick_size = 8
    legend_size = 8

    plt.rcParams.update({
        'font.size': base_size,
        'axes.titlesize': base_size,
        'axes.labelsize': base_size,
        'xtick.labelsize': tick_size,
        'ytick.labelsize': tick_size,
        'legend.fontsize': legend_size,
        'legend.title_fontsize': legend_size,
        'figure.titlesize': base_size,
    })

    try:
        if any('Arial' in font.name for font in font_manager.fontManager.ttflist):
            plt.rcParams['font.family'] = 'Arial'
        else:
            # Ensure Arial is first in the sans-serif fallback list so it is used when available
            sans_fonts = list(plt.rcParams.get('font.sans-serif', []))
            if 'Arial' not in sans_fonts:
                plt.rcParams['font.sans-serif'] = ['Arial'] + sans_fonts
    except Exception:
        pass


_configure_plot_fonts()

# macOS-specific fixes will be applied after root window creation

class ElectrolyzerDataAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Electrolyzer Data Analyzer")
        self.root.geometry("900x700")
        
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
        self.step_threshold = 0.5  # Minimum current step (A) to treat as ramp
        self.active_area_var = tk.DoubleVar(value=25.0)  # Electrode active area in cm²
        self.additional_axes = []  # Secondary matplotlib axes for multi-axis plots
        self._scroll_accumulator = 0.0  # Trackpad-friendly scroll accumulator
        self.voltage_columns = []
        self.selected_voltage_tags = []

        self.create_widgets()
        
    def create_widgets(self):
        # Create main canvas with scrollbar for the entire window
        self.main_canvas = tk.Canvas(self.root, highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas)

        # Configure scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )

        self.scrollable_window = self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        # Ensure inner frame matches canvas width so widgets stay within 900px window
        self.main_canvas.bind("<Configure>", self._resize_canvas)

        # Pack canvas and scrollbar
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.main_scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel globally so scrolling works anywhere over the window
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)  # Linux scroll up
        self.root.bind_all("<Button-5>", self._on_mousewheel)  # Linux scroll down
        
        # Main frame inside scrollable area
        main_frame = ttk.Frame(self.scrollable_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.scrollable_frame.columnconfigure(0, weight=1)
        self.scrollable_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1, minsize=320)
        main_frame.columnconfigure(1, weight=3)
        
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
        self.path_entry = ttk.Entry(folder_frame, textvariable=self.path_var, width=42)
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
        file_frame.grid(row=1, column=0, sticky=(tk.N, tk.W, tk.E), pady=(0, 10))
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
        self.selected_info = ttk.Label(file_frame, text="No files selected", wraplength=820)
        self.selected_info.grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        
        # Process button
        self.process_btn = ttk.Button(file_frame, text="Process Selected Files", command=self.process_files)
        self.process_btn.grid(row=3, column=0, sticky=tk.W, pady=(10, 0))

        process_all_btn = ttk.Button(file_frame, text="Process All Files", command=self.process_all_files)
        process_all_btn.grid(row=3, column=0, sticky=tk.E, pady=(10, 0))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(file_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Progress label
        self.progress_label = ttk.Label(file_frame, text="", wraplength=820)
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
        export_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Label(export_frame, text="Export and reporting features will be implemented in future steps").pack()
        
    def create_data_processing_section(self, parent):
        # Section 3: Data Processing
        process_frame = ttk.LabelFrame(parent, text="3. Data Processing", padding="10")
        process_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 10))
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
        viz_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        viz_frame.columnconfigure(0, weight=1)
        viz_frame.rowconfigure(3, weight=1)
        
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
        
        ttk.Label(y_frame, text="Y-axis Series:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        primary_list_frame = ttk.Frame(y_frame)
        primary_list_frame.grid(row=0, column=1, sticky=(tk.W, tk.E))
        primary_list_frame.columnconfigure(0, weight=1)

        self.y_axis_listbox = tk.Listbox(primary_list_frame, selectmode=tk.MULTIPLE,
                                         exportselection=False, height=6)
        self.y_axis_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))

        primary_scrollbar = ttk.Scrollbar(primary_list_frame, orient=tk.VERTICAL,
                                          command=self.y_axis_listbox.yview)
        primary_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.y_axis_listbox.configure(yscrollcommand=primary_scrollbar.set)
        
        # Add more Y-axis button
        add_y_btn = ttk.Button(y_frame, text="Add Y-axis", command=self.add_y_axis)
        add_y_btn.grid(row=0, column=2)
        
        # Y-axis list frame
        self.y_axis_frame = ttk.Frame(viz_frame)
        self.y_axis_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Plot button
        plot_btn = ttk.Button(viz_frame, text="Generate Plot", command=self.generate_plot)
        plot_btn.grid(row=2, column=0, sticky=tk.E, pady=(0, 10))

        # Plot display area
        plot_frame = ttk.Frame(viz_frame)
        plot_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
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
        pol_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        pol_frame.columnconfigure(0, weight=1)
        pol_frame.rowconfigure(4, weight=1)
        
        # Control frame
        control_frame = ttk.Frame(pol_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)

        # Analyze button
        analyze_btn = ttk.Button(control_frame, text="Analyze Polarization Tests", command=self.analyze_polarization_tests)
        analyze_btn.grid(row=0, column=0, padx=(0, 10))

        # Status label
        self.pol_status = ttk.Label(control_frame, text="No polarization analysis performed", wraplength=820)
        self.pol_status.grid(row=0, column=1, sticky=tk.W)

        # Active area input
        area_label = ttk.Label(control_frame, text="Active Area (cm²):")
        area_label.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        self.active_area_entry = ttk.Entry(control_frame, textvariable=self.active_area_var, width=10)
        self.active_area_entry.grid(row=1, column=1, sticky=tk.W, pady=(6, 0))

        # Voltage tag selection
        voltage_frame = ttk.LabelFrame(control_frame, text="Voltage Tags", padding="5")
        voltage_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(6, 0))
        voltage_frame.columnconfigure(0, weight=1)

        voltage_list_frame = ttk.Frame(voltage_frame)
        voltage_list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        voltage_list_frame.columnconfigure(0, weight=1)

        self.voltage_tag_listbox = tk.Listbox(voltage_list_frame, selectmode=tk.MULTIPLE,
                                              exportselection=False, height=5)
        self.voltage_tag_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))

        voltage_scrollbar = ttk.Scrollbar(voltage_list_frame, orient=tk.VERTICAL,
                                          command=self.voltage_tag_listbox.yview)
        voltage_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.voltage_tag_listbox.configure(yscrollcommand=voltage_scrollbar.set)

        # Polarization tests list frame
        list_frame = ttk.Frame(pol_frame)
        list_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
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
        pol_plot_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
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

    def process_all_files(self):
        """Select every file in the list and process them"""
        file_count = self.file_listbox.size()
        if file_count == 0:
            messagebox.showwarning("Warning", "No files available to process. Please read files first.")
            return

        # Select all entries in the listbox
        self.file_listbox.selection_set(0, tk.END)
        self.selected_files = [self.file_listbox.get(i) for i in range(file_count)]
        self.selected_info.config(text=f"Selected {file_count} file(s): {', '.join(self.selected_files)}")

        # Proceed with normal processing flow
        self.process_files()

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
        self.voltage_columns = [col for col in self.data_columns if 'volt' in col.lower()]

        # Update combo boxes
        self.x_axis_combo['values'] = self.timestamp_columns
        if self.timestamp_columns:
            self.x_axis_var.set(self.timestamp_columns[0])

        # Update primary Y-axis listbox selections
        primary_selected = self._get_selected_listbox_items(self.y_axis_listbox)
        self._populate_listbox(self.y_axis_listbox, self.data_columns, primary_selected)
        if not primary_selected and self.data_columns:
            self.y_axis_listbox.selection_set(0)

        # Update additional Y-axis listboxes
        for y_info in self.y_axis_selections:
            selected = self._get_selected_listbox_items(y_info['listbox'])
            self._populate_listbox(y_info['listbox'], self.data_columns, selected)

        if hasattr(self, 'voltage_tag_listbox'):
            voltage_selected = self._get_selected_listbox_items(self.voltage_tag_listbox)
            self._populate_listbox(self.voltage_tag_listbox, self.voltage_columns, voltage_selected)
            if not voltage_selected and self.voltage_columns:
                self.voltage_tag_listbox.selection_set(0)

    def _populate_listbox(self, listbox, options, selected_values=None):
        """Populate a listbox with options, preserving selections when possible"""
        if selected_values is None:
            selected_values = []

        listbox.delete(0, tk.END)
        for option in options:
            listbox.insert(tk.END, option)

        for idx, option in enumerate(options):
            if option in selected_values:
                listbox.selection_set(idx)

    def _get_selected_listbox_items(self, listbox):
        """Return selected items from a listbox"""
        selection = listbox.curselection()
        return [listbox.get(i) for i in selection]

    def _refresh_y_axis_labels(self):
        """Refresh label text for dynamically added Y-axis frames"""
        for idx, y_info in enumerate(self.y_axis_selections, start=2):
            frame = y_info.get('frame')
            try:
                frame.configure(text=f"Y-axis {idx}")
            except Exception:
                pass

    def add_y_axis(self):
        """Add another Y-axis selection"""
        if not self.data_columns:
            messagebox.showwarning("Warning", "No data columns available. Please process files first.")
            return
            
        axis_number = len(self.y_axis_selections) + 2

        # Create new Y-axis selection frame with its own label
        y_axis_frame = ttk.LabelFrame(self.y_axis_frame, text=f"Y-axis {axis_number}", padding="5")
        y_axis_frame.pack(fill=tk.X, pady=4)
        y_axis_frame.columnconfigure(0, weight=1)

        list_container = ttk.Frame(y_axis_frame)
        list_container.grid(row=0, column=0, sticky=(tk.W, tk.E))
        list_container.columnconfigure(0, weight=1)

        listbox = tk.Listbox(list_container, selectmode=tk.MULTIPLE, exportselection=False, height=6)
        listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        listbox.configure(yscrollcommand=scrollbar.set)

        remove_btn = ttk.Button(y_axis_frame, text="Remove",
                                command=lambda: self.remove_y_axis(y_axis_frame))
        remove_btn.grid(row=1, column=0, sticky=tk.E, pady=(6, 0))

        y_axis_info = {
            'frame': y_axis_frame,
            'listbox': listbox,
        }
        self.y_axis_selections.append(y_axis_info)

        self._populate_listbox(listbox, self.data_columns)

    def remove_y_axis(self, frame):
        """Remove a Y-axis selection"""
        # Find and remove from list
        for i, y_info in enumerate(self.y_axis_selections):
            if y_info['frame'] == frame:
                self.y_axis_selections.pop(i)
                break
        frame.destroy()
        self._refresh_y_axis_labels()
        
    def generate_plot(self):
        """Generate plot with selected axes (optimized for large datasets)"""
        if self.combined_df is None:
            messagebox.showwarning("Warning", "No data available. Please process files first.")
            return
            
        x_col = self.x_axis_var.get()
        if not x_col:
            messagebox.showwarning("Warning", "Please select an X-axis (time) column.")
            return
            
        # Get Y-axis selections for each axis
        primary_cols = self._get_selected_listbox_items(self.y_axis_listbox)
        if not primary_cols:
            messagebox.showwarning("Warning", "Please select at least one Y-axis column.")
            return

        axis_requests = [
            {
                'columns': primary_cols,
                'axis_label': 'Value'
            }
        ]

        for idx, y_info in enumerate(self.y_axis_selections, start=2):
            axis_cols = self._get_selected_listbox_items(y_info['listbox'])
            if axis_cols:
                axis_requests.append({
                    'columns': axis_cols,
                    'axis_label': f'Axis {idx}'
                })

        if self.plotting_thread and self.plotting_thread.is_alive():
            messagebox.showinfo("Info", "Plot generation is already in progress. Please wait.")
            return
            
        # Start plotting in background thread
        self.plotting_thread = threading.Thread(target=self._generate_plot_thread, args=(x_col, axis_requests))
        self.plotting_thread.daemon = True
        self.plotting_thread.start()

    def _generate_plot_thread(self, x_col, axis_requests):
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
                
                axis_series = []

                for axis_idx, axis_info in enumerate(axis_requests):
                    series_list = []
                    for y_col in axis_info['columns']:
                        if y_col in plot_df.columns:
                            y_data = pd.to_numeric(plot_df[y_col], errors='coerce')
                            series_list.append({
                                'x': x_data,
                                'y': y_data,
                                'label': y_col
                            })

                    if series_list:
                        axis_series.append({
                            'series': series_list,
                            'axis_label': axis_info.get('axis_label', f'Axis {axis_idx + 1}')
                        })

                if not axis_series:
                    self.root.after(0, lambda: messagebox.showwarning("Warning", "No valid Y-axis columns found in the data."))
                    return

                # Update UI and create plot
                self.root.after(0, lambda: self._create_plot(axis_series, x_col, len(self.combined_df) > max_points))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error generating plot: {str(e)}"))

    def _create_plot(self, axis_series, x_col, is_sampled):
        """Create the actual plot with support for multiple Y-axes"""
        try:
            # Clear previous plot
            self.ax.clear()

            # Remove previously created secondary axes
            for extra_ax in self.additional_axes:
                try:
                    self.fig.delaxes(extra_ax)
                except Exception:
                    extra_ax.remove()
            self.additional_axes = []

            axes_objects = [self.ax]

            # Prepare additional axes as needed
            for axis_idx in range(1, len(axis_series)):
                new_ax = self.ax.twinx()
                offset = 0.08 * axis_idx
                new_ax.spines["right"].set_position(("axes", 1 + offset))
                new_ax.spines["right"].set_visible(True)
                new_ax.grid(False)
                self.additional_axes.append(new_ax)
                axes_objects.append(new_ax)

            # Plot series on each axis
            all_labels = []
            for axis_idx, axis_info in enumerate(axis_series):
                axis = axes_objects[axis_idx]
                axis_label = axis_info.get('axis_label', f'Axis {axis_idx + 1}')

                for series in axis_info['series']:
                    axis.plot(series['x'], series['y'], label=series['label'], linewidth=1, alpha=0.8)
                    all_labels.append(series['label'])

                axis.set_ylabel(axis_label)
                if axis_idx == 0:
                    axis.grid(True, alpha=0.3)
                else:
                    axis.grid(False)

            # Format plot
            if all_labels:
                title = f"Electrolyzer Data: {', '.join(all_labels)} vs {x_col}"
            else:
                title = f"Electrolyzer Data vs {x_col}"

            if is_sampled and axis_series and axis_series[0]['series']:
                title += f" (Sampled: {len(axis_series[0]['series'][0]['x']):,} points)"

            self.ax.set_title(title)
            self.ax.set_xlabel(x_col)

            # Consolidated legend across all axes
            for legend in list(self.fig.legends):
                legend.remove()

            handles, labels = [], []
            for axis in axes_objects:
                h, l = axis.get_legend_handles_labels()
                handles.extend(h)
                labels.extend(l)

            if handles:
                self.fig.legend(handles, labels, loc='upper right', bbox_to_anchor=(1.02, 1.0))

            # Rotate x-axis labels for better readability
            plt.setp(self.ax.xaxis.get_majorticklabels(), rotation=45)

            # Adjust layout to accommodate multiple Y-axes
            right_margin = 0.9 - 0.08 * (len(axes_objects) - 1)
            right_margin = max(0.6, right_margin)
            self.fig.subplots_adjust(right=right_margin, top=0.9)

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
        event_num = getattr(event, 'num', None)

        if event_num == 4:  # Linux scroll up
            self.main_canvas.yview_scroll(-1, "units")
            return
        if event_num == 5:  # Linux scroll down
            self.main_canvas.yview_scroll(1, "units")
            return

        delta = getattr(event, 'delta', 0)
        if delta == 0:
            return

        if platform.system() == "Darwin":
            self._scroll_accumulator += delta / 10.0
            steps = int(self._scroll_accumulator)
            if steps != 0:
                self.main_canvas.yview_scroll(-steps, "units")
                self._scroll_accumulator -= steps
        else:
            scroll_units = -1 * int(delta / 120)
            if scroll_units == 0:
                scroll_units = -1 if delta < 0 else 1
            self.main_canvas.yview_scroll(scroll_units, "units")

    def _on_file_list_mousewheel(self, event):
        """Handle mousewheel scrolling for file list"""
        self.file_listbox.yview_scroll(int(-1*(event.delta/120)), "units")

    def _resize_canvas(self, event):
        """Keep scrollable frame width in sync with the canvas"""
        if hasattr(self, 'scrollable_window'):
            self.main_canvas.itemconfigure(self.scrollable_window, width=event.width)

    def analyze_polarization_tests(self):
        """Analyze data to detect polarization tests"""
        if self.combined_df is None:
            messagebox.showwarning("Warning", "No data available. Please process files first.")
            return
            
        try:
            voltage_tags = self.voltage_columns
            if not voltage_tags:
                messagebox.showwarning("Warning", "No voltage-related columns found to analyze.")
                return

            self.pol_status.config(text="Analyzing polarization tests...")
            self.root.update()
            
            # Detect polarization tests
            self.polarization_tests = self._detect_polarization_tests(voltage_tags)
            
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
            
    def _detect_polarization_tests(self, voltage_tags):
        """Detect polarization tests in the data based on current step ramps"""
        tests = []

        current_cols = [col for col in self.combined_df.columns if 'current' in col.lower()]
        if not current_cols or not voltage_tags:
            return tests

        current_col = current_cols[0]
        voltage_tags = [tag for tag in voltage_tags if tag in self.combined_df.columns]
        if not voltage_tags:
            return tests

        time_col = self.timestamp_columns[0] if self.timestamp_columns else None
        if not time_col:
            return tests

        current_data = pd.to_numeric(self.combined_df[current_col], errors='coerce')
        voltage_series = {tag: pd.to_numeric(self.combined_df[tag], errors='coerce') for tag in voltage_tags}
        time_data = pd.to_datetime(self.combined_df[time_col], errors='coerce')

        valid_mask = ~(current_data.isna() | time_data.isna())
        for series in voltage_series.values():
            valid_mask &= ~series.isna()

        current_clean = current_data[valid_mask].reset_index(drop=True)
        time_clean = time_data[valid_mask].reset_index(drop=True)
        voltage_clean = {tag: series[valid_mask].reset_index(drop=True) for tag, series in voltage_series.items()}

        if len(current_clean) < 2:
            return tests

        threshold = getattr(self, 'step_threshold', 0.5)
        sequence_dir = 0
        sequence_start = None
        last_idx = None
        step_events = 0

        def finalize_sequence(start_idx, end_idx, direction, steps):
            if start_idx is None or end_idx is None or end_idx <= start_idx or steps == 0:
                return

            start_time = time_clean.iloc[start_idx]
            end_time = time_clean.iloc[end_idx]
            duration = (end_time - start_time).total_seconds() if pd.notna(start_time) and pd.notna(end_time) else 0.0

            tests.append({
                'start_time': start_time,
                'end_time': end_time,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'type': 'Ramp Up' if direction > 0 else 'Ramp Down',
                'duration': duration,
                'step_count': steps,
                'current_data': current_clean.iloc[start_idx:end_idx + 1],
                'voltage_series': {tag: series.iloc[start_idx:end_idx + 1] for tag, series in voltage_clean.items()},
                'time_data': time_clean.iloc[start_idx:end_idx + 1]
            })

        for idx in range(1, len(current_clean)):
            delta = current_clean.iloc[idx] - current_clean.iloc[idx - 1]

            if pd.isna(delta):
                continue

            step_dir = 0
            if delta >= threshold:
                step_dir = 1
            elif delta <= -threshold:
                step_dir = -1

            if sequence_dir == 0:
                if step_dir != 0:
                    sequence_dir = step_dir
                    sequence_start = idx - 1
                    last_idx = idx
                    step_events = 1
                continue

            if step_dir == 0:
                last_idx = idx
                continue

            if step_dir == sequence_dir:
                step_events += 1
                last_idx = idx
                continue

            if last_idx is None:
                last_idx = idx - 1
            finalize_sequence(sequence_start, last_idx, sequence_dir, step_events)

            sequence_dir = step_dir
            sequence_start = idx - 1
            last_idx = idx
            step_events = 1

        if sequence_dir != 0:
            if last_idx is None:
                last_idx = len(current_clean) - 1
            finalize_sequence(sequence_start, last_idx, sequence_dir, step_events)

        tests.sort(key=lambda x: x['start_time'])

        return tests
        
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

        try:
            active_area = float(self.active_area_var.get())
        except (tk.TclError, ValueError):
            active_area = 25.0

        if active_area <= 0:
            active_area = 25.0

        selected_tags = []
        if hasattr(self, 'voltage_tag_listbox'):
            selected_tags = [tag for tag in self._get_selected_listbox_items(self.voltage_tag_listbox)
                             if tag in self.voltage_columns]

        if not selected_tags:
            messagebox.showwarning("Warning", "Please select at least one voltage tag to plot.")
            return

        self.selected_voltage_tags = selected_tags

        # Start plotting in background thread
        self.pol_plotting_thread = threading.Thread(
            target=self._plot_polarization_thread,
            args=(selected_indices, selected_tags, active_area)
        )
        self.pol_plotting_thread.daemon = True
        self.pol_plotting_thread.start()
        
    def _plot_polarization_thread(self, selected_indices, voltage_tags, active_area):
        """Background thread for plotting polarization tests"""
        try:
            # Update UI
            self.root.after(0, lambda: self.pol_status.config(text="Generating polarization plot..."))
            
            # Get selected tests
            selected_tests = [self.polarization_tests[i] for i in selected_indices]
            
            # Update UI and create plot
            self.root.after(0, lambda: self._create_polarization_plot(selected_tests, voltage_tags, active_area))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error generating polarization plot: {str(e)}"))
            
    def _create_polarization_plot(self, tests, voltage_tags, active_area):
        """Create the polarization plot (thread-safe)"""
        try:
            # Clear previous plot
            self.pol_ax.clear()

            colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
            markers = ['o', '^', 's', 'D', 'P', 'X', '*', 'v', 'h', '<', '>']

            if not voltage_tags and tests:
                tag_union = set()
                for test in tests:
                    tag_union.update(test.get('voltage_series', {}).keys())
                voltage_tags = sorted(tag_union)

            plotted_series = 0

            for i, test in enumerate(tests):
                color = colors[i % len(colors)]
                current_series = pd.to_numeric(test['current_data'], errors='coerce')

                if current_series.dropna().empty:
                    continue

                for tag_index, tag in enumerate(voltage_tags):
                    if tag not in test['voltage_series']:
                        continue

                    voltage_series = pd.to_numeric(test['voltage_series'][tag], errors='coerce')
                    step_df = pd.DataFrame({
                        'current': current_series,
                        'voltage': voltage_series,
                    }).dropna()

                    if step_df.empty:
                        continue

                    step_df['current_bin'] = step_df['current'].round(6)
                    averaged_steps = (step_df
                                      .groupby('current_bin', as_index=False)
                                      .agg({'current': 'mean', 'voltage': 'mean'})
                                      .sort_values('current'))

                    if averaged_steps.empty:
                        continue

                    current_density = averaged_steps['current'] / active_area
                    voltage_avg = averaged_steps['voltage']

                    marker = markers[tag_index % len(markers)]

                    self.pol_ax.plot(
                        current_density,
                        voltage_avg,
                        label=f"{test['type']} {tag} ({test['start_time'].strftime('%H:%M:%S')})",
                        color=color,
                        linewidth=2,
                        marker=marker,
                        markersize=4
                    )

                    plotted_series += 1

            if plotted_series == 0:
                self.pol_ax.set_title("No polarization data to display")
                self.pol_ax.set_xlabel("Current Density (A/cm²)")
                self.pol_ax.set_ylabel("Voltage (V)")
                self.pol_canvas.draw()
                self.pol_status.config(text="No polarization data to plot")
                return

            self.pol_ax.set_title(f"Polarization Curves - {plotted_series} Series")
            self.pol_ax.set_xlabel("Current Density (A/cm²)")
            self.pol_ax.set_ylabel("Voltage (V)")
            self.pol_ax.legend()
            self.pol_ax.grid(True, alpha=0.3)

            self.pol_fig.tight_layout()
            self.pol_canvas.draw()

            self.pol_status.config(text=f"Plotted {plotted_series} polarization series")

        except Exception as e:
            messagebox.showerror("Error", f"Error creating polarization plot: {str(e)}")

def main():
    root = tk.Tk()
    app = ElectrolyzerDataAnalyzer(root)
    root.mainloop()

if __name__ == "__main__":
    main()
